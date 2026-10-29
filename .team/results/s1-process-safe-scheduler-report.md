# Task S1 Result — process-safe Daily Radar scheduler

- **Role**: worker
- **Task ID**: s1-process-safe-scheduler
- **Target**: Vũ Học AI Radar v1.0

## Files Changed/Added

1. `backend/app/migrate.py`:
   - Thêm trạng thái `RADAR_SCHEDULE_STATUS = ("RUNNING", "COMPLETED", "FAILED", "EXHAUSTED")`.
   - Thêm DDL bảng ledger `radar_schedule_runs` (additive, idempotent `CREATE TABLE IF NOT EXISTS` + CHECK constraints).
   - Thêm index `idx_radar_schedule_runs_status`.
2. `backend/app/radar/scheduler.py` (mới):
   - Quản lý logical run identity theo ngày lịch địa phương `YYYY-MM-DD` tại 07:00 Asia/Ho_Chi_Minh (`run_identity_for`).
   - Claim và lease hữu hạn (`claim_run`), chống race condition giữa các kết nối/tiến trình SQLite (`BEGIN IMMEDIATE`), tại mỗi thời điểm tối đa 1 owner có active lease.
   - Bounded lease reclaim sau finite timeout (`lease_seconds`, mặc định 300s).
   - Bounded retry (`max_attempts`, mặc định 3): vượt quá trần chuyển sang `EXHAUSTED` và dừng retry.
   - Idempotence qua restart: identity đã `COMPLETED` không bao giờ chạy lại.
   - `run_daily_radar_once`: chỉ tính toán cục bộ (`daily_radar`), không publish, không verify, không sửa DRAFT/SAMPLE, không gọi mạng.
   - Đồng hồ giả hoàn toàn (`now` tham số hóa), không thread nền, không sleep.
3. `backend/app/main.py`:
   - Tích hợp scheduler ledger vào endpoint `GET /api/radar` (thêm trường `durable` trong snapshot) và `POST /api/admin/radar/refresh` (chạy qua scheduler ledger, bảo lưu xác thực `require_admin` trước DB).
4. `backend/tests/test_radar_scheduler.py` (mới):
   - 19 test cases toàn diện: schema ledger, claim race giữa 2 SQLite connections, lease expiry reclaim, failed run retry bound / EXHAUSTED, idempotence sau restart, fake-clock boundary 07:00 local time, no-publish / no-mutation / no-network isolation, manual refresh auth-before-DB.

## Test & Gate Verification

- `uv run python -m unittest backend.tests.test_radar_scheduler`: exit code `0` (19/19 tests PASS).
- `uv run python -m unittest backend.tests.test_radar_daily`: exit code `0` (27/27 tests PASS).
- `npm run build`: exit code `0` (Vite build thành công).
- `uv run python checks/p3.py`: exit code `0` (PASS 13/13).
- `uv run python checks/p4.py`: exit code `0` (PASS 15/15).
- `uv run python checks/p5.py`: exit code `0` (PASS 11/11).
- `git diff --check`: exit code `0` (không có trailing whitespace / conflict marker).

## Ruling

`PASS`
