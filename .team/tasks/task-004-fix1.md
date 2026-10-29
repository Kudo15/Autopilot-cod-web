# TASK 004 FIX 1 — remediate P5 seed/review findings | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

- Original task: `.team/tasks/task-004.md`; original candidate commit: `bab3b02`.
- Review package: `.team/tasks/task-004-review.md`.
- Design: `docs/superpowers/specs/2026-10-24-ai-radar-completion-design.md`.
- Current gates before this fix: backend unittest 16/16 PASS and `checks/p5.py` 11/11 PASS, but reviewer found correctness/isolation defects that would break the Phase 6 dedup contract or make tests pass falsely.
- Prompt template source: `Unit Tester Assistant`, modernized for focused regression tests and safe fixture isolation.

## TÁC VỤ

Act as the original implementation engineer remediating exactly the reviewer findings below. Use TDD: add/adjust a regression test for each finding, run it RED against the candidate, then make the minimum code/test changes and run all gates.

1. `backend/app/seed.py`: `seed_legacy_public_article()` must call the existing `backend.app.ingest.normalize.normalize_item()` (or exactly reuse its normalization contract) so `canonical_url`, `normalized_title` and `content_hash` match manual importer behavior. Persist the normalized values and add a regression assertion.
2. `backend/tests/test_public_articles.py`: isolate the seed/feed integration test in a fresh temporary SQLite database by patching all relevant database/migration path constants. Assert empty-before-seed, run seed twice, assert exactly one REAL/PUBLISHED legacy article and one matching provenance raw item. Do not mutate the developer’s live `backend/data/radar.db` during unit tests.
3. `backend/app/seed.py`: a REAL/DRAFT row with the legacy URL must not suppress creation of the required REAL/PUBLISHED legacy article. Guard only against the existing published legacy record (and preserve unrelated drafts/raw items). Add a regression test.

Do not broaden into P6 dedup implementation. Do not edit `checks/`, `PLAN.md` or `docs/MISSION.md`. Do not invent data or alter the official URL/content already justified in the original task.

## FILES_ALLOWED

- `backend/app/seed.py`
- `backend/tests/test_public_articles.py`
- No other product files.

## VERIFY

- Focused regression tests fail before the fix for the intended reasons.
- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py'` exits 0.
- `PYTHONIOENCODING=utf-8 python checks/p5.py` outside sandbox exits 0.
- `PYTHONIOENCODING=utf-8 python checks/p4.py` outside sandbox exits 0 and seed remains idempotent.
- `npm run build` outside sandbox exits 0.
- `git diff --check` exits 0.
- Commit the remediation only, then report exact commands/exit codes.

## REPORT

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
