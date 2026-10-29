# TASK 004 REVIEW — close P5 public feed contract | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

You are an independent Code Review Agent adapted from the prompt-librarian `Code Review Agent` template. Do not edit files. Review the current candidate for Task 004 against the task pack and design/implementation plan.

## Scope under review

- `backend/app/seed.py`
- `backend/tests/test_public_articles.py`

The worker did not return a handoff; therefore reproduce the evidence yourself. The coordinator independently observed:

- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py' -v` → exit 0, 16/16.
- `PYTHONIOENCODING=utf-8 python checks/p5.py` outside sandbox → exit 0, 11/11.
- Current candidate adds one provenance-backed REAL/PUBLISHED legacy article and keeps SAMPLE/DRAFT exclusion.

## Review requirements

1. Check spec compliance: no fake data, no relabelled SAMPLE, official/public URL and provenance are evidenced, public response remains explicit and private fields are excluded.
2. Check code quality/security: idempotence, migration/seed behavior, stable hashes/URLs, test isolation, no secret or unintended external side effects.
3. Check scope: no files outside Task 004 ownership were changed by the candidate.
4. Run the relevant tests/referee yourself; do not trust the coordinator’s claims.
5. Return exactly one verdict and list every finding with priority, file:line, evidence and actionable fix.

## Output

```
VERDICT: APPROVED — <one line>
or
VERDICT: CHANGES_REQUESTED — <P1/P2 findings>

Evidence:
- command → exit code/result

Not verified:
- <anything not reproduced>
```

Do not modify code, commit, push or dispatch another task.
