"""Safe parsing and transactional persistence for manual imports."""
from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
import json
import sqlite3
from typing import Any

from .normalize import NormalizedItem, normalize_item


ALLOWED_FIELDS = ("title", "url", "content")
MAX_UPLOAD_BYTES = 1_000_000


class ImportValidationError(ValueError):
    """An uploaded document cannot be safely imported."""


def _safe_item(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ImportValidationError("each import item must be an object")
    item = {key: value.get(key) for key in ALLOWED_FIELDS}
    if any(not isinstance(item[key], str) or not item[key].strip() for key in ALLOWED_FIELDS):
        raise ImportValidationError("title, url and content must be non-empty strings")
    return item  # type: ignore[return-value]


def parse_markdown(text: str) -> list[dict]:
    """Parse one Markdown document with required plain-text front matter."""
    if not text.startswith("---\n"):
        raise ImportValidationError("Markdown must begin with front matter")
    try:
        header, content = text[4:].split("\n---\n", 1)
    except ValueError as error:
        raise ImportValidationError("Markdown front matter is not closed") from error
    fields: dict[str, str] = {}
    for line in header.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise ImportValidationError("Markdown front matter contains an invalid line")
        if key.strip() in ("title", "url"):
            fields[key.strip()] = value.strip()
    fields["content"] = content.strip()
    return [_safe_item(fields)]


def parse_csv(text: str) -> list[dict]:
    """Parse CSV using only the fields accepted by normalization."""
    try:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or not set(ALLOWED_FIELDS).issubset(reader.fieldnames):
            raise ImportValidationError("CSV must include title, url and content columns")
        items = [_safe_item(row) for row in reader]
    except csv.Error as error:
        raise ImportValidationError("CSV is malformed") from error
    if not items:
        raise ImportValidationError("CSV contains no items")
    return items


def parse_json(text: str) -> list[dict]:
    """Parse a JSON item, list of items, or object containing ``items``."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ImportValidationError("JSON is malformed") from error
    if isinstance(payload, dict) and "items" in payload:
        payload = payload["items"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise ImportValidationError("JSON must contain one or more items")
    return [_safe_item(value) for value in payload]


def parse_upload(filename: str, text: str) -> tuple[list[dict], str]:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    parsers = {"md": parse_markdown, "csv": parse_csv, "json": parse_json}
    parser = parsers.get(extension)
    if parser is None:
        raise ImportValidationError("only .md, .csv and .json uploads are accepted")
    return parser(text), extension


def persist_import(
    conn: sqlite3.Connection, items: list[dict], source_id: str, content_type: str
) -> dict[str, int]:
    """Normalize and write all rows atomically; an invalid item writes nothing."""
    fetched_at = datetime.now(UTC).isoformat()
    try:
        normalized: list[NormalizedItem] = [
            normalize_item(item, source_id, fetched_at) for item in items
        ]
    except ValueError as error:
        raise ImportValidationError(str(error)) from error
    try:
        conn.execute("BEGIN")
        conn.execute(
            """INSERT OR IGNORE INTO sources
               (source_id, name, type, collection_method, priority, status, data_origin)
               VALUES (?, ?, 'manual', 'manual_import', 9, 'active', 'REAL')""",
            (source_id, f"Manual import: {source_id}"),
        )
        for item in normalized:
            conn.execute(
                """INSERT INTO raw_items
                   (source_id, canonical_url, normalized_title, content_hash, raw_content,
                    content_type, fetched_at, provenance, data_origin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REAL')""",
                (item.source_id, item.canonical_url, item.normalized_title, item.content_hash,
                 item.content, content_type, item.fetched_at, json.dumps(item.provenance)),
            )
            conn.execute(
                """INSERT INTO articles
                   (title, url, source, summary, data_origin, article_status)
                   VALUES (?, ?, ?, ?, 'REAL', 'DRAFT')""",
                (item.title, item.canonical_url, item.source_id, item.content),
            )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    return {"inserted": len(normalized), "skipped": 0, "errors": 0}
