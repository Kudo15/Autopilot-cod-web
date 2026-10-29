# REVIEW TASK 015 — Daily Radar candidate

## Review basis

Adapt the prompt-librarian Code Review Agent pattern: inspect the exact candidate, verify the contract and security boundaries, run independent tests, and return APPROVED or CHANGES_REQUESTED with concrete evidence.

## Candidate

Review exact commit `9fb92f5` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_d1b6b6b2`.

## Contract questions

1. Does `backend/app/radar/daily.py` implement exact window allowlist, Asia/Ho_Chi_Minh today boundary, UTC rolling windows, explicit bound SQL, SAMPLE/PUBLISHED filtering, stale/current/SIGNAL_WEAK, and no raw snapshot/content leakage?
2. Are GET and authenticated admin refresh wired safely, with `require_admin` before DB access and no external calls/publish/verify side effects?
3. Is the 07:00 scheduler marker honest/deferred-to-request, bounded and testable without a sleeping thread or new dependency?
4. Are untrusted text/timestamps handled safely and output bounded/deterministic?
5. Is the diff exactly scoped to daily.py, main.py route/lifecycle changes, and test_radar_daily.py; are existing gates preserved?

## Evidence required

- Inspect exact diff and changed-file scope.
- Run focused `backend.tests.test_radar_daily`, full backend with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, `git diff --check`.
- Independently probe auth-before-DB, SAMPLE exclusion, SQL injection-shaped text, timezone/window boundaries, stale/empty state, schedule deferral, and source/bundle secret scans.
- Mark external freshness/live network `NOT_VERIFIED`.

## Output

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```

Do not edit product files.
