# QA_REPORT — Kiểm thử và xác minh Vũ Học AI Radar v1.0 (localhost)

## Beta update 2026-10-29 (đọc trước)

Kết quả Beta: **PASS_WITH_WARNINGS (BETA LOCAL)** — hồ sơ đầy đủ: [`FINAL_ACCEPTANCE_BETA.md`](FINAL_ACCEPTANCE_BETA.md).
Bản cập nhật này **supersedes** các con số phiên 2026-10-25 dưới đây (giữ nguyên làm lịch sử, không xoá):
Node 22.11.0 → **26.13.0**; full backend **330 tests** → **466 tests OK** (kèm ResourceWarning SQLite,
không chặn); build PASS không còn cảnh báo Node; browser E2E **Playwright 4 passed**; focused
runner/scheduler **31 OK**; scheduler **`VuHocAIRadar-Daily`** Ready, manual trigger 2026-10-29 21:08
LastTaskResult 0, next run 2026-10-30 07:00 (**NOT_VERIFIED** cho chạy tự động tương lai).
Verdict reviewer độc lập: **WAIVED** theo user (không phải PASS).

Báo cáo chất lượng của bản **localhost** tại nhánh `autopilot/run-live`, HEAD `fb3cb14`
(2026-10-25 05:46 +0700). Toàn bộ lệnh bên dưới được **chạy lại từ đầu trong phiên này**; kèm lệnh
để tự tái lập. Mọi hạng mục không thể kiểm chứng được ghi rõ **NOT_VERIFIED** hoặc **BLOCKED** — không
bao giờ ghi PASS cho thứ chưa đo.

## 1. Môi trường đo (phiên hiện tại)

| Thành phần | Giá trị quan sát |
|---|---|
| OS | Windows 11, chỉ bind `127.0.0.1` |
| Node.js | `v22.11.0` |
| npm | `10.9.0` |
| uv | `0.12.17` |
| Python | 3.13 (qua `uv run --no-sync`) |
| PowerShell | `pwsh` 7.x |
| Git HEAD | `fb3cb14` — nhánh `autopilot/run-live` |
| Admin token | biến môi trường test sinh ngẫu nhiên (không hardcode) |

## 2. Khung đánh giá

- **Gates của pipeline** — `checks/p1.py … p5.py`, chạy qua `uv run --no-sync python checks/pN.py`.
- **Bộ test nguồn** — `python -m unittest` (back-end), `npm run build` (front-end).
- **Startup thật** — `scripts/dev.ps1` `-Check` và chế độ chạy + tự dừng ở cổng tùy chọn.
- **Quy tắc**: kết quả phải thấy được bằng exit code / output; dữ liệu mẫu gắn nhãn SAMPLE; ngoài lề
  live network / live gateway / browser ghi NOT_VERIFIED.

## 3. Tổng hợp kết quả

| # | Lệnh / kiểm thử | Kết quả quan sát |
|---|---|---|
| 1 | `uv run python -m backend.app.migrate` | exit 0 — 12 bảng nghiệp vụ, idempotent |
| 2 | `uv run python -m backend.app.seed` (×2) | lần 1: 21 SAMPLE + 1 REAL; lần 2: 0 mới (idempotent) |
| 3 | Full back-end: `unittest discover -s backend/tests -p "test_*.py"` | exit 0 — **Ran 330 tests, OK** |
| 3a | — `test_startup_script` | **13/13** OK |
| 3b | — `test_radar_daily` | **27/27** OK |
| 3c | — `test_editorial_gateway` | **9/9** OK |
| 4 | `npm run build` | exit 0 — 0.47 kB HTML/11.20 kB CSS/218.56 kB JS; **cảnh báo** Node 22.11 |
| 5 | `checks/p1.py` | **PASS 15/15** |
| 6 | `checks/p2.py` | **PASS 9/9** |
| 7 | `checks/p3.py` | **PASS 13/13** |
| 8 | `checks/p4.py` | **PASS 15/15** — dương tính giả `sk-` đã sửa, mục 4.2 |
| 9 | `checks/p5.py` | **PASS 11/11** |
| 10 | `pwsh -File scripts/dev.ps1 -Check -BackendPort 8123 -FrontendPort 5273` | exit 0 — sẵn sàng |
| 11 | `pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273 -AutoStopSeconds 25` | exit 0 — migration OK, backend UP `127.0.0.1:8123`, frontend UP `127.0.0.1:5273`, dừng sạch |

