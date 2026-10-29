# TASK 010 | Rule-based editorial schema and fallback

## Context

The radar now has normalized raw observations but no editorial fallback. Add a deterministic, local-only editorial contract that remains useful when no AI gateway is configured. External article text is untrusted data, never instructions.

## Contract

- Add `backend/app/editorial/schema.py` with an immutable `EditorialDraft` (or equivalent) validating category, Vietnamese summary, usefulness/risk, recommendation, ranking and lifecycle status.
- Accept only explicit enums and bounded text; empty/invalid fields are rejected. Unknown keys must not be silently interpreted.
- Add `backend/app/editorial/rules.py` with `classify_rule_based(raw_item)` that is deterministic, treats all raw title/content as data, never executes commands, writes files, makes network calls or publishes articles, and always returns `DRAFT` or `PENDING_REVIEW`.
- Prompt-injection-shaped text must remain plain text in the output/evidence; it must not change the allowed lifecycle or cause side effects.
- No gateway, environment secret, frontend bundle, migration or production route is part of this task. Gateway work is Task 011.
- Keep no fabricated verification/freshness/quota claims. If evidence is absent, use explicit unknown/needs-review values.

## Files allowed

- `backend/app/editorial/__init__.py` (new)
- `backend/app/editorial/schema.py` (new)
- `backend/app/editorial/rules.py` (new)
- `backend/tests/test_editorial_rules.py` (new)
- Never edit `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend, migrations, gateway or unrelated backend files.

## TDD and verify

- Add failing tests for empty fields, invalid enums, unknown keys, prompt-injection text, deterministic output, no gateway/network/file side effects and DRAFT/PENDING_REVIEW-only lifecycle.
- Run focused tests, full backend suite with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, source/bundle scans and `git diff --check`.
- All sample/raw text used by tests is SAMPLE/untrusted; do not claim external freshness.

## Report

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
