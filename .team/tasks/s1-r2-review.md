# Independent review S1 + R2 (read-only)

Review current worktree only; do not edit files, start/stop servers, or touch the
real DB. Inspect the S1 durable scheduler (`backend/app/radar/scheduler.py`,
migration, main integration, `test_radar_scheduler.py`) and R2 repository
catalog (`main.py`, migration, `RepositoryView.jsx`, focused tests).

Check exact contracts: SQLite race-safe lease/idempotence/retry/fake-clock and
auth-before-DB/manual refresh/no publish; repository public allowlist,
canonical https://github.com, VERIFIED/REAL/provenance/license gates, bounded
filters, no network and safe UI. Run only read-only verification commands if
needed. End with `VERDICT: APPROVED`, `VERDICT: CHANGES_REQUESTED`, or
`VERDICT: NOT_VERIFIED`, severity-ranked findings, and evidence.