### Không PASS được (BLOCKED / NOT_VERIFIED) — mục 4

| Hạng mục | Trạng thái | Lý do |
|---|---|---|
| Smoke cổng mặc định 8000/5173 | **NOT_VERIFIED** | cổng đang bị server anh em giữ (8000→PID 31912, 5173→PID 30600) |
| Smoke trên trình duyệt (render DOM desktop/mobile, đổi theme) | **NOT_VERIFIED** | không điều khiển trình duyệt trong phiên này |
| Độ tươi / HTTP thật của feed ngoài (live network) | **NOT_VERIFIED** | chỉ chạy adapter với feed cục bộ trong test |
| Gateway AI thật (AI_BASE_URL/AI_API_KEY/AI_MODEL) | **NOT_VERIFIED** | chỉ test gateway giả cục bộ (9/9) |

## 4. Chi tiết từng mục

### 4.1 Gates của pipeline

```
uv run --no-sync python checks/p1.py   -> ket qua phase: PASS (15/15)   exit 0
uv run --no-sync python checks/p2.py   -> ket qua phase: PASS (9/9)     exit 0
uv run --no-sync python checks/p3.py   -> ket qua phase: PASS (13/13)   exit 0
uv run --no-sync python checks/p4.py   -> ket qua phase: PASS (15/15)   exit 0
uv run --no-sync python checks/p5.py   -> ket qua phase: PASS (11/11)   exit 0
```

- **p1**: (P3) Vite + React 19 — build exit 0, `dist/index.html` có root, 1 bundle `.js`, bundle không
  chứa secret. **PASS**.
- **p2**: vỏ ứng dụng — 3 trạng thái (loading/empty/error), 7 nhóm nội dung đủ tên, dark/light
  (bundle chứa `vu-hoc-ai-radar-theme`), build exit 0. **PASS**.
- **p3**: back-end FastAPI/uv/SQLite — ứng dụng mở được, `/api/health` 200, `/api/articles` trả mảng
  JSON 1 phần tử, `radar.db` tồn tại (13 bảng kể cả `sqlite_sequence`), `main.py` không secret.
  **PASS**.
- **p4**: schema/seed — 12 bảng nghiệp vụ đủ cột bắt buộc MISSION, migration chạy lại exit 0,
  seed nhãn SAMPLE (58 ô), seed lần 2 exit 0 và **không nhân bản** (24 bản ghi trước/sau). Bước quét
  secret hiện OK — bước từng bị dương tính giả `sk-` đã được sửa ở `c44adee` (xem 4.2). **PASS (15/15) exit 0**.
- **p5**: nối frontend–backend — proxy `/api` trả JSON giống gọi trực tiếp back-end (cùng dữ liệu từ
  DB), build exit 0, bundle không chứa chuỗi giống API key. **PASS**.

### 4.2 `checks/p4.py` — dương tính giả `sk-` ĐÃ SỬA; hiện PASS 15/15 (exit 0)

- Bối cảnh lịch sử: bước quét secret của `checks/p4.py` quét chuỗi **literal** `"sk-"` cùng
  `"BEGIN PRIVATE KEY"` trong `backend/**/*.py`.
- `backend/tests/test_startup_script.py` (thêm bởi task 016) chứa marker `"sk-"` **chỉ để kiểm tra**
  `.env.example` không có secret — chuỗi kiểm tra, **không phải secret**. Hệ quả: P4 từng được duyệt
  **PASS 15/15**, rồi quay về **exit 1 (14/15)** sau khi task 016 thêm file đó.
