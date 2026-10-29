# TASK 018 — Remove false-positive secret-scan marker

## Prompt basis

Adapt the prompt-librarian Code Review Assistant pattern: diagnose the current gate failure from concrete output, make the smallest scoped fix, and verify the exact gate before claiming success.

## Contract

The current `checks/p4.py` scan reports a false positive because `backend/tests/test_startup_script.py` contains a literal `sk-` marker as test input. Preserve the test's intent while ensuring the source scan no longer matches that marker literally. Do not weaken or modify any check, production auth behavior, or secret policy.

## Files allowed

- `backend/tests/test_startup_script.py`

Never edit `checks/`, `PLAN.md`, `docs/MISSION.md`, or product source.

## Verify

- Run the focused startup tests and record the exact count.
- Run the full backend suite with a generated `ADMIN_TOKEN`.
- Run `python checks/p4.py` and require 15/15 PASS.
- Run P3, P5, `npm run build`, and `git diff --check`.
- Commit only the allowed test file and report the exact commit.
