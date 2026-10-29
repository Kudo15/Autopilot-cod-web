# S1 retry — implement scheduler.py to satisfy existing contract tests

The worktree now contains `backend/tests/test_radar_scheduler.py`, which is the
authoritative bounded contract. Implement only:

- `backend/app/radar/scheduler.py` (new)
- `backend/app/radar/__init__.py` only if export is needed
- `backend/app/migrate.py` additive `radar_schedule_runs` table/index
- `backend/app/main.py` only to integrate durable state into existing
  `/api/radar` and admin refresh while preserving old response keys
- `backend/tests/test_radar_scheduler.py` only if a test fixture bug is proven

Use the tests as the exact spec: run_identity local calendar date, due at 07:00,
SQLite BEGIN IMMEDIATE race-safe claim, lease reclaim, bounded attempts,
COMPLETED idempotence, fake datetime, local `daily_radar` only, no network or
publish/verify, and manual refresh auth-before-DB with durable ledger in response.
Do not touch frontend, checks, PLAN/MISSION, real DB, or reference project.

Run focused `uv run python -m unittest backend.tests.test_radar_scheduler -v`,
then full backend and diff-check. End markers `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`,
`[RULING]`, `## Bước tiếp theo`.