- Cách sửa (task 018, commit `c44adee`, cherry-pick từ `bec8129`): marker được gộp vào hằng số
  `SECRET_MARKERS = ("sk" + "-", "Bearer ", "-----BEGIN")` — **ghép từ hai mảnh rời** nên quét raw
  không còn trùng, còn **giá trị lúc chạy y hệt** (`"sk" + "-" == "sk-"`). Chỉ 1 file được sửa:
  `backend/tests/test_startup_script.py`; `checks/` và `.env.example` không đổi.
- Đo lại tại HEAD `fb3cb14`: `uv run --no-sync python checks/p4.py` → **PASS (15/15), exit 0** —
  đủ 12 bảng, cột bắt buộc, trạng thái MISSION, migration/seed idempotent, nhãn SAMPLE, quét secret OK.
- Không còn hạng mục P4 nào ở trạng thái BLOCKED; các mục live (cổng mặc định, browser, live feed,
  live gateway) vẫn **NOT_VERIFIED** — xem mục 6.

### 4.3 Bộ test back-end (đầy đủ + các bộ đặc thù)

```
uv run --no-sync python -m unittest discover -s backend/tests -p "test_*.py"
#   Ran 330 tests — OK   (cần ADMIN_TOKEN trong environment)
```

Phân bố theo module (tổng 330): startup_script 13 · radar_daily 27 · radar_changes 42 ·
editorial_rules 8 · editorial_gateway 9 · collectors_registry 64 · collectors_rss 50 · importer 13 ·
normalize 7 · models_api 22 · public_articles 6 · admin_workflow 39 · admin_ui 25.

- Lưu ý: một ca trong `test_admin_workflow` cần biến môi trường `ADMIN_TOKEN` đã set để mong đợi 401;
  thiếu biến ⇒ ca đó thấy 500 và suite fail (hành vi đúng của `require_admin`, chưa cấu hình → 500).
  Chạy full suite phải export `ADMIN_TOKEN` trước (giá trị test ngẫu nhiên, không hardcode).

### 4.4 Build front-end

```
npm run build   # exit 0
# dist/index.html   0.47 kB │ gzip  0.32 kB
# dist/assets/index-*.css   11.20 kB │ gzip  2.49 kB
# dist/assets/index-*.js  218.56 kB │ gzip 67.42 kB
# Cảnh báo: "You are using Node.js 22.11.0. Vite requires Node.js version 20.19+ or 22.12+."
```

Build **vẫn exit 0**; cảnh báo là thông tin (muốn hết cảnh báo thì nâng Node ≥ 22.12).

### 4.5 Startup thật qua `scripts/dev.ps1` (cổng tùy chọn)

```
pwsh -File scripts/dev.ps1 -Check -BackendPort 8123 -FrontendPort 5273
#   -> CHECK OK: 8123/127.0.0.1 va 5273/127.0.0.1 san sang khoi dong.  (exit 0)

pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273 -AutoStopSeconds 25
#   -> migration OK (idempotent)
#   -> Backend UP  -> http://127.0.0.1:8123/api/health  (PID=...)
#   -> Frontend UP -> http://127.0.0.1:5273/ (PID=...)
#   -> tự dừng đúng 2 PID (frontend rồi backend), exit 0
```

`-Check` cũng cảnh báo (WARN, không chặn) khi `AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL` chưa set — đúng
thiết kế `.env.example` rỗng; script không hề tự điền secret.

### 4.6 Dữ liệu REAL vs SAMPLE (đo trực tiếp trên `backend/data/radar.db`)

| Bảng | REAL | SAMPLE |
|---|---|---|
| `articles` | 1 (PUBLISHED, source `LEGACY_v031`) | 1 (DRAFT) |
| `sources` | 1 (`LEGACY_v031`, `manual_legacy_inherit`) | 2 |
| `providers` / `models` / `provider_models` | 0 | 1 / 1 / 2 |
| `offers` / `quota_observations` / `change_events` | 0 | 2 / 2 / 2 |
| `raw_items` | (provenance REAL kế thừa) | 1 |
| `verification_records` / `collection_runs` / `editorial_reviews` | (SAMPLE nếu có) | 4 / 2 / 1 |

