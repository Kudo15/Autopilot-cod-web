# ARCHITECTURE — Vũ Học AI Radar v1.0 (localhost)

Kiến trúc được mô tả từ **hành vi đã quan sát** trong repo tại commit `b2a0805` (nhánh
`wt/t_5fd6d5ec`): đường khởi động, module có thật, ranh giới dữ liệu. Không mô tả thứ chưa triển khai.

## 1. Tổng quan hai nửa

```
Trình duyệt (localhost)
   │  http://localhost:5173  (Vite dev server, 127.0.0.1)
   ▼
┌───────────────────────────── Vite (frontend) ─────────────────────────────┐
│ src/  React 19 + CSS thuần  ·  proxy /api → http://127.0.0.1:8000          │
│   App.jsx (điều hướng 7 nhóm)  ·  GroupView (feed bài)                      │
│   ExplorerView (GET /api/models)  ·  AdminView (GET/POST /api/admin/*)     │
│   hooks/useTheme.js  (dark/light, localStorage 'vu-hoc-ai-radar-theme')    │
└────────────────────────────────────────────────────────────────────────────┘
   │  /api/*  (vite.config.js proxy, changeOrigin, host 127.0.0.1)
   ▼
┌────────────────────────── FastAPI (backend) ──────────────────────────────┐
│ backend/app/main.py  — mọi route HTTP                                      │
│   public read-only: /api/health · /api/articles · /api/models · /api/radar │
│   admin (require_admin ở dòng đầu): /api/admin/* (import, sources, reviews,│
│       articles/{id}/review, provider-models/{id}/verification,             │
│       radar/refresh)                                                       │
│  ┌─────────────┬──────────────┬────────────────┬───────────────────────┐   │
│  │ auth.py     │ ingest/      │ collectors/    │ editorial/            │   │
│  │ (ADMIN_TOKEN│ normalize.py │ registry.py    │ rules.py (fallback)   │   │
│  │  runtime)   │ importers.py │ rss.py (bounded│ gateway.py (tuỳ chọn) │   │
│  │             │              │  RSS/Atom)     │ schema.py (validate)  │   │
│  │             │              │ runs.py (sổ   │                       │   │
│  │             │              │  collection)   │                       │   │
│  └──────┬──────┴──────┬───────┴───────┬────────┴──────────┬────────────┘   │
│         │             │               │                  │                │
│  radar/ changes.py · quota.py · daily.py   │           migrate.py + seed.py│
│  database.py = sqlite3 → backend/data/radar.db (12 bảng)                   │
└────────────────────────────────────────────────────────────────────────────┘
   │  source-registry/sources.json  (tài sản phía SERVER, không vào bundle)
```

## 2. Ranh giới sở hữu dữ liệu (đã kiểm trong code)

- **Public feed** `GET /api/articles`: chỉ bài `article_status = 'PUBLISHED'` và
  `data_origin != 'SAMPLE'`; không trả cột nội bộ.
- **Public explorer** `GET /api/models`: `SELECT` tường minh (không `SELECT *`), loại SAMPLE ở
  `models`/`provider_models`/`providers`; không trả registry/provenance/ghi chú nội bộ.
- **Daily Radar** `GET /api/radar`: chỉ bài PUBLISHED không-SAMPLE + change_event không-SAMPLE;
  không trả `before_snapshot`/`after_snapshot`/`raw_content`.
- **Admin API** `/api/admin/*`: mọi handler gọi `require_admin()` ở dòng đầu, **trước khi mở DB**;
  token kỳ vọng đọc từ `ADMIN_TOKEN` tại thời điểm request; public API không bao giờ trả cột nội bộ.
- **Source registry** nằm ở `source-registry/sources.json` (ngoài `src/`, không import/đóng gói vào
  frontend); content registry chỉ là dữ liệu, không bao giờ thực thi.
- **Dữ liệu ngoài = untrusted**: title/url/event text/feed bytes/upload chỉ được đọc và trả nguyên
  văn làm dữ liệu, không thành instruction/command/SQL/file-op. Mọi SQL truy vấn dùng bind parameter.

## 3. Backend

