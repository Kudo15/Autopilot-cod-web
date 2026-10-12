"""Migration schema — Vũ Học AI Radar v1.0 (Phase 4).

Hợp đồng (PLAN.md phase 4): chạy từ thư mục gốc repo bằng đúng lệnh::

    uv run python -m backend.app.migrate

Thiết kế (theo docs/MISSION.md mục 5):
- 12 bảng nghiệp vụ: sources, raw_items, articles, providers, models,
  provider_models, offers, quota_observations, verification_records,
  change_events, collection_runs, editorial_reviews.
- Một model có thể do nhiều provider cung cấp với quota/giá khác nhau
  (quan hệ models <-> provider_models <-> providers).
- Trạng thái dùng đúng tập giá trị MISSION, bảo vệ bằng CHECK:
    free status:     FREE_API / FREE_CREDIT / FREE_TRIAL / FREE_WEB_ONLY / PROMO / PAID / UNKNOWN
    verification:    VERIFIED / UNVERIFIED / STALE / EXPIRED / NEEDS_REVIEW
    recommendation:  SAFE_TO_TRY / CAUTION / INFO_ONLY
- Chưa xác minh = NULL (0/1/NULL cho kiểu boolean SQLite), không suy đoán.
- Cột data_origin ('REAL' | 'SAMPLE') tách dữ liệu mẫu khỏi dữ liệu thật.

Nguyên tắc idempotent:
- Chỉ dùng CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
- Cột nâng cấp cho bảng đã tồn tại được kiểm tra bằng PRAGMA table_info
  trước khi ALTER TABLE (SQLite không có ADD COLUMN IF NOT EXISTS).
- KHÔNG DROP TABLE, không xóa .db, không chạm dữ liệu có sẵn;
  toàn bộ DDL nằm trong một transaction để tránh DB nâng cấp dở dang.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from .database import DATA_DIR, DB_PATH

#: 12 bảng nghiệp vụ bắt buộc (tên chính xác theo MISSION mục 5).
BUSINESS_TABLES = (
    "sources",
    "raw_items",
    "articles",
    "providers",
    "models",
    "provider_models",
    "offers",
    "quota_observations",
    "verification_records",
    "change_events",
    "collection_runs",
    "editorial_reviews",
)

# Tập giá trị trạng thái theo MISSION — dùng chung trong CHECK constraint.
FREE_STATUS = ("FREE_API", "FREE_CREDIT", "FREE_TRIAL", "FREE_WEB_ONLY", "PROMO", "PAID", "UNKNOWN")
VERIFICATION_STATUS = ("VERIFIED", "UNVERIFIED", "STALE", "EXPIRED", "NEEDS_REVIEW")
RECOMMENDATION = ("SAFE_TO_TRY", "CAUTION", "INFO_ONLY")
ARTICLE_STATUS = ("DRAFT", "PENDING_REVIEW", "PUBLISHED")


def _check(values: tuple[str, ...]) -> str:
    """Chuỗi IN(...) cho CHECK; NULL luôn đi qua CHECK trong SQLite."""
    return "IN ({})".format(", ".join(f"'{v}'" for v in values))

#: Định nghĩa bảng mới — tất cả CREATE ... IF NOT EXISTS.
#: articles đã có từ Phase 3 nên KHÔNG nằm ở đây; migrate sẽ thêm
#: cột còn thiếu (data_origin, article_status) an toàn sau khi check PRAGMA.
TABLES_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS sources (
        source_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        url TEXT,
        collection_method TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 5,
        status TEXT NOT NULL DEFAULT 'active',
        last_checked_at TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL REFERENCES sources(source_id),
        canonical_url TEXT,
        normalized_title TEXT,
        content_hash TEXT,
        raw_content TEXT,
        content_type TEXT,
        fetched_at TEXT,
        provenance TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS providers (
        provider_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        website TEXT,
        api_base_url TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS models (
        model_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        organization TEXT,
        context_window INTEGER,
        supports_vision INTEGER CHECK (supports_vision IS NULL OR supports_vision IN (0, 1)),
        supports_tools INTEGER CHECK (supports_tools IS NULL OR supports_tools IN (0, 1)),
        supports_json INTEGER CHECK (supports_json IS NULL OR supports_json IN (0, 1)),
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL REFERENCES providers(provider_id),
        model_id TEXT NOT NULL REFERENCES models(model_id),
        api_model_id TEXT,
        official_url TEXT,
        free_status TEXT CHECK (free_status IS NULL OR free_status %s),
        rate_limit TEXT,
        daily_quota INTEGER,
        account_required INTEGER CHECK (account_required IS NULL OR account_required IN (0, 1)),
        card_required INTEGER CHECK (card_required IS NULL OR card_required IN (0, 1)),
        context_window INTEGER,
        supports_vision INTEGER CHECK (supports_vision IS NULL OR supports_vision IN (0, 1)),
        supports_tools INTEGER CHECK (supports_tools IS NULL OR supports_tools IN (0, 1)),
        supports_json INTEGER CHECK (supports_json IS NULL OR supports_json IN (0, 1)),
        verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
            CHECK (verification_status IS NULL OR verification_status %s),
        last_verified TEXT,
        valid_until TEXT,
        recommendation_level TEXT CHECK (recommendation_level IS NULL OR recommendation_level %s),
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % (_check(FREE_STATUS), _check(VERIFICATION_STATUS), _check(RECOMMENDATION)),
    """
    CREATE TABLE IF NOT EXISTS offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT REFERENCES providers(provider_id),
        provider_model_id INTEGER REFERENCES provider_models(id),
        title TEXT NOT NULL,
        offer_type TEXT NOT NULL CHECK (offer_type IS NULL OR offer_type %s),
        code TEXT,
        description TEXT,
        terms TEXT,
        starts_at TEXT,
        ends_at TEXT,
        account_required INTEGER CHECK (account_required IS NULL OR account_required IN (0, 1)),
        card_required INTEGER CHECK (card_required IS NULL OR card_required IN (0, 1)),
        verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
            CHECK (verification_status IS NULL OR verification_status %s),
        last_verified TEXT,
        valid_until TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % (_check(FREE_STATUS), _check(VERIFICATION_STATUS)),
    """
    CREATE TABLE IF NOT EXISTS quota_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_model_id INTEGER NOT NULL REFERENCES provider_models(id),
        observed_at TEXT NOT NULL,
        rate_limit TEXT,
        daily_quota INTEGER,
        observed_value TEXT,
        note TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verification_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_model_id INTEGER NOT NULL REFERENCES provider_models(id),
        offer_id INTEGER REFERENCES offers(id),
        verification_status TEXT NOT NULL CHECK (verification_status %s),
        method TEXT,
        evidence TEXT,
        note TEXT,
        verified_at TEXT NOT NULL,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % _check(VERIFICATION_STATUS),
    """
    CREATE TABLE IF NOT EXISTS change_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL CHECK (event_type IN (
            'NEW_PROVIDER', 'NEW_MODEL', 'MODEL_REMOVED', 'FREE_TO_PAID',
            'PAID_TO_FREE', 'QUOTA_CHANGED', 'OFFER_STARTED', 'OFFER_EXPIRED',
            'TERMS_CHANGED'
        )),
        provider_model_id INTEGER REFERENCES provider_models(id),
        offer_id INTEGER REFERENCES offers(id),
        before_snapshot TEXT,
        after_snapshot TEXT,
        detected_at TEXT NOT NULL,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT REFERENCES sources(source_id),
        run_type TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        status TEXT NOT NULL,
        items_collected INTEGER,
        error_message TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS editorial_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL REFERENCES articles(id),
        review_status TEXT NOT NULL CHECK (review_status IN ('DRAFT', 'PENDING_REVIEW', 'REJECTED', 'PUBLISHED')),
        reviewer_note TEXT,
        ranking_suggestion TEXT,
        content_safety TEXT CHECK (content_safety IS NULL OR content_safety %s),
        reviewed_at TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % _check(RECOMMENDATION),
)

