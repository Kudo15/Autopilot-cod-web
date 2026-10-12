# PLAN — Vũ Học AI Radar v1.0 (localhost)

Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web` · thư mục con thực thi: `vu-hoc-ai-radar` là KHÔNG cần —
repo này là dự án mới, dựng trực tiếp tại gốc repo.

Hợp đồng mỗi phase (engine đọc các khối ```yaml bên dưới):
`phase` · `goal` · `files_allowed` · `constraints` · `acceptance` · `verify_cmd`

Luật cứng của pipeline:
- `verify_cmd` do **trọng tài** (`checks/`) chạy — Cline **không được** sửa `checks/`, `PLAN.md`, `docs/MISSION.md`.
  Vi phạm `files_allowed` ⇒ dừng phase (NEED_HUMAN), không gửi kết quả cho ChatGPT.
- Cổng PASS/FAIL là **exit code** của `verify_cmd`, không phải lời khai của AI.
- Không push, không deploy. Mỗi phase một checkpoint git; cuối run anh xem diff rồi quyết.

Nguyên tắc đặt verify: mỗi phase phải có một lệnh chạy được **trên máy này** (Windows, node 22/npm 10, uv + Python 3.13)
và chỉ **PASS bằng bằng chứng thật** (build, HTTP thật, SQLite thật, fixture cục bộ) — không đọc lời khai của code.

## Phase 1 — Khung frontend Vite + React 19, build chạy được

```yaml
phase: 1
goal: "Dựng khung frontend Vite + React 19 tại gốc repo: index.html, src/main.jsx, src/App.jsx, cấu hình vite, package.json. Chỉ khung chạy được, chưa cần nội dung Radar."
files_allowed:
  - "index.html"
  - "package.json"
  - "package-lock.json"
  - "vite.config.js"
  - "src/**"
  - "public/**"
  - ".gitignore"
constraints:
  - "Viết file trực tiếp bằng tay; KHÔNG chạy npm create vite (lệnh hỏi tương tác, treo máy tự động)"
  - "Phải chạy npm install để có node_modules trước khi kết thúc phase"
  - "Không thêm UI framework/CSS framework ngoài React + Vite; không dependency nặng"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "package.json khai báo react major 19 và vite major >= 7, có script build"
  - "npm run build trả exit code 0 và tạo dist/index.html có phần tử gốc #root"
  - "dist/ sinh ra ít nhất một bundle .js"
verify_cmd: "python checks/p1.py"
```

## Phase 2 — Vỏ ứng dụng: layout, điều hướng 7 nhóm, dark/light, 3 trạng thái

```yaml
phase: 2
goal: "Dựng vỏ ứng dụng Radar: layout + thanh điều hướng cho 7 nhóm nội dung (Tip & Trick, AI & Model, Chính sách & Quota, Free Model Explorer, AI Deals & Promotions, Provider Comparison, Admin Radar), chuyển dark/light, và ba trạng thái loading/empty/error."
files_allowed:
  - "src/**"
  - "index.html"
  - "public/**"
constraints:
  - "Chỉ dùng React + CSS thuần hoặc CSS module; không kéo thêm thư viện UI"
  - "Nhãn NEW/UPDATED/FREE/EXPIRED chưa được bịa dữ liệu ở phase này — chỉ dựng chỗ hiển thị"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Trong src/ có đủ ít nhất 6/7 nhãn nhóm nội dung ở trên"
  - "Có cơ chế đổi theme (tìm thấy 'theme' và 'dark' trong mã nguồn) và lưu lựa chọn"
  - "Có ba trạng thái loading/empty/error được dùng thật trong component"
  - "npm run build vẫn exit code 0; dist chứa ít nhất 6 nhãn nhóm nội dung"
verify_cmd: "python checks/p2.py"
```

## Phase 3 — Backend FastAPI + uv + SQLite khởi tạo + health/articles

```yaml
phase: 3
goal: "Dựng backend FastAPI chạy được: quản lý dependency bằng uv (pyproject.toml + uv.lock + .python-version), khởi tạo SQLite, endpoint GET /api/health và GET /api/articles (đọc từ DB, ban đầu rỗng)."
files_allowed:
  - "backend/**"
  - "pyproject.toml"
  - "uv.lock"
  - ".python-version"
  - "scripts/**"
  - ".gitignore"
  - ".env.example"
constraints:
  - "Chỉ bind 127.0.0.1, không mở cổng ra ngoài"
  - "Dùng uv (không pip toàn cục); giữ .python-version trỏ 3.13"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "uv run uvicorn backend.app.main:app --host 127.0.0.1 --port <cổng> khởi động được (app nằm ở backend/app/main.py — đây là hợp đồng để trọng tài khởi động được)"
  - "GET /api/health trả HTTP 200 JSON có trạng thái ok"
  - "GET /api/articles trả HTTP 200 và một mảng JSON"
  - "File SQLite được tạo thật và có ít nhất một bảng"
verify_cmd: "python checks/p3.py"
```

