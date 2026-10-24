"""Deterministic normalization for imported content."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Any
import unicodedata
from urllib.parse import urlsplit, urlunsplit


_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class NormalizedItem:
    source_id: str
    fetched_at: str
    title: str
    url: str
    canonical_url: str
    normalized_title: str
    content: str
    content_hash: str
    provenance: dict[str, str]


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _required_timestamp(value: Any) -> str:
    timestamp = _required_text(value, "fetched_at")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("fetched_at must be an ISO-8601 timestamp") from error
    return timestamp


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def _canonicalize_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise ValueError("url must be an absolute HTTP(S) URL")

    hostname = parts.hostname
    if not hostname:
        raise ValueError("url must include a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("url user-info is not supported")
    host = hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    path = parts.path or ""
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def normalize_item(payload: dict, source_id: str, fetched_at: str) -> NormalizedItem:
    """Normalize one imported payload without I/O or interpretation of its text."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    source = _required_text(source_id, "source_id")
    fetched = _required_timestamp(fetched_at)
    title = _required_text(payload.get("title"), "title")
    url = _required_text(payload.get("url"), "url")
    content = _required_text(payload.get("content"), "content")
    normalized_title = _normalize_whitespace(title)
    normalized_content = _normalize_whitespace(content)
    return NormalizedItem(
        source_id=source,
        fetched_at=fetched,
        title=title,
        url=url,
        canonical_url=_canonicalize_url(url),
        normalized_title=normalized_title,
        content=normalized_content,
        content_hash=hashlib.sha256(normalized_content.encode("utf-8")).hexdigest(),
        provenance={"source": source, "fetched_at": fetched},
    )
