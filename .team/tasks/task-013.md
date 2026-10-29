# TASK 013 — Bounded RSS/Atom collector

## Context

Task 012 provides strict server-only source validation and transactional `collection_runs`. Add the bounded RSS/Atom adapter on top of that foundation. Keep external content untrusted data and use only local fixtures/fakes in verification.

## Contract

- Add `backend/app/collectors/rss.py` with a public `collect_feed(source, client=..., now=...) -> CollectionResult` (or equivalent explicit result) and no hidden global network client.
- Use stdlib XML parsing or an already-installed dependency; do not expand `pyproject.toml` unless a failing test proves it is necessary. No CAPTCHA, login, paywall or rate-limit bypass.
- Enforce localhost-only operation for the app itself and a strict outbound URL/redirect policy: HTTP(S) only, reject private/loopback/link-local/metadata/CGNAT hosts, cap redirects, reject unsafe redirect targets, and never follow arbitrary schemes.
- Bound timeout, body size, item count, retry count and backoff; timeout/malformed XML/unsafe redirect must return a bounded failure and must never claim success.
- Parse RSS 2.0 and Atom title/link/summary/content fields as untrusted text. Normalize canonical URL/title/content hash; ignore malformed items safely.
- Persist raw observations and collection-run status transactionally using existing schema/helpers. Repeated identical items must not create duplicate raw rows; preserve source/data_origin and do not publish articles.
- External freshness is `NOT_VERIFIED` unless observed through a real permitted run; local fixtures must be labelled SAMPLE.
- No frontend changes and no production deployment.

## Files allowed

- `backend/app/collectors/rss.py` (new)
- `backend/app/collectors/__init__.py` only for a narrow export if needed
- `backend/app/collectors/runs.py` only for a narrowly related helper test proves necessary
- `backend/app/main.py` only if a minimal, authenticated admin collection route is required by a failing contract test
- `backend/tests/test_collectors_rss.py` and local feed fixtures under `backend/tests/fixtures/`
- Never edit `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend files or unrelated migrations.

## TDD and verify

- Add failing tests for RSS/Atom local fixtures, malformed XML, missing fields, duplicate item, timeout, retry/backoff, unsafe redirect/private host, body/item bounds and transactional rollback.
- Run focused collector tests and full backend suite with generated `ADMIN_TOKEN`.
- Run `npm run build`, P3/P4/P5, `git diff --check`, and source/bundle scans proving no raw feed fixture or external registry is imported by frontend.
- All network evidence must be local fake/fixture evidence; external freshness is `NOT_VERIFIED`.

## Report

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
