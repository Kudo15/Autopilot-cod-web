"""Safe scheduled inbox scanner and deterministic persistence (sri-001c).

Hợp đồng:
- Chỉ xử lý file ``*.json`` cuối cùng (regular file, không symlink) nằm
  TRỰC TIẾP trong thư mục inbox; ``*.tmp``, nested, thư mục, đuôi khác bị
  lờ đi hoàn toàn — không parse, không cách ly.
- Nội dung artifact là untrusted data: parse UTF-8 → validate qua
  ``ScheduledReport``; không thực thi text, không gọi mạng, không dùng
  text của artifact làm đường dẫn hay SQL identifier (100% parameterized
  SQL; đường dẫn cách ly sinh từ SHA-256 của chính byte).
- Mỗi artifact chạy trong đúng một transaction SQLite; lỗi một file không
  để lại row source/raw/article/ledger nửa vời và không chặn file khác.
- ``run_id + content_hash`` đã có trong ledger với cùng hash = idempotent
  skip (không thêm row). ``run_id`` bị tái dùng với byte khác = cách ly
  an toàn, không cập nhật/xóa row ledger gốc (INSERT OR IGNORE, không
  có destructive SQL).

Chưa có ở task này (cố ý): AI/gateway enrichment, HTTP API, React UI,
scheduler, docs, deploy, publication.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..ingest.normalize import NormalizedItem, normalize_item
from .schema import ScheduledReport

#: Source row do server tự quản — cố định, không bao giờ lấy từ artifact.
SOURCE_ID = "scheduled_inbox"
SOURCE_NAME = "Scheduled inbox (server-owned)"
SOURCE_TYPE = "radar"
COLLECTION_METHOD = "scheduled_inbox_scan"
SOURCE_PRIORITY = 9

#: Nơi đặt file bị cách ly — thư mục con của inbox, tên file chỉ là hash.
QUARANTINE_DIRNAME = "quarantine"
CONTENT_TYPE = "application/json"

#: Giới hạn độ dài thông lỗi lưu ledger (bounded, inert text).
MAX_ERROR_CHARS = 500

#: Giá trị placeholder cho artifact không parse được (không có dữ tin cậy).
UNKNOWN = "unknown"

#: Projection allowlist của list_inbox_runs — đúng các cột ledger an toàn.
_RUN_KEYS: tuple[str, ...] = (
    "run_id",
    "report_kind",
    "content_hash",
    "observed_at",
    "status",
    "finding_count",
    "accepted_count",
    "skipped_count",
    "error_message",
    "processed_at",
    "data_origin",
)


@dataclass(frozen=True)
class InboxScanResult:
    """Bộ đếm của một lần quét — đủ phân biệt imported/skipped/quarantined
    runs và accepted/skipped findings."""

    imported_runs: int = 0
    skipped_runs: int = 0
    quarantined_runs: int = 0
    accepted_findings: int = 0
    skipped_findings: int = 0


class _RunIdConflict(RuntimeError):
    """run_id đã có trong ledger với content_hash khác — phải cách ly."""

    def __init__(self, run_id: str, content_hash: str) -> None:
        super().__init__(
            f"run_id {run_id!r} already recorded with different content"
        )
        self.run_id = run_id
        self.content_hash = content_hash


class _LedgerRaceError(RuntimeError):
    """Row ledger xuất hiện giữa bước kiểm tra và INSERT (race)."""


@dataclass(frozen=True)
class _Outcome:
    kind: str  # "imported" | "skipped" | "quarantined"
    accepted: int = 0
    skipped: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _bounded_error(error: BaseException) -> str:
    """Chuỗi lỗi ngắn, bounded — lưu như inert text, không bao giờ thực thi."""
    return f"{type(error).__name__}: {error}"[:MAX_ERROR_CHARS]


def _iter_artifacts(directory: Path) -> list[Path]:
    """Chỉ file regular ``*.json`` trực tiếp trong directory, theo thứ tự tên."""
    artifacts: list[Path] = []
    for entry in directory.iterdir():
        try:
            if entry.is_symlink() or not entry.is_file():
                continue  # symlink, thư mục (kể cả tên *.json), device...
        except OSError:
            continue
        if entry.suffix.lower() != ".json":  # lờ .tmp, .txt, đuôi khác
            continue
        artifacts.append(entry)
    return sorted(artifacts, key=lambda p: p.name)


def _finding_already_recorded(conn: sqlite3.Connection, item: NormalizedItem) -> bool:
    """Observation cùng (canonical_url, normalized_title, content_hash) đã có
    ở raw_items (bất kỳ source nào) hoặc articles — không thêm row nữa."""
    row = conn.execute(
        """SELECT 1 FROM raw_items
           WHERE canonical_url = ?
             AND normalized_title = ?
             AND content_hash = ?
             AND (data_origin IS NULL OR data_origin != 'SAMPLE')
           LIMIT 1""",
        (item.canonical_url, item.normalized_title, item.content_hash),
    ).fetchone()
    if row is not None:
        return True
    row = conn.execute(
        """SELECT 1 FROM articles
           WHERE url = ?
             AND normalized_title = ?
             AND content_hash = ?
             AND (data_origin IS NULL OR data_origin != 'SAMPLE')
           LIMIT 1""",
        (item.canonical_url, item.normalized_title, item.content_hash),
    ).fetchone()
    return row is not None


def _write_quarantine_file(directory: Path, content_hash: str, raw: bytes | None) -> None:
    """Sao byte artifact vào quarantine/<sha256>.json — tên chỉ từ hash của
    chính byte, KHÔNG interpolate field của artifact hay relative path.
    Best-effort: ledger là bằng chứng chính."""
    if not content_hash or raw is None:
        return
    target = directory / QUARANTINE_DIRNAME / f"{content_hash}.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(raw)
    except OSError:
        pass


def _record_quarantine(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    report_kind: str,
    content_hash: str,
    observed_at: str,
    error: BaseException,
) -> None:
    """Một row QUARANTINED — INSERT OR IGNORE nên KHÔNG BAO GIỜ ghi đè
    row ledger đã tồn tại cho cùng run_id. Không có destructive SQL."""
    own_transaction = not conn.in_transaction
    conn.execute(
        """INSERT OR IGNORE INTO scheduled_inbox_runs
           (run_id, report_kind, content_hash, observed_at, status, finding_count,
            accepted_count, skipped_count, error_message, processed_at, data_origin)
           VALUES (?, ?, ?, ?, 'QUARANTINED', 0, 0, 0, ?, ?, 'REAL')""",
        (run_id, report_kind, content_hash, observed_at, _bounded_error(error), _now()),
    )
    if own_transaction:
        conn.commit()


def _import_report(
    conn: sqlite3.Connection, report: ScheduledReport, content_hash: str
) -> _Outcome:
    """Nạp một report hợp lệ trong đúng MỘT transaction (BEGIN IMMEDIATE hoặc
    SAVEPOINT nếu caller đang giữ transaction). Bất kỳ lỗi nào → rollback
    toàn bộ artifact."""

    def run() -> _Outcome:
        existing = conn.execute(
            "SELECT content_hash FROM scheduled_inbox_runs WHERE run_id = ?",
            (report.run_id,),
        ).fetchone()
        if existing is not None:
            if existing[0] == content_hash:
                # Idempotent: cùng run_id + cùng byte — không thêm row nào.
                return _Outcome("skipped", 0, len(report.findings))
            raise _RunIdConflict(report.run_id, content_hash)

        conn.execute(
            """INSERT OR IGNORE INTO sources
               (source_id, name, type, collection_method, priority, status, data_origin)
               VALUES (?, ?, ?, ?, ?, 'active', 'REAL')""",
            (SOURCE_ID, SOURCE_NAME, SOURCE_TYPE, COLLECTION_METHOD, SOURCE_PRIORITY),
        )

        observed_at = report.observed_at.isoformat()
        accepted = 0
        skipped = 0
        for finding in report.findings:
            # URL canonical đầu tiên + thời điểm quan sát của report.
            item = normalize_item(
                {
                    "title": finding.title,
                    "url": finding.canonical_urls[0],
                    "content": finding.summary,
                },
                SOURCE_ID,
                observed_at,
            )
            if _finding_already_recorded(conn, item):
                skipped += 1
                continue
            provenance: dict[str, object] = dict(item.provenance)
            provenance.update(
                {
                    "report_kind": report.report_kind,
                    "run_id": report.run_id,
                    "external_id": finding.external_id,
                    "canonical_urls": list(finding.canonical_urls),
                    "source_type": finding.source_type,
                    "verification_status": finding.verification_status,
                    "evidence_note": finding.evidence_note,
                    "risk_note": finding.risk_note,
                }
            )
            conn.execute(
                """INSERT INTO raw_items
                   (source_id, canonical_url, normalized_title, content_hash, raw_content,
                    content_type, fetched_at, provenance, data_origin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REAL')""",
                (
                    SOURCE_ID,
                    item.canonical_url,
                    item.normalized_title,
                    item.content_hash,
                    item.content,
                    CONTENT_TYPE,
                    item.fetched_at,
                    json.dumps(provenance, ensure_ascii=False),
                ),
            )
            conn.execute(
                """INSERT INTO articles
                   (title, url, source, category, summary, published_at,
                    data_origin, article_status, normalized_title, content_hash)
                   VALUES (?, ?, ?, ?, ?, NULL, 'REAL', 'DRAFT', ?, ?)""",
                (
                    item.normalized_title,
                    item.canonical_url,
                    SOURCE_ID,
                    finding.category,
                    finding.summary,
                    item.normalized_title,
                    item.content_hash,
                ),
            )
            accepted += 1

        inserted = conn.execute(
            """INSERT OR IGNORE INTO scheduled_inbox_runs
               (run_id, report_kind, content_hash, observed_at, status, finding_count,
                accepted_count, skipped_count, error_message, processed_at, data_origin)
               VALUES (?, ?, ?, ?, 'IMPORTED', ?, ?, ?, NULL, ?, 'REAL')""",
            (
                report.run_id,
                report.report_kind,
                content_hash,
                observed_at,
                len(report.findings),
                accepted,
                skipped,
                _now(),
            ),
        )
        if inserted.rowcount != 1:
            raise _LedgerRaceError(
                f"ledger row for run_id {report.run_id!r} appeared during import"
            )
        return _Outcome("imported", accepted, skipped)

    own_transaction = not conn.in_transaction
    if own_transaction:
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SAVEPOINT inbox_artifact")
    try:
        outcome = run()
    except Exception:
        if own_transaction:
            conn.rollback()
        else:
            conn.execute("ROLLBACK TO SAVEPOINT inbox_artifact")
            conn.execute("RELEASE SAVEPOINT inbox_artifact")
        raise
    else:
        if own_transaction:
            conn.commit()
        else:
            conn.execute("RELEASE SAVEPOINT inbox_artifact")
    return outcome


