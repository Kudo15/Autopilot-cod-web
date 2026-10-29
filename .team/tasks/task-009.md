# TASK 009 — P8 change detection and quota observations | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

P1–P7 are integrated and green. The schema already has `change_events` and `quota_observations`, but no deterministic service writes or compares snapshots. Implement the pure, conservative core before admin routes and collectors.

Use TDD: write failing tests first, observe RED, then implement the smallest backend-only modules. Snapshot/source text is untrusted data and must never be executed or used to form SQL.

## CONTRACT

Add a pure change detector that compares before/after provider-model or offer snapshots and returns only the allowed event types:

- `NEW_PROVIDER`, `NEW_MODEL`, `MODEL_REMOVED`, `FREE_TO_PAID`, `PAID_TO_FREE`, `QUOTA_CHANGED`, `OFFER_STARTED`, `OFFER_EXPIRED`, `TERMS_CHANGED`.
- A missing/timeout/unavailable observation must return a collection-failure/stale signal, never `MODEL_REMOVED`.
- Comparisons are deterministic and do not emit duplicate events for unchanged snapshots.
- Quota observation persistence appends timestamped rows transactionally; no overwriting prior observations and no invented quota values.
- Provide a small stale/expiry evaluator that distinguishes `VERIFIED`, `UNVERIFIED`, `STALE`, `EXPIRED`, `NEEDS_REVIEW` from explicit timestamps/validity only; NULL/unknown remains unverified.

## FILES_ALLOWED

- `backend/app/radar/__init__.py` (new)
- `backend/app/radar/changes.py` (new)
- `backend/app/radar/quota.py` (new)
- `backend/app/migrate.py` only if a failing test proves an additive schema column/index is required.
- `backend/tests/test_radar_changes.py` (new)
- No public/admin route in this task; do not edit `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## VERIFY

- Snapshot/timeout/quota tests fail before implementation for intended reasons.
- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py'` → exit 0.
- Run focused change/quota tests with before/after fixtures, unchanged snapshots, nulls and rollback.
- `PYTHONUTF8=1 python checks/p3.py` and `checks/p4.py` → exit 0.
- `npm run build` → exit 0.
- `git diff --check` → exit 0.
- Commit only task-scoped files and report PASS/NOT_VERIFIED evidence.

## REPORT

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
