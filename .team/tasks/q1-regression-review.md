# Q1 Regression Fix — Independent Review

## Role

You are the independent reviewer for `q1-regression-fix`. Review the current
working-tree diff and the worker's evidence. Do not edit files, do not commit,
and do not touch the reference project.

## Scope / allowed read-only files

- `backend/app/auth.py`
- `backend/tests/test_admin_workflow.py`
- `backend/tests/test_radar_daily.py`
- Relevant existing auth/radar implementation and tests needed for context
- `.team/results/q1-regression-fix.hermes-gui.jsonl` for worker evidence

Do not modify `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend files, database
files, `.team/scripts/`, `.team/routing.json`, or any file outside this review.

## Required review questions

1. Does `require_admin` preserve the intended security contract: missing
   credential returns 401 before configuration lookup, supplied credential with
   missing server token returns 500 without secret disclosure, wrong token is
   403, and valid token succeeds? Check auth-before-DB behavior and all tests.
2. Is the new regression test minimal and correctly scoped?
3. Is `fresh_today_vn_timestamp()` a sound, non-flaky fix for the stale test
   fixture, including midnight/timezone behavior? Confirm production code was
   not changed to weaken the CURRENT/SIGNAL_WEAK contract.
4. Check for accidental scope creep, malformed documentation, hardcoded
   secrets, data mutation, or whitespace issues.
5. Independently run the focused auth/radar tests and the full backend suite if
   feasible. Validate the worker's reported build/check evidence; do not repeat
   unsupported claims.

## Required output

Return a concise report with:

- `VERDICT: APPROVED` only if no blocking correctness/security/scope issue is
  found; otherwise `VERDICT: CHANGES_REQUESTED`.
- Findings ordered by severity with exact file/line references.
- Commands run and exit codes.
- Any residual risk or NOT_VERIFIED item.

Do not create a review file. Stream the report to the caller.
