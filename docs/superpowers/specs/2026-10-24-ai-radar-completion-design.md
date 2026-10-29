# Vũ Học AI Radar — completion design contract

**Date:** 2026-10-24  
**Scope:** Complete the remaining implementation from the current end-of-Phase-5 baseline through Phase 11, the v2.0 product-completion tasks, and the release-candidate QA tasks in `.team/plans/remaining.md`.

## Intent

Finish Vũ Học AI Radar as a localhost-only Vietnamese editorial radar that can safely ingest user-provided or permitted official-source data, normalize and verify it, keep internal provenance private, and expose only reviewed public content. The existing React 19 + Vite frontend, FastAPI + SQLite backend, migration contract, SAMPLE isolation, and seven-group shell remain the foundation.

The first release milestone is not “show something that looks real”; it is a trustworthy local workflow:

`COLLECT/MANUAL IMPORT → NORMALIZE → DEDUPLICATE → VERIFY → AI ENRICH (optional) → REVIEW → PUBLISH → PUBLIC FEED/RADAR`

No external source is called successful unless a real local run produces evidence. SAMPLE, DRAFT, UNVERIFIED and internal provenance never become public facts.

## Goals

- Close the real P5 feed contract with a provenance-backed `REAL/PUBLISHED` fixture or manual-import path without relabeling SAMPLE data.
- Complete Markdown/CSV/JSON import, deduplication and provenance retention.
- Add model/provider/offer exploration and safe, published-only search/filter APIs.
- Add verification records, quota observations, change detection and server-side admin workflow.
- Add server-only source registry, bounded RSS/Atom collection and manual fallback.
- Add deterministic editorial fallback and an OpenAI-compatible gateway that validates output and never auto-publishes.
- Add Daily Radar, stale state, manual refresh, one-command localhost startup and release documentation.
- Add the v2 taxonomy, bookmarks/article dialog, permitted GitHub/news manual or official-source paths, security tests, SQLite backup/restore and final acceptance reporting.
- Preserve localhost binding, legacy bookmark data, existing public articles, migration idempotence and the no-secret-in-bundle rule.

## Non-goals

- No production deployment, cloud hosting, GitHub push, remote creation or merge.
- No CAPTCHA, login, paywall, rate-limit or terms-of-service bypass.
- No automatic publication, automatic verification or fabricated quotas, prices, credits, expiry dates or “free” claims.
- No PostgreSQL, Redis, Docker or external hosting requirement.
- No broad refactor of the existing UI or framework migration.
- No editing `checks/`, `PLAN.md` or `docs/MISSION.md`.

## Anti-goals

- A visually complete UI backed by invented records is a failure.
- A collector that treats timeout as model removal is a failure.
- A public endpoint that returns raw source registry, provenance, reviewer notes, SAMPLE or DRAFT data is a failure.
- A gateway that logs API keys, executes article text, or publishes invalid AI output is a failure.
- A backup/restore script that deletes or overwrites the original database without explicit validated targets is a failure.

## Constraints

- Bind services to `127.0.0.1` only; frontend `5173`, backend `8000`.
- Keep React 19 + Vite and FastAPI + SQLite.
- Use `uv` and the repository `.python-version`; keep dependencies declared and locked.
- Keep all external content untrusted data, never instructions or commands.
- Use parameterized SQL and allowlisted filter values.
- Keep admin authentication server-side using a runtime environment token; never embed it in frontend code.
- Any source without a permitted official API/RSS path stays `manual` and `UNVERIFIED`.
- Every behavior change follows TDD: observe a focused failing test, implement the minimum, then run the full available suite.
- Each task is reviewed independently, and final integration review is performed on exact HEAD.

## Approaches considered

### A. Sequential phase contract (selected)

Implement the existing dependency order: close P5/P6, then P7/P8, P9/P10, P11, and finally v2.0/QA. Each task owns a coherent test cycle and is reviewed before its dependents start. This is the safest choice because the repository has a shared `main.py`, shared schema, and public/private data-boundary risks.

### B. Vertical slice first

Build import → review → publish → feed → Explorer as one visible slice, postponing collectors and AI. This would show a demo sooner, but it would cross the current phase contracts and make migration, auth and data-boundary defects harder to isolate.

### C. Broad parallel implementation

Run backend, frontend, collectors and release documentation workers at once. This could reduce elapsed time, but the shared schema/API/UI files would create merge and integration risk and would weaken the required sequential review gates.

**Decision:** use A, with worker/reviewer tasks small enough to run independently and a final integration review. Parallel work is limited to tasks with disjoint files and no unmet dependency.

## Architecture decisions

### Data and publication boundary

`raw_items` stores normalized source content and provenance. `articles` stores editorial records with `DRAFT`, `PENDING_REVIEW` or `PUBLISHED`. Public queries require `PUBLISHED` and exclude `data_origin = SAMPLE`; admin queries require runtime authentication and may expose internal fields. Import always creates DRAFT records. Only an explicit admin transition can publish.

Deduplication uses the tuple `(canonical_url, normalized_title, content_hash)` inside a transaction. Existing records are preserved; repeated input increments/skips rather than overwriting provenance. A source-specific provenance history remains available to authenticated admin code.

### Explorer and radar

Provider/model relationships stay normalized through `provider_models`, allowing one model to have different quotas, prices and verification states per provider. Explorer/search/radar queries use parameterized SQL and explicit allowlists. A timeout or unavailable source produces a collection failure/stale signal, never `MODEL_REMOVED`.