#: Index cho các truy vấn thường gặp (luôn CREATE INDEX IF NOT EXISTS).
INDEXES_DDL: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_raw_items_source ON raw_items(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_canonical_url ON raw_items(canonical_url)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_content_hash ON raw_items(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_fetched_at ON raw_items(fetched_at)",
    "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)",
    "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
    "CREATE INDEX IF NOT EXISTS idx_provider_models_provider ON provider_models(provider_id)",
    "CREATE INDEX IF NOT EXISTS idx_provider_models_model ON provider_models(model_id)",
    "CREATE INDEX IF NOT EXISTS idx_provider_models_free_status ON provider_models(free_status)",
    "CREATE INDEX IF NOT EXISTS idx_provider_models_verification ON provider_models(verification_status)",
    "CREATE INDEX IF NOT EXISTS idx_offers_provider ON offers(provider_id)",
    "CREATE INDEX IF NOT EXISTS idx_offers_pm ON offers(provider_model_id)",
    "CREATE INDEX IF NOT EXISTS idx_offers_valid_until ON offers(valid_until)",
    "CREATE INDEX IF NOT EXISTS idx_quota_obs_pm ON quota_observations(provider_model_id)",
    "CREATE INDEX IF NOT EXISTS idx_quota_obs_time ON quota_observations(observed_at)",
    "CREATE INDEX IF NOT EXISTS idx_verification_pm ON verification_records(provider_model_id)",
    "CREATE INDEX IF NOT EXISTS idx_change_events_type ON change_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_change_events_detected_at ON change_events(detected_at)",
    "CREATE INDEX IF NOT EXISTS idx_collection_runs_source ON collection_runs(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_editorial_reviews_article ON editorial_reviews(article_id)",
)

#: Cột nâng cấp cho bảng articles (đã tồn tại từ Phase 3, không có các cột này).
#: Dạng (tên_cột, định_nghĩa) — chỉ ALTER sau khi PRAGMA table_info cho thấy thiếu.
ARTICLES_UPGRADE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("data_origin",
     "data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE'))"),
    ("article_status",
     "article_status TEXT CHECK (article_status IS NULL OR article_status %s)" % _check(ARTICLE_STATUS)),
)


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def apply_migration() -> Path:
    """Chạy migration đầy đủ, idempotent, trong một transaction.

    Trả về đường dẫn file SQLite. Lỗi -> rollback + ném exception.
    Không bao giờ DROP TABLE hay xóa dữ liệu có sẵn.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA foreign_keys = ON")
        # Transaction thủ công: toàn bộ DDL commit cùng một lúc,
        # tránh database bị nâng cấp dở dang giữa chừng.
        conn.execute("BEGIN IMMEDIATE")
        try:
            for ddl in TABLES_DDL:
                conn.execute(ddl)
            for idx in INDEXES_DDL:
                conn.execute(idx)
            # Nâng cấp an toàn bảng articles của Phase 3 (nếu đã tồn tại).
            if _table_exists(conn, "articles"):
                cols = _existing_columns(conn, "articles")
                for col_name, col_def in ARTICLES_UPGRADE_COLUMNS:
                    if col_name not in cols:
                        conn.execute(f"ALTER TABLE articles ADD COLUMN {col_def}")
            conn.execute("PRAGMA foreign_key_check")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()
    return DB_PATH


def main() -> int:
    try:
        db = apply_migration()
    except Exception as exc:
        print(f"[MIGRATE] THẤT BẠI: {type(exc).__name__}: {exc}")
        return 1
    print(f"[MIGRATE] OK: schema 12 bảng nghiệp vụ đã sẵn sàng tại {db}")
    print(f"[MIGRATE] Bảng: {', '.join(BUSINESS_TABLES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())



