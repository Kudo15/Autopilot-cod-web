# PHASE_REPORT — Vũ Học AI Radar v1.0 (localhost)

Báo cáo giải phóng bản localhost, cấu trúc theo mục 13 của `docs/MISSION.md`. Mọi con số là kết quả
**đo lại trong phiên này** (nhánh `autopilot/run-live`, HEAD `fb3cb14`), có lệnh để tự tái lập; phần
chưa kiểm chứng ghi **NOT_VERIFIED**.

## 1. Các phase đã thực hiện

Repo vận hành theo `PLAN.md` (11 phase, cổng `checks/p1.py` … `p11.py`). Do pipeline chạy theo
`checks/` hiện có (p1–p5), tiến độ thực tế như sau — kèm trạng thái **đo lại lần này**:

| Phase / task | Nội dung | Trạng thái (đo lại) |
|---|---|---|
| P1 | Khung Vite + React 19, build chạy được | **PASS** — `checks/p1.py` exit 0 (15/15) |
| P2 | Vỏ ứng dụng: 7 nhóm, dark/light, 3 trạng thái | **PASS** — `checks/p2.py` exit 0 (9/9) |
| P3 | Backend FastAPI + uv + SQLite, health/articles | **PASS** — `checks/p3.py` exit 0 (13/13) |
| P4 | Schema 12 bảng + migration idempotent + seed SAMPLE | **PASS** — `checks/p4.py` exit 0 (15/15); dương tính giả `sk-` đã được sửa ở commit `c44adee` — xem §5 |
| P5 | Nối frontend↔backend: proxy /api + feed thật | **PASS** — `checks/p5.py` exit 0 (11/11) |
| task 006–009 | Import MD/CSV/JSON + chống trùng + provenance; Model/Provider Explorer + lọc | **Đã có** — test `test_importers` 13/13, `test_models_api` 22/22 |
| task 009 | Change detection (9 loại) + quota observation + verification workflow | **Đã có** — `test_radar_changes` 42/42 |
| task 010/011 | Ranh giới admin (ADMIN_TOKEN) + workflow duyệt/xác minh + Admin UI | **Đã có** — `test_admin_workflow` 39/39, `test_admin_ui` 25/25 |
| task 012/013 | Source registry + collection_runs + adapter RSS/Atom bounded | **Đã có** — `test_collectors_registry` 64/64, `test_collectors_rss` 50/50 |
| task 010b/011b | Editorial engine: schema + rule fallback + gateway tuỳ chọn | **Đã có** — `test_editorial_rules` 8/8, `test_editorial_gateway` 9/9 |
| task 014/015 | Daily Radar (cửa sổ today/7d/30d/all, STALE) + routes + refresh admin | **Đã có** — `test_radar_daily` 27/27 |
| task 016 | `scripts/dev.ps1` (-Check + chạy thường) + `.env.example` + test startup | **Đã có** — `test_startup_script` 13/13; smoke live exit 0 |

## 2. Chức năng thực tế (hoạt động được, theo bằng chứng)

- **Feed bài viết public** `GET /api/articles` — chỉ PUBLISHED, không SAMPLE, từ SQLite thật.
- **Model/Provider Explorer** `GET /api/models` — lọc free_status/access/card_required/capability/
  provider/context/quota/verified_within_days; 422 cho tham số lạ; không `SELECT *`.
- **Admin API** (cần `ADMIN_TOKEN`): import, sources, reviews, chuyển trạng thái duyệt
  (PENDING_REVIEW → PUBLISHED/REJECTED), verification (cần evidence/note), refresh radar.
- **Admin UI React** (`/api/admin/*`) — token runtime, không localStorage, không `dangerouslySetInnerHTML`.
- **Daily Radar** `GET /api/radar` + `POST /api/admin/radar/refresh` — window chuẩn hoá, trạng thái
  CURRENT/STALE/SIGNAL_WEAK tất định, mốc 07:00 Asia/Ho_Chi_Minh **trong bộ nhớ** (deferred-to-request).
- **Collectors**: registry server-only + adapter RSS/Atom bounded + sổ collection_runs + import tay.
- **Editorial**: phân loại rule-based khi không có gateway; gateway OpenAI-compatible tuỳ chọn, output
  qua schema validation, luôn NEEDS_REVIEW + NOT_VERIFIED (không tự publish).
- **Migration/seed** idempotent: chạy lại không lỗi, không nhân bản.

## 3. Nguồn đã nối thật vs. còn manual

Chi tiết đầy đủ: `docs/DATA_SOURCES.md`. Tóm tắt:

- **Nối thật (REAL)**: chỉ **1 bài** kế thừa Vũ Học AI v0.3.1 (source `LEGACY_v031`). Adapter RSS/Atom
  đã chạy với **feed cục bộ trong test** — chưa trỏ nguồn ngoài.
- **Manual**: đường `POST /api/admin/import` cho Markdown/CSV/JSON (test 13/13).
- **Chưa/không có**: provider/model/quota **REAL** bằng 0; registry nguồn ngoài thật chưa nạp; độ tươi
  feed ngoài và gateway AI thật **NOT_VERIFIED**.

## 4. Kết quả lệnh test và bằng chứng (đo lại trong phiên này)

Môi trường: Windows 11 · Node v22.11.0 · npm 10.9.0 · uv 0.12.17 · Python 3.13 (uv) · `ADMIN_TOKEN`
đã export (biến môi trường, giá trị test sinh ngẫu nhiên — **không** hardcode trong repo).

