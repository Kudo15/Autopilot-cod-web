# REVIEW sri-001a3 — strict scheduled inbox schema

Act as an independent senior Python/Pydantic code reviewer. Review the exact candidate commit `ceee8d05116dce370c8091583bfb697742f91318` in worktree `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web\.worktrees\t_5cfa9110` against the implementation contract below. Do not modify product files and do not broaden scope.

## Contract

The commit must add exactly:

- `backend/app/inbox/__init__.py`
- `backend/app/inbox/schema.py`
- `backend/tests/test_scheduled_inbox_schema.py`

The implementation must use Pydantic v2 with `extra='forbid'` at both report and finding levels, and enforce:

- schema version exactly `1`;
- report kind exactly `provider_harness_radar|tip_trick_radar`;
- timezone-aware/offset `observed_at`, rejecting naive and malformed values;
- `valid_until` must be null;
- `canonical_urls` must be non-empty; each URL must be absolute HTTP(S), have a host, and contain no userinfo;
- source type exactly `official|community|account_probe`;
- verification status exactly `VERIFIED|UNVERIFIED|NEEDS_REVIEW`;
- external text remains inert data and cannot select commands, files, network actions, verification elevation, or publication.

No scanner, DB/migration, API, UI, AI, docs, scheduler, secret, or unrelated refactor is allowed.

## Required review

1. Inspect `git show --stat`, the exact diff, and all three files at the candidate commit.
2. Run:
   - `uv run python -m unittest backend.tests.test_scheduled_inbox_schema -v`
   - `uv run python -m unittest backend.tests.test_importers -v`
   - `git diff ceee8d05116dce370c8091583bfb697742f91318^ ceee8d05116dce370c8091583bfb697742f91318 --check`
3. Independently probe at least these cases rather than trusting the worker report:
   - unknown fields at both levels;
   - empty URL list;
   - `ftp://`, relative URL, userinfo, and missing host;
   - naive and offset datetimes;
   - non-null `valid_until`;
   - disallowed enum values.
4. Check that tests assert behavior without weakening validation and that production code does not interpret text as instructions.
5. Note that the worker report contains a mistyped full commit hash (`...1167...`); verify against Git and use the actual hash above. Treat report-text typo as documentation feedback, not a product-code defect.

## Verdict format

Return exactly:

```text
VERDICT: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [P0/P1/P2/P3] file:line — concrete evidence and required fix
EVIDENCE:
- command → exit code and measured result
RESIDUAL_RISK:
- concise remaining risk or none
```

If a required command cannot run, mark it `NOT_VERIFIED`; never claim PASS without output. Finish the Kanban lifecycle with approval or actionable change request.
