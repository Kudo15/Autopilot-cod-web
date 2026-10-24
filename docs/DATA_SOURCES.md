# DATA_SOURCES — Nguồn dữ liệu của Vũ Học AI Radar v1.0

Tài liệu này mô tả **cơ chế thu thập có thật trong repo** và **nguồn nào thực sự đã nối**. Điểm cốt
lõi: hiện tại **chưa có nguồn ngoài nào được thu thập thật**; chỉ có (a) 3 fixture **SAMPLE** trong
registry, (b) một adapter RSS/Atom đã chạy được với **feed cục bộ trong test**, (c) nhập tay
Markdown/CSV/JSON, và (d) **1 bài REAL** kế thừa v0.3.1. Không có số liệu provider/quota nào là thật.

## 1. Registry nguồn — tài sản phía server

- File: `source-registry/sources.json`. Loader: `backend/app/collectors/registry.py`.
- Nằm **ngoài** `src/`; không bao giờ được import/đóng gói vào frontend bundle. Nội dung registry chỉ
  là **dữ liệu**, không bao giờ là instruction/command/SQL.
- Mỗi entry phải khai báo tường minh: `source_id`, `name`, `type`, `url`, `collection_method`,
  `priority`, `status` (và tuỳ chọn `last_checked_at`, `data_origin`, `note`). Field lạ bị **từ chối**
  (không có field nào bị bỏ qua âm thầm).
- Luật validate:
  - `type` ∈ {rss, atom, api, website, manual}; `collection_method` ∈ {rss, atom, api, manual_import};
    `status` ∈ {active, paused, sample, manual, unavailable}; `priority` 1..10; `url` phải là HTTP(S)
    tuyệt đối, **không** user-info, **không** host private/loopback/metadata/mDNS/nội bộ.
  - `last_checked_at` = **bằng chứng quan sát**: chỉ nhận ISO-8601 có offset và **không ở tương lai**
    (không bịa độ tươi); thiếu → `observation_state = 'NEVER_OBSERVED'`.
- `automated_collectable` **chỉ** true khi method tự động **và** `status='active'`. Fixture (`sample`),
  `manual`, `unavailable`, `paused` đều **không** tự động thu thập.

### Nội dung registry hiện tại (đúng 3 entry, tất cả SAMPLE)

| source_id | name | type | collection_method | status | data_origin |
|---|---|---|---|---|---|
| `SAMPLE_rss_demo` | SAMPLE RSS demo feed | rss | rss | sample | SAMPLE |
| `SAMPLE_manual_demo` | SAMPLE manual import source | manual | manual_import | manual | SAMPLE |
| `SAMPLE_unavailable_demo` | SAMPLE unavailable source | website | manual_import | unavailable | SAMPLE |

> Đây là **fixture cấu trúc**, không phải nguồn ngoài thật. Danh sách nguồn mong muốn trong
> `docs/MISSION.md` mục 4 (OneHack, Habr, Promo2day, BlackHatWorld, n8n, Show HN, GitHub, LowEndTalk,
> r/LLMDevs, r/selfhosted, r/LocalLLaMA; LLM24, OpenRouter, Hugging Face, Vercel AI Gateway,
> ModelScope, Hetzner AI, immers.cloud, TeamoRouter…) **chưa** được nạp thành entry thật — xem §5.

## 2. Adapter RSS/Atom (đã chạy với feed cục bộ)

`backend/app/collectors/rss.py`:

- Parse RSS/Atom/RDF bounded; **chặn** `<!DOCTYPE`/`<!ENTITY`. Mọi text feed là untrusted: chỉ đọc ra.
- Mạng chỉ qua client được inject; client mặc định tạo mỗi lần gọi, thoát kết nối sau dùng.
- **Giới hạn hữu hạn**: `timeout 10s`, body ≤ 5 MB, ≤ 1000 item, ≤ 3 redirect, ≤ 3 retry, backoff
  có trần 30s; mọi redirect/URL kiểm lại theo host policy công khai (chống SSRF/metadata).
