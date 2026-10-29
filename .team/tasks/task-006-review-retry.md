# REVIEW RETRY TASK 006 — independent P6 dedup review | role: reviewer | harness: hermes-kanban

Review exact candidate commit `daf8abee5b17c6f8b1d1dc827b8856a366f869db` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_8d65f6f4`, parent `7eb27d4`. This is a retry because the first reviewer hit a provider quota wall; use the fallback model assigned by the coordinator.

Use the Code Review Agent template. Do not edit product files. Inspect only the exact candidate commit and verify:

1. Dedup identity is normalized `(canonical_url, normalized_title, content_hash)`.
2. Same-source reimport creates no duplicate raw/article rows and preserves provenance/fetched time.
3. Cross-source observation stays traceable in `raw_items` without overwriting provenance or duplicating `articles`.
4. Mixed counts and full-batch rollback are exact, including source-row rollback.
5. Migration/index changes are additive/idempotent and P1–P5 remain green.
6. Tests are isolated, show RED before GREEN, and no public endpoint exposes raw/provenance fields.

Run focused and full backend tests, UTF-8 `checks/p3.py`, `checks/p4.py`, `checks/p5.py`, `npm run build`, `git diff --check`, and inspect allowed-file scope.

Return exactly:

```
VERDICT: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [P0/P1/P2/P3] file:line — concrete evidence and required fix
EVIDENCE:
- command → exit code and measured result
```
