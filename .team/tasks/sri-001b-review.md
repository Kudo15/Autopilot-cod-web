# REVIEW sri-001b — scheduled inbox run ledger migration

Khuôn mẫu: Code Reviewer + Software Quality Assurance Tester (prompts.chat, adapted by prompt-librarian).

Act as an independent senior Python/SQLite reviewer. Review commit `16e50ba` on branch/worktree `wt/t_df2afde2` at:

`D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web\.worktrees\t_df2afde2`

This is a read-only review. Do not edit files, commit, merge, push, deploy, or change task state.

## Specification source

Read `.team/tasks/sri-001b-inbox-migration.md` from the project root and inspect exactly `16e50ba^..16e50ba`.

## Review in two ordered layers

1. SPEC COMPLIANCE
   - Verify only `backend/app/migrate.py` and `backend/tests/test_scheduled_inbox_migration.py` are committed.
   - Check the exact table columns, defaults, NOT NULL clauses, CHECK constraints, primary key, and both requested indexes.
   - Check idempotence, preservation of a previously inserted row, valid insertion/readback, invalid-value rejection, and preservation of existing business tables.
   - Confirm no destructive migration or unrelated change.
2. CODE QUALITY
   - Assess migration safety, SQLite correctness, test isolation, determinism, readability, and meaningful assertions.

## Independent verification

Run from the worktree and report exact exit codes:

1. `uv run python -m unittest backend.tests.test_scheduled_inbox_migration -v`
2. `uv run python -m unittest backend.tests.test_importers backend.tests.test_scheduled_inbox_schema -v`
3. `git diff --check 16e50ba^ 16e50ba`
4. Inspect commit file list with `git diff-tree --no-commit-id --name-only -r 16e50ba`.

Do not trust the worker summary as evidence. If a command cannot run, mark it `NOT_VERIFIED`.

## Output

Each finding must be `[P1|P2|P3] file:line — reason — recommended correction`. Do not invent findings without evidence.

Finish with exactly one:

`VERDICT: APPROVED — <one-line reason>`

or

`VERDICT: CHANGES_REQUESTED — <P1/P2 items that must be fixed>`

Write the review report to `.team/results/sri-001b-review-report.md` in the main project directory if accessible; otherwise include the complete report in the task result.