- Ghi `raw_items` + một dòng `collection_runs` (`RUNNING` → `SUCCESS`/`SKIPPED`/`FAILED`).
- Nguồn không `automated_collectable` → ghi `SKIPPED`, **không** tạo bài giả.
- Lỗi mạng/parse → `FAILED` kèm `error_message` đã cắt trần + **che secret**; không giả lập kết quả.

Đã kiểm chứng: bộ test `backend/tests/test_collectors_rss.py` (**50/50**) và
`test_collectors_registry.py` (**64/64**) chạy trên feed cục bộ do test dựng — **không** chạm mạng ngoài.

## 3. Nhập tay (manual import) — đường cho nguồn không tự động được

`backend/app/ingest/` + route admin `POST /api/admin/import` (cần `ADMIN_TOKEN`):

- Nhận **.md / .csv / .json** (≤ 1 MB). Markdown cần front matter `---` với `title`/`url`.
- Chuẩn hoá tất định: canonical URL, normalize title (NFC/gộp khoảng trắng), SHA-256 content hash.
- **Chống trùng** theo `(canonical_url, normalized_title, content_hash)` → import lần hai không nhân bản.
- Lưu provenance (`source` + `fetched_at`) vào `raw_items`; tạo `articles` ở trạng thái **DRAFT**.
- Nội dung upload là untrusted: không thành instruction/command; batch lỗi thì ghi **không gì** (atomic).

## 4. Dữ liệu REAL duy nhất hiện có

- **1 bài REAL/PUBLISHED** kế thừa nội dung công khai Vũ Học AI v0.3.1: *"Đọc quota trong 60 giây:
  request khác token"* (source `LEGACY_v031`, `collection_method='manual_legacy_inherit'`).
- Đây là nội dung biên tập do chủ dự án công bố, **không** dùng làm bằng chứng xác minh provider/model;
  registry v0.3.1 đánh dấu bản ghi nguồn là `unverified`. Provenance nằm trong `raw_items`, không lộ
  ra public API.
- Trạng thái dữ liệu thật đo trên `backend/data/radar.db`:

| Bảng | REAL | SAMPLE |
|---|---|---|
| `articles` | 1 (PUBLISHED) | 1 (DRAFT) |
| `sources` | 1 (`LEGACY_v031`) | 2 |
| `providers` / `models` / `provider_models` | 0 | fixture SAMPLE |
| `change_events` | 0 | 2 |

## 5. Nguồn nối thật vs. còn lại — trạng thái trung thực

| Hạng mục | Trạng thái |
|---|---|
| Adapter RSS/Atom | **Đã chạy** — với feed **cục bộ** trong test; chưa trỏ nguồn ngoài nào |
| Registry nguồn ngoài thật | **Chưa có** (chỉ 3 fixture SAMPLE) |
| Nhập tay MD/CSV/JSON | **Đã chạy** (test 13/13 `test_importers.py`) |
| Bài REAL công khai | **1** (kế thừa v0.3.1) |
| Provider/model/quota REAL | **0** — mọi số liệu hiện là SAMPLE |
| Độ tươi/HTTP của feed ngoài (live network) | **NOT_VERIFIED** — chưa gọi mạng ngoài trong phiên này |
| Gateway AI thật | **NOT_VERIFIED** — chỉ test bằng gateway giả cục bộ (`test_editorial_gateway.py` 9/9) |

Danh sách nguồn MISSION mục 4 là **mục tiêu cho phiên bản sau**: mỗi nguồn cần được nạp thành entry
registry thật với `status='active'` + `collection_method` hợp lệ (rss/atom/api) và chứng cứ HTTP thật,
hoặc khai `manual`/`unavailable` nếu không có đường truy cập hợp lệ (không vượt CAPTCHA/login/paywall/
rate limit/ToS).

## 6. Quy tắc an toàn bắt buộc khi thêm nguồn mới

- Không vượt CAPTCHA/login/paywall/rate limit/điều khoản dịch vụ; nguồn không hợp lệ ⇒ để **manual**.
- Không giả lập kết quả thu thập; lỗi mạng ghi rõ trạng thái (`FAILED` + `error_message`).
- Registry **không** lọt vào public/frontend bundle.
- Text từ ngoài chỉ là **dữ liệu** — không thành instruction/command/SQL/file-op.
- Không hardcode key/secret; không log secret.
