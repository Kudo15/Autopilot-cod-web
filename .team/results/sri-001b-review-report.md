# REVIEW sri-001b — scheduled inbox run ledger migration

- Task: `sri-001b-review` (t_ba0f9557)
- Reviewed commit: `16e50ba` (`feat: add scheduled inbox run ledger`), parent `6bfa3bc` (approved schema package — matches spec base)
- Worktree: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web\.worktrees\t_df2afde2` (HEAD = 16e50ba, worktree clean; only untracked `.team/results/`)
- Spec: `.team/tasks/sri-001b-inbox-migration.md`
- Reviewer: default profile, independent senior Python/SQLite review, read-only

## 1. Independent verification (actually run, exact exit codes)

| # | Command | Result |
|---|---------|--------|
| 1 | `uv run python -m unittest backend.tests.test_scheduled_inbox_migration -v` | **PASS — 10/10 OK, exit 0** |
| 2 | `uv run python -m unittest backend.tests.test_importers backend.tests.test_scheduled_inbox_schema -v` | **PASS — 30/30 OK, exit 0** |
| 3 | `git diff --check 16e50ba^ 16e50ba` | **exit 0** (no whitespace errors) |
| 4 | `git diff-tree --no-commit-id --name-only -r 16e50ba` | exactly `backend/app/migrate.py`, `backend/tests/test_scheduled_inbox_migration.py` |

All four commands ran from the worktree; nothing marked NOT_VERIFIED.

## 2. Layer 1 — SPEC COMPLIANCE

### 2.1 Scope
- Commit touches exactly the two contracted files: +27 lines in `backend/app/migrate.py`, +207 new lines in `backend/tests/test_scheduled_inbox_migration.py` (new file, mode 100644). No other file in the commit. ✅
- Commit message matches spec exactly: `feat: add scheduled inbox run ledger`. ✅

### 2.2 Table definition (verified in diff, `migrate.py` TABLES_DDL)
- `run_id TEXT PRIMARY KEY` ✅
- `report_kind TEXT NOT NULL` ✅
- `content_hash TEXT NOT NULL` ✅
- `observed_at TEXT NOT NULL` ✅
- `status TEXT NOT NULL CHECK (status IN ('IMPORTED', 'QUARANTINED'))` — built via existing `_check(INBOX_RUN_STATUS)` helper, consistent with file conventions ✅
- `finding_count INTEGER NOT NULL DEFAULT 0 CHECK (finding_count >= 0)` ✅
- `accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0)` ✅
- `skipped_count INTEGER NOT NULL DEFAULT 0 CHECK (skipped_count >= 0)` ✅
- `error_message TEXT` (nullable, no default) ✅
- `processed_at TEXT NOT NULL` ✅
- `data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL', 'SAMPLE'))` ✅

### 2.3 Indexes
- `CREATE INDEX IF NOT EXISTS idx_scheduled_inbox_runs_processed_at ON scheduled_inbox_runs(processed_at)` ✅
- `CREATE INDEX IF NOT EXISTS idx_scheduled_inbox_runs_status ON scheduled_inbox_runs(status)` ✅
- Both follow the existing `IF NOT EXISTS` convention. ✅

### 2.4 Behavioral requirements (each backed by an executed test, not just claimed)
- Idempotence — `test_migration_twice_succeeds_and_preserves_rows` runs `apply_migration()` twice; row preserved. ✅
- Preservation of previously inserted row — same test, asserts `[("run-keep", "IMPORTED")]` after second run. ✅
- Valid insertion/readback with defaults — `test_valid_row_roundtrip_and_defaults` asserts all 11 values incl. counters=0, `data_origin='REAL'`. ✅
- Invalid-value rejection — `test_status_restricted_to_imported_or_quarantined`, `test_negative_counts_rejected` (all 3 counters, subTest), `test_data_origin_restricted_to_real_or_sample` — all assert `sqlite3.IntegrityError`. ✅
- Existing business tables preserved — `test_preexisting_business_tables_still_present` asserts all `BUSINESS_TABLES` present after two migration runs. ✅
- No destructive migration — diff is purely additive: one new constant, one new DDL string appended to `TABLES_DDL`, two new index strings appended to `INDEXES_DDL`, docstring/comment updates. No existing DDL line modified or removed; `apply_migration()` itself unchanged. ✅
- No unrelated change — only docstring lines + the ledger additions. ✅

