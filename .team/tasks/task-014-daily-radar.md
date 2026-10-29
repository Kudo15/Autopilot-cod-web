# TASK 014 — Daily Radar aggregation and stale status

## Prompt basis

Adapt the prompt-librarian Code Review Assistant / Code Review Agent pattern: inspect the existing FastAPI/SQLite code, implement the smallest testable change, and report concrete evidence for correctness, security, and scope.

## Context

The project already has SQLite tables `articles`, `change_events`, and `collection_runs`, plus deterministic change detection in `backend/app/radar/changes.py`. The remaining product contract needs a server-only Daily Radar read API and an authenticated manual refresh. SAMPLE data must never appear as real evidence.

## Contract

- Add a small radar service module under `backend/app/radar/` that reads SQLite using bound parameters and explicit columns.
- `GET /api/radar?window=today|7d|30d|all` returns a deterministic JSON object containing the selected window, `generated_at`, `stale_after_days`, current/stale state, published article signals, real change-event signals, and `SIGNAL_WEAK` when there is no qualifying real evidence. The exact response shape may be chosen if documented by tests.
- Include only `articles.article_status = 'PUBLISHED'` and `data_origin != 'SAMPLE'`; include only `change_events.data_origin != 'SAMPLE'`. Never expose raw content or untrusted text as executable instructions.
- Window filtering must be explicit and timezone-safe. `today` means the current Asia/Ho_Chi_Minh calendar day; `7d` and `30d` are rolling UTC-aware windows; `all` has no lower bound. Invalid windows return 422.
- Stale status is deterministic: no qualifying real evidence => `SIGNAL_WEAK`; otherwise stale if the newest qualifying observation is older than the configured/default 30 days, otherwise current. Do not claim verification/freshness that is not represented by timestamps.
- `POST /api/admin/radar/refresh` requires the existing `require_admin` boundary before any DB work. It performs a bounded local recomputation/returns the current result and must not call external services or publish/verify anything.
- Provide a scheduler hook or lifecycle-owned refresh marker for 07:00 `Asia/Ho_Chi_Minh` while the backend is running. It must be local, bounded, and testable without sleeping for real time; do not add dependencies. If the implementation intentionally defers execution to the next request, expose that fact in tests/docs rather than pretending a job ran.
- No frontend, migration, external network, secrets, or changes to `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## Files allowed

- `backend/app/radar/daily.py` (new)
- `backend/app/main.py` only for the two routes and lifespan/scheduler hook
- `backend/tests/test_radar_daily.py` and narrowly related tests
- `docs/superpowers/plans/2026-10-24-ai-radar-completion-plan.md` is coordinator-owned; do not edit it in the worker.

## TDD and verify

- Write focused failing tests first for windows, timezone boundary, SAMPLE exclusion, stale/empty status, admin auth-before-DB, refresh, and scheduler marker.
- Run focused tests and full backend suite with a generated `ADMIN_TOKEN`.
- Run `npm run build`, `python checks/p3.py`, `python checks/p4.py`, `python checks/p5.py`, and `git diff --check` where environment allows.
- Do not report external freshness or a real scheduled job as verified; mark those `NOT_VERIFIED` if only deterministic local behavior is tested.

## Report

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
