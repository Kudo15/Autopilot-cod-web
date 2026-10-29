# TASK 006 REVIEW RETRY — independent P6 dedup review | reviewer report

Candidate: `daf8abee5b17c6f8b1d1dc827b8856a366f869db` (worktree t_8d65f6f4), parent `7eb27d4`
Scope checked: candidate diff only (4 files, all inside P6 `files_allowed` `backend/**`).
No product files were modified; only scratch (probe_t006) + this report were written.

## Verdict

```
VERDICT: APPROVED
FINDINGS:
- [P3] backend/app/ingest/importers.py:177-179 — a cross-source observation writes a
  real row into raw_items but is reported under the `skipped` counter (probe: result
  {'inserted':0,'skipped':1} while raw_items grew by 1). Semantics: inserted/skipped
  count article writes only. Non-blocking (matches task contract and tests), but the
  counter is ambiguous for operators. Optional fix: add a separate `observed` counter
  or document that skipped counts non-article writes.
- [P3] backend/app/ingest/importers.py:88-127 — per-item SELECTs in _has_source_observation/
  _has_normalized_item are O(n) queries per batch with no in-batch cache. Fine for 1MB
  uploads; optional: normalize within the batch before hitting the DB.
EVIDENCE:
- git show daf8abe --name-status -> only backend/app/database.py, backend/app/migrate.py,
  backend/app/ingest/importers.py, backend/tests/test_importers.py changed (allowed scope ok)
- HEAD = daf8abe, parent = 7eb27d4, worktree clean (git status --porcelain empty; radar.db gitignored)
- uv run --project . python -m unittest backend.tests.test_importers -v -> exit 0, 13/13 OK
- uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py' -> exit 0, 26/26 OK
- RED-before-GREEN: candidate test_importers.py run against PARENT 7eb27d4 source (scratch
  redcheck_t006) -> exit 1, FAILED (failures=5, errors=1): the 6 dedup/provenance/rollback/
  mixed-count/migration tests fail on pre-impl code for the intended reason
- PYTHONUTF8=1 uv run --project . python checks/p1.py -> exit 0, PASS (15/15)
- PYTHONUTF8=1 uv run --project . python checks/p2.py -> exit 0, PASS (9/9)
- PYTHONUTF8=1 uv run --project . python checks/p3.py -> exit 0, PASS (13/13)
- PYTHONUTF8=1 uv run --project . python checks/p4.py -> exit 0, PASS (15/15)
- PYTHONUTF8=1 uv run --project . python checks/p5.py -> exit 0, PASS (11/11)
- npm run build -> exit 0 (vite build ok, dist generated; Node 22.11 warning only)
- git diff --check 7eb27d4 daf8abe -> exit 0
- probe_t006: apply_migration on a copy of the REAL pre-upgrade live DB (main repo
  backend/data/radar.db) -> adds normalized_title/content_hash, preserves 2 article rows,
  creates uq_articles_dedup_identity + uq_raw_items_source_observation + dedup index; run
  twice + seed twice -> counts stay (2,2,3), no duplication; real legacy reimport via
  persist_import skips article (inserted 0 / skipped 1, delta articles 0)
- Routes: only /api/health, /api/articles, /api/admin/import; /api/articles returns
  ARTICLES_COLUMNS (public fields only, no provenance/raw_content); no provenance/raw strings
  in src/ bundle
```

## Layer 1 — spec compliance (all six review questions)

1. Identity normalized `(canonical_url, normalized_title, content_hash)` — yes: created
   in normalize_item (canonical url, NFC+whitespace title, sha256 of normalized content),
   enforced by partial unique indexes uq_raw_items_source_observation and
   uq_articles_dedup_identity, and checked by _has_source_observation/_has_normalized_item.
2. Same-source reimport — no duplicate raw/article rows; original fetched_at + provenance
   preserved (test_reimporting_same_observation... asserts t1 timestamp survives a reimport
   at t2; single raw row, single article row).
3. Cross-source observation — distinct raw_items row per (source_id, identity) with its own
   provenance; articles not duplicated (test_same_normalized_item_from_different_source
   asserts 2 raw rows / 1 article row; probe4 delta raw +1, delta articles 0).
4. Mixed counts + full-batch rollback — exact inserted/skipped (2/2 in mixed test);
   validation failure and mid-batch SQL failure roll back articles+raw_items+the newly
   inserted source row (asserted; `in_transaction False` after failure).
5. Migration/index changes — additive (CREATE IF NOT EXISTS, PRAGMA-guided ALTER), idempotent
   (run twice on fresh + real pre-upgrade DB); articles/articles-upgrade ordering fixed so
   indexes are built after columns; P1–P5 all green.
6. Tests — isolated (in-memory + temp-dir patching; LivePublicFeedContractTests asserts the
   real live DB file is untouched); RED before GREEN reproduced (6 failures on parent);
   no public endpoint exposes raw/provenance fields.

## Layer 2 — code quality

- Solid transactional design: BEGIN IMMEDIATE own-transaction, SAVEPOINT when caller already
  in a transaction; count map returned is honest about article writes.
- Untrusted-content handling preserved (fields whitelisted, parameterized inserts, no
  execution of imported text).
- Two P3 nits above. No P0/P1/P2 defects found with evidence.

## Not verified

- `checks/p6.py` does not exist anywhere in the repo (PLAN.md phase 6 points at it but the
  file was never added), so the official P6 referee gate could not be run; verification
  relied on the focused P6 tests, the real-DB upgrade probe, and P1–P5 gates. This is a
  harness gap, not a candidate defect (checks/ is outside files_allowed).
