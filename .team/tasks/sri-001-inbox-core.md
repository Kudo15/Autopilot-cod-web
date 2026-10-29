# TASK sri-001-inbox-core — structured inbox schema, scan, persistence | harness: hermes-kanban | worktree: Hermes-managed

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`.
- Stack: Python 3.13, FastAPI, SQLite, `unittest`; React/Vite exists but is out of scope here.
- Approved spec: `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`.
- Exact task contract: `docs/superpowers/plans/2026-10-25-scheduled-radar-inbox-plan.md`, **Task 1 only**.
- Existing patterns to preserve: `backend/app/ingest/importers.py` for normalize/dedup/transactions; `backend/app/migrate.py` for additive idempotent migrations; `backend/app/database.py` for DB paths. Existing manual import must continue to work unchanged.
- The root checkout is dirty. Work only in your Hermes worktree, stage/commit only files you change, and never discard or rewrite unrelated work.

## TÁC VỤ (một việc duy nhất)

Act as a senior full-stack backend engineer. Read the approved spec and Task 1 section first; they are the requirements with exact values. Implement the structured scheduled-radar inbox core using TDD.

Create `backend/app/inbox/` with strict schema-version-1 models and a scanner that consumes only completed JSON artifacts from a server-controlled inbox directory. Add the additive `scheduled_inbox_runs` migration and a focused unittest module. The scanner must write provenance-backed `REAL/DRAFT` raw/article records transactionally, reuse existing normalization/dedup semantics, be idempotent by `run_id + content_hash`, ignore `*.tmp`, quarantine invalid or altered-replay artifacts safely, and never execute artifact text as instructions/paths/commands.

Use only two report kinds: `provider_harness_radar` and `tip_trick_radar`. Accept exactly the fields/types/states in the approved design; reject unknown fields, absent canonical URLs, invalid timestamps/statuses and oversized/malformed input. Do not create API routes, UI, AI enrichment, scheduled prompts, or deployment work.

Khuôn mẫu tham khảo đã dùng: **Fullstack Software Developer** — vai trò backend cụ thể, đầu ra testable, phạm vi giới hạn và báo cáo bằng chứng. Hiện đại hóa: dùng codebase thật, schema allowlist, transaction/idempotency và security boundary của dự án.

## QUY TẮC BẤT DI BIẾN

- TDD: viết test fail trước; không có production code trước test. Nếu có code trước test, xóa và viết lại từ test.
- Chỉ sửa/tạo: `backend/app/inbox/**`, `backend/app/migrate.py`, `backend/app/database.py` (chỉ nếu cần config path), `backend/tests/test_scheduled_inbox.py`; nếu cần một test fixture thì đặt dưới `backend/tests/fixtures/`.
- Không sửa `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend, API route, prompt schedule hoặc deployment.
- Không thêm dependency mới nếu stdlib/Pydantic hiện hữu đủ dùng; không hardcode secret.
- `run_id` lặp với hash khác phải bị quarantine, không ghi đè review/dữ liệu trước.
- Mỗi artifact hợp lệ là một transaction; lỗi của artifact không để lại raw/article/source nửa chừng.
- Không tự publish: mọi article mới là `data_origin='REAL'`, `article_status='DRAFT'`.
- Narrate tối đa 1 dòng giữa các tool call. Mơ hồ thì tự quyết theo spec, ghi `Ruling: ... — why — cost` vào báo cáo thay vì chờ.

## HOÀN THÀNH KHI

1. Các test mới chứng minh: 1 report 3 findings tạo 3 raw + 3 draft; re-scan idempotent; altered `run_id` bị quarantine; `*.tmp` bị bỏ qua; malformed/unknown/injection-shaped input không tạo side effect.
2. `uv run python -m unittest backend.tests.test_scheduled_inbox -v` xanh.
3. `uv run python -m unittest backend.tests.test_importers -v` vẫn xanh.
4. `uv run python -m backend.app.migrate` chạy lặp lại exit 0.
5. Commit scoped changes trong worktree với message dạng `feat: add scheduled radar inbox core`.
6. Tự review một lượt và ghi report tại `.team/results/sri-001-inbox-core-report.md` trong worktree, theo mẫu:

```
[ĐÃ LÀM] tóm tắt tối đa 3 dòng
[BẰNG CHỨNG] lệnh + exit code/kết quả
[RULING] quyết định tự chủ (nếu có)
[CÂU HỎI] chỉ khi bế tắc hoàn toàn
```