def _process_artifact(directory: Path, path: Path, conn: sqlite3.Connection) -> _Outcome:
    """Xử lý một file artifact; mọi thất bại được cách ly an toàn."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        _record_quarantine(
            conn,
            run_id=f"quarantined-unreadable-{uuid.uuid4().hex}",
            report_kind=UNKNOWN,
            content_hash="",
            observed_at="",
            error=error,
        )
        return _Outcome("quarantined")

    content_hash = hashlib.sha256(raw).hexdigest()

    try:
        # json.JSONDecodeError, UnicodeDecodeError, pydantic ValidationError
        # đều là ValueError.
        payload = json.loads(raw.decode("utf-8"))
        report = ScheduledReport.model_validate(payload)
    except ValueError as error:
        _write_quarantine_file(directory, content_hash, raw)
        _record_quarantine(
            conn,
            run_id=f"quarantined-{content_hash}",
            report_kind=UNKNOWN,
            content_hash=content_hash,
            observed_at="",
            error=error,
        )
        return _Outcome("quarantined")

    observed_at = report.observed_at.isoformat()
    try:
        return _import_report(conn, report, content_hash)
    except _RunIdConflict as conflict:
        _write_quarantine_file(directory, content_hash, raw)
        _record_quarantine(
            conn,
            run_id=conflict.run_id,
            report_kind=report.report_kind,
            content_hash=conflict.content_hash,
            observed_at=observed_at,
            error=conflict,
        )
        return _Outcome("quarantined")
    except (sqlite3.Error, _LedgerRaceError, ValueError) as error:
        # normalize_item (ValueError) hay SQL (sqlite3.Error) — transaction
        # đã được rollback bởi _import_report.
        _write_quarantine_file(directory, content_hash, raw)
        _record_quarantine(
            conn,
            run_id=report.run_id,
            report_kind=report.report_kind,
            content_hash=content_hash,
            observed_at=observed_at,
            error=error,
        )
        return _Outcome("quarantined")


def scan_inbox(directory: Path, conn: sqlite3.Connection) -> InboxScanResult:
    """Quét một lần các artifact inbox cuối cùng trong ``directory``.

    Không gọi mạng, không chạy lệnh, không dùng text artifact làm đường dẫn
    hay SQL identifier. Mỗi file xử lý độc lập trong một transaction;
    file lỗi không chặn file khác.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"inbox directory is not a directory: {directory!r}")

    imported_runs = 0
    skipped_runs = 0
    quarantined_runs = 0
    accepted_findings = 0
    skipped_findings = 0
    for path in _iter_artifacts(directory):
        outcome = _process_artifact(directory, path, conn)
        if outcome.kind == "imported":
            imported_runs += 1
            accepted_findings += outcome.accepted
            skipped_findings += outcome.skipped
        elif outcome.kind == "skipped":
            skipped_runs += 1
            skipped_findings += outcome.skipped
        else:
            quarantined_runs += 1
    return InboxScanResult(
        imported_runs=imported_runs,
        skipped_runs=skipped_runs,
        quarantined_runs=quarantined_runs,
        accepted_findings=accepted_findings,
        skipped_findings=skipped_findings,
    )


def list_inbox_runs(conn: sqlite3.Connection) -> list[dict]:
    """Dự phóng allowlist các row ledger, mới nhất trước.

    Chỉ trả các cột của chính ledger — không có report text, không có
    đường dẫn filesystem, không có provenance blob.
    """
    rows = conn.execute(
        "SELECT "
        + ", ".join(_RUN_KEYS)
        + " FROM scheduled_inbox_runs ORDER BY processed_at DESC, run_id DESC"
    ).fetchall()
    return [dict(zip(_RUN_KEYS, row)) for row in rows]
