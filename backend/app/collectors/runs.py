"""Transactional helpers for ``collection_runs`` (task 012).

Hợp đồng:
- Vòng đời một lần thu thập: ``start_run`` (RUNNING) -> ``finish_run`` (SUCCESS/SKIPPED)
  hoặc ``fail_run`` (FAILED). Không có đường nào nhảy thẳng sang trạng thái kết thúc
  mà không qua RUNNING, và một run đã kết thúc KHÔNG BAO GIỜ bị ghi đè lần hai.
- Mọi giá trị đều đi qua **bind parameter**; không giá trị nào (run_type, source_id,
  error_message) được nối vào SQL. Text lấy từ ngoài là dữ liệu không tin cậy.
- ``error_message`` là metadata **chặn (bounded)**: cắt trần độ dài, bỏ ký tự điều
  khiển, gộp khoảng trắng và che các giá trị giống secret trước khi lưu. Nó chỉ được
  LƯU, không bao giờ được thực thi hay diễn giải thành lệnh.
- Ghi trong transaction: helper tự mở transaction riêng (commit/rollback) khi caller
  chưa có transaction; nếu caller đang mở transaction thì helper chỉ nối vào đó và để
  caller quyết định commit/rollback toàn bộ.
- ``start_run`` không tạo ra bài viết/raw item nào và không gọi mạng — nó chỉ ghi sổ.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import sqlite3
from typing import Any, Sequence

#: Trạng thái hợp lệ của collection_runs (khớp dữ liệu seed SAMPLE sẵn có).
STATUS_RUNNING = "RUNNING"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUSES: tuple[str, ...] = (STATUS_RUNNING, STATUS_SUCCESS, STATUS_FAILED, STATUS_SKIPPED)

#: finish_run chỉ được đóng một run sang hai trạng thái này; FAILED đi qua fail_run
#: để bắt buộc có error_message.
FINISH_STATUSES: tuple[str, ...] = (STATUS_SUCCESS, STATUS_SKIPPED)

#: Data origin hợp lệ cho một dòng sổ.
SUPPORTED_DATA_ORIGINS: tuple[str, ...] = ("REAL", "SAMPLE")

#: Trần độ dài metadata — sổ collection_runs không phải chỗ chứa log khổng lồ.
MAX_ERROR_CHARS = 400
MAX_RUN_TYPE_CHARS = 100
MAX_SOURCE_ID_CHARS = 128

#: Dấu hiệu bị cắt, giữ tổng độ dài <= trần.
TRUNCATION_MARKER = "…[truncated]"

#: Ký tự điều khiển (gồm \r \n \t \x00 \x1b) -> khoảng trắng trước khi lưu.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")

#: Mẫu che secret. Chỉ áp dụng cho error_message — không áp dụng cho run_type/source_id
#: (định danh) để không làm sai lệch vết kiểm toán.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Authorization: Bearer <token>
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-+/=]{4,}"), r"\1 [REDACTED]"),
    # Khóa API dạng "tiền tố ngắn + gạch nối" (prefix like sk, ak, ghp, xoxb)…
    (re.compile(r"(?i)\b(?:sk|ak|pk|ghp|xoxb)-[A-Za-z0-9_\-]{6,}"), "[REDACTED]"),
    # key=value / key: value / "key value" cho các tên trường nhạy cảm
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|"
            r"password|passwd|pwd|authorization|credential)\b\s*(?:[:=]\s*|\s+)"
            r"([^\s,;\"']+)"
        ),
        r"\1=[REDACTED]",
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_secrets(text: str) -> str:
    """Che các giá trị giống secret trong một chuỗi (idempotent).

    Dùng cho metadata lỗi trước khi ghi sổ: một token vô tình lọt vào thông báo lỗi
    sẽ không bao giờ được lưu lại. Hàm này KHÔNG đọc biến môi trường và không truy
    cập secret nào — nó chỉ thay thế mẫu văn bản.
    """
    if not isinstance(text, str):
        raise ValueError("redact_secrets expects a string")
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def bounded_text(
    value: Any,
    field: str,
    *,
    max_chars: int,
    required: bool = True,
    redact: bool = False,
) -> str | None:
    """Chuẩn hoá text metadata: bỏ ký tự điều khiển, gộp khoảng trắng, cắt trần.

    Raises:
        ValueError: giá trị rỗng khi bắt buộc, hoặc không phải chuỗi.
    """
    if value is None:
        if required:
            raise ValueError(f"{field} must be a non-empty string")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    text = _WHITESPACE.sub(" ", _CONTROL_CHARS.sub(" ", value)).strip()
    if not text:
        if required:
            raise ValueError(f"{field} must be a non-empty string")
        return None
    # Che secret TRƯỚC khi cắt trần để không cắt vụn một mẫu secret thành chuỗi
    # vẫn nhận ra được (và vẫn giữ tổng độ dài dưới trần).
    if redact:
        text = redact_secrets(text)
    if len(text) > max_chars:
        keep = max(max_chars - len(TRUNCATION_MARKER), 0)
        text = text[:keep] + TRUNCATION_MARKER
    return text


def _validate_run_id(value: Any, field: str = "run_id") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive int")
    return value


def _validate_optional_identifier(value: Any, field: str, max_chars: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string or None")
    text = value.strip()
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds {max_chars} characters")
    return text


def _validate_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone offset")
    return text


def _validate_items_collected(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("items_collected must be a non-negative int or None")
    if value < 0:
        raise ValueError("items_collected must be a non-negative int or None")
    return value


def _validate_data_origin(value: Any) -> str:
    if value not in SUPPORTED_DATA_ORIGINS:
        raise ValueError(
            f"data_origin must be one of {', '.join(SUPPORTED_DATA_ORIGINS)}"
        )
    return value


def _write(conn: sqlite3.Connection, sql: str, parameters: Sequence[Any]) -> sqlite3.Cursor:
    """Thực thi một câu ghi parameterized trong transaction đúng ngữ cảnh.

    - Caller đã có transaction -> chỉ nối vào, không tự commit.
    - Ngược lại -> tự mở transaction riêng: thành công commit, lỗi rollback.
    """
    if conn.in_transaction:
        return conn.execute(sql, tuple(parameters))
    with conn:
        return conn.execute(sql, tuple(parameters))


_INSERT_RUN_SQL = """
INSERT INTO collection_runs (source_id, run_type, started_at, status, data_origin)
VALUES (?, ?, ?, ?, ?)
"""

#: Chỉ đóng được một run ĐANG ở trạng thái RUNNING — chặn ghi đè lần hai.
_FINISH_RUN_SQL = """
UPDATE collection_runs
   SET status = ?, finished_at = ?, items_collected = ?
 WHERE id = ? AND status = ?
