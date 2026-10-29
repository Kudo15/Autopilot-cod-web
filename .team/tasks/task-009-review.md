# REVIEW TASK 009 — independent P8 change/quota review | role: reviewer | harness: hermes-kanban

## CANDIDATE

- Candidate worktree: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_39e86174`
- Exact candidate commit: `a19467a`
- Parent: `c23431c`
- Files: `backend/app/radar/__init__.py`, `backend/app/radar/changes.py`, `backend/app/radar/quota.py`, `backend/tests/test_radar_changes.py`

Use the Code Review Agent template. Review exact commit and do not edit product files.

## REVIEW QUESTIONS

1. Does snapshot comparison emit only the nine schema event types and remain deterministic/idempotent for unchanged snapshots?
2. Do timeout/unavailable observations produce a stale/collection-failure signal rather than `MODEL_REMOVED`?
3. Does quota persistence append without overwriting, preserve NULL/unknown semantics, and rollback correctly inside/outside caller transactions?
4. Does verification freshness use explicit timestamps/validity only and distinguish VERIFIED/UNVERIFIED/STALE/EXPIRED/NEEDS_REVIEW without inference?
5. Are SQL statements parameterized, inputs validated, tests isolated, and only allowed files changed?

## REQUIRED EVIDENCE

- Inspect `git show --stat` and `git diff c23431c..a19467a`.
- Run focused P8 tests and full backend suite.
- Run UTF-8 `checks/p3.py`, `checks/p4.py`, `checks/p5.py`, `npm run build`, and `git diff --check`.
- Run a temporary real-schema smoke that confirms writes/rollback leave no DB residue.

## VERDICT FORMAT

```
VERDICT: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [P0/P1/P2/P3] file:line — concrete evidence and required fix
EVIDENCE:
- command → exit code and measured result
```