### 2.5 Notes on deliberate choices (verified, not findings)
- New table intentionally NOT added to `BUSINESS_TABLES` (documented in diff comment: not part of the 12 MISSION tables). `BUSINESS_TABLES` is only consumed for the `main()` print (migrate.py:383), so behavior is unaffected; keeping the MISSION contract intact is the safer choice.
- `test_required_columns_reject_null` correctly skips `run_id`: `TEXT PRIMARY KEY` in SQLite does not reject NULL (only `INTEGER PRIMARY KEY` aliases rowid). The test documents this in a comment and covers the other 5 NOT NULL columns. This matches the spec's literal `run_id TEXT PRIMARY KEY` — compliant.

## 3. Layer 2 — CODE QUALITY

- **Migration safety**: `CREATE TABLE/INDEX IF NOT EXISTS` inside the existing transactional `apply_migration()`; no drops, no alters, no data touching. Safe to re-run. ✅
- **SQLite correctness**: DDL is valid and idempotent; CHECK uses the file's `_check()` helper for `status` (consistent with sibling tables) while `data_origin` uses inline `IN` (also valid, slightly less consistent — see P3-1). NULLs pass CHECK, which is fine here since every CHECK-ed column is also NOT NULL.
- **Test isolation**: fresh `tempfile.TemporaryDirectory` per test with `addCleanup`; patches both `database` and `migrate` module attributes (`DATA_DIR`, `DB_PATH`), which is necessary because `migrate` imports the names into its own namespace (migrate.py:36) — patching only `database.DB_PATH` would have been insufficient. Real DB `backend/data/radar.db` never touched. ✅
- **Determinism**: no time-dependent assertions (fixed timestamp literals), no network, no shared state between tests, ordered `ORDER BY run_id` in the only multi-row query. ✅
- **Readability**: Vietnamese docstrings consistent with the repo; `_insert()` helper keeps the 11-column INSERT DRY; `EXPECTED_COLUMNS` table documents the contract and the `table_info` pk/notnull nuance. ✅
- **Meaningful assertions**: exact-tuple `assertEqual` on `PRAGMA table_info` (catches column order, type, NOT NULL, PK — stronger than per-name checks); exact row roundtrip; real `IntegrityError` for each constraint; `PRAGMA index_list/index_info` verifies both indexes' column composition. ✅
- **TDD evidence in repo**: not part of the commit (RED run was terminal-only), which is acceptable — the commit scope was constrained to two files.

## 4. Findings

- `[P3] backend/app/migrate.py:272 — data_origin CHECK written inline as `IN ('REAL', 'SAMPLE')` while status uses the `_check()` helper tuple convention used by every other CHECK in the file — for consistency, define a `DATA_ORIGIN = ("REAL", "SAMPLE")` tuple and use `CHECK (data_origin %s) % _check(DATA_ORIGIN)`. Cosmetic only; behavior identical.`
- `[P3] backend/tests/test_scheduled_inbox_migration.py:197 (index test) — index verification asserts column tuples via `assertIn` over values but does not assert index names, so an accidental extra index on the same columns would not be flagged — acceptable for this contract; could name-assert `idx_scheduled_inbox_runs_processed_at`/`idx_scheduled_inbox_runs_status` if the names are to be treated as part of the contract. Cosmetic only.`

No P1 or P2 findings.

## 5. Verdict

All spec items verified by inspection and by independently re-running the test suites (10/10 and 30/30, exit 0) plus clean `git diff --check` and a two-file commit scope.

VERDICT: APPROVED — exactly the two contracted files; DDL matches the spec column-for-column with both required indexes, idempotent and purely additive, and all behavioral claims reproduce in independent runs (10/10 migration tests, 30/30 regression, exit 0).
