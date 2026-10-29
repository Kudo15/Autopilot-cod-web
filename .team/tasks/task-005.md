# TASK 005 — Task 004 remediation: normalize seed and isolate tests | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

- Candidate commit: `bab3b02` (P5 feed closure). Reviewer package: `.team/tasks/task-004-review.md`.
- Design: `docs/superpowers/specs/2026-10-24-ai-radar-completion-design.md`.
- Existing candidate gates: unittest 16/16 and `checks/p5.py` 11/11, but reviewer found three correctness issues.
- Use the Unit Tester Assistant template: test each concrete behavior first, observe RED, then implement minimum fix.

## FINDINGS TO FIX

1. In `backend/app/seed.py`, `seed_legacy_public_article()` computes a custom content hash and writes unnormalized strings. Reuse `backend.app.ingest.normalize.normalize_item()` so canonical URL, normalized title and content hash match manual importer behavior. Add a regression assertion.
2. In `backend/tests/test_public_articles.py`, the live-feed integration test mutates `backend/data/radar.db` and can pass because pre-existing rows exist. Isolate it in a fresh temporary database by patching database/migration path constants; assert empty-before-seed, run seed twice, and assert exactly one matching REAL/PUBLISHED article and raw provenance row.
3. A REAL/DRAFT import with the legacy URL must not suppress the required REAL/PUBLISHED legacy seed. Guard only on the existing published legacy row and add a regression test.

## FILES_ALLOWED

- `backend/app/seed.py`
- `backend/tests/test_public_articles.py`
- No other product files; never edit `checks/`, `PLAN.md` or `docs/MISSION.md`.

## VERIFY

- Focused regression tests fail before the fix for the intended reasons.
- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py'` → exit 0.
- `PYTHONIOENCODING=utf-8 python checks/p4.py` and `checks/p5.py` outside sandbox → exit 0.
- `npm run build` outside sandbox → exit 0.
- `git diff --check` → exit 0.
- Commit only this remediation and report exact commands and exit codes.

## REPORT

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
