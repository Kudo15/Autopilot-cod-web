"""Seed dữ liệu mẫu (SAMPLE) — Vũ Học AI Radar v1.0 (Phase 4).

Hợp đồng (PLAN.md phase 4): chạy từ thư mục gốc repo bằng đúng lệnh::

    uv run python -m backend.app.seed

Nguyên tắc (theo MISSION mục 5 + constraint phase 4):
- Mọi bản ghi mẫu đều có data_origin = 'SAMPLE' (tách khỏi dữ liệu thật)
  và định danh/định danh ổn định có prefix SAMPLE_.
- KHÔNG bịa quota, credit, hạn mức, giá hay thông số kỹ thuật của model:
  các trường chưa xác minh để NULL.
- Không gắn nhãn VERIFIED cho dữ liệu mẫu — mặc định UNVERIFIED; các
  trạng thái STALE/EXPIRED/NEEDS_REVIEW chỉ dùng làm ví dụ cấu trúc
  gắn trên chính bản ghi SAMPLE (được ghi rõ trong note).
- Chạy lại seed KHÔNG nhân bản bản ghi: mỗi bảng chỉ seed khi chưa có
  bản ghi data_origin = 'SAMPLE' nào, và mọi INSERT dùng
  ON CONFLICT DO NOTHING với id ổn định.
- Seed KHÔNG xóa/ghi đè dữ liệu thật, KHÔNG reset database.
"""
from __future__ import annotations

import sqlite3
import sys

from .database import get_connection
from .migrate import apply_migration

#: id ổn định cho các bảng AUTOINCREMENT — tách hẳn vùng id của dữ liệu thật.
_SAMPLE_ID = 900001

#: Thời điểm cố định cho dữ liệu mẫu (không phải "bây giờ" thật).
_T = "2026-01-01T00:00:00+07:00"

#: Ghi chú chuẩn gắn cho mọi bản ghi mẫu để người đọc không nhầm.
_NOTE = ("Dữ liệu mẫu SAMPLE — ví dụ cấu trúc, không phải thông tin nhà "
         "cung cấp thật. Trường chưa xác minh để NULL, không suy đoán.")


def _has_sample(conn: sqlite3.Connection, table: str) -> bool:
    try:
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE data_origin = 'SAMPLE' LIMIT 1"
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError:
        # Bảng chưa có cột data_origin (chưa migration) -> coi là chưa seed.
        return False


