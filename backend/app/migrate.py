"""Migration schema — Vũ Học AI Radar v1.0 (Phase 4).

Hợp đồng (PLAN.md phase 4): chạy từ thư mục gốc repo bằng đúng lệnh::

    uv run python -m backend.app.migrate

Thiết kế (theo docs/MISSION.md mục 5):
- 12 bảng nghiệp vụ: sources, raw_items, articles, providers, models,
  provider_models, offers, quota_observations, verification_records,
  change_events, collection_runs, editorial_reviews.
- Bổ sung (sri-001b): bảng ledger scheduled_inbox_runs cho các lần chạy
  inbox theo lịch — không thuộc 12 bảng MISSION nên KHÔNG thêm vào
  BUSINESS_TABLES.
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

#: Trạng thái một lần chạy inbox theo lịch (sri-001b): IMPORTED (đã nạp)
#: hoặc QUARANTINED (bị cách ly chờ xử lý).
INBOX_RUN_STATUS = ("IMPORTED", "QUARANTINED")

#: Trạng thái của một mốc lịch Daily Radar (s1-process-safe-scheduler):
#: RUNNING (đang có lease) / COMPLETED (thành công) / FAILED (thất bại tạm) /
#: EXHAUSTED (quá số lần retry tối đa).
RADAR_SCHEDULE_STATUS = ("RUNNING", "COMPLETED", "FAILED", "EXHAUSTED")

#: Mức độ khó hợp lệ của một repository trong catalogue (task r2) — UNKNOWN
#: cho phép giữ "chưa biết" thay vì suy đoán.
REPOSITORY_DIFFICULTY = ("BEGINNER", "INTERMEDIATE", "ADVANCED", "UNKNOWN")


def _check(values: tuple[str, ...]) -> str:
    """Chuỗi IN(...) cho CHECK; NULL luôn đi qua CHECK trong SQLite."""
    return "IN ({})".format(", ".join(f"'{v}'" for v in values))

#: Định nghĩa 12 bảng nghiệp vụ — tất cả CREATE ... IF NOT EXISTS.
#: Nếu bảng articles đã có từ Phase 3 thì giữ nguyên dữ liệu và nâng cấp
#: các cột còn thiếu qua ARTICLES_UPGRADE_COLUMNS trước khi tạo index.
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
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT,
        source TEXT,
        category TEXT,
        summary TEXT,
        published_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        article_status TEXT CHECK (article_status IS NULL OR article_status %s),
        normalized_title TEXT,
        content_hash TEXT
    )
    """ % _check(ARTICLE_STATUS),
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
    # sri-001b: ledger các lần chạy inbox theo lịch — một dòng mỗi run,
    # bảo vệ status và data_origin bằng CHECK, bộ đếm không âm.
    """
    CREATE TABLE IF NOT EXISTS scheduled_inbox_runs (
        run_id TEXT PRIMARY KEY,
        report_kind TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status %s),
        finding_count INTEGER NOT NULL DEFAULT 0 CHECK (finding_count >= 0),
        accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
        skipped_count INTEGER NOT NULL DEFAULT 0 CHECK (skipped_count >= 0),
        error_message TEXT,
        processed_at TEXT NOT NULL,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE'))
    )
    """ % _check(INBOX_RUN_STATUS),
    # task r2: catalogue explorer các repository GitHub — bảng bổ sung
    # KHÔNG thuộc 12 bảng MISSION (như scheduled_inbox_runs). Không seed
    # row công khai nào: row SAMPLE tuyệt đối không được trình bày public.
    """
    CREATE TABLE IF NOT EXISTS repositories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_url TEXT NOT NULL,
        name TEXT NOT NULL,
        purpose TEXT,
        use_case TEXT,
        tradeoffs TEXT,
        license TEXT,
        updated_at TEXT,
        difficulty TEXT CHECK (difficulty IS NULL OR difficulty %s),
        provenance TEXT,
        verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
            CHECK (verification_status IS NULL OR verification_status %s),
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """ % (_check(REPOSITORY_DIFFICULTY), _check(VERIFICATION_STATUS)),
    # s1-process-safe-scheduler: ledger các lần chạy Daily Radar theo lịch —
    # một dòng mỗi run identity ('YYYY-MM-DD' 07:00 Asia/Ho_Chi_Minh).
    # Chống race condition giữa nhiều connection/process, lease hữu hạn, bounded retry.
    """
    CREATE TABLE IF NOT EXISTS radar_schedule_runs (
        run_identity TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status %s),
        owner TEXT,
        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        claimed_at TEXT,
        lease_expires_at TEXT,
        completed_at TEXT,
        last_error TEXT,
        summary TEXT,
        data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE'))
    )
    """ % _check(RADAR_SCHEDULE_STATUS),
)