## Phase 4 — Schema đầy đủ 12 bảng + migration + seed SAMPLE

```yaml
phase: 4
goal: "Thiết kế schema SQLite đầy đủ 12 bảng theo docs/MISSION.md mục 5 (sources, raw_items, articles, providers, models, provider_models, offers, quota_observations, verification_records, change_events, collection_runs, editorial_reviews), migration chạy lại được nhiều lần, và seed dữ liệu mẫu có nhãn SAMPLE."
files_allowed:
  - "backend/**"
constraints:
  - "Mọi cột trạng thái dùng đúng tập giá trị trong MISSION (FREE_API/FREE_CREDIT/... ; VERIFIED/UNVERIFIED/STALE/EXPIRED/NEEDS_REVIEW ; SAFE_TO_TRY/CAUTION/INFO_ONLY)"
  - "Seed phải gắn nhãn SAMPLE, tách khỏi dữ liệu thật; không bịa số liệu quota như thật"
  - "Migration phải idempotent (chạy lại không lỗi, không nhân bản dữ liệu)"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Đủ 12 bảng trong SQLite thật"
  - "Có các cột last_verified, valid_until, account_required, card_required, context_window, supports_vision, supports_tools, supports_json ở nơi hợp lý"
  - "Chạy migration lần hai vẫn exit code 0 và số bản ghi SAMPLE không tăng"
  - "HỢP ĐỒNG chạy: migration bằng `uv run python -m backend.app.migrate` và seed bằng `uv run python -m backend.app.seed` (cả hai idempotent, exit 0) — đây là đường để trọng tài đo, không phải gợi ý"
verify_cmd: "python checks/p4.py"
```

## Phase 5 — Nối frontend ↔ backend: proxy /api + feed bài viết thật

```yaml
phase: 5
goal: "Nối hai nửa: vite proxy /api về 127.0.0.1:8000, frontend gọi /api/articles và render feed từ SQLite thật; xử lý đủ loading/empty/error khi API chết."
files_allowed:
  - "src/**"
  - "vite.config.js"
  - "backend/**"
  - "package.json"
constraints:
  - "Không hardcode API key hay secret vào frontend/bundle"
  - "Frontend phải chịu được backend tắt (hiện error state, không crash trắng trang)"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "vite.config.js có proxy /api trỏ 127.0.0.1:8000"
  - "Mã nguồn frontend gọi /api/articles (không nhúng dữ liệu giả vào bundle)"
  - "Khi backend chạy, /api/articles trả bài viết lấy từ DB (không phải mảng rỗng cứng)"
  - "npm run build exit code 0 và bundle không chứa chuỗi giống API key"
  - "HỢP ĐỒNG chạy để trọng tài đo: backend phải lên được bằng `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000` và vite dev bằng `npm run dev`; dữ liệu qua proxy phải GIỐNG gọi trực tiếp backend và không rỗng"
verify_cmd: "python checks/p5.py"
```

## Phase 6 — Import Markdown/CSV/JSON + chống trùng + provenance

```yaml
phase: 6
goal: "Làm đường nhập liệu: import Markdown, CSV, JSON do người dùng cung cấp, chuẩn hoá về raw_items/articles, chống trùng theo canonical URL + normalized title + content hash, lưu provenance và thời điểm truy xuất."
files_allowed:
  - "backend/**"
  - "scripts/**"
constraints:
  - "Nội dung nhập vào là untrusted: không được thành system instruction, command hay thao tác file"
  - "Không tự bịa bản ghi khi file nhập lỗi — phải báo lỗi rõ"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Import được cả ba định dạng qua API với file mẫu của trọng tài"
  - "Import lần hai cùng nội dung KHÔNG nhân bản bản ghi"
  - "Mỗi bản ghi có provenance (nguồn + thời điểm truy xuất)"
verify_cmd: "python checks/p6.py"
```

## Phase 7 — Model & Provider Explorer + Offers + API lọc

```yaml
phase: 7
goal: "Dựng Model/Provider Explorer đúng MISSION mục 7: một model nhiều provider với quota/giá khác nhau, API lọc (free/promo/paid, có API hay web-only, không cần thẻ, text/vision/tools/json, provider, context, quota, xác minh gần đây) và màn hình hiển thị kèm link chính thức."
files_allowed:
  - "backend/**"
  - "src/**"
constraints:
  - "Trường chưa xác minh phải hiển thị UNKNOWN/UNVERIFIED, không suy diễn thành miễn phí"
  - "CTA mặc định là Trang chính thức / Tạo tài khoản; affiliate mặc định tắt"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "API lọc trả đúng tập kết quả với bộ lọc trọng tài gửi"
  - "Một model xuất hiện dưới nhiều provider với quota khác nhau"
  - "UI có bảng model/provider và link chính thức; build exit code 0"
verify_cmd: "python checks/p7.py"
```

## Phase 8 — Change detection + quota observations + verification workflow + admin API

