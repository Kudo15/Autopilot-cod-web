# TASK 015 — Implement Daily Radar (recovery path)

## Context

Implement the remaining Daily Radar contract in a fresh worktree. Existing code has SQLite tables `articles`, `change_events`, `collection_runs`, FastAPI `backend/app/main.py`, `require_admin`, and `backend/app/radar/changes.py`. Do not depend on another worker’s uncommitted files.

## Required behavior

1. Add `backend/app/radar/daily.py` with a small pure/testable service:
   - allowed windows exactly `today`, `7d`, `30d`, `all`; invalid raises `ValueError` and route returns 422;
   - `today` uses Asia/Ho_Chi_Minh local calendar boundaries; `7d`/`30d` use UTC-aware rolling lower bound; `all` has no lower bound;
   - query only explicit columns with `?` parameters; include published non-SAMPLE articles and non-SAMPLE change events; never return raw snapshots/content;
   - newest qualifying timestamp drives `CURRENT` vs `STALE` at >30 days; no evidence is `SIGNAL_WEAK`; unknown/undated timestamps never become fresh evidence;
   - include bounded counts/items and `generated_at`, with no secrets or instruction execution.
2. Wire `GET /api/radar?window=...` and `POST /api/admin/radar/refresh` in `backend/app/main.py`. The admin route must call `require_admin(request)` before opening/querying the DB, then recompute locally only.
3. Provide an in-memory `RadarSchedule`/marker with 07:00 Asia/Ho_Chi_Minh and explicit `deferred-to-request` state; no sleeping thread, dependency, external network, publish, or verification.
4. Add `backend/tests/test_radar_daily.py` with focused tests for the above, including auth-before-DB, SAMPLE exclusion, injection-shaped text, timezone boundary, stale/empty state, and schedule marker. Keep tests concise.

## Files allowed

- `backend/app/radar/daily.py` (new)
- `backend/app/main.py` only for Daily Radar imports, routes, and scheduler marker
- `backend/tests/test_radar_daily.py`

Do not edit migration/schema, frontend, `checks/`, `PLAN.md`, `docs/MISSION.md`, or meta-plan docs.

## Verify

Run focused tests, full backend tests with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, `git diff --check`. Record external freshness as NOT_VERIFIED. Commit only scoped files and report the exact commit.

## Execution instruction

Stop speculative design once the contract is clear. Use small patches, write code, run tests, fix failures, commit.
