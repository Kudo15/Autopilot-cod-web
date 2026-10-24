"""Bounded, server-only RSS/Atom collection primitives.

The module treats feed bytes and fields as untrusted data. Network access is
available only through an injected client; the default client is constructed
per call and never stored as module state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from typing import Any, Callable, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from backend.app import database
from backend.app.collectors import registry, runs

MAX_BODY_BYTES = 5_000_000
MAX_ITEMS = 1_000
MAX_REDIRECTS = 3
MAX_RETRIES = 3
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_BACKOFF_S = 0.5
MAX_BACKOFF_S = 30.0
_WS = re.compile(r"\s+")


class FeedError(ValueError):
    """Bounded, expected feed failure."""


class FeedTransportError(FeedError):
    """Transport failure eligible for bounded retry."""


class UnsafeUrlError(FeedError):
    """URL rejected by the shared outbound policy."""


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes = b""
    location: str | None = None
    content_type: str | None = None


class FeedClient(Protocol):
    def get(self, url: str, *, timeout: float, max_bytes: int) -> HttpResponse: ...


@dataclass(frozen=True)
class FeedLimits:
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_body_bytes: int = MAX_BODY_BYTES
    max_items: int = MAX_ITEMS
    max_redirects: int = MAX_REDIRECTS
    max_retries: int = MAX_RETRIES
    backoff_s: float = DEFAULT_BACKOFF_S
    max_backoff_s: float = MAX_BACKOFF_S

    def __post_init__(self) -> None:
        checks = (
            (self.timeout_s, "timeout_s", 0.0, 30.0),
            (self.max_body_bytes, "max_body_bytes", 1, 50_000_000),
            (self.max_items, "max_items", 1, 5_000),
            (self.max_redirects, "max_redirects", 0, 10),
            (self.max_retries, "max_retries", 0, 5),
            (self.backoff_s, "backoff_s", 0.0, 30.0),
            (self.max_backoff_s, "max_backoff_s", 0.0, 30.0),
        )
        for value, name, lower, upper in checks:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise FeedError(f"{name} must be numeric")
            if value < lower or value > upper:
                raise FeedError(f"{name} is outside its bound")
        if self.max_backoff_s < self.backoff_s:
            raise FeedError("max_backoff_s must be at least backoff_s")


@dataclass(frozen=True)
class FeedItem:
    title: str
    canonical_url: str
    normalized_title: str
    content: str
    content_hash: str
    content_type: str = "text/plain"
    published_at: str | None = None


@dataclass(frozen=True)
class ParsedFeed:
    feed_title: str
    items: tuple[FeedItem, ...]
    items_ignored: int = 0


@dataclass(frozen=True)
class CollectionResult:
    source_id: str
    status: str
    data_origin: str
    fetched_at: str
    error: str | None = None
    items_collected: int = 0
    items_ignored: int = 0
    inserted: int = 0
    duplicates: int = 0
    run_id: int | None = None
    freshness: str = field(default="NOT_VERIFIED", init=False)

    def __post_init__(self) -> None:
        if self.status not in {"SUCCESS", "FAILED", "SKIPPED"}:
            raise FeedError("invalid collection result status")
        if self.data_origin not in {"REAL", "SAMPLE"}:
            raise FeedError("invalid data origin")
        try:
            datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise FeedError("fetched_at must be an ISO-8601 timestamp") from exc
        for value, name in (
            (self.items_collected, "items_collected"),
            (self.items_ignored, "items_ignored"),
            (self.inserted, "inserted"),
            (self.duplicates, "duplicates"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise FeedError(f"{name} must be a non-negative integer")
        if self.run_id is not None and (not isinstance(self.run_id, int) or self.run_id <= 0):
            raise FeedError("run_id must be a positive integer or None")
        if self.error is not None:
            if not isinstance(self.error, str):
                raise FeedError("error must be text or None")
            safe = runs.bounded_text(self.error, "error", max_chars=runs.MAX_ERROR_CHARS, redact=True)
            object.__setattr__(self, "error", safe)

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return _WS.sub(" ", str(value)).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(node: ET.Element | None) -> str:
    return _clean("" if node is None else "".join(node.itertext()))


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    path = parts.path or ""
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def validate_outbound_url(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeUrlError("URL must be HTTP(S) text")
    text = value.strip()
    try:
        parts = urlsplit(text)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise UnsafeUrlError("URL is malformed") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or not hostname:
        raise UnsafeUrlError("URL must be an absolute HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("URL credentials are not accepted")
    if registry._is_unsafe_host(hostname):
        raise UnsafeUrlError("unsafe or non-public URL host")
    if port is not None and not 1 <= port <= 65535:
        raise UnsafeUrlError("URL port is invalid")
    return text


def _item_link(node: ET.Element, base_url: str) -> str:
    href = node.attrib.get("href")
    rel = node.attrib.get("rel", "alternate").lower()
    raw = href if href and rel in {"", "alternate"} else _text(node)
    return validate_outbound_url(urljoin(base_url, raw))


def _child(node: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    for child in list(node):
        if _local(child.tag) in names:
            return child
    return None


def _preferred_child(node: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    if node is None:
        return None
    for name in names:
        for child in list(node):
            if _local(child.tag) == name:
                return child
    return None


def parse_feed(payload: bytes, *, base_url: str, max_bytes: int = MAX_BODY_BYTES, max_items: int = MAX_ITEMS) -> ParsedFeed:
    if not isinstance(payload, (bytes, bytearray)):
        raise FeedError("feed body must be bytes")
    if len(payload) > max_bytes:
        raise FeedError("feed body exceeds configured limit")
    if b"<!DOCTYPE" in bytes(payload).upper() or b"<!ENTITY" in bytes(payload).upper():
        raise FeedError("DOCTYPE or entity declarations are refused")
    try:
        root = ET.fromstring(bytes(payload))
    except ET.ParseError as exc:
        raise FeedError("malformed feed XML") from exc
    root_name = _local(root.tag)
    if root_name not in {"rss", "feed", "rdf"}:
        raise FeedError("unsupported feed root")
    validate_outbound_url(base_url)
    title_node = _child(root, ("title",))
    if title_node is None:
        channel = _child(root, ("channel",))
        title_node = _child(channel, ("title",)) if channel is not None else None
    feed_title = _text(title_node)
    candidates = [node for node in root.iter() if _local(node.tag) in {"item", "entry"}]
    items: list[FeedItem] = []
    ignored = 0
    for node in candidates[:max_items]:
        title = _text(_child(node, ("title",)))
        link_node = _child(node, ("link",))
        try:
            if not title or link_node is None:
                raise FeedError("item missing title or link")
            link = _item_link(link_node, base_url)
            content_node = _preferred_child(node, ("content", "description", "summary", "encoded"))
            content = _text(content_node)
            normalized_title = _clean(title)
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            published = _text(_child(node, ("published", "updated", "pubdate"))) or None
            items.append(FeedItem(title=title, canonical_url=_canonical_url(link), normalized_title=normalized_title,
                                  content=content, content_hash=content_hash, published_at=published))
        except (FeedError, ValueError):
            ignored += 1
    return ParsedFeed(feed_title=feed_title, items=tuple(items), items_ignored=ignored)


class UrllibFeedClient:
    """Small stdlib client with no automatic redirect handling."""

    def get(self, url: str, *, timeout: float, max_bytes: int) -> HttpResponse:
        checked = validate_outbound_url(url)
        parts = urlsplit(checked)
        host = parts.hostname or ""
        try:
            resolved = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
            for row in resolved:
                address = row[4][0]
                if registry._is_unsafe_host(address):
                    raise UnsafeUrlError("resolved host is not public")
        except socket.gaierror as exc:
            raise FeedTransportError("feed host could not be resolved") from exc
        connection_cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(host, parts.port, timeout=timeout)
        try:
            path = urlunsplit(("", "", parts.path or "/", parts.query, ""))
            connection.request("GET", path, headers={"Accept": "application/rss+xml, application/atom+xml, text/xml"})
            response = connection.getresponse()
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise FeedError("feed body exceeds configured limit")
            return HttpResponse(status_code=response.status, body=body, location=response.getheader("Location"),
                                content_type=response.getheader("Content-Type"))
        except (TimeoutError, socket.timeout, OSError, http.client.HTTPException) as exc:
            raise FeedTransportError("feed transport failure") from exc
        finally:
            connection.close()


def _now_iso(now: datetime | None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.isoformat()


def _failure(source: Any, fetched_at: str, error: str, conn: Any = None) -> CollectionResult:
    source_id = getattr(source, "source_id", "unknown")
    origin = getattr(source, "data_origin", "REAL")
    run_id = None
    if conn is not None:
        owns = not conn.in_transaction
        try:
            if owns:
                conn.execute("BEGIN")
            run_id = runs.start_run(conn, run_type="rss", source_id=source_id, data_origin=origin, started_at=fetched_at)
            runs.fail_run(conn, run_id, error_message=error, finished_at=fetched_at)
            if owns:
                conn.commit()
        except Exception:
            if owns:
                conn.rollback()
            run_id = None
    return CollectionResult(source_id=source_id, status="FAILED", data_origin=origin, fetched_at=fetched_at,
                            error=error, run_id=run_id)


def _record_skipped(source: Any, fetched_at: str, conn: Any) -> CollectionResult:
    source_id = source.source_id
    origin = source.data_origin
    run_id = None
    if conn is not None:
        owns = not conn.in_transaction
        try:
            if owns:
                conn.execute("BEGIN")
            run_id = runs.start_run(conn, run_type="rss", source_id=source_id, data_origin=origin, started_at=fetched_at)
            runs.finish_run(conn, run_id, status=runs.STATUS_SKIPPED, items_collected=0, finished_at=fetched_at)
            if owns:
                conn.commit()
        except Exception:
            if owns:
                conn.rollback()
            run_id = None
    return CollectionResult(source_id=source_id, status="SKIPPED", data_origin=origin, fetched_at=fetched_at, run_id=run_id)


def _fetch(client: FeedClient, source_url: str, limits: FeedLimits, sleep: Callable[[float], None]) -> tuple[HttpResponse, str]:
    current = validate_outbound_url(source_url)
    redirects = 0
    attempts = 0
    while True:
        try:
            response = client.get(current, timeout=limits.timeout_s, max_bytes=limits.max_body_bytes)
        except UnsafeUrlError:
            raise
        except FeedTransportError:
            if attempts >= limits.max_retries:
                raise FeedError("feed fetch failed after bounded retries")
            delay = min(limits.backoff_s * (2 ** attempts), limits.max_backoff_s)
            attempts += 1
            sleep(delay)
            continue
        if 300 <= response.status_code < 400:
            if redirects >= limits.max_redirects or not response.location:
                raise FeedError("redirect limit exceeded")
            redirects += 1
            current = validate_outbound_url(urljoin(current, response.location))
            continue
        if 500 <= response.status_code <= 599:
            if attempts >= limits.max_retries:
                raise FeedError("feed fetch failed after bounded retries")
            delay = min(limits.backoff_s * (2 ** attempts), limits.max_backoff_s)
            attempts += 1
            sleep(delay)
            continue
        if response.status_code < 200 or response.status_code >= 300:
            raise FeedError("feed returned a non-success status")
        if not isinstance(response.body, (bytes, bytearray)) or len(response.body) > limits.max_body_bytes:
            raise FeedError("feed body exceeds configured limit")
        return response, current


def _persist_success(conn: Any, source: Any, fetched_at: str, parsed: ParsedFeed) -> tuple[int, int, int]:
    owns = not conn.in_transaction
    run_id: int | None = None
    inserted = 0
    duplicates = 0
    try:
        if owns:
            conn.execute("BEGIN")
        run_id = runs.start_run(conn, run_type="rss", source_id=source.source_id, data_origin=source.data_origin, started_at=fetched_at)
        for item in parsed.items:
            existing = conn.execute(
                "SELECT 1 FROM raw_items WHERE source_id = ? AND canonical_url = ? AND normalized_title = ? AND content_hash = ? LIMIT 1",
                (source.source_id, item.canonical_url, item.normalized_title, item.content_hash),
            ).fetchone()
            if existing is not None:
                duplicates += 1
                continue
            conn.execute(
                """INSERT INTO raw_items
                   (source_id, canonical_url, normalized_title, content_hash, raw_content,
                    content_type, fetched_at, provenance, data_origin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source.source_id, item.canonical_url, item.normalized_title, item.content_hash, item.content,
                 item.content_type, fetched_at, json.dumps({"source": source.source_id, "fetched_at": fetched_at}, ensure_ascii=False),
                 source.data_origin),
            )
            inserted += 1
        runs.finish_run(conn, run_id, status=runs.STATUS_SUCCESS, items_collected=len(parsed.items), finished_at=fetched_at)
        if owns:
            conn.commit()
        return run_id, inserted, duplicates
    except Exception:
        if owns:
            conn.rollback()
        raise


