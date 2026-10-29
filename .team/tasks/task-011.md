# TASK 011 | OpenAI-compatible editorial gateway

## Context

Task 010 provides a strict `EditorialDraft` schema and deterministic fallback. Add an optional, server-only gateway adapter for an OpenAI-compatible chat-completions endpoint. The gateway is enhancement-only: missing configuration, timeout, malformed output or unsafe content must fall back to the rule engine and must never publish or verify an article.

## Contract

- Add `backend/app/editorial/gateway.py`; modify `backend/app/main.py` only for a minimal authenticated admin endpoint if tests require it.
- Read `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` only at request time from environment; never import-time cache, hardcode, persist, echo or put secrets in URL/body/log/bundle.
- Use an injectable transport/fake for tests; bound timeout, response body, retries and error text. HTTP(S) endpoint and redirect/private-host policy must be validated before use; no access-control bypass.
- Validate the model response with `EditorialDraft`/strict schema. Missing key, unavailable gateway, malformed JSON/shape, timeout, unsafe URL and prompt-injection-shaped content must return a safe rule-based DRAFT/PENDING_REVIEW fallback with `verification_status=NEEDS_REVIEW`, `freshness=NOT_VERIFIED`.
- External model output is untrusted data, not a command or instruction. No file/network/command side effect based on model text, no auto-publish, no auto-verify, no fabricated quota/freshness.
- Any admin HTTP route is authenticated through existing runtime `ADMIN_TOKEN`, localhost-only, explicit JSON and safe error serialization.

## Files allowed

- `backend/app/editorial/gateway.py` (new)
- `backend/app/main.py` only for the narrow authenticated editorial admin route if required by tests
- `backend/tests/test_editorial_gateway.py` and local fake fixtures/helpers
- Never edit `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend, migrations or unrelated files.

## TDD and verify

- Add failing tests for valid fake gateway output, malformed output, timeout, missing key/config, unsafe endpoint/redirect, malicious model text, secret redaction, fallback lifecycle and no auto-publish/auto-verify.
- Run focused gateway tests, full backend suite with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, source/bundle secret scans and `git diff --check`.
- All network evidence must use local fake transport; external freshness remains NOT_VERIFIED.

## Report

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