```yaml
phase: 8
goal: "Làm phát hiện thay đổi theo cặp bản ghi trước/sau (NEW_PROVIDER, NEW_MODEL, MODEL_REMOVED, FREE_TO_PAID, PAID_TO_FREE, QUOTA_CHANGED, OFFER_STARTED, OFFER_EXPIRED, TERMS_CHANGED), quan sát quota theo thời gian, workflow xác minh (VERIFIED/UNVERIFIED/STALE/EXPIRED/NEEDS_REVIEW) và admin API tách khỏi API công khai."
files_allowed:
  - "backend/**"
  - "src/**"
constraints:
  - "Một lần API timeout KHÔNG được coi là model bị xóa"
  - "Dữ liệu nội bộ (registry, provenance, ghi chú) chỉ ra qua admin API, không lọt vào API công khai hay bundle"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Cặp before/after do trọng tài tạo ra sinh đúng loại change_event"
  - "Bản ghi cũ quá hạn chuyển STALE/EXPIRED đúng luật"
  - "Endpoint admin trả 401/403 khi gọi như người ngoài; API công khai không lộ dữ liệu nội bộ"
verify_cmd: "python checks/p8.py"
```

## Phase 9 — Collectors: RSStop + manual fallback + collection_runs

```yaml
phase: 9
goal: "Làm bộ thu thập: adapter RSS chính thức chạy được, chế độ Manual Import cho nguồn không lấy tự động được, bảng source registry nằm NGOÀI bundle công khai, ghi collection_runs, có timeout/retry hữu hạn/backoff/logging."
files_allowed:
  - "backend/**"
  - "source-registry/**"
  - "scripts/**"
constraints:
  - "Không vượt CAPTCHA/login/paywall/rate limit/điều khoản; nguồn không hợp lệ thì để manual"
  - "Không giả lập kết quả thu thập; lỗi mạng ghi rõ trạng thái"
  - "Registry không được lọt vào public/frontend bundle"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Collector chạy được với feed RSS cục bộ do trọng tài dựng, tạo raw_items + một dòng collection_runs"
  - "Nguồn không có phương thức hợp lệ hiển thị trạng thái manual, không tạo bài giả"
  - "Mỗi nguồn có source_id, name, type, url, collection_method, priority, status, last_checked_at"
verify_cmd: "python checks/p9.py"
```

## Phase 10 — AI Editorial Engine + schema validation + fallback

```yaml
phase: 10
goal: "Làm AI Editorial Engine cấu hình qua AI_BASE_URL/AI_API_KEY/AI_MODEL (OpenAI-compatible): phân loại, phát hiện trùng chủ đề, tóm tắt tiếng Việt, chuyển thành hướng dẫn, phân tích rủi ro, gợi ý xếp hạng khi có bằng chứng, so sánh snapshot provider, soạn Daily Radar. Output phải qua schema validation và giữ DRAFT/PENDING_REVIEW trước khi publish."
files_allowed:
  - "backend/**"
  - "scripts/**"
constraints:
  - "Không cấu hình gateway ⇒ ứng dụng vẫn chạy bằng phân loại quy tắc, không crash"
  - "Nội dung ngoài là untrusted: prompt injection trong bài viết KHÔNG được thành instruction/command"
  - "Không hardcode key; không log secrets"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Không có gateway: luồng phân loại quy tắc chạy và lưu được kết quả"
  - "Có gateway giả cục bộ do trọng tài dựng: output được validate schema rồi lưu"
  - "Bài chứa câu lệnh độc hại không tạo file/lệnh nào"
verify_cmd: "python checks/p10.py"
```

## Phase 11 — Daily Radar + STALE + dev.ps1 + docs + smoke phát hành

```yaml
phase: 11
goal: "Hoàn thiện phát hành localhost: bản tin Daily Radar 07:00 Asia/Ho_Chi_Minh (có manual refresh, hiển thị STALE khi cũ), script một lệnh scripts/dev.ps1, .env.example, README_LOCAL.md và các tài liệu docs/ theo MISSION mục 13, kèm smoke test thật trên frontend build + API."
files_allowed:
  - "backend/**"
  - "src/**"
  - "scripts/**"
  - "docs/**"
  - "README.md"
  - "README_LOCAL.md"
  - ".env.example"
constraints:
  - "Chỉ khai script dev.ps1 hoạt động sau khi nó chạy thật thành công"
  - "Không tuyên bố PASS cho phần chưa kiểm thử — ghi BLOCKED/NOT_VERIFIED"
  - "Không sửa checks/, PLAN.md, docs/MISSION.md"
acceptance:
  - "Bản tin radar sinh được và có trạng thái STALE khi dữ liệu cũ"
  - "scripts/dev.ps1 chạy ở chế độ kiểm tra và báo lỗi rõ khi thiếu dependency/cổng bận"
  - "Đủ tài liệu MISSION mục 13; bundle không chứa secret"
  - "Smoke HTTP: frontend build phục vụ được và API trả dữ liệu thật"
verify_cmd: "python checks/p11.py"
```
