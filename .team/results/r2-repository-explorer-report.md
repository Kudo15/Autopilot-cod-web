# Task R2 — GitHub repository explorer — report

Worker: r2-repository-explorer (Hermes, worker role) · 2026-10-27 · bounded, no network

## Phạm vi
- Chỉ sửa file nằm trong FILES_ALLOWED của task pack:
  `backend/app/main.py`, `backend/app/migrate.py`, `backend/tests/test_repository_explorer.py`,
  `src/data/groups.js`, `src/App.jsx`, `src/components/RepositoryView.jsx`, `src/styles.css`, `.team/results/**`.
- Không push, không deploy, không gọi GitHub API, không seed row public nào.
- KHÔNG chạy migrate trên DB thật trong test: mọi test dùng DB tạm (tmp dir / in-memory).

[ĐÃ LÀM]

### 1. Schema (backend/app/migrate.py)
- Bảng additive `repositories` (CREATE TABLE IF NOT EXISTS, nằm trong transaction migration có sẵn,
  KHÔNG thuộc BUSINESS_TABLES 12 bảng MISSION — cùng kiểu với `scheduled_inbox_runs`):
  `id, canonical_url (NOT NULL), name (NOT NULL), purpose, use_case, tradeoffs, license,
  updated_at, difficulty, provenance, verification_status (NOT NULL DEFAULT 'UNVERIFIED',
  CHECK theo VERIFICATION_STATUS), data_origin (NOT NULL DEFAULT 'REAL', CHECK REAL|SAMPLE), created_at`.
- `difficulty` CHECK theo hằng số mới `REPOSITORY_DIFFICULTY = (BEGINNER, INTERMEDIATE, ADVANCED, UNKNOWN)`.
- Index: `idx_repositories_verification` + unique partial index
  `uq_repositories_canonical_url` (chỉ dữ liệu non-SAMPLE, khớp convention của raw_items/articles).
- KHÔNG có seed: DB mới sau migration có 0 row (đã test).

### 2. API (backend/app/main.py — section mới cuối file, additive)
- `GET /api/repositories`:
  - Query params DUY NHẤT được phép: `q, difficulty, license, verification_status, limit`
    (tham số lạ -> 422, liệt kê tên).
  - `q` <= 200 ký tự, LIKE bind parameter trên name/purpose/use_case.
  - `difficulty` phải thuộc allowlist; `verification_status` phải thuộc VERIFICATION_STATUS;
    `license` phải khác rỗng; `limit` 1..100 (mặc định 50). Sai -> 422.
  - SQL toàn bộ parameterized (`?`); SELECT tường minh, không `SELECT *`.
  - Public default (không có verification_status): LOẠI row SAMPLE, CHỈ canonical
    `https://github.com/%`, yêu cầu `VERIFIED` + provenance khác rỗng + license khác rỗng
    (row 5 trong test: lookalike `https://github.com.example.com/...` bị loại).
  - Có `verification_status`: chế độ xem lịch sử theo trạng thái — vẫn loại SAMPLE,
    vẫn yêu cầu canonical GitHub URL.
  - Response: đúng 10 cột `PUBLIC_REPOSITORY_FIELDS` — KHÔNG provenance, KHÔNG data_origin.
  - Không có bất kỳ cuộc gọi mạng nào (test patch socket.socket để chứng minh).

### 3. UI
- `src/data/groups.js`: thêm nhóm `{ id: 'repository-explorer', name: 'Repository Explorer' }`.
- `src/components/RepositoryView.jsx` (mới): gọi `GET /api/repositories` với
  search (q) + filter difficulty + license + verification_status; đủ trạng thái
  loading / error (có nút "Thử lại") / empty (thông báo khác nhau cho default vs
  chế độ lịch sử); card hiển thị purpose/use_case/tradeoffs/license/difficulty/
  updated_at; canonical URL chỉ render thành link khi đúng `https://github.com/...`
  (parse bằng `new URL`, rel="noreferrer noopener"), còn lại không liên kết.
- `src/App.jsx`: route nhóm `repository-explorer` -> `<RepositoryView />`; nhóm này
  không gọi feed `/api/articles`.
- `src/styles.css`: thêm block styles `.repo-*` / `.repository-*` (additive, dùng
  CSS variables hiện có).

### 4. Tests (backend/tests/test_repository_explorer.py — 13 tests)
- Migration trên DB tạm (tmp dir + patch DATA_DIR/DB_PATH của cả `database` và `migrate`):
  đúng 13 cột/không-thiếu, idempotent (chạy 2 lần giữ row), DB mới = 0 row (không seed).