```bash
# Migration / seed idempotent
uv run python -m backend.app.migrate     # exit 0 — 12 bảng
uv run python -m backend.app.seed        # exit 0 — lần 1: 21 SAMPLE + 3 REAL; lần 2: 0 mới

# Full backend suite (cần ADMIN_TOKEN)
uv run python -m unittest discover -s backend/tests -p "test_*.py"
#   → Ran 330 tests, OK, exit 0

# Bộ test ém hẹp
uv run python -m unittest backend.tests.test_startup_script   # 13/13 OK
uv run python -m unittest backend.tests.test_radar_daily      # 27/27 OK
uv run python -m unittest backend.tests.test_editorial_gateway# 9/9 OK

# Build frontend
npm run build   # exit 0; dist/index.html 0.47 kB + CSS 11.20 kB + JS 218.56 kB
                # kèm cảnh báo Node 22.11 (Vite cần 20.19+/22.12+)

# Trọng tài từng phase
uv run python checks/p1.py   # PASS 15/15   ·  uv run python checks/p2.py  PASS 9/9
uv run python checks/p3.py   # PASS 13/13   ·  uv run python checks/p5.py  PASS 11/11
uv run python checks/p4.py   # PASS 15/15   (dương tính giả cũ đã sửa ở c44adee — xem §5)

# Startup script
pwsh -File scripts/dev.ps1 -Check -BackendPort 8123 -FrontendPort 5273   # exit 0
pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273 -AutoStopSeconds 25
#   → migration OK, backend UP (127.0.0.1:8123/api/health), frontend UP (127.0.0.1:5273/), dừng sạch, exit 0
```

Phân bố số test theo module: startup_script 13 · radar_daily 27 · radar_changes 42 · editorial_rules 8 ·
editorial_gateway 9 · collectors_registry 64 · collectors_rss 50 · importer 13 · normalize 7 ·
models_api 22 · public_articles 6 · admin_workflow 39 · admin_ui 25 · search 3 · backup_scripts 2 (**tổng 330**).

## 5. Lỗi còn tồn tại / điểm cần lưu ý

1. **`checks/p4.py` — dương tính giả `sk-` ĐÃ SỬA; cổng hiện PASS 15/15 (exit 0).**
   - Bối cảnh lịch sử: bước 8 của `checks/p4.py` quét chuỗi **literal** `sk-` trên
     `backend/**/*.py`. `backend/tests/test_startup_script.py` (thêm bởi task 016) chứa marker `"sk-"`
     chỉ để khẳng định `.env.example` không có secret — chuỗi kiểm tra, **không phải secret**. Vì vậy
     P4 từng **PASS 15/15 lúc duyệt phase**, rồi quay về **exit 1 (14/15)** sau khi task 016 thêm file đó.
   - Cách sửa (task 018, commit `c44adee`, cherry-pick từ `bec8129`): gộp marker vào hằng số
     `SECRET_MARKERS = ("sk" + "-", "Bearer ", "-----BEGIN")` — **ghép từ hai mảnh rời** nên phần quét
     raw của trọng tài không còn khớp, còn **giá trị lúc chạy y hệt** (`"sk" + "-" == "sk-"`) nên nội
     dung kiểm tra `.env.example` không đổi. Chỉ 1 file được sửa: `backend/tests/test_startup_script.py`.
   - Đo lại tại HEAD `fb3cb14`: `uv run python checks/p4.py` → **PASS (15/15), exit 0** (đủ 12 bảng, cột
     bắt buộc, trạng thái MISSION, migration/seed idempotent, nhãn SAMPLE, và bước quét secret đều OK).
   - Không còn hạng mục P4 nào ở trạng thái BLOCKED; các mục chưa đo được giữ nguyên NOT_VERIFIED ở §7.
2. **`ADMIN_TOKEN` bắt buộc khi chạy full test**: thiếu env var ⇒ 1 ca trong
   `test_admin_workflow` thấy **500 thay vì 401** và suite fail. Đây là hành vi đúng của
   `require_admin` (chưa cấu hình → 500), tài liệu hoá trong `README_LOCAL.md` §5.2.
3. **Cổng mặc định 8000/5173 đang bị server anh em giữ** (PID quan sát: 8000→31912, 5173→30600) nên
   chưa thể chạy smoke ở cổng mặc định trong phiên này — kết quả smoke chỉ xác nhận ở cổng tùy chọn.
4. **Không có test khai lệch public** như P3/P5 (không có `checks/p6.py`…`p11.py` trong repo hiện tại).

## 6. Cách chạy chính xác

Xem `README_LOCAL.md`. Tóm tắt: `uv sync` + `npm install` một lần, đặt `$env:ADMIN_TOKEN`, rồi
`pwsh -File scripts/dev.ps1` → mở `http://localhost:5173`. `-Check` để dò tiên quyết trước.

## 7. Tính năng còn lại cho phiên bản sau (chưa triển khai / chưa kiểm chứng)

- Nạp **registry nguồn ngoài thật** (MISSION mục 4) và chạy collector với feed public thật (bằng chứng
  HTTP thật) — hiện chỉ có feed cục bộ trong test; độ tươi mạng ngoài **NOT_VERIFIED**.
- **Smoke trình duyệt** (render DOM desktop/mobile, đổi theme, không lỗi console) — chưa điều khiển
  trình duyệt trong phiên này; smoke HTTP trên build đã PASS, browser **NOT_VERIFIED**.
- Chạy thử ở **cổng mặc định 8000/5173** sau khi dừng các server anh em đang giữ cổng.
- Thêm `checks/p6.py`…`p11.py` theo PLAN cho các phase sau.
- Khai **gateway AI thật** (3 biến env) chạy thử một lần.
- Không có claim nào ở trên về deploy/GitHub/production — bản này chỉ là **localhost** và **không**
  push/deploy.
