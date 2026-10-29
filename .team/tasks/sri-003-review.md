# TASK sri-003-review — independent inbox admin API review | harness: hermes-kanban | workspace: scratch

Khuôn mẫu: Code Review Agent + Code Reviewer (prompts.chat, adapted by prompt-librarian).

Act as an independent senior FastAPI/SQLite security reviewer. This is read-only: do not edit product files, commit, merge, push, deploy, or alter task lifecycle.

## Target and contract

- Exact candidate commit: `73b5981`
- Candidate worktree: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web\.worktrees\t_e6897cdd`
- Implementation task: `.team/tasks/sri-003-inbox-admin-api.md`
- Design: `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`

## Review in two layers

### 1. Specification compliance

1. Verify commit scope is exactly `backend/app/main.py`, `backend/app/inbox/service.py`, and `backend/tests/test_inbox_admin_api.py`.
2. Verify `POST /api/admin/inbox/scan`, `GET /api/admin/inbox/runs`, and `GET /api/admin/inbox/articles` enforce `require_admin(request)` before any DB/inbox access. Missing/wrong token must be 401/403.
3. Verify scan accepts no caller-supplied path/body/source/model control and uses only server-owned inbox configuration.
4. Verify explicit response allowlists: no raw report/content, provenance blob, quarantine path, token, registry config or private reviewer notes.
5. Verify scanner remains DRAFT-only/idempotent and public `/api/articles` cannot expose inbox drafts/pending/SAMPLE/private data. Existing review lifecycle must remain the only publishing path.

### 2. Code quality/security

Audit server-owned path resolution, SQL/query safety, bounded errors, serialisation of untrusted values, source URL safety, no secret logging/no extra network/dependency, test isolation and no weakened existing boundary.

## Evidence required

Run in candidate worktree and report exact exit codes:

1. `git diff-tree --no-commit-id --name-only -r 73b5981`
2. `uv run python -m unittest backend.tests.test_inbox_admin_api backend.tests.test_admin_workflow backend.tests.test_public_articles backend.tests.test_scheduled_inbox backend.tests.test_inbox_editorial -v`
3. `git diff 73b5981^ 73b5981 --check`

Independently probe auth-before-DB, no request path control, public response exclusion, unsafe/raw field exclusion, and existing review-to-PUBLISHED workflow. Do not rely solely on worker prose.

## Output

Return exactly one `VERDICT: APPROVED` or `VERDICT: CHANGES_REQUESTED`. Each finding: `[P1|P2|P3] file:line — evidence — smallest safe fix`. Include exact commit and concise evidence.
