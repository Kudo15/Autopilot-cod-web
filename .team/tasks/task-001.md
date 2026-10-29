# TASK 001 — Proxy và public article feed | harness: Codex local task | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web` | Stack: React 19 + Vite 7, FastAPI + SQLite, Python qua uv.
- Kế hoạch: `.team/plans/remaining.md`, Task 1 (PLAN phase 5.1). Đọc thêm `.team/audit.md` để biết bằng chứng hiện tại.
- File liên quan và phạm vi: `vite.config.js` thêm proxy; `src/App.jsx`, `src/components/GroupView.jsx`, `src/styles.css` nối public feed/error UI; `backend/app/main.py` điều chỉnh public article query. Không sửa `checks/`, `PLAN.md`, `docs/MISSION.md`, `.team/CHARTER.md`.
- Hiện trạng: backend `/api/articles` tồn tại nhưng trả dữ liệu chưa lọc public; frontend chưa gọi API; `checks/p5.py` hiện FAIL vì thiếu proxy/feed.

## TÁC VỤ (một việc duy nhất, 2–5 phút)

Hoàn thiện kết nối frontend ↔ backend cho public article feed: proxy Vite `/api` tới `http://127.0.0.1:8000`, frontend gọi `/api/articles` và render dữ liệu SQLite thật; khi backend tắt hoặc response lỗi phải hiện error state, không trắng trang. Public feed phải loại record không được publish hoặc có `data_origin = SAMPLE` nếu schema hiện có các cột đó; giữ loading/empty/error và dark/light hiện tại.

Khuôn mẫu: Fullstack Software Developer. Biến thể hiện đại hóa: giữ React/FastAPI/SQLite hiện có, chỉ bind localhost, dùng API allowlist/parameterized query, không thêm framework UI, không nhúng dữ liệu giả.

## INTERFACES BẮT BUỘC

- Backend: `GET /api/articles` trả HTTP 200 và JSON array; mỗi item chỉ chứa public article fields đang có trong schema, ưu tiên `article_status = 'PUBLISHED'` và `data_origin != 'SAMPLE'` khi các cột tồn tại. Nếu DB chưa có bài public, trả `[]` chứ không seed/đưa SAMPLE vào public.
- Frontend: thực hiện `fetch('/api/articles')`; trạng thái `loading`, `empty`, `error` phải được dùng thật trong component. Lỗi HTTP/non-JSON/network phải chuyển sang error state có nút thử lại.
- Vite: `server.proxy['/api'].target` phải là `http://127.0.0.1:8000` và dev server vẫn bind `127.0.0.1`.

## QUY TẮC BẤT DI BIẾN

- TDD: viết test/fixture fail trước khi sửa production; nếu không có test runner phù hợp, tạo focused backend test trong `backend/tests/**` hoặc ghi rõ lý do trong report.
- Không mở rộng sang importer, model explorer, admin auth, collector hoặc UI redesign; đó là task sau.
- Không bịa article, quota, provider, promotion; SAMPLE/DRAFT/UNVERIFIED không được public.
- Không hardcode API key/secret; không ghi log secret; không gửi request ngoài localhost.
- Không tự dispatch subagent/reviewer. Worker chỉ làm task này, tự review, chạy test, ghi report vào `.team/tasks/task-001-report.md`, và commit các file implementation của task.
- Narrate tối đa 1 dòng giữa các tool call.

## HOÀN THÀNH KHI

- `vite.config.js` có proxy `/api` đúng target và localhost binding.
- Frontend gọi `/api/articles`, render article list khi backend trả dữ liệu, và chịu được loading/empty/error.
- Public backend API không lộ SAMPLE/DRAFT/internal fields.
- `npm run build` exit 0.
- `PYTHONIOENCODING=utf-8 python checks/p5.py` chạy ngoài sandbox exit 0; nếu sandbox chặn spawn/uv, ghi nguyên văn và chạy lại có quyền theo coordinator.

## BÁO CÁO WORKER

Ghi đầy đủ vào `.team/tasks/task-001-report.md`:

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] lệnh đã chạy + exit code/output chính xác
[RULING] quyết định tự chủ — nếu có
[CÂU HỎI] chỉ khi bế tắc hoàn toàn
```
