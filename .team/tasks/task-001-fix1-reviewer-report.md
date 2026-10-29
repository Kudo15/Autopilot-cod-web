# Task 001 — Fix round 1 re-review

Fix base: `5b5c1737f20ff2a91e23cac941de239c41517651`  
Fix head: `4f9684b884b8fe469a9b9e8fd88303c7215c9aca`

## Finding

`[P2] backend/app/main.py:45 — data_origin != ? loại data_origin IS NULL; preserve legacy public rows with NULL origin và thêm regression test.` — **ADDRESSED**

- `backend/app/main.py:48` now uses `(data_origin IS NULL OR data_origin != ?)` with the existing parameterized `SAMPLE` value. This preserves legacy published rows whose origin is NULL while still excluding SAMPLE rows.
- `backend/tests/test_public_articles.py:47-59` adds a published legacy fixture with `data_origin = NULL` and asserts it appears alongside the real published article; the SAMPLE and DRAFT fixtures remain excluded.

## New breakage in fix diff

No new breakage found in the scoped two-file fix diff. The SQL change is limited to NULL handling, and the regression test covers the requested boundary.

Verification evidence in the supplied report: focused test RED before the fix, full unittest GREEN (`Ran 1 test ... OK`), `npm run build` exit 0, `checks/p5.py` exit 0 (`PASS (11/11)`), and `git diff --check` exit 0.

Independent rerun note: `uv run python -m unittest backend.tests.test_public_articles -v` was **NOT_VERIFIED** in this review environment because uv could not initialize `C:\Users\Panda\AppData\Local\uv\cache` (`Access is denied`, exit 2). `git diff --check` independently exited 0.

## Out-of-scope observations

None. Untouched code and unrelated behavior were not re-reviewed.

Fix round: 1 — **ADDRESSED**
