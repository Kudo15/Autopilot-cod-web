# TASK 003 — Import Markdown/CSV/JSON | harness: Codex local task | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

- Repo: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web` | FastAPI + SQLite, Python qua uv.
- Plan: `.team/plans/remaining.md`, Task 3 (PLAN phase 6.2). Predecessor Task 2 provides `backend.app.ingest.normalize.normalize_item` and `NormalizedItem`.
- Scope: `backend/app/main.py`, new `backend/app/ingest/importers.py`, `backend/tests/**`; do not modify checks/PLAN/docs/MISSION/frontend.
- Admin authorization is completed in Task 8; for this task keep endpoint namespace `/api/admin/import` and use a clearly isolated temporary/internal guard without exposing data publicly, or document the boundary if auth is deferred.

## TÁC VỤ

Implement real Markdown/CSV/JSON import parsing and persistence for user-provided files. Khuôn mẫu: Shell Script Specialist — Data Processing. Biến thể: translate its input validation/error-handling discipline into Python/FastAPI; do not create shell scripts or TODO files.

## INTERFACES

- `POST /api/admin/import` multipart file + `source_id`; accepted extensions `.md`, `.csv`, `.json`; successful response includes inserted/skipped/error counts.
- `parse_markdown(text: str) -> list[dict]`, `parse_csv(text: str) -> list[dict]`, `parse_json(text: str) -> list[dict]` must return safe field dictionaries for Task 2 normalization.
- Required fields ultimately include title, URL and content; malformed format or missing required fields returns a clear 4xx error and does not create a partial record.
- Persist raw item/article provenance and fetched timestamp inside one SQLite transaction; no command/file execution based on imported content.

## QUY TẮC BẤT DI BIẾN

- TDD red-green; include fixtures for all three formats, malformed payload and prompt injection content.
- No fake records; no SAMPLE promoted to public; preserve untrusted text as data.
- Bound upload size, validate extension/content, whitelist keys, parameterize SQL, rollback on any invalid record.
- No API keys/secrets, no network calls, no changes outside scope, no subagents.
- Write `.team/tasks/task-003-report.md`, commit local, return short status/commit/tests/concerns.

## VERIFY

- Focused `python -m unittest backend.tests.test_importers -v` (or equivalent) exits 0.
- Endpoint test proves Markdown/CSV/JSON success, malformed input 4xx, and repeated call does not create a partial duplicate (dedup finalization is Task 4, so only transaction/error semantics are required here).
- `git diff --check` exits 0; report any uv/sandbox limitation exactly.
