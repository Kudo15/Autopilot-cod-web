"""Quota observation persistence (Phase 8, task 009).

Hợp đồng:
- Chỉ thêm dòng (append-only) theo thời gian — KHÔNG bao giờ ghi đè quan sát cũ.
- Mỗi dòng mang `observed_at` bắt buộc; ghi trong transaction (commit/rollback).
- Không bịa giá trị quota: toàn bộ trường giá trị rỗng -> bị từ chối.
- Snapshot/giá trị quan sát là dữ liệu không tin cậy: chỉ lưu, không thực thi,
  không dùng để dựng SQL (mọi truy vấn đều parameterized).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Iterable, Sequence

#: Cột bắt buộc được ghi khi thêm một quan sát — thứ tự khớp placeholder bên dưới.
_INSERT_COLUMNS = (
    "provider_model_id",
    "observed_at",
    "rate_limit",
    "daily_quota",
    "observed_value",
    "note",
    "data_origin",
)

_INSERT_SQL = f"""
INSERT INTO quota_observations ({", ".join(_INSERT_COLUMNS)})
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_COLUMNS = (
    "id",
    "provider_model_id",
    "observed_at",
    "rate_limit",
    "daily_quota",
    "observed_value",
    "note",
    "data_origin",
    "created_at",
)


def _validate_observed_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("observed_at must be a non-empty ISO-8601 string")
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("observed_at must be an ISO-8601 timestamp") from error
    return value


def record_quota_observation(
    conn: sqlite3.Connection,
    *,
    provider_model_id: int,
    observed_at: str,
    rate_limit: str | None = None,
    daily_quota: int | None = None,
    observed_value: str | None = None,
    note: str | None = None,
    data_origin: str = "REAL",
) -> int:
    """Thêm một quan sát quota theo thời gian; trả về id dòng mới.

    Transactional: khi không có transaction ngoài đang mở, khối `with conn:`
    commit khi thành công và rollback khi lỗi — một lệnh ghi lỗi không để lại
    dòng rác hay database đứt giữa chừng. Nếu caller đã mở transaction riêng
    (`conn.in_transaction`), lệnh ghi chỉ NỐI VÀO transaction đó và để caller
    quyết định commit/rollback toàn bộ. Chỉ INSERT, không bao giờ UPDATE quá khứ.
    """
    if not isinstance(provider_model_id, int) or isinstance(provider_model_id, bool) or provider_model_id <= 0:
        raise ValueError("provider_model_id must be a positive int")
    if daily_quota is not None:
        if not isinstance(daily_quota, int) or isinstance(daily_quota, bool):
            raise ValueError("daily_quota must be an int or None")
        if daily_quota < 0:
            raise ValueError("daily_quota must be a non-negative int")
    if rate_limit is not None and (not isinstance(rate_limit, str) or not rate_limit.strip()):
        raise ValueError("rate_limit must be a non-empty string or None")
    if observed_value is not None and not isinstance(observed_value, str):
        raise ValueError("observed_value must be a string or None")
    if note is not None and not isinstance(note, str):
        raise ValueError("note must be a string or None")
    if data_origin not in ("REAL", "SAMPLE"):
        raise ValueError("data_origin must be 'REAL' or 'SAMPLE'")

    timestamp = _validate_observed_at(observed_at)

    # Không bịa giá trị: một quan sát không mang giá trị nào thì không được ghi.
    has_value = any(
        value is not None for value in (rate_limit, daily_quota, observed_value)
    )
    if not has_value and not note:
        raise ValueError("refusing to record an observation with no value fields")

    if conn.in_transaction:
        # Caller đang ôm transaction ngoài — chỉ thêm dòng, không tự commit.
        cursor = conn.execute(
            _INSERT_SQL,
            (provider_model_id, timestamp, rate_limit, daily_quota, observed_value, note, data_origin),
        )
    else:
        with conn:
            cursor = conn.execute(
                _INSERT_SQL,
                (provider_model_id, timestamp, rate_limit, daily_quota, observed_value, note, data_origin),
            )
    lastrowid = cursor.lastrowid
    if lastrowid is None:
        raise ValueError("database did not return a row id for the inserted observation")
    return int(lastrowid)


def quota_history(
    conn: sqlite3.Connection,
    *,
    provider_model_id: int | None = None,
    limit: int | None = None,
) -> Sequence[sqlite3.Row]:
    """Lịch sử quan sát của một provider_model, sắp theo thời gian (append-only).

    Chỉ SELECT chỉ-mục thật, không bao giờ làm thay đổi dữ liệu; mọi điều kiện
    đều parameterized nên snapshot text không thể thành SQL.
    """
    if provider_model_id is not None and (
        not isinstance(provider_model_id, int)
        or isinstance(provider_model_id, bool)
        or provider_model_id <= 0
    ):
        raise ValueError("provider_model_id must be a positive int or None")
    if limit is not None and (
        not isinstance(limit, int) or isinstance(limit, bool) or limit < 0
    ):
        raise ValueError("limit must be a non-negative int or None")

    sql = f"SELECT {', '.join(_SELECT_COLUMNS)} FROM quota_observations"
    parameters: list[Any] = []
    if provider_model_id is not None:
        sql += " WHERE provider_model_id = ?"
        parameters.append(provider_model_id)
    sql += " ORDER BY observed_at, id"
    if limit is not None:
        sql += " LIMIT ?"
        parameters.append(limit)
    return conn.execute(sql, parameters).fetchall()
