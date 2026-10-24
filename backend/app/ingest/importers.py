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


def _has_source_observation(conn: sqlite3.Connection, item: NormalizedItem) -> bool:
    row = conn.execute(
        """SELECT 1 FROM raw_items
           WHERE source_id = ?
             AND canonical_url = ?
             AND normalized_title = ?
             AND content_hash = ?
             AND (data_origin IS NULL OR data_origin != 'SAMPLE')
           LIMIT 1""",
        (item.source_id, item.canonical_url, item.normalized_title, item.content_hash),
    ).fetchone()
    return row is not None


def _has_normalized_item(
    conn: sqlite3.Connection, item: NormalizedItem, has_article_dedup_cols: bool
) -> bool:
    raw_row = conn.execute(
        """SELECT 1 FROM raw_items
           WHERE canonical_url = ?
             AND normalized_title = ?
             AND content_hash = ?
             AND (data_origin IS NULL OR data_origin != 'SAMPLE')
           LIMIT 1""",
        (item.canonical_url, item.normalized_title, item.content_hash),
    ).fetchone()
    if raw_row is not None:
        return True
    if has_article_dedup_cols:
        article_row = conn.execute(
            """SELECT 1 FROM articles
               WHERE url = ?
                 AND normalized_title = ?
                 AND content_hash = ?
                 AND (data_origin IS NULL OR data_origin != 'SAMPLE')
               LIMIT 1""",
            (item.canonical_url, item.normalized_title, item.content_hash),
        ).fetchone()
        return article_row is not None
    return False


def persist_import(
    conn: sqlite3.Connection, items: list[dict], source_id: str, content_type: str
) -> dict[str, int]:
    """Normalize, deduplicate, and write all rows atomically; an invalid batch writes nothing."""
    if not isinstance(items, list) or not items:
        raise ImportValidationError("import batch must contain at least one item")
    if not isinstance(content_type, str) or not content_type.strip():
        raise ImportValidationError("content_type must be a non-empty string")
    fetched_at = datetime.now(UTC).isoformat()
    try:
        normalized: list[NormalizedItem] = [
            normalize_item(item, source_id, fetched_at) for item in items
        ]
    except ValueError as error:
        raise ImportValidationError(str(error)) from error
    normalized_source_id = normalized[0].source_id
    inserted = 0
    skipped = 0
    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN IMMEDIATE")
        else:
            conn.execute("SAVEPOINT persist_import_batch")
        article_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        has_article_dedup_cols = {"normalized_title", "content_hash"}.issubset(article_columns)
        conn.execute(
            """INSERT OR IGNORE INTO sources
               (source_id, name, type, collection_method, priority, status, data_origin)
               VALUES (?, ?, 'manual', 'manual_import', 9, 'active', 'REAL')""",
            (normalized_source_id, f"Manual import: {normalized_source_id}"),
        )
        for item in normalized:
            if _has_source_observation(conn, item):
                skipped += 1
                continue
            already_known = _has_normalized_item(conn, item, has_article_dedup_cols)
            conn.execute(
                """INSERT INTO raw_items
                   (source_id, canonical_url, normalized_title, content_hash, raw_content,
                    content_type, fetched_at, provenance, data_origin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REAL')""",
                (item.source_id, item.canonical_url, item.normalized_title, item.content_hash,
                 item.content, content_type, item.fetched_at, json.dumps(item.provenance)),
            )
            if already_known:
                skipped += 1
                continue
            if has_article_dedup_cols:
                conn.execute(
                    """INSERT INTO articles
                       (title, url, source, summary, data_origin, article_status,
                        normalized_title, content_hash)
                       VALUES (?, ?, ?, ?, 'REAL', 'DRAFT', ?, ?)""",
                    (
                        item.normalized_title,
                        item.canonical_url,
                        item.source_id,
                        item.content,
                        item.normalized_title,
                        item.content_hash,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO articles
                       (title, url, source, summary, data_origin, article_status)
                       VALUES (?, ?, ?, ?, 'REAL', 'DRAFT')""",
                    (item.normalized_title, item.canonical_url, item.source_id, item.content),
                )
            inserted += 1
        if own_transaction:
            conn.commit()
        else:
            conn.execute("RELEASE SAVEPOINT persist_import_batch")
    except Exception:
        if own_transaction:
            conn.rollback()
        else:
            conn.execute("ROLLBACK TO SAVEPOINT persist_import_batch")
            conn.execute("RELEASE SAVEPOINT persist_import_batch")
        raise
    return {"inserted": inserted, "skipped": skipped, "errors": 0}
