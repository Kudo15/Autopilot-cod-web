# README_LOCAL — Chạy Vũ Học AI Radar v1.0 trên Windows localhost

Tài liệu này chỉ mô tả **những gì đã chạy thật và đo được trên máy này**. Mọi kết quả dưới đây đều
kèm lệnh và exit code; phần chưa kiểm chứng được ghi rõ **NOT_VERIFIED**, tuyệt đối không ghi PASS.

> Bối cảnh đầy đủ: `docs/MISSION.md` · chia phase: `PLAN.md` · luật repo: `AGENTS.md`.
> Kiến trúc: `docs/ARCHITECTURE.md` · nguồn dữ liệu: `docs/DATA_SOURCES.md` ·
> schema: `docs/DATA_SCHEMA.md` · tiến độ: `docs/PHASE_REPORT.md` · kiểm thử: `docs/QA_REPORT.md`.

## 1. Điều kiện tiên quyết (đã đo trên máy này)

| Thành phần | Phiên bản quan sát | Ghi chú |
|---|---|---|
| Windows | Windows 11 | Chỉ bind `127.0.0.1`; không mở cổng ra ngoài |
| Node.js | `v22.11.0` | Vite 7 cảnh báo cần `20.19+` hoặc `22.12+` — xem §5 |
| npm | `10.9.0` | |
| uv | `0.12.17` | Quản lý Python + dependency, **không** pip toàn cục |
| Python | 3.13 (qua `uv`) | `.python-version` trỏ 3.13; uv tự tạo `.venv` |
| PowerShell | `pwsh` 7.6.5 và `powershell.exe` 5.1 | Script khai `#Requires -Version 5.1` nên chạy được cả hai |

## 2. Cài đặt lần đầu (một lần)

Chạy trong PowerShell tại thư mục gốc repo:

```powershell
uv sync            # tạo .venv + cài fastapi/uvicorn (đọc uv.lock)
npm install        # cài vite/react vào node_modules
Copy-Item .env.example .env    # rồi điền secret THẬT vào .env (file đã bị gitignore)
$env:ADMIN_TOKEN = 'chuoi-ngau-nhien-dai-that-cua-ban'   # bắt buộc khi dùng route /api/admin/*
```

