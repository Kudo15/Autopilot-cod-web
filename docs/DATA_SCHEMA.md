# DATA_SCHEMA — SQLite schema của Vũ Học AI Radar v1.0

Nguồn duy nhất của schema là `backend/app/migrate.py` (DDL) + `backend/app/database.py` (đường dẫn).
Tài liệu này mô tả **đúng những gì migration tạo ra**, đo được bằng cách chạy
`uv run python -m backend.app.migrate` rồi mở SQLite thật.

- DB: `backend/data/radar.db` (đường dẫn tính từ module, không phụ thuộc cwd).
- `PRAGMA foreign_keys = ON`; `PRAGMA busy_timeout = 30000`.
- Migration **idempotent**: chỉ `CREATE TABLE/INDEX IF NOT EXISTS`, cột nâng cấp qua `PRAGMA
  table_info`, toàn bộ DDL trong một transaction, **không bao giờ** `DROP TABLE`/xóa dữ liệu.

## 0. Quy ước chung

- **`data_origin`** (`'REAL' | 'SAMPLE'`, mặc định `'REAL'`): tách dữ liệu mẫu khỏi dữ liệu thật.
  Mọi API công khai **loại SAMPLE**; chỉ admin API thấy bản ghi SAMPLE.
- **Ba tập trạng thái** (bảo vệ bằng `CHECK`):
  - Free status: `FREE_API · FREE_CREDIT · FREE_TRIAL · FREE_WEB_ONLY · PROMO · PAID · UNKNOWN`
  - Verification: `VERIFIED · UNVERIFIED · STALE · EXPIRED · NEEDS_REVIEW`
  - Recommendation (`recommendation_level` / `content_safety`): `SAFE_TO_TRY · CAUTION · INFO_ONLY`
  - Article status (`articles.article_status`): `DRAFT · PENDING_REVIEW · PUBLISHED`
- **Boolean** là `INTEGER` với `CHECK (x IS NULL OR x IN (0,1))` — `NULL` = chưa biết, **không** suy
  diễn thành false/true.
- **Chưa xác minh = `NULL`**: không bịa quota, giá, mốc thời gian hay độ tươi.

## 1. Mười hai bảng nghiệp vụ

### `sources` — registry nguồn
| Cột | Kiểu / ràng buộc |
|---|---|
| `source_id` | TEXT PRIMARY KEY |
| `name` | TEXT NOT NULL |
| `type` | TEXT NOT NULL |
| `url` | TEXT |
| `collection_method` | TEXT NOT NULL |
| `priority` | INTEGER NOT NULL DEFAULT 5 |
| `status` | TEXT NOT NULL DEFAULT `'active'` |
| `last_checked_at` | TEXT |
| `data_origin` | TEXT NOT NULL DEFAULT `'REAL'` CHECK IN (REAL,SAMPLE) |
| `created_at` | TEXT DEFAULT CURRENT_TIMESTAMP |

### `raw_items` — quan sát thô có provenance
`id` PK · `source_id` → `sources(source_id)` · `canonical_url` · `normalized_title` · `content_hash` ·
`raw_content` · `content_type` · `fetched_at` · `provenance` · `data_origin` · `created_at`.

### `articles` — bài biên tập
`id` PK · `title` NOT NULL · `url` · `source` · `category` · `summary` · `published_at` · `created_at` ·
`data_origin` · `article_status` CHECK · `normalized_title` · `content_hash`.
(Cột `data_origin/article_status/normalized_title/content_hash` được thêm khi nâng cấp bảng Phase 3.)

### `providers`
`provider_id` PK · `name` NOT NULL · `website` · `api_base_url` · `data_origin` · `created_at`.

### `models`
`model_id` PK · `model_name` NOT NULL · `organization` · `context_window` ·
`supports_vision/supports_tools/supports_json` (INTEGER 0/1/NULL) · `data_origin` · `created_at`.

### `provider_models` — một model nhiều provider, quota/giá riêng
`id` PK · `provider_id` → providers · `model_id` → models · `api_model_id` · `official_url` ·
`free_status` CHECK · `rate_limit` · `daily_quota` · `account_required` (0/1) · `card_required` (0/1) ·
`context_window` · `supports_vision/tools/json` · `verification_status` NOT NULL DEFAULT `'UNVERIFIED'`
CHECK · `last_verified` · `valid_until` · `recommendation_level` CHECK · `data_origin` · `created_at`.