- Query trên in-memory DB + patch `main.get_connection` (không DB thật, không mạng):
  - query allowlist: `order_by=provenance`, `bogus=1` -> 422; 5 params cho phép -> 200.
  - SAMPLE exclusion: default lẫn chế độ history (`verification_status=UNVERIFIED` vẫn loại row SAMPLE).
  - Invalid URL exclusion: `javascript:bad`, gitlab.com, lookalike domain, non-GitHub đều loại.
  - Default yêu cầu VERIFIED + provenance + license (rows noprovenance/nolicense bị loại).
  - Field allowlist: response key set == PUBLIC_REPOSITORY_FIELDS, không provenance/data_origin.
  - Bounded limit: default <= 50, `limit=3` tôn trọng, `limit=0/101/abc` -> 422.
  - SQL injection trong `q` chỉ là bind parameter, bảng nguyên vẹn sau đó.
  - No-network: patch `socket.socket` không được gọi.
- Lưu ý: file test này đã có phiên bản tối thiểu (3 tests) từ trước trong working tree
  (untracked) — tôi GIỮ nguyên 3 tests đó và mở rộng, không ghi đè bừa.

[BẰNG CHỨNG]
- Focused: `uv run python -m unittest backend.tests.test_repository_explorer -v`
  -> `Ran 13 tests ... OK` (exit 0).
- Full backend: `uv run python -m unittest discover -s backend/tests -t .`
  -> `Ran 441 tests in 5.429s ... OK` (exit 0).
- Frontend: `npm run build` -> `✓ built in 885ms` (dist/assets/index-DyptceNv.js 229.20 kB).
- `git diff --check` -> exit 0 (không lỗi whitespace; chỉ có CRLF autocrlf warnings vốn có sẵn).
- `uv run python -c "from backend.app.main import app"` -> import ok.

[BẰNG CHỨNG bổ sung — sự thật cần nói]
- `backend/app/main.py` trong working tree có thay đổi chưa commit từ task khác (lúc đọc lần đầu
  file là 1360 dòng, trên disk lúc patch là ngắn hơn — phần `/api/offers` + admin verification
  bị định nghĩa 2 lần trong snapshot ban đầu; bản trên disk đã sạch hơn). Tôi chỉ THÊM section
  mới ở cuối file, không sửa/chỉnh dòng hiện có ngoài 1 dòng import. Chặn `git diff --check` và
  full test suite (441 tests OK) xác nhận không phá gì.
- `src/App.jsx` working tree cũng có changes chưa commit của task Promotion (PROMOTION_GROUP_ID)
  — tôi layer thêm repository group trên đó, giữ nguyên logic promotion.

[RULING]
- Ruling: thêm nhóm MỚI `repository-explorer` thay vì gộp vào `provider-comparison`
  — lý do: `provider-comparison` hiện là nhóm feed bài viết (GROUP_VIEW) bình thường,
  gắn RepositoryView vào đó phải xoá feed hiện có = sửa hành vi ngoài task; nhóm mới là
  additive 100%. Chi phí nếu sai: chỉ thiếu 1 nhóm sidebar, revert groups.js + App.jsx là xong.
- Ruling: `verification_status` filter = chế độ xem lịch sử (vẫn loại SAMPLE + vẫn bắt
  canonical GitHub URL), theo precedent `GET /api/offers` (status history mode) trong repo.
  Chi phí nếu sai: chỉ là hành vi filter rộng hơn dự định, luật default public không đổi.
- Ruling: license là exact-match bind parameter (không enum allowlist) — tập license GitHub
  là mở (MIT, Apache-2.0, GPL-3.0, custom...); allowlist đóng sẽ chặn repo thật. q/difficulty/
  verification_status/limit vẫn strict allowlist. Chi phí nếu sai: filter license kém hữu ích
  hơn 1 chút, không có lỗ an toàn (vẫn parameterized).
- NOT_VERIFIED: UI chưa chạy e2e trong browser (task chỉ yêu cầu build + unit test;
  e2e nằm ở nhóm kiểm thử browser của đội). API đã được test qua handler thật (Request scope).

## Bước tiếp theo
1. Reviewer chạy lại: `uv run python -m unittest backend.tests.test_repository_explorer -v`,
   `uv run python -m unittest discover -s backend/tests -t .`, `npm run build`, `git diff --check`.
2. Nếu muốn UI thật có dữ liệu: cần bước IMPORT/ADMIN (ngoài task r2) để nạp repo REAL
   đã xác minh vào bảng `repositories` — task này cố ý không seed và không có endpoint
   write (chỉ-đọc).
3. E2E browser cho nhóm Repository Explorer (loading/empty/error) nếu đội muốn nghiệm thu UI.
4. Cân nhắc (task sau): unique constraint chỉ ép non-SAMPLE — nếu sau này có admin import,
   nên đi qua cùng ràng buộc này.
