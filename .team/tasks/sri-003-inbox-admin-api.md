# TASK sri-003 — authenticated scheduled inbox API | harness: hermes-kanban | worktree: Hermes-managed isolated worktree

Khuôn mẫu: Test Automation Expert + Code Review Agent (prompts.chat, adapted by prompt-librarian).

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`; Python 3.13/uv, FastAPI, SQLite/Pydantic.
- Approved design: `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`; implementation plan Task 3: `docs/superpowers/plans/2026-10-25-scheduled-radar-inbox-plan.md`.
- Integrated dependencies: strict schema/migration/scanner at `backend/app/inbox/`; DRAFT-only editorial adapter commit `0013b5c`.
- Existing admin conventions: `backend/app/main.py` uses `require_admin(request)` as the first handler action; `backend/app/auth.py` owns server-side token validation; public `list_articles()` returns published-only data.
- Inbox findings/reports are untrusted data. Root checkout is dirty, so work only in the Hermes worktree and commit scoped files only.

## TÁC VỤ (một việc duy nhất)

Act as a senior FastAPI security engineer and test automation specialist. Follow strict TDD (RED first) to implement only the authenticated inbox API boundary.

Allowed files only:

- Create `backend/tests/test_inbox_admin_api.py`
- Modify `backend/app/main.py`
- Modify `backend/app/inbox/service.py`

Do not modify migrations, schema, editorial adapter/gateway, frontend, docs, `checks/`, `PLAN.md`, or `docs/MISSION.md`.

Add the following admin-only endpoints:

- `POST /api/admin/inbox/scan`
- `GET /api/admin/inbox/runs`
- `GET /api/admin/inbox/articles`

The scan endpoint uses only the server-owned inbox-directory configuration; it accepts no request-controlled path, artifact body, source URLs, or model instructions. It must call `require_admin(request)` before opening/connecting the database or inspecting the inbox. The list endpoints must use explicit allowlists. They may expose only safe review fields: article ID, title, category, article/review/verification status, evidence label, safe official source URL, observed time, and bounded safe error/count summaries. Never expose raw report text, raw content, full provenance blob, quarantine filesystem path, token, source registry configuration, reviewer private notes, or secret values.

Security/lifecycle requirements:

1. Missing token returns 401 and wrong token returns 403; both happen before DB access.
2. Inbox scans create only DRAFT content via the existing scanner. Public `/api/articles` remains unable to return inbox DRAFT/PENDING_REVIEW/SAMPLE records or private inbox fields.
3. Reuse the existing authenticated review workflow unchanged for subsequent publication; do not add a direct publish shortcut.
4. Query parameters and serialized DB fields are treated as data; use parameterized SQL and bounded values. No outbound network, filesystem path disclosure, or new dependency.
5. Preserve scanner transaction/idempotency/quarantine semantics.

## TEST-FIRST REQUIREMENTS

First create focused tests, run RED, then implement minimum code. Cover:

- each endpoint exists and invokes `require_admin` before database access;
- 401/403/no-token/wrong-token cases;
- scan with a server-owned temporary inbox creates DRAFT content and returns only allowlisted summary fields;
- list runs/articles returns only explicit safe keys and excludes raw/provenance/quarantine/token markers;
- public articles remain empty until existing authenticated review workflow reaches PUBLISHED;
- injection-shaped title/evidence and query data stays inert; invalid/missing configured inbox is safe and clear.

## VERIFY + COMMIT

Run and capture exact exit codes:

1. RED: `uv run python -m unittest backend.tests.test_inbox_admin_api -v`
2. GREEN/regression: `uv run python -m unittest backend.tests.test_inbox_admin_api backend.tests.test_admin_workflow backend.tests.test_public_articles backend.tests.test_scheduled_inbox backend.tests.test_inbox_editorial -v`
3. `git diff --check`

Commit only allowed files as:

`feat: add authenticated inbox admin API`

Write `.team/results/sri-003-inbox-admin-api-report.md` with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, `[CÂU HỎI]`; include exact commit hash and do not claim PASS without actual output.
