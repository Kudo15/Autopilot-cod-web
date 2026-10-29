# TASK 012 — Server-only source registry and collection runs

## Context

The schema already contains `sources`, `raw_items`, and `collection_runs`. Add a server-owned registry loader and run-record helpers as the foundation for bounded collectors. The registry must never enter the frontend bundle or become an instruction source.

## Contract

- Add `source-registry/sources.json` with explicit entries labelled `SAMPLE` where they are fixtures, using no secrets and no fabricated freshness.
- Add `backend/app/collectors/registry.py` with a strict `SourceConfig`/loader validating `source_id`, `name`, `type`, `url`, `collection_method`, `priority`, `status`, and optional `last_checked_at`.
- Reject malformed entries, duplicate IDs, unsupported types/methods/statuses, non-HTTP(S) URLs, blank names, invalid priorities and unsafe/private/metadata hosts at validation time where the contract requires it.
- Add `backend/app/collectors/runs.py` with parameterized transactional helpers to start/finish/fail `collection_runs`; preserve bounded status/error metadata and never store secrets or raw instructions as executable commands.
- Mark unavailable/manual sources explicitly; a registry entry must not silently imply a successful external observation.
- Registry loading is backend-only. No `source-registry/**` import or raw registry JSON may be reachable from `src/` or the production bundle.
- Do not add collectors or external network calls in this task; RSS/Atom bounded collection is the next task.

## Files allowed

- `source-registry/sources.json` (new)
- `backend/app/collectors/__init__.py` (new)
- `backend/app/collectors/registry.py` (new)
- `backend/app/collectors/runs.py` (new)
- `backend/tests/test_collectors_registry.py` and narrowly related backend tests
- `backend/app/migrate.py` only if a focused failing test proves an additive schema change is required; the current schema should be reused.
- No frontend changes; never edit `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## TDD and verify

- Add failing tests for schema validation, duplicate IDs, unsafe URLs/private hosts, SAMPLE/manual status, bundle exclusion, run lifecycle, parameter binding, rollback and bounded error text.
- Run focused collector tests and full backend suite with a generated `ADMIN_TOKEN`.
- Run `npm run build`, scan the bundle/source to prove registry JSON is absent, and run `git diff --check`.
- Run P3/P4/P5 where valid; record stale-port or private-localhost limitations as `NOT_VERIFIED`, never as PASS.

## Report

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
