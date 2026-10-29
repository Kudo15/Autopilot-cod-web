# TASK 005 REVIEW — remediation for P5 seed findings | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

You are an independent Code Review Agent using the repository’s two-layer review protocol. Do not edit files, commit, merge or dispatch another task.

## Candidate

- Candidate worktree: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_fe627e26`
- Candidate commit: `7dbdec9fcef0157fc8c87609f71bbb168ac94797`
- Original reviewer findings: `.team/tasks/task-004-review.md`.
- Remediation task: `.team/tasks/task-005.md`.

## Required review

Review the exact candidate commit in the candidate worktree. Reproduce all relevant commands there:

- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py' -v`
- `PYTHONIOENCODING=utf-8 python checks/p4.py`
- `PYTHONIOENCODING=utf-8 python checks/p5.py`
- `npm run build`
- `git diff --check HEAD~1..HEAD`

Check the original findings specifically:

1. `seed_legacy_public_article()` must reuse `normalize_item()` outputs for canonical URL, normalized title and content hash.
2. Live feed tests must use temporary isolated databases and prove empty-before-seed plus two-run idempotence without mutating `backend/data/radar.db`.
3. REAL/DRAFT duplicate URL must not suppress the REAL/PUBLISHED legacy seed.

Also check task scope, migration safety, provenance preservation, public field boundary, test determinism, and whether the worker’s TDD evidence is sufficient. Findings must include priority and `file:line`; do not infer defects without evidence.

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