"""

_FAIL_RUN_SQL = """
UPDATE collection_runs
   SET status = ?, finished_at = ?, error_message = ?
 WHERE id = ? AND status = ?
"""

_RUN_COLUMNS = (
    "id",
    "source_id",
    "run_type",
    "started_at",
    "finished_at",
    "status",
    "items_collected",
    "error_message",
    "data_origin",
    "created_at",
)


def start_run(
    conn: sqlite3.Connection,
    *,
    run_type: str,
    source_id: str | None = None,
    data_origin: str = "REAL",
    started_at: str | None = None,
) -> int:
    """Mở một dòng collection_runs ở trạng thái RUNNING; trả về id dòng mới.

    Raises:
        ValueError: run_type/source_id/data_origin/started_at không hợp lệ.
        sqlite3.IntegrityError: source_id không tồn tại trong bảng sources
            (khi foreign key đang bật) — transaction tự rollback, không để lại rác.
    """
    normalized_type = bounded_text(
        run_type, "run_type", max_chars=MAX_RUN_TYPE_CHARS, required=True
    )
    source = _validate_optional_identifier(source_id, "source_id", MAX_SOURCE_ID_CHARS)
    origin = _validate_data_origin(data_origin)
    started = _validate_timestamp(started_at, "started_at") if started_at is not None else _now()

    cursor = _write(
        conn,
        _INSERT_RUN_SQL,
        (source, normalized_type, started, STATUS_RUNNING, origin),
    )
    run_id = cursor.lastrowid
    if run_id is None:
        raise ValueError("database did not return a row id for the inserted run")
    return int(run_id)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    items_collected: int | None = None,
    status: str = STATUS_SUCCESS,
    finished_at: str | None = None,
) -> None:
    """Đóng một run đang RUNNING với số item đã thu được.

    Raises:
        ValueError: tham số không hợp lệ, hoặc run không tồn tại / không ở RUNNING.
    """
    identifier = _validate_run_id(run_id)
    if status not in FINISH_STATUSES:
        raise ValueError(f"status must be one of {', '.join(FINISH_STATUSES)}")
    items = _validate_items_collected(items_collected)
    finished = _validate_timestamp(finished_at, "finished_at") if finished_at is not None else _now()

    cursor = _write(
        conn,
        _FINISH_RUN_SQL,
        (status, finished, items, identifier, STATUS_RUNNING),
    )
    if cursor.rowcount != 1:
        raise ValueError(
            f"run {identifier} is not RUNNING (already finished or missing)"
        )


def fail_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    error_message: str,
    finished_at: str | None = None,
) -> None:
    """Đóng một run đang RUNNING ở trạng thái FAILED với metadata lỗi đã chặn.

    ``error_message`` được chuẩn hoá (bỏ ký tự điều khiển, gộp khoảng trắng, che
    secret, cắt trần) và chỉ được LƯU như dữ liệu — không bao giờ thực thi.

    Raises:
        ValueError: error_message rỗng/không phải chuỗi, run không tồn tại hoặc
            không ở trạng thái RUNNING.
    """
    identifier = _validate_run_id(run_id)
    message = bounded_text(
        error_message, "error_message", max_chars=MAX_ERROR_CHARS, required=True, redact=True
    )
    finished = _validate_timestamp(finished_at, "finished_at") if finished_at is not None else _now()

    cursor = _write(
        conn,
        _FAIL_RUN_SQL,
        (STATUS_FAILED, finished, message, identifier, STATUS_RUNNING),
    )
    if cursor.rowcount != 1:
        raise ValueError(
            f"run {identifier} is not RUNNING (already finished or missing)"
        )


def get_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    """Đọc một dòng collection_runs; None nếu không tồn tại."""
    identifier = _validate_run_id(run_id)
    columns = ", ".join(_RUN_COLUMNS)
    return conn.execute(
        f"SELECT {columns} FROM collection_runs WHERE id = ?", (identifier,)
    ).fetchone()


def run_history(
    conn: sqlite3.Connection,
    *,
    source_id: str | None = None,
    limit: int | None = None,
) -> Sequence[sqlite3.Row]:
    """Lịch sử các lần thu thập, mới nhất trước; mọi điều kiện đều parameterized."""
    source = _validate_optional_identifier(source_id, "source_id", MAX_SOURCE_ID_CHARS)
    if limit is not None and (
        not isinstance(limit, int) or isinstance(limit, bool) or limit < 0
    ):
        raise ValueError("limit must be a non-negative int or None")

    columns = ", ".join(_RUN_COLUMNS)
    sql = f"SELECT {columns} FROM collection_runs"
    parameters: list[Any] = []
    if source is not None:
        sql += " WHERE source_id = ?"
        parameters.append(source)
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    return conn.execute(sql, parameters).fetchall()