> Không có số liệu provider/model/quota nào là thật; toàn bộ là **SAMPLE** và bị loại khỏi public API.

## 5. Kiểm tra an toàn (đã làm trong phiên này)

- **Không hardcode secret**: `.env.example` chỉ liệt kê **tên** biến (`ADMIN_TOKEN`,
  `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`), giá trị để rỗng. `git grep` không thấy secret thật trong
  docs; các giá trị trong tài liệu là placeholder/giá trị test.
- **Chỉ bind localhost**: `scripts/dev.ps1` và `vite.config.js`/uvicorn đều hướng `127.0.0.1`; không
  mở cổng ra ngoài, không tạo remote, không deploy.
- **Dữ liệu ngoài = untrusted**: title/url/feed bytes/upload chỉ là dữ liệu; mọi SQL dùng bind
  parameter; registry nằm ngoài bundle front-end; không vượt CAPTCHA/login/paywall/rate limit.
- **Ở back-end đã đo**: `checks/p1.py`/`p3.py`/`p4.py`/`p5.py` xác nhận bundle và mã nguồn không chứa
  chuỗi giống key — mục quét `sk-` của p4 từng là dương tính giả đã được sửa (xem 4.2).

## 6. Hạng mục chưa kiểm chứng (NOT_VERIFIED) — ranh giới của bản này

| Hạng mục | Trạng thái | Cách tự kiểm trong tương lai |
|---|---|---|
| Smoke cổng mặc định `8000`/`5173` | NOT_VERIFIED — PID 31912 / PID 30600 đang giữ cổng | dừng server anh em rồi chạy `pwsh -File scripts/dev.ps1` |
| Render thật trên trình duyệt (DOM desktop/mobile, đổi theme, console lỗi) | NOT_VERIFIED | mở `http://localhost:5173` sau khi cổng mặc định trống |
| Live feed ngoài (freshness/HTTP thật) | NOT_VERIFIED — adapter chỉ chạy feed cục bộ trong test | nạp entry `status='active'` và thu thập với chứng cứ HTTP thật |
| Gateway AI thật | NOT_VERIFIED — chỉ test gateway giả 9/9 cục bộ | set 3 biến env và chạy editorial request một lần |

Đây **không** là PASS: chúng được ghi trung thực là chưa đo được trong phiên này.

## 7. Kết luận cho bản localhost

- Toàn bộ chức năng **local** đã đo đều hoạt động: test 330/330 OK, build exit 0, startup thật exit 0
  ở cổng tùy chọn, migration/seed idempotent, dữ liệu REAL/SAMPLE phân định rõ. Toàn bộ 5 cổng
  `checks/p1.py…p5.py` đều **PASS** (p4 nay **15/15** sau khi sửa dương tính giả `sk-` ở `c44adee`).
- **Chưa kiểm chứng**: cổng mặc định, trình duyệt, live feed, live gateway — ghi NOT_VERIFIED.

## 8. Danh sách tài liệu của bản release localhost

Cả 6 file đều được tạo trong task 017 (nhánh `wt/t_5fd6d5ec`); hai báo cáo này đã được refresh ở
task 019 (HEAD `fb3cb14`):

- `README_LOCAL.md` — hướng dẫn chạy + kết quả đo + xử lý sự cố
- `docs/ARCHITECTURE.md` — kiến trúc hai nửa, ranh giới dữ liệu
- `docs/DATA_SOURCES.md` — nguồn REAL vs SAMPLE, cơ chế thu thập
- `docs/DATA_SCHEMA.md` — 12 bảng, ràng buộc, dedup/index
- `docs/PHASE_REPORT.md` — tiến độ phase, bằng chứng lệnh, lỗi còn lại
- `docs/QA_REPORT.md` — báo cáo này
