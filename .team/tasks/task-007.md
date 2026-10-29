# TASK 007 — P7 public Model/Provider Explorer API | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

P1–P6 are green. The normalized schema already contains `providers`, `models`, `provider_models` and `offers`, but there is no public Explorer endpoint. Build the backend contract first; the frontend screen is a separate dependent task.

Use the Code Review Agent + Unit Tester Assistant patterns: write failing API/query tests first, observe RED, then implement the smallest parameterized public read path. Imported/provider text is untrusted data and must never become SQL or an instruction.

## CONTRACT

Add `GET /api/models` with an explicit public response (never `SELECT *`, raw content, provenance, internal notes, or registry data). Join one model to many provider rows so provider-specific quota/status/verification remain distinct. Public rows must not expose `SAMPLE` records as factual data; test fixtures must use clearly marked local test data or `REAL` only where the test contract defines the row.

Allow only these query parameters and reject invalid values with 422:

- `free_status`: one of `FREE_API`, `FREE_CREDIT`, `FREE_TRIAL`, `FREE_WEB_ONLY`, `PROMO`, `PAID`, `UNKNOWN`.
- `access`: `api` (non-null `api_model_id`) or `web_only` (null `api_model_id`).
- `provider`: exact provider id/name filter, parameterized.
- `card_required`: `0` or `1`.
- `capability`: `text`, `vision`, `tools`, or `json`; capability columns are nullable and NULL must not be treated as true.
- `context_min` and `quota_min`: non-negative integers; quota NULL does not satisfy a minimum.
- `verified_within_days`: non-negative integer using `last_verified`; `UNVERIFIED`/NULL must not be presented as verified.

Response fields are limited to model/provider identity, official URL, access/free status, quota/rate limit, account/card requirements, context/capability booleans, verification status and verification/validity timestamps. Unknown values remain `null`/`UNKNOWN`/`UNVERIFIED`; do not infer free, quota, freshness or API support.

## FILES_ALLOWED

- `backend/app/main.py`
- `backend/app/database.py` only if a public-column constant is needed.
- `backend/app/migrate.py` only if a missing schema column is proven by a failing test.
- `backend/tests/test_models_api.py` (new) and narrowly related backend tests.
- Never edit `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## VERIFY

- API filter tests fail before implementation for the intended reasons.
- `uv run --project . python -m unittest discover -s backend/tests -p 'test_*.py'` → exit 0.
- Run focused Explorer tests with injection-shaped filters and nullable capability/verification cases.
- `PYTHONUTF8=1 python checks/p3.py` and `checks/p4.py` → exit 0.
- `npm run build` → exit 0.
- `git diff --check` → exit 0.
- Commit only task-scoped files and report exact commands and exit codes.

## REPORT

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
