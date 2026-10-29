# Task S1 — process-safe Daily Radar scheduler

## Context

Autopilot already has a truthful Daily Radar service in `backend/app/radar/daily.py` and authenticated manual refresh in `backend/app/main.py`, but `RadarSchedule` is currently in-memory. The Master Mission requires a durable/idempotent 07:00 Asia/Ho_Chi_Minh run identity, bounded retry/lock, and no duplicate work across processes or restarts. D1 live external freshness remains NOT_VERIFIED; this task must stay local and must not invent external signals.

## Scope and allowed files

Work only in this repository. Do not inspect or modify `Vu-Agent-Room-PC`.

Allowed product files:

- `backend/app/radar/**`
- `backend/app/main.py`
- `backend/app/migrate.py` or another existing backend schema/service file only if required for an additive scheduler ledger
- `backend/tests/test_radar_daily.py`
- narrowly related `backend/tests/**`
- `scripts/**` only for a bounded local smoke helper if strictly required
- `.team/results/**` via route output

Do not edit `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend files, package files, source registry, real DB contents, or reference project.

## Required behavior

1. Keep the existing public radar contract and auth-before-DB manual refresh behavior unchanged.
2. Add a durable scheduler ledger with a unique logical run identity for each local-calendar 07:00 Asia/Ho_Chi_Minh run. It must be safe when two SQLite connections/processes race: at most one owner may perform a run for the same identity.
3. Persist run status/ownership and bounded retry/lease information. A crashed/expired lease may be reclaimed after a finite timeout; an already completed identity must not run again after restart.
4. Use fake timestamps/clocks in tests; do not add sleeping background threads, external services, or dependencies. If execution remains deferred-to-request, expose that honestly and make the durable claim/complete boundary testable.
5. Scheduler work may recompute local radar only. It must never publish, verify, mutate DRAFT/SAMPLE into public data, or call external collection.
6. Keep all SQL parameterized and migrations additive/idempotent. Preserve existing DB data.

## TDD and verification

Write focused failing tests first for: same-run concurrent claim, completed-run idempotence after restart, expired-lease bounded reclaim, fake-clock 07:00 boundary, manual refresh auth-before-DB, and no-publish behavior. Then implement the minimum.

Run and record exact exit codes for focused scheduler tests, full backend unittest discovery, `npm run build`, P3/P4/P5 where environment permits, and scoped `git diff --check`. Use a temporary SQLite database for scheduler tests; do not alter `backend/data/radar.db`.

## Required output markers

End with:

- `[ĐÃ LÀM]`
- `[BẰNG CHỨNG]`
- `[RULING]` — `PASS` only when all scheduler acceptance tests and regression gates pass; otherwise `BLOCKED` with the exact failure.
- `## Bước tiếp theo`

Never claim a real timed job ran unless the evidence shows it. External freshness remains NOT_VERIFIED.