### `offers` — promo/free credit/trial
`id` PK · `provider_id` → providers · `provider_model_id` → provider_models · `title` NOT NULL ·
`offer_type` CHECK (dùng tập free status) · `code` · `description` · `terms` · `starts_at` · `ends_at` ·
`account_required` · `card_required` · `verification_status` CHECK · `last_verified` · `valid_until` ·
`data_origin` · `created_at`.

### `quota_observations` — quan sát quota theo thời gian (append-only)
`id` PK · `provider_model_id` NOT NULL → provider_models · `observed_at` NOT NULL · `rate_limit` ·
`daily_quota` · `observed_value` · `note` · `data_origin` · `created_at`.

### `verification_records` — sổ xác minh
`id` PK · `provider_model_id` NOT NULL → provider_models · `offer_id` → offers · `verification_status`
NOT NULL CHECK · `method` · `evidence` · `note` · `verified_at` NOT NULL · `data_origin` · `created_at`.

### `change_events` — phát hiện thay đổi
`id` PK · `event_type` NOT NULL CHECK IN (`NEW_PROVIDER, NEW_MODEL, MODEL_REMOVED, FREE_TO_PAID,
PAID_TO_FREE, QUOTA_CHANGED, OFFER_STARTED, OFFER_EXPIRED, TERMS_CHANGED`) · `provider_model_id` ·
`offer_id` · `before_snapshot` · `after_snapshot` · `detected_at` NOT NULL · `data_origin` · `created_at`.

### `collection_runs` — sổ thu thập
`id` PK · `source_id` → sources · `run_type` NOT NULL · `started_at` · `finished_at` · `status` NOT NULL
(`RUNNING/SUCCESS/FAILED/SKIPPED`) · `items_collected` · `error_message` · `data_origin` · `created_at`.

### `editorial_reviews` — workflow duyệt/xác minh
`id` PK · `article_id` NOT NULL → articles · `review_status` NOT NULL CHECK IN
(`DRAFT, PENDING_REVIEW, REJECTED, PUBLISHED`) · `reviewer_note` · `ranking_suggestion` ·
`content_safety` CHECK (SAFE_TO_TRY/CAUTION/INFO_ONLY) · `reviewed_at` · `data_origin` · `created_at`.

## 2. Cột bắt buộc theo MISSION (đã đo là có mặt)

`last_verified`, `valid_until`, `account_required`, `card_required`, `context_window`,
`supports_vision`, `supports_tools`, `supports_json` — mỗi cột xuất hiện ở nơi hợp lý
(`provider_models`/`models`). Cổng `checks/p4.py` xác nhận đủ 12 bảng và đủ các cột này.

## 3. Dedup & index

- Unique chống trùng (partial, bỏ SAMPLE):
  - `uq_raw_items_source_observation` ON `raw_items(source_id, canonical_url, normalized_title, content_hash)`
  - `uq_articles_dedup_identity` ON `articles(url, normalized_title, content_hash)`
- Index phụ trợ cho truy vấn thường gặp: `raw_items(source_id / canonical_url / content_hash /
  fetched_at)`, `articles(category / published_at)`, `provider_models(provider_id / model_id /
  free_status / verification_status)`, `offers(provider_id / provider_model_id / valid_until)`,
  `quota_observations(provider_model_id / observed_at)`, `verification_records(provider_model_id)`,
  `change_events(event_type / detected_at)`, `collection_runs(source_id)`,
  `editorial_reviews(article_id)`.

## 4. Ví dụ đọc schema thật

```bash
uv run python -m backend.app.migrate     # exit 0, tạo/cập nhật schema
uv run python scripts/check_db.py        # chỉ đọc: in DB path, size, bảng, cột, số dòng
```

## 5. Bản ghi SAMPLE (fixture) — không phải dữ liệu thật

Seed nạp fixture với id ổn định vùng `900001..` và mọi ô text có nhãn `SAMPLE`. Các trường quota/
credit/giá để `NULL` (không bịa). Trạng thái `STALE/EXPIRED/NEEDS_REVIEW` trong seed chỉ là **ví dụ
cấu trúc** để minh hoạ cột, ghi rõ trong `note`. Ngoài khối SAMPLE, seed nạp **đúng 1 bài
REAL/PUBLISHED** kế thừa v0.3.1 (xem `docs/DATA_SOURCES.md`).
