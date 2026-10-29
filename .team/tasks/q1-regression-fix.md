# TASK q1-regression-fix | harness: Hermes GUI | role: worker

## Context

Repository: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web`  
Stack: FastAPI + SQLite + Python unittest; frontend build is Vite/React. The worktree is intentionally dirty; preserve all pre-existing product edits and all files outside this task's allowlist.

The fresh Hermes GUI audit reproduced three failures outside the sandbox:

1. `backend.tests.test_admin_workflow.AdminRouteCoverageTests.test_unauthenticated_admin_calls_fail_before_touching_the_database` — `admin_sources` returns HTTP 500 instead of 401 when no credential is supplied and `ADMIN_TOKEN` is not configured.
2. `backend.tests.test_radar_daily.RadarRoutesTests.test_admin_refresh_with_valid_token_recomputes_locally_and_marks` — expected `CURRENT`, received `SIGNAL_WEAK` for a fresh REAL published article.
3. `backend.tests.test_radar_daily.RadarRoutesTests.test_public_radar_returns_schedule_with_current_default_window` — expected `CURRENT`, received `SIGNAL_WEAK` for the same fresh REAL fixture.

The exact focused command was:
`uv run python -m unittest backend.tests.test_admin_workflow.AdminRouteCoverageTests.test_unauthenticated_admin_calls_fail_before_touching_the_database backend.tests.test_radar_daily.RadarRoutesTests.test_admin_refresh_with_valid_token_recomputes_locally_and_marks backend.tests.test_radar_daily.RadarRoutesTests.test_public_radar_returns_schedule_with_current_default_window -v`
It ran 3 tests and failed 3. Do not weaken or delete assertions. Preserve the invariant that no-signal/invalid/undated timestamps remain `SIGNAL_WEAK`, and that admin authentication is checked before opening a database.

## Allowed files

- `backend/app/auth.py`
- `backend/app/radar/**`
- `backend/tests/test_admin_workflow.py`
- `backend/tests/test_radar_daily.py`
- `backend/tests/**` only when adding a narrowly focused regression fixture needed to prove isolation
- `scripts/**` only if a test entrypoint is strictly required

Do not modify `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend files, database fixtures under `backend/data/`, `.team/scripts/`, `.team/routing.json`, or `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Vu-Agent-Room-PC`.

## Task

Act as a test-writer/fixer and bug-discovery engineer. Use strict RED → GREEN → focused refactor:

1. Read the current auth and Daily Radar implementation plus the failing tests. Add or sharpen only the minimum regression coverage needed to expose the actual defects without changing the intended contract.
2. Fix the smallest production surface. Missing admin credentials must still reject the request before any DB access with 401 when the request has no credential; a supplied but invalid credential remains 403; a configured-token request continues to work. Daily Radar must derive `CURRENT` only from a valid fresh REAL/PUBLISHED timestamp and must not turn missing, invalid, SAMPLE, or stale evidence into CURRENT.
3. Ensure test fixtures use isolated temporary SQLite connections and never mutate `backend/data/radar.db`.
4. Run, in order, the focused three-test command above, the relevant auth/radar modules, full `uv run python -m unittest discover -s backend/tests -p "test_*.py" -v`, `npm run build`, `python checks/p1.py` through `python checks/p5.py`, and `git diff --check`. Record exact exit codes and any environment caveat. If an allowed-file boundary makes a required fix impossible, stop and report `BLOCKED` rather than editing outside scope.

## Completion contract

- Focused RED is demonstrated before the fix and focused GREEN after it.
- Full backend discovery has zero failures/errors, or a concrete non-code environment blocker is documented.
- Existing public/private, SAMPLE, auth-before-DB, and freshness assertions remain intact.
- No secrets, network collection, production deployment, push, merge, or reference-project change.
- Worker report ends with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and `## Bước tiếp theo`, naming every changed file and exact command/exit code.