### Source collection

`source-registry/sources.json` is loaded server-side only. Each source declares its permitted method. RSS/Atom collection uses bounded timeout, finite retry/backoff, redirect/host safety checks and `collection_runs`; sources without a permitted path use manual import.

### Editorial AI

Rule-based classification is always available. The optional gateway reads `AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL` only from environment variables. Gateway output is parsed into a strict schema, rejected on invalid enums/fields, redacted in logs, and kept in DRAFT/PENDING_REVIEW. Gateway failure falls back to deterministic rules.

### Frontend

The frontend uses one shared fetch/error/loading model for feed, search, Explorer, radar and admin screens. Public UI renders escaped text through React, keeps bookmarks in versioned localStorage with defensive legacy migration, and uses an accessible article dialog. Admin token input is runtime-only and never bundled.

## Required public/admin interfaces

- `GET /api/health`
- `GET /api/articles` — published, non-SAMPLE fields only
- `GET /api/search?q=&category=&window=` — published-only search
- `GET /api/models` — allowlisted filters; no internal fields
- `GET /api/radar?window=today|7d|30d|all`
- `POST /api/admin/import` — requires the same server-side runtime admin-token check as every admin route; creates DRAFT records
- Admin endpoints for review, verification, collection refresh and radar refresh — token required, runtime-only
- `GET /api/admin/sources`, `GET /api/admin/reviews`, and observation/change endpoints remain internal and never feed public assets

The auth helper and token contract land before any admin route is exposed. Exact response fields and status transitions will be fixed in the implementation plan and tests before each task is dispatched; publication is only allowed from an authenticated server-side `APPROVED` review state.

## Acceptance contract

| Requirement | Instrument | Wrong implementation rejected | Limit |
|---|---|---|---|
| P5 public feed works through Vite proxy | `checks/p5.py` plus a provenance-backed `REAL/PUBLISHED` fixture | Direct backend works but proxy returns HTML/empty data | Requires an approved real/manual fixture; SAMPLE cannot satisfy it |
| Import supports Markdown/CSV/JSON | focused unittest/API tests | One format silently accepted as another or malformed upload partially commits | Does not prove external source freshness |
| Dedup is idempotent | repeat-import test and SQLite row counts | Same item creates extra raw/article rows or overwrites provenance | Does not prove semantic duplicate detection beyond the tuple |
| Public/private boundary holds | API contract tests with SAMPLE/DRAFT/REAL rows | Public response leaks notes, provenance, registry or unreviewed rows | Does not replace a formal penetration test |
| Explorer filters are safe | parameterized API tests with injection-shaped params | SQL concatenation, cross-provider mixing or unverified-as-fact output | Query completeness depends on fixture coverage |
| Change detection is conservative | before/after unit tests | Timeout emits `MODEL_REMOVED` or misses FREE/PAID/quota/offer events | Does not prove real provider freshness |
| Admin workflow is server-owned | token/state-transition tests | Client-only auth or unauthorized publish/verify succeeds | Token transport/security outside localhost remains out of scope |
| Collector is bounded | local RSS fixtures for valid, malformed, timeout, redirect and duplicate feeds | Infinite retry, SSRF to private host, or unsafe redirect | External network freshness remains NOT_VERIFIED unless observed |
| AI fallback is safe | fake gateway tests for valid/invalid/timeout/missing key | Invalid output publishes, secret logs, or article text executes | Model quality is not automatically assessed |
| Radar is factual and stale-aware | time-window/stale/manual-refresh tests | Synthetic findings or stale data shown as current | Scheduler only runs while backend is alive |
| Startup and release docs are usable | `scripts/dev.ps1 -Check`, real startup, docs command audit | Claims success without runnable commands or binds publicly | Windows prerequisites still matter |
| Bookmark migration works | browser/localStorage tests | Legacy data is lost, duplicated or dialog is inaccessible | Browser automation must be available for full PASS |
| Backup/restore preserves data | temp-target row-count and invalid-file tests | Original DB deleted or invalid backup restored | Does not replace disaster-recovery testing |

## Risk controls

- Migration changes are additive and idempotent; no `DROP`, reset or implicit data deletion.
- Import and collector writes use transactions and bounded input sizes.
- URL policy rejects credentials, private/metadata hosts and unsafe redirects where network collection is involved.
- Logs redact secrets and external content is never passed to shell/file operations.
- Public payloads are explicit field lists, not `SELECT *`.
- Every phase records PASS/FAIL/BLOCKED/NOT_VERIFIED from commands, not worker claims.
- Existing dirty bootstrap files and `.team/` artifacts are protected; no reset/clean/stash is allowed.

## Implementation boundary for the plan

The implementation plan will split the work into these dependency groups:

1. P5 feed fixture/contract closure.
2. P6 dedup and importer integration.
3. P7 Explorer API and UI.
4. P8 verification/change detection/admin boundary/UI.
5. P9 registry and bounded collectors.
6. P10 editorial schema/rules/gateway.
7. P11 radar/startup/release docs.
8. v2 search/taxonomy, bookmarks/dialog, GitHub/news manual paths.
9. security/invalid-input audit, backup/restore and final acceptance report.

No production code, dependency installation or generated artifact is authorized by this contract until the design is approved and the task plan is written.
