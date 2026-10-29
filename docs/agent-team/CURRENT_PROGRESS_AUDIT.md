# Current Progress Audit — fresh Hermes GUI evidence

Ngày: 2026-10-27 (SEA Standard Time, UTC+07)  
Worktree: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`  
HEAD: `f41b1298eaac058f14f1a6d1ef8cc7e6b8a137da` — nhánh `autopilot/run-live` (ahead origin 29 commit)  
Harness: Hermes GUI, source `cli`, pid 26384  
Nguyên tắc: mọi mục dưới đây là **BẰNG CHỨNG MỚI (FRESH)** đo được trong phiên này; phân biệt rạch ròi với tài liệu lịch sử.

## 1. Kết luận ngắn

Nền phase 1–5 trọng tài referee `python checks/p1.py` đến `checks/p5.py` đều **PASS (100%)** khi chạy ngoài sandbox với console UTF-8. Frontend build `npm run build` exit 0 (cảnh báo Node 22.11.0 thấp hơn floor khuyến nghị 22.12+).
Backend unittest qua `uv run python -m unittest discover` chạy được **404 tests** nhưng **FAILED**:
- Khi thiếu biến `ADMIN_TOKEN`: 3 failures (1 do cấu hình môi trường test, 2 do code/fixture).
- Khi có `ADMIN_TOKEN` hợp lệ: **2 failures thật** tại `test_radar_daily.py` (fixture hardcode ngày 2026-10-25 + đồng hồ thật → rơi ngoài cửa sổ `today` → trả `SIGNAL_WEAK` thay vì `CURRENT`).
Vì vậy chưa thể công bố Release Candidate. Toàn bộ 18 file mã nguồn dirty có sẵn được bảo toàn nguyên vẹn.

## 2. Evidence ledger (đo fresh trong phiên này)

| DoD / kiểm tra | Trạng thái | Lệnh chạy | Exit code | Bằng chứng thực tế |
|---|---|---|---|---|
| P1 frontend scaffold/build | PASS | `PYTHONIOENCODING=utf-8 python checks/p1.py` | 0 | 15/15 checks OK: package.json, index.html, #root, bundle, không secret |
| P2 UI states/theme/categories | PASS | `PYTHONIOENCODING=utf-8 python checks/p2.py` | 0 | 9/9 checks OK: 7/7 nhãn nhóm, dark/light, localStorage, 3 trạng thái |
| P3 FastAPI/SQLite/health/articles | PASS | `PYTHONIOENCODING=utf-8 python checks/p3.py` | 0 | 13/13 checks OK: uvicorn port 50425, health 200, articles mảng 1 phần tử |
| P4 migration/seed/idempotency | PASS | `PYTHONIOENCODING=utf-8 python checks/p4.py` | 0 | 15/15 checks OK: 12 bảng, migration/seed idempotent, 24 bản ghi, 58 ô SAMPLE |
| P5 FE↔BE proxy/feed | PASS | `PYTHONIOENCODING=utf-8 python checks/p5.py` | 0 | 11/11 checks OK: proxy 8000, 1 bài từ DB, build exit 0, không secret |
| Production build | PASS (warning) | `npm run build` | 0 | Vite v7.3.7, 41 modules, dist/index.html + assets JS (222.9 kB)/CSS (12.2 kB); cảnh báo Node 22.11 < 22.12+ |
| Full backend regression | FAIL | `PYTHONIOENCODING=utf-8 uv run python -m unittest discover -s backend/tests -p "test_*.py"` | 1 | Ran 404 tests trong ~5s. Không ADMIN_TOKEN: 3 failures; có ADMIN_TOKEN: 2 failures |
| SQLite table & counts | OBSERVED | Script Python chỉ-đọc trên `file:backend/data/radar.db?mode=ro` | 0 | 13 bảng (12 MISSION + scheduled_inbox_runs); REAL=3 (1 article id 900002 PUBLISHED LEGACY_v031, 1 raw_item, 1 source), SAMPLE=21 across 11 tables |
| Browser / E2E config | BLOCKED | `ls playwright.config.* e2e`; `npx --no-install playwright --version` | 1 | Không có file config hay e2e/; package.json/lock không có playwright; npx exit 1. Runtime chromium-1243 có sẵn trong %LOCALAPPDATA%\ms-playwright |
| Public/private boundary | OBSERVED | `curl` live trên 127.0.0.1:8000 + grep bundle dist | 0 | GET /api/articles chỉ trả 1 bài REAL; GET /api/admin/* trả 401 khi không token; dist/assets bundle không chứa secret/private registry |
| Startup script | BLOCKED | `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1 -Check` | 1 | Prerequisites đủ (Node/npm/uv/Python 3.13/.venv/node_modules); báo lỗi đúng "cong 8000 dang ban" (PID 17468 python uvicorn) |

## 3. Chi tiết 2 failing tests (code / fixture defect)

File: `backend/tests/test_radar_daily.py:484-560`
1. `test_admin_refresh_with_valid_token_recomputes_locally_and_marks`:
   `AssertionError: 'SIGNAL_WEAK' != 'CURRENT'` tại dòng 536.
2. `test_public_radar_returns_schedule_with_current_default_window`:
   `AssertionError: 'SIGNAL_WEAK' != 'CURRENT'` tại dòng 553.

**Root cause:** Cả hai test sử dụng fixture `UPDATE_ARTICLE = "2026-10-25T00:30:00+07:00"` nhưng gọi
route với `window="today"` dựa vào `datetime.now()` thật của hệ thống. Tại ngày audit (2026-10-27),
bài viết rơi ra ngoài cửa sổ 24h của ngày hôm nay, bộ lọc SQL trả về rỗng, `daily.py:322` gán
`status = STATUS_SIGNAL_WEAK`. Đây là vi phạm tính tất định của test suite (đúng mục tiêu task Q1
trong kế hoạch `.team/plans/finish-all.md`).

## 4. Ranh giới an toàn và phạm vi audit

- **Không sửa file cấm**: `checks/`, `PLAN.md`, `docs/MISSION.md`, mã nguồn sản phẩm (`src/**`, `backend/app/**`) không bị sửa đổi.
- **Không push / merge / deploy**: không tạo remote mới; `git diff --check` sạch lỗi whitespace (chỉ có warning CRLF).
- **Bảo toàn thay đổi dirty có sẵn**: 18 file modified từ trước (JSX `import React`, `VITE_BACKEND_PORT`, contract tests) giữ nguyên 100%.

## 5. Phân biệt lịch sử vs fresh

- `docs/QA_REPORT.md` (HEAD `fb3cb14`, 2026-10-25) báo cáo 330 tests OK: đây là **bằng chứng lịch sử** trước khi thêm các test inbox (sri-001..sri-003) và trước khi ngày trôi qua làm hỏng fixture ngày 25.
- `.team/audit.md` phần cũ ghi P5 FAIL: đây là **bằng chứng lịch sử** thời điểm P0; hiện tại P5 đã PASS fresh 11/11.