def collect_feed(source: Any, client: FeedClient | None = None, now: datetime | None = None, conn: Any = None,
                 sleep: Callable[[float], None] | None = None, limits: FeedLimits | None = None) -> CollectionResult:
    """Collect one bounded feed using an injected client and optional DB connection."""
    fetched_at = _now_iso(now)
    limits = limits or FeedLimits()
    sleep = sleep or time.sleep
    source_id = getattr(source, "source_id", "unknown")
    origin = getattr(source, "data_origin", "REAL")
    try:
        validate_outbound_url(getattr(source, "url", None))
        if not getattr(source, "automated_collectable", False):
            return _record_skipped(source, fetched_at, conn)
        active_client = client or UrllibFeedClient()
        response, final_url = _fetch(active_client, source.url, limits, sleep)
        parsed = parse_feed(bytes(response.body), base_url=final_url, max_bytes=limits.max_body_bytes, max_items=limits.max_items)
    except (FeedError, ValueError, OSError) as exc:
        message = "unsafe outbound URL" if isinstance(exc, UnsafeUrlError) else ("malformed feed" if isinstance(exc, ET.ParseError) else str(exc))
        if not message or "timed out" in message.lower() or "timeout" in message.lower():
            message = "feed fetch failed after bounded retries"
        return _failure(source, fetched_at, message, conn)
    if conn is None:
        return CollectionResult(source_id=source_id, status="SUCCESS", data_origin=origin, fetched_at=fetched_at,
                                items_collected=len(parsed.items), items_ignored=parsed.items_ignored)
    try:
        run_id, inserted, duplicates = _persist_success(conn, source, fetched_at, parsed)
    except Exception as exc:
        return _failure(source, fetched_at, "feed persistence failed", conn=None)
    return CollectionResult(source_id=source_id, status="SUCCESS", data_origin=origin, fetched_at=fetched_at,
                            items_collected=len(parsed.items), items_ignored=parsed.items_ignored,
                            inserted=inserted, duplicates=duplicates, run_id=run_id)