- **FastAPI** (`backend/app/main.py`, `app = FastAPI(title="Vũ Học AI Radar", version="1.0.0")`),
  khởi động theo hợp đồng: `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.
- **SQLite** qua `backend/app/database.py`: đường dẫn cố định `DATA_DIR/radar.db` (tính từ module,
  không phụ thuộc working directory); `init_db()` → `migrate.apply_migration()` (idempotent).
- **Migration** `backend/app/migrate.py`: hằng số `BUSINESS_TABLES` đúng 12 bảng MISSION; mọi DDL
  `IF NOT EXISTS`; cột nâng cấp bảng cũ qua `PRAGMA table_info`; toàn bộ trong một transaction;
  không bao giờ `DROP TABLE`/xóa dữ liệu. Cổng: `python -m backend.app.migrate` (exit 0).
- **Seed** `backend/app/seed.py`: mọi bản ghi mẫu có `data_origin='SAMPLE'` và id ổn định vùng
  `9xxxxx`; chạy lại không nhân bản; ngoài ra nạp **đúng 1 bài REAL/PUBLISHED** kế thừa v0.3.1.
  Cổng: `python -m backend.app.seed` (exit 0).
- **Xác thực admin** `backend/app/auth.py`: `hmac.compare_digest` hằng thời gian; thiếu token → 401,
  sai token → 403, chưa cấu hình env → 500 không kèm secret. Header hỗ trợ: `Authorization: Bearer`,
  `X-Admin-Token`.
- **Ingest** `backend/app/ingest/`: normalize tất định (canonical URL, normalize title, SHA-256 hash)
  rồi import Markdown/CSV/JSON thành `raw_items` + bản nháp `articles` (DRAFT), chống trùng theo
  `(canonical_url, normalized_title, content_hash)`, `MAX_UPLOAD_BYTES = 1_000_000`.
- **Collectors** `backend/app/collectors/`: registry validate chặt host công khai (chặn
  loopback/private/metadata/mDNS), adapter RSS/Atom bounded (redirect/retry/backoff/trigger giới hạn),
  sổ `collection_runs` (RUNNING → SUCCESS/SKIPPED/FAILED, error message cắt trần + che secret).
- **Editorial** `backend/app/editorial/`: rule-based phân loại tất định khi **không có gateway**;
  nếu đủ `AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL` thì gọi OpenAI-compatible qua
  `gateway.py` (bounded retry, output được `schema.py` validate, luôn giữ
  `verification_status='NEEDS_REVIEW'` + `freshness='NOT_VERIFIED'`; mọi lỗi fallback về rules).
- **Radar** `backend/app/radar/`: `changes.py` (9 loại change_event; **một lần timeout không bao giờ
  thành MODEL_REMOVED**), `quota.py` (append-only observation), `daily.py` (tổng hợp PUBLISHED +
  change_event theo window `today/7d/30d/all`; trạng thái `CURRENT`/`STALE`/`SIGNAL_WEAK`; mốc lịch
  07:00 `Asia/Ho_Chi_Minh` — **chỉ trong bộ nhớ**, `deferred-to-request`, không thread/sleep/mạng).

## 4. Frontend

- **Vite 7 + React 19**; không UI framework ngoài; CSS thuần `src/styles.css`.
- **`src/App.jsx`**: 7 nhóm nội dung (`src/data/groups.js`): Tip & Trick, AI & Model, Chính sách &
  Quota, Free Model Explorer, AI Deals & Promotions, Provider Comparison, Admin Radar.
  - Nhóm feed → `GroupView` gọi `/api/articles` (có AbortController; làm đủ loading/empty/error).
  - `free-model-explorer` → `ExplorerView` gọi `/api/models`.
  - `admin-radar` → `AdminView` gọi `/api/admin/*` qua `src/components/admin/adminClient.js`
    (token truyền theo tham số từng lệnh gọi; không localStorage/cookie).
- **`vite.config.js`**: host `127.0.0.1`, port 5173, proxy `/api` → `http://127.0.0.1:8000`.

## 5. Dữ liệu REAL so với SAMPLE (tại thời điểm viết tài liệu)

| Hạng mục | REAL | SAMPLE |
|---|---|---|
| articles | 1 (đã PUBLISHED, kế thừa v0.3.1, source `LEGACY_v031`) | 1 (DRAFT, fixture) |
| sources | 1 (`LEGACY_v031`, manual_legacy_inherit) | 2 fixture |
| providers / models / provider_models | 0 | fixture SAMPLE |
| change_events | 0 | 2 fixture |

→ Bảng explorer công khai hiện gần như rỗng về REAL; toàn bộ số liệu provider/model/quota là
**SAMPLE** và bị loại khỏi public API. Xem `docs/DATA_SOURCES.md`.
