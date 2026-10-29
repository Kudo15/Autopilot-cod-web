# TASK 019 — Refresh QA docs after P4 fix

## Prompt basis

Adapt the prompt-librarian Code Review Assistant pattern: reconcile documentation with the exact current HEAD and observed verification output; preserve historical context without claiming unverified external behavior.

## Contract

The current HEAD includes the approved P4 false-positive fix `c44adee` (cherry-picked from `bec8129`). Update only the documentation that still says the current P4 gate is BLOCKED 14/15:
- `docs/PHASE_REPORT.md`
- `docs/QA_REPORT.md`

Record current P4 as PASS 15/15, exit 0, and explain that the historical 14/15 false positive was fixed by splitting the test-only marker while preserving its runtime value. Keep genuine NOT_VERIFIED/BLOCKED items (live external freshness, live AI gateway, browser/default-port smoke) unchanged. Refresh exact HEAD/commit references where needed. Do not invent new test results; use current local evidence. Ensure no secret value is introduced.

## Files allowed

- `docs/PHASE_REPORT.md`
- `docs/QA_REPORT.md`

Never edit checks, product source, `README_LOCAL.md`, `PLAN.md`, or `docs/MISSION.md`.

## Verify

- Run `python checks/p4.py` and record 15/15 PASS.
- Run `git diff --check` and scope-check exactly the two docs.
- Scan the docs for secret-looking values and stale claims that current P4 is 14/15.
- Commit only the two allowed docs and report exact commit.
