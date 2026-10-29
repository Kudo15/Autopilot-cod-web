# Task O1 Preflight Fix Report — 2026-10-27

## Tóm tắt nhiệm vụ
- Task ID: `o1-preflight-fix`
- Mục tiêu: Bổ sung cơ chế fallback an toàn vào `scripts/dev.ps1 -Check` để khi `uv python find 3.13` không khả dụng (ví dụ uv cache bị từ chối quyền trên Windows), `.venv\Scripts\python.exe` của dự án (nếu đúng Python 3.13) vẫn đáp ứng điều kiện tiên quyết.
- Báo lỗi rõ ràng nếu cả uv lẫn .venv đều không chứng minh được Python 3.13.
- Bảo toàn nguyên vẹn: không tự cài qua mạng (`-NoInstall`), chỉ bind `127.0.0.1`, chỉ kill đúng cây tiến trình con của script qua `/PID` + `/T`.
- Ghi nhận trung thực: cổng 8000 đang bị uvicorn PID 17468 chiếm; không claim CHECK OK khi cổng 8000 đang bận.

## Thay đổi đã thực hiện

1. `scripts/dev.ps1`:
   - Hàm `Invoke-Preflight` kiểm tra Python 3.13 theo 3 bậc:
     - Bậc 1: `uv python find 3.13` — tin exit code của uv (exit 0 = đã tìm thấy Python 3.13).
     - Bậc 2 (fallback): Nếu uv không có hoặc `uv python find` thất bại, kiểm tra `sys.version_info` từ `$venvPython` (`.venv\Scripts\python.exe`). Nếu phiên bản bắt đầu bằng `3.13`, nghiệm thu OK kèm log rõ ràng: `Python 3.13 project venv: $venvPython`.
     - Bậc 3: Nếu cả hai đường đều không chứng minh được, thêm problem rõ ràng vào danh sách: `Thieu Python 3.13 cho du an: chay uv python install 3.13 hoac tao .venv Python 3.13`.
   - Giữ nguyên toàn bộ cơ chế bảo vệ: không tự cài khi không có quyền, chỉ bind `127.0.0.1`, dừng tiến trình theo PID.

2. `backend/tests/test_startup_script.py`:
   - Bổ sung test tĩnh `test_python_preflight_falls_back_to_project_venv` kiểm chứng hợp đồng 3 bậc trong `scripts/dev.ps1`.
   - Bổ sung `test_frontend_proxy_follows_the_selected_backend_port`.

3. `README_LOCAL.md`:
   - Cập nhật số lượng test backend mới nhất: **Ran 453 tests, OK**.
   - Cập nhật bảng kết quả đo thật: `pwsh -File scripts/dev.ps1 -Check` cổng mặc định trả **exit 1** vì cổng 8000 đang bị PID 17468 chiếm (không nhận bừa là OK).
   - Mục §5.4: Ghi rõ hợp đồng nhận diện Python 3.13 theo 3 bậc an toàn.

## Kết quả kiểm thử thực tế

1. **Focused startup script tests**:
   - Lệnh: `uv run --no-sync python -m unittest discover -s backend/tests -p "test_startup_script.py" -v`
   - Kết quả: **Ran 15 tests, OK** (exit 0).

2. **Full backend regression suite**:
   - Lệnh: `ADMIN_TOKEN='o1-local-qa-token-not-a-secret' uv run --no-sync python -m unittest discover -s backend/tests -p "test_*.py"`
   - Kết quả: **Ran 453 tests, OK** (exit 0).

3. **Preflight script thật (`dev.ps1 -Check`)**:
   - Chạy trên cổng mặc định (cổng 8000 đang bị PID 17468 chiếm):
     - Lệnh: `pwsh -NoProfile -File scripts/dev.ps1 -Check`
     - Kết quả: **exit 1** — báo lỗi đúng: `cong 8000 (backend) dang ban: dung tien trinh cu tren cong do roi chay lai`.
   - Chạy với cổng dự phòng tự do (8123/5273) để kiểm tra preflight:
     - Lệnh: `pwsh -NoProfile -File scripts/dev.ps1 -Check -BackendPort 8123 -FrontendPort 5273`
     - Kết quả: **exit 0** — `CHECK OK: 8123/127.0.0.1 va 5273/127.0.0.1 san sang khoi dong.`

4. **Kiểm thử trường hợp biên fallback (shim uv lỗi exit 1)**:
   - Mô phỏng uv lỗi cache:
     - Nhánh fallback kích hoạt: `[WARN] uv python find 3.13 khong kha dung (exit 1); se kiem tra .venv cua project.`
     - Nhận diện thành công: `[ OK ] Python 3.13 project venv: ...\.venv\Scripts\python.exe`
     - Cổng tự do 8123/5273: `CHECK OK` (exit 0).
     - Cổng mặc định 8000: Báo đúng cổng 8000 đang bận (exit 1).
   - Mô phỏng cả uv lẫn venv đều thiếu/sai:
     - Báo lỗi rõ ràng: `Thieu Python 3.13 cho du an: chay uv python install 3.13 hoac tao .venv Python 3.13` (exit 1).

5. **Frontend build**:
   - Lệnh: `npm run build`
   - Kết quả: **exit 0** (dist/index.html 0.47 kB, CSS 14.84 kB, JS 234.63 kB).

6. **Diff & Whitespace check**:
   - Lệnh: `git diff --check`
   - Kết quả: **exit 0** (chỉ có warning chuyển đổi CRLF).
