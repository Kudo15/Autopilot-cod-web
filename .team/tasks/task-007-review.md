# REVIEW TASK 007 — independent public Explorer API review | role: reviewer | harness: hermes-kanban

## CANDIDATE

- Candidate worktree: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_534b44c9`
- Exact candidate commit: `132f145`
- Parent: `5ba24ea`
- Files: `backend/app/main.py`, `backend/tests/test_models_api.py`

Use the Code Review Agent template and review the exact commit, not an uncommitted tree. Do not edit product files.

## REVIEW QUESTIONS

1. Does `GET /api/models` join normalized models/providers/provider_models and preserve one model with provider-specific quota/status?
2. Are response fields explicit and free of SAMPLE rows, raw/provenance, registry, API base URLs or internal notes?
3. Are all filters allowlisted, validated and parameterized, including injection-shaped provider input, nullable capabilities, context/quota minimums and verification freshness?
4. Is `UNKNOWN`/`UNVERIFIED`/NULL preserved rather than inferred as free, verified, fresh or API-capable?
5. Are tests isolated and RED-before-GREEN evidence credible; do P1–P6 regressions remain green?

## REQUIRED EVIDENCE

- Inspect `git show --stat` and `git diff 5ba24ea..132f145`.
- Run focused Explorer tests and full backend suite.
- Run UTF-8 `checks/p3.py`, `checks/p4.py`, `checks/p5.py`, `npm run build`, `git diff --check`.
- Exercise real HTTP `200`/`422` filter behavior on localhost and verify only allowed files changed.

## VERDICT FORMAT

```
VERDICT: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [P0/P1/P2/P3] file:line — concrete evidence and required fix
EVIDENCE:
- command → exit code and measured result
```
