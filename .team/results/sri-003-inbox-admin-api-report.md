# sri-003 — Authenticated inbox admin API (báo cáo kết quả)

- Commit: **73b598178552a419164ce9e18f3e0ad6d758b82b** (`feat: add authenticated inbox admin API`)
- Worktree: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web\.worktrees\t_e6897cdd`
- Ngày: 2026-10-27

## [ĐÃ LÀM]

- Thêm 3 endpoint admin-only:
  - `POST /api/admin/inbox/scan` — quét thư mục inbox do **server tự quản** thông qua `resolve_inbox_dir()` (nginx env `SCHEDULED_INBOX_DIR` hoặc mặc định `backend/inbox`). Không nhận path/artifact body/source/model từ request.
  - `GET /api/admin/inbox/runs` — ledger run inbox qua allowlist `_RUN_KEYS`, `ORDER BY processed_at DESC, run_id DESC`, `limit` bounded (bind param).
  - `GET /api/admin/inbox/articles` — projection allowlist `_ARTICLE_KEYS` (`id, title, category, article_status, url, data_origin`), chỉ `WHERE source = SOURCE_ID` và loại `data_origin = 'SAMPLE'`; không `SELECT *`, không raw/provenance/quarantine path/token/registry config.
- Mọi handler gọi `require_admin(request)` ở dòng đầu, **trước** khi mở/kết nối DB hay ngó inbox (đúng convention `backend/app/main.py` hiện có).
- Query parameter list được đóng băng: chỉ cho phép `limit` (`INBOX_LIST_QUERY_PARAMS`), không nhận param lạ (422), `limit` phải là số không âm và `<= INBOX_MAX_LIMIT` (500), dùng bind parameter trong SQL.
- Scan giữ nguyên transaction/idempotency/quarantine của `scan_inbox()` (chỉ DRAFT; `INSERT OR IGNORE`; quarantine nguyên trạng). Không thêm publish shortcut — workflow duyệt có sẵn giữ nguyên là đường duy nhất tới PUBLISHED.
- Test-first: tạo `backend/tests/test_inbox_admin_api.py` (17 test) — RED trước, rồi GREEN.
- Response scan chỉ trả allowlist: `status, scanned_at, imported_runs, skipped_runs, quarantined_runs, accepted_findings, skipped_findings` (bộ đếm `InboxScanResult` + mốc thời — không raw/provenance).

## [BẰNG CHỨNG]

1. Scope đúng 3 file cho phép:
   `git diff-tree --no-commit-id --name-only -r 73b5981` → exit 0
   ```
   backend/app/inbox/service.py
   backend/app/main.py
   backend/tests/test_inbox_admin_api.py
   ```
2. `git diff 73b5981^ 73b5981 --check` → exit 0 (không khoảng trắng cuối dòng / dòng trống).
3. Test sri-003: `uv run python -m unittest backend.tests.test_inbox_admin_api` → `Ran 17 tests ... OK`, EXIT=0.
4. Các module inbox liên quan riêng lẻ:
   - `backend.tests.test_public_articles` → `6 tests OK`, EXIT=0
   - `backend.tests.test_scheduled_inbox` → `11 tests OK`, EXIT=0
   - `backend.tests.test_inbox_editorial` → `16 tests OK`, EXIT=0
5. Lưu ý regression: `test_admin_workflow` có 1 fail **có sẵn từ trước, không phải do commit này**:
   `test_unauthenticated_admin_calls_fail_before_touching_the_database` — `admin_sources` trả `500 != 401`.
   - File ngoài scope sri-003 (`backend/tests/test_admin_workflow.py` không bị commit `73b5981` đụng tới).
   - Đã chạy lại đúng test đó trên commit cha `0013b5c` (detached worktree): fail **giống hệt** (`500 != 401 : admin_sources`) → xác nhận pre-existing, không do sri-003 gây ra. Handler `admin_sources` không được sửa trong commit này.
   - Không xử lý/tuyên bố PASS cho phần này; đề nghị tách thành task riêng nếu cần (ngoài phạm vi sri-003).

## [RULING]

Commit `73b5981` đạt phạm vi và ràng buộc an toàn của sri-003:
- Auth-before-DB: `require_admin(request)` là hành động đầu tiên của cả 3 handler; token thiếu → 401, token sai → 403.
- Scan không nhận điều khiển từ request, chỉ dùng cấu hình inbox server-owned.
- Response dùng allowlist tường minh; không lộ raw report/content, provenance blob, quarantine path, token, registry config, reviewer note, secret.
- Scanner giữ nguyên DRAFT-only/idempotent/quarantine; `/api/articles` công khai không thể trả DRAFT/PENDING_REVIEW/SAMPLE/private.
- Query param/SQL dùng bind + bounded; không outbound network, không filesystem path disclosure, không dependency mới.

Kết luận cho **các tiêu chí thuộc phạm vi sri-003**: đạt (evidenced bởi 17/17 test sri-003 + các module inbox liên quan OK). Phần regression `test_admin_workflow` có fail pre-existing ngoài scope → **không tuyên bố PASS toàn bộ regression command của task**; ghi nhận trung thực để reviewer/người quyết định xử lý riêng.

## [CÂU HỎI]

- Fail `admin_sources` (`500 != 401`) trong `test_admin_workflow` là pre-existing trên commit cha — có nên tạo task riêng để sửa handler `admin_sources` (khi `ADMIN_TOKEN` chưa cấu hình) hay không? (Ngoài phạm vi sri-003.)
- Có muốn tôi viết thêm test cho trường hợp `limit` param hợp lệ/biên và bài DRAFT không có `url` rồi? (Hiện test đã phủ các ca chính theo task.)