# Mỗi entry: (table, [(column_list, params_list)]) — chỉ chạy nếu bảng
# chưa có bản ghi SAMPLE nào.
def _inserts():
    yield "sources", """
        INSERT INTO sources (
            source_id, name, type, url, collection_method, priority, status,
            last_checked_at, data_origin, created_at
        ) VALUES
            ('SAMPLE_src_rss', 'SAMPLE RSS Feed (ví dụ cấu trúc)', 'rss',
             NULL, 'rss', 5, 'active', NULL, 'SAMPLE', :ts),
            ('SAMPLE_src_manual', 'SAMPLE Manual Import (ví dụ cấu trúc)', 'manual',
             NULL, 'manual_import', 9, 'active', NULL, 'SAMPLE', :ts)
        ON CONFLICT(source_id) DO NOTHING
    """, {"ts": _T}

    yield "raw_items", """
        INSERT INTO raw_items (
            id, source_id, canonical_url, normalized_title, content_hash,
            raw_content, content_type, fetched_at, provenance, data_origin, created_at
        ) VALUES
            (:id, 'SAMPLE_src_rss', NULL, 'SAMPLE item — ví dụ cấu trúc raw item',
             'sample_content_hash_0001',
             'Dữ liệu mẫu SAMPLE: minh hoạ một raw item thu được từ nguồn.',
             'text/markdown', NULL, 'SAMPLE_seed: fixture nội bộ (không phải nguồn thật)',
             'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"id": _SAMPLE_ID, "ts": _T}

    yield "articles", """
        INSERT INTO articles (
            id, title, url, source, category, summary, published_at,
            data_origin, article_status, created_at
        ) VALUES
            (:id, 'SAMPLE Bài viết mẫu — ví dụ cấu trúc', NULL, 'SAMPLE_src_rss',
             'tip-trick',
             'Dữ liệu mẫu SAMPLE (không phải bài thật): minh hoạ đường pipeline raw_item -> article. article_status giữ DRAFT, không tự động publish.',
             NULL, 'SAMPLE', 'DRAFT', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"id": _SAMPLE_ID, "ts": _T}

    yield "providers", """
        INSERT INTO providers (provider_id, name, website, api_base_url,
                               data_origin, created_at)
        VALUES ('SAMPLE_provider', 'SAMPLE Provider (ví dụ cấu trúc)', NULL, NULL,
                'SAMPLE', :ts)
        ON CONFLICT(provider_id) DO NOTHING
    """, {"ts": _T}

    yield "models", """
        INSERT INTO models (model_id, model_name, organization, context_window,
                            supports_vision, supports_tools, supports_json,
                            data_origin, created_at)
        VALUES ('SAMPLE_model', 'SAMPLE Model (ví dụ cấu trúc)', NULL,
                NULL, NULL, NULL, NULL, 'SAMPLE', :ts)
        ON CONFLICT(model_id) DO NOTHING
    """, {"ts": _T}

    yield "provider_models", """
        INSERT INTO provider_models (
            id, provider_id, model_id, api_model_id, official_url, free_status,
            rate_limit, daily_quota, account_required, card_required,
            context_window, supports_vision, supports_tools, supports_json,
            verification_status, last_verified, valid_until, recommendation_level,
            data_origin, created_at
        ) VALUES
            (900001, 'SAMPLE_provider', 'SAMPLE_model', NULL, NULL, NULL,
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
             'UNVERIFIED', NULL, NULL, 'INFO_ONLY', 'SAMPLE', :ts),
            (900002, 'SAMPLE_provider', 'SAMPLE_model_2', NULL, NULL, 'FREE_TRIAL',
             NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
             'UNVERIFIED', NULL, NULL, 'INFO_ONLY', 'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

    yield "offers", """
        INSERT INTO offers (
            id, provider_id, provider_model_id, title, offer_type, code,
            description, terms, starts_at, ends_at, account_required,
            card_required, verification_status, last_verified, valid_until,
            data_origin, created_at
        ) VALUES
            (900001, 'SAMPLE_provider', 900002,
             'SAMPLE Offer: free trial (ví dụ cấu trúc)', 'FREE_TRIAL',
             'SAMPLE_CODE_DEMO',
             'Dữ liệu mẫu SAMPLE: minh hoạ cấu trúc offer, không phải khuyến mãi thật, không có credit/quota thật.', NULL, NULL, NULL,
             NULL, NULL, 'UNVERIFIED', NULL, NULL, 'SAMPLE', :ts),
            (900002, 'SAMPLE_provider', NULL,
             'SAMPLE Offer: đã hết hạn (ví dụ cấu trúc)', 'FREE_CREDIT',
             NULL,
             'Dữ liệu mẫu SAMPLE: minh hoạ offer đã EXPIRED, không phải khuyến mãi thật, không bịa số credit.', NULL, NULL, NULL,
             NULL, NULL, 'EXPIRED', NULL, NULL, 'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

    yield "quota_observations", """
        INSERT INTO quota_observations (
            id, provider_model_id, observed_at, rate_limit, daily_quota,
            observed_value, note, data_origin, created_at
        ) VALUES
            (900001, 900001, :ts, NULL, NULL, NULL,
             'Dữ liệu mẫu SAMPLE: quota chưa xác minh — để NULL, không bịa.',
             'SAMPLE', :ts),
            (900002, 900001, :ts2, NULL, NULL, NULL,
             'Dữ liệu mẫu SAMPLE: quan sát cũ hơn, minh hoạ cặp before/after cho change detection.',
             'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T, "ts2": "2025-12-31T00:00:00+07:00"}

    yield "verification_records", """
        INSERT INTO verification_records (
            id, provider_model_id, offer_id, verification_status, method,
            evidence, note, verified_at, data_origin, created_at
        ) VALUES
            (900001, 900001, NULL, 'UNVERIFIED', 'manual', NULL,
             'Dữ liệu mẫu SAMPLE: chưa xác minh — không gắn nhãn VERIFIED.',
             :ts, 'SAMPLE', :ts),
            (900002, 900002, 900001, 'EXPIRED', 'manual', NULL,
             'Dữ liệu mẫu SAMPLE: offer mẫu hết hạn theo cấu trúc (không phải bằng chứng thật).',
             :ts, 'SAMPLE', :ts),
            (900003, 900002, NULL, 'STALE', 'manual', NULL,
             'Dữ liệu mẫu SAMPLE: bản ghi mẫu quá hạn kiểm tra — minh hoạ trạng thái STALE.',
             :ts, 'SAMPLE', :ts),
            (900004, 900001, NULL, 'NEEDS_REVIEW', 'manual', NULL,
             'Dữ liệu mẫu SAMPLE: cần xem lại — minh hoạ NEEDS_REVIEW.',
             :ts, 'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

    yield "change_events", """
        INSERT INTO change_events (
            id, event_type, provider_model_id, offer_id, before_snapshot,
            after_snapshot, detected_at, data_origin, created_at
        ) VALUES
            (900001, 'QUOTA_CHANGED', 900001, NULL,
             '{"daily_quota": null}', '{"daily_quota": null}', :ts,
             'SAMPLE', :ts),
            (900002, 'OFFER_EXPIRED', NULL, 900002,
             '{"verification_status": "UNVERIFIED"}',
             '{"verification_status": "EXPIRED"}', :ts, 'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

    yield "collection_runs", """
        INSERT INTO collection_runs (
            id, source_id, run_type, started_at, finished_at, status,
            items_collected, error_message, data_origin, created_at
        ) VALUES
            (900001, 'SAMPLE_src_manual', 'manual_import', :ts, :ts, 'SUCCESS',
             1, NULL, 'SAMPLE', :ts),
            (900002, 'SAMPLE_src_rss', 'rss', :ts, :ts, 'FAILED',
             0, 'Dữ liệu mẫu SAMPLE: feed mẫu không tồn tại — minh hoạ trạng thái FAILED (không phải lỗi thật).',
             'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

    yield "editorial_reviews", """
        INSERT INTO editorial_reviews (
            id, article_id, review_status, reviewer_note,
             ranking_suggestion, content_safety, reviewed_at, data_origin,
             created_at
        ) VALUES
            (900001, 900001, 'PENDING_REVIEW',
             'Dữ liệu mẫu SAMPLE: bài mẫu chờ duyệt — không tự động publish.',
             NULL, 'INFO_ONLY', :ts, 'SAMPLE', :ts)
        ON CONFLICT(id) DO NOTHING
    """, {"ts": _T}

def _count_sample(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE data_origin = 'SAMPLE'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def run_seed() -> dict[str, int]:
    """Chạy seed SAMPLE idempotent. Trả về số bản ghi SAMPLE theo bảng.

    Mỗi bảng chỉ được seed khi chưa có bản ghi data_origin = 'SAMPLE'
    nào trong bảng đó (kèm ON CONFLICT DO NOTHING với id ổn định làm
    lớp bảo vệ thứ hai). Không chạm dữ liệu data_origin = 'REAL'.
    """
    apply_migration()  # an toàn nếu schema chưa tồn tại; không reset DB
    conn = get_connection()
    try:
        inserted = 0
        for table, sql, params in _inserts():
            if _has_sample(conn, table):
                continue
            cur = conn.execute(sql, params)
            inserted += max(cur.rowcount, 0)
        conn.commit()
        counts = {t: _count_sample(conn, t) for t, _, _ in _inserts()}
        counts["_inserted_this_run"] = inserted
        return counts
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    try:
        counts = run_seed()
    except Exception as exc:
        print(f"[SEED] THẤT BẠI: {type(exc).__name__}: {exc}")
        return 1
    inserted = counts.pop("_inserted_this_run")
    total = sum(counts.values())
    print(f"[SEED] OK: bản ghi SAMPLE mới lần chạy này: {inserted}; "
          f"tổng bản ghi SAMPLE trong DB: {total}")
    for table in sorted(counts):
        print(f"[SEED]   {table}: {counts[table]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# __SEED_CHUNK3_END__