#: Index cho các truy vấn thường gặp (luôn CREATE INDEX IF NOT EXISTS).
INDEXES_DDL: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_raw_items_source ON raw_items(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_canonical_url ON raw_items(canonical_url)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_content_hash ON raw_items(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_fetched_at ON raw_items(fetched_at)",
    "CREATE INDEX IF NOT EXISTS idx_raw_items_dedup_identity ON raw_items(canonical_url, normalized_title, content_hash)",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_items_source_observation
       ON raw_items(source_id, canonical_url, normalized_title, content_hash)
       WHERE canonical_url IS NOT NULL
         AND normalized_title IS NOT NULL
         AND content_hash IS NOT NULL
         AND (data_origin IS NULL OR data_origin != 'SAMPLE')""",
    "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)",
    "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_articles_dedup_identity
       ON articles(url, normalized_title, content_hash)
       WHERE url IS NOT NULL
         AND normalized_title IS NOT NULL
         AND content_hash IS NOT NULL
         AND (data_origin IS NULL OR data_origin != 'SAMPLE')""",
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
    # sri-001b: query theo lịch theo dõi (thời điểm xử lý) và lọc theo trạng thái run.
    "CREATE INDEX IF NOT EXISTS idx_scheduled_inbox_runs_processed_at ON scheduled_inbox_runs(processed_at)",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_inbox_runs_status ON scheduled_inbox_runs(status)",
    # task r2: truy vấn public lọc theo trạng thái xác minh; canonical_url
    # duy nhất trong dữ liệu REAL (row SAMPLE không tham gia ràng buộc).
    "CREATE INDEX IF NOT EXISTS idx_repositories_verification ON repositories(verification_status)",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_repositories_canonical_url
       ON repositories(canonical_url)
       WHERE canonical_url IS NOT NULL
         AND (data_origin IS NULL OR data_origin != 'SAMPLE')""",
    # s1-process-safe-scheduler: index trên status để truy vấn nhanh trạng thái run
    "CREATE INDEX IF NOT EXISTS idx_radar_schedule_runs_status ON radar_schedule_runs(status)",
)

#: Cột nâng cấp cho bảng articles (đã tồn tại từ Phase 3, không có các cột này).
#: Dạng (tên_cột, định_nghĩa) — chỉ ALTER sau khi PRAGMA table_info cho thấy thiếu.
ARTICLES_UPGRADE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("data_origin",
     "data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE'))"),
    ("article_status",
     "article_status TEXT CHECK (article_status IS NULL OR article_status %s)" % _check(ARTICLE_STATUS)),
    ("normalized_title", "normalized_title TEXT"),
    ("content_hash", "content_hash TEXT"),
)

#: Cột nâng cấp cho bảng offers — Promotion Radar cần official CTA riêng của
#: từng offer (CTA không suy ra từ provider/model, offer thiếu CTA tuyệt đối
#: không được coi là active). Chỉ ALTER thêm, không động dữ liệu có sẵn.
OFFERS_UPGRADE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("official_url", "official_url TEXT"),
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
            # Nâng cấp an toàn bảng articles của Phase 3/4/5 trước khi tạo index.
            if _table_exists(conn, "articles"):
                cols = _existing_columns(conn, "articles")
                for col_name, col_def in ARTICLES_UPGRADE_COLUMNS:
                    if col_name not in cols:
                        conn.execute(f"ALTER TABLE articles ADD COLUMN {col_def}")
            # Nâng cấp an toàn bảng offers (thêm official CTA cho Promotion Radar).
            if _table_exists(conn, "offers"):
                cols = _existing_columns(conn, "offers")
                for col_name, col_def in OFFERS_UPGRADE_COLUMNS:
                    if col_name not in cols:
                        conn.execute(f"ALTER TABLE offers ADD COLUMN {col_def}")
            for idx in INDEXES_DDL:
                conn.execute(idx)
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