`.env.example` là **mẫu**: mọi giá trị để RỖNG, chỉ liệt kê **tên** biến
(`ADMIN_TOKEN`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`). Không bao giờ điền secret thật vào
`.env.example`. Ứng dụng đọc secret trực tiếp từ **environment**, không nạp `.env` tự động.

## 3. Chạy thường ngày — một lệnh

```powershell
pwsh -File scripts/dev.ps1
```

Script sẽ: kiểm tra tiên quyết → chạy migration idempotent (`uv run --no-sync python -m backend.app.migrate`)
→ mở backend `127.0.0.1:8000` → mở Vite `127.0.0.1:5173` → chờ cả hai trả HTTP → in PID và URL.
`Ctrl+C` dừng **đúng hai tiến trình do script này mở** (`taskkill /PID <id> /T`), không đụng tiến trình khác.

Mở trình duyệt: **http://localhost:5173**

### Các tham số phổ biến

```powershell
pwsh -File scripts/dev.ps1 -Check                                   # chỉ kiểm tra, không mở server
pwsh -File scripts/dev.ps1 -NoInstall                               # không tự uv sync / npm install
pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273     # đổi cổng (vẫn 127.0.0.1)
```

`-Check` trả **exit 0 = sẵn sàng**, **exit khác 0 = thiếu điều kiện tiên quyết** (kèm việc cần làm).

## 4. Kết quả đã đo (exit code thật)

| Lệnh | Kết quả quan sát |
|---|---|
| `uv run python -m backend.app.migrate` | exit 0 — 12 bảng nghiệp vụ sẵn sàng |
| `uv run python -m backend.app.seed` | exit 0 — lần 1: 21 bản ghi SAMPLE + 3 bản ghi REAL kế thừa; lần 2: 0 bản ghi mới (idempotent) |
| `uv run python -m unittest discover -s backend/tests -p "test_*.py"` (có `ADMIN_TOKEN`) | exit 0 — **Ran 466 tests, OK** |
| `uv run python -m backend.app.radar.run_daily --db-path <db-tạm>` | exit 0 — 1 dòng JSON status không secret, ledger bền ghi COMPLETED (đo trên DB tạm, KHÔNG đụng `backend/data/radar.db`) |
| `pwsh -File scripts/register_radar_task.ps1 -Status` (task chưa đăng ký) | exit 1 — lỗi rõ "Task 'VuHocAIRadar-Daily' not found" (chế độ tra cứu, không tác dụng phụ) |
| Parse `scripts/register_radar_task.ps1` bằng `System.Management.Automation.Language.Parser::ParseFile` | exit 0 — `PARSE_OK`, 0 lỗi cú pháp |
| `npm run build` | exit 0 — `dist/index.html` 0.47 kB, CSS 14.84 kB, JS 234.63 kB (kèm cảnh báo Node 22.11) |
| `pwsh -File scripts/dev.ps1 -Check -BackendPort 8123 -FrontendPort 5273` | exit 0 — cổng trống, sẵn sàng |
| `pwsh -File scripts/dev.ps1 -Check` (cổng mặc định) | exit 1 — chẩn đoán đúng: cổng 8000 đang bị uvicorn PID 17468 chiếm (xem §5.1) |
| `pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273 -AutoStopSeconds 25` | exit 0 — migration OK, backend + frontend **UP**, dừng sạch |

Chi tiết đầy đủ (kể cả hạng mục **NOT_VERIFIED**) ở `docs/QA_REPORT.md`.

## 5. Xử lý sự cố

### 5.1 Cổng đang bận (8000/5173)

Triệu chứng — `-Check` trả exit 1:

```
[FAIL] Vi pham dieu kien tien quyet (2):
  - cong 8000 (backend) dang ban: dung tien trinh cu tren cong do roi chay lai
  - cong 5173 (frontend) dang ban: dung tien trinh cu tren cong do roi chay lai
```

Trên máy này, tại thời điểm viết tài liệu, `127.0.0.1:8000` và `127.0.0.1:5173` đang bị các server
anh em giữ (xem §6). Cách xử lý:

```powershell
# Cách 1 — đổi cổng:
pwsh -File scripts/dev.ps1 -BackendPort 8123 -FrontendPort 5273

# Cách 2 — tìm PID đang giữ cổng rồi tự quyết định dừng (script KHÔNG tự kill):
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
```

### 5.2 `ADMIN_TOKEN` cho route admin

Mọi route `/api/admin/*` gọi `require_admin()` ở **dòng đầu handler, trước khi chạm DB**:

- Chưa set `ADMIN_TOKEN` → HTTP **500** (`server is missing required ADMIN_TOKEN environment variable`).
- Không có header token → **401**.
- Sai token / scheme lạ → **403** (so sánh hằng thời gian; token ngoài ASCII bị từ chối 403, không 500).

```powershell
$env:ADMIN_TOKEN = 'chuoi-ngau-nhien-dai'    # đặt trong CÙNG terminal rồi chạy dev.ps1
```

Token chỉ đi vào header `Authorization: Bearer <token>` hoặc `X-Admin-Token`; **không** nằm trong URL,
body, bundle hay `localStorage` của frontend (UI nhập token tại runtime).

### 5.3 Cảnh báo phiên bản Node

`npm run build` in ra:

```
You are using Node.js 22.11.0. Vite requires Node.js version 20.19+ or 22.12+. Please upgrade your Node.js version.
```

Build **vẫn exit 0**; đây là cảnh báo thông tin. Nếu muốn hết cảnh báo, nâng Node lên 22.12+ hoặc 20.19+.

### 5.4 Thiếu dependency và nhận diện Python 3.13

`-Check` kiểm tra Python 3.13 theo 3 bậc an toàn:
1. `uv python find 3.13`: nếu uv hoạt động bình thường, chấp nhận trực tiếp.
2. Fallback `.venv` dự án: nếu `uv python find` thất bại (ví dụ uv cache bị từ chối quyền trên Windows), script tự động kiểm tra `.venv\Scripts\python.exe` của dự án; nếu đúng Python 3.13 thì nghiệm thu OK.
3. Nếu cả hai đường đều không chứng minh được: báo lỗi rõ ràng yêu cầu chạy `uv python install 3.13` hoặc tạo `.venv` Python 3.13.

`-Check` cũng báo thiếu `.venv`/`node_modules` kèm đúng lệnh cần chạy (`uv sync` / `npm install`). Dùng
`-NoInstall` khi muốn chặn mọi bước cài qua mạng ngoài ý muốn.

### 5.5 Kết quả test phụ thuộc environment

Bộ test backend có một ca cần `ADMIN_TOKEN` **đã set trong environment** để mong đợi 401; nếu biến
chưa set, ca đó thấy 500 và báo fail. Vì vậy hãy export `ADMIN_TOKEN` trước khi chạy full suite
(xem lệnh ở §4).

## 6. Daily Radar — runner one-shot + Task Scheduler (s2-windows-scheduler)

### 6.1 Runner one-shot

```powershell
uv run python -m backend.app.radar.run_daily
```

Một lần chạy rồi thoát (không server, không thread, không mạng, không publish):
migration idempotent → mở database cục bộ đã cấu hình → gọi
`run_daily_radar_once` **đúng một lần** với thời điểm hiện tại thực và owner tất định
(`windows-task:radar-daily`) → in **một dòng JSON không secret** rồi thoát.

- **exit 0** = job đúng hợp đồng — kể cả `not_due` (chưa đến 07:00 VN) hay
  `already_completed` (identity hôm nay đã có trong ledger bền).
- **exit 1** = thất bại bất ngờ của job — ledger bền đã ghi `FAILED`
  (bounded retry theo hợp đồng s1); thông báo `error` chỉ gồm tên exception + thông điệp ngắn.

Tham số tùy chọn: `--window today|7d|30d|all` (mặc định `today`), `--owner`
(mặc định tất định), `--db-path <đường-dẫn>` (override DB — dùng cho smoke test
trên DB tạm mà không đụng `backend/data/radar.db`).

### 6.2 Đăng ký task hàng ngày 07:00 (chạy THỦ CÔNG bởi người dùng/coordinator)

```powershell
pwsh -File scripts/register_radar_task.ps1            # đăng ký idempotent
pwsh -File scripts/register_radar_task.ps1 -Status    # tra cứu trạng thái
```

Script đăng ký task **per-user** `VuHocAIRadar-Daily` (LogonType Interactive,
RunLevel Limited — không cần mật khẩu, không cần quyền admin), trigger **daily 07:00**
giờ địa phương, action chạy đúng runner trên bằng `uv` (đường dẫn tuyệt đối của uv +
working directory là đường dẫn tuyệt đối của repo, tính từ `$PSScriptRoot`),
kèm `StartWhenAvailable` (máy off lúc 07:00 thì bù chạy sau khi khởi động) và
giới hạn thời gian chạy 10 phút.

An toàn: đăng ký **idempotent** — task đã tồn tại thì in `already registered` và
thoát 0, **không chỉnh sửa, không xóa** (script không bao giờ
`Unregister-ScheduledTask`); thiếu tiên quyết (repo/uv/runner module) thì báo lỗi rõ
và exit 2; không có kết nối remote; không đụng database.

> **NOT_VERIFIED — chưa đăng ký task thật trên máy này.** Theo biên độ của tác vụ,
> hành động đăng ký Windows Task Scheduler được dành cho coordinator sau khi code đã
> verify. Đã kiểm chứng: parse cú pháp (PARSE_OK), hợp đồng nội dung (3 test trong
> `backend/tests/test_radar_daily_runner.py`), chế độ `-Status` (exit 1 rõ ràng khi
> task chưa tồn tại), và runner one-shot trên DB tạm (exit 0, JSON, ledger COMPLETED).
> Sau khi đăng ký, kiểm tra bằng `-Status` (State = Ready, NextRunTime = 07:00 ngày mai).

## 7. Ranh giới đã biết của bản localhost này

- Chỉ chạy **localhost** (`127.0.0.1`), không deploy, không push, không tạo remote.
- Bản ghi **REAL** hiện chỉ có **1 bài báo đã xuất bản kế thừa từ Vũ Học AI v0.3.1**; các bảng
  provider/model/quota chỉ có dữ liệu **SAMPLE**. Xem `docs/DATA_SOURCES.md`.
- **NOT_VERIFIED** (chưa đo được, không được coi là PASS): độ tươi dữ liệu từ nguồn ngoài/live network,
  gateway AI thật, và **smoke trên trình duyệt** (cả cổng mặc định 8000/5173 lẫn render DOM). Lý do:
  cổng mặc định đang bị server anh em giữ; trình duyệt chưa được điều khiển trong phiên này.
  Chi tiết và cách tự kiểm ở `docs/QA_REPORT.md`.
