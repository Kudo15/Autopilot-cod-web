# Vũ Học AI Radar Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete the remaining Vũ Học AI Radar localhost product from the current P5/P6 baseline through P11, v2.0 product completion and release-candidate QA.

**Architecture:** Keep React 19 + Vite, FastAPI + SQLite and localhost-only binding. Build the safe content pipeline `IMPORT/COLLECT → NORMALIZE → DEDUPLICATE → VERIFY → AI ENRICH → REVIEW → PUBLISH`, with explicit public/admin field boundaries and server-owned publication state.

**Tech Stack:** React 19, Vite 7, FastAPI, Pydantic, SQLite, uv/Python 3.13, HTTPX/feedparser where needed, PowerShell, unittest/pytest-compatible tests and Playwright when available.

**Spec:** `docs/superpowers/specs/2026-10-24-ai-radar-completion-design.md`

## Global Constraints

- Never modify `checks/`, `PLAN.md` or `docs/MISSION.md`.
- Only change files listed by the active task and preserve existing dirty bootstrap files.
- Bind only to `127.0.0.1`; do not deploy, push, merge or create remotes.
- Do not fabricate provider/model/quota/promo/expiry data. SAMPLE/DRAFT/UNVERIFIED remain non-public.
- Treat external content as untrusted data; never execute it or turn it into instructions.
- Use TDD: write a focused failing test, observe the expected failure, implement the minimum, then run the full available suite.
- Admin routes require server-side runtime authentication; never bundle tokens or secrets.
- Every task must report exact commands and exit codes, including BLOCKED/NOT_VERIFIED conditions.
- Each task gets a fresh worker and independent reviewer through `.team/scripts/route.mjs`; coordinator does not implement production code.

## Review Focus

- Published-only public APIs must reject SAMPLE, DRAFT, internal notes and provenance.
- Duplicate import must not create rows or overwrite existing provenance.
- Query filters must resist SQL injection-shaped values and preserve multi-provider relationships.
- Collector redirects/private hosts/timeouts must be bounded and safe.
- AI gateway failures or malformed output must fall back without publish/verify side effects.
- Browser UI must preserve legacy bookmarks, escape article data and expose loading/empty/error states.
- Backup/restore must never delete the original database or accept an invalid target.

## Baseline reconciliation

- Existing P1–P4 referee gates are green outside the sandbox.
- Existing P5 implementation has proxy/feed wiring but fails because the database contains no `REAL/PUBLISHED` article. Task 1 closes this with provenance-backed local/manual data; it must not relabel SAMPLE.
- Existing normalization and Markdown/CSV/JSON parser tests pass in uv. Task 2 hardens persistence with deduplication and idempotence rather than replacing those helpers.
- P6–P11 referee files are absent; use focused tests, HTTP fixtures, browser checks and documented NOT_VERIFIED results until an approved referee exists.

---

### Task 1: Close P5 with a real published feed fixture

**Files:** Modify `backend/app/seed.py` only if a permitted, provenance-backed fixture is available; otherwise add a local test fixture under `backend/tests/fixtures/`; modify `backend/tests/test_public_articles.py`, `src/App.jsx` or `src/components/GroupView.jsx` only for a failing behavior; do not modify `checks/p5.py`.

**Interfaces:** `GET /api/articles` returns at least one `REAL/PUBLISHED` article through the Vite proxy while excluding SAMPLE/DRAFT/internal fields.

- [x] Write a failing integration test proving the current seeded database produces an empty public feed and defining the approved fixture/provenance shape.
- [x] Run the focused test and observe the failure for the intended reason.
- [x] Add the smallest provenance-backed fixture or manual-import setup; never invent a provider claim and never relabel SAMPLE.
- [x] Run `PYTHONIOENCODING=utf-8 python checks/p5.py` outside sandbox and `npm run build`.
- [x] Run the full backend suite; commit only task-scoped files.
- [x] Fresh reviewer reproduces proxy HTTP, non-empty public JSON and secret scan.

### Task 2: Complete P6 deduplication and provenance persistence

**Files:** Modify `backend/app/ingest/importers.py`, `backend/app/migrate.py`, `backend/app/database.py`; add/update `backend/tests/test_importers.py` and focused fixtures.

**Interfaces:** Repeated `(canonical_url, normalized_title, content_hash)` input returns `skipped` without new rows or overwriting provenance; distinct source observations remain traceable.

- [x] Add failing tests for duplicate same-source import, duplicate cross-source import, mixed batch insert/skip counts and transaction rollback.
- [x] Observe RED with the current direct insert behavior.
- [x] Add additive/idempotent indexes or uniqueness strategy and transaction-safe lookup/insert logic.
- [x] Verify counts before/after repeated imports, provenance retention and malformed-input rollback.
- [x] Run `uv run python -m unittest discover -s backend/tests -p 'test_*.py'` and database migration twice.
- [x] Reviewer checks no destructive migration and no public raw-field leakage.

### Task 3: Model/provider/offer query API

**Files:** Modify `backend/app/main.py`; add `backend/tests/test_models_api.py`.

**Interfaces:** `GET /api/models` supports allowlisted free/API/card/capability/provider/context/quota/recent-verification filters and returns explicit public fields only.

- [x] Write failing tests for one model with multiple providers, UNKNOWN/UNVERIFIED exclusion rules and injection-shaped filters.
- [x] Implement parameterized queries and explicit response serialization.
- [x] Verify with seeded SQLite fixtures and HTTP calls.
- [x] Run all backend tests and source secret scan; reviewer checks SQL and public boundary.

### Task 4: Explorer, comparison and promotion UI

**Files:** Modify `src/App.jsx`, `src/components/**`, `src/data/groups.js`, `src/styles.css`; add frontend tests only if a runner is introduced within scope.

**Interfaces:** UI calls `/api/models`, renders model/provider/API ID/free status/quota/verification/official CTA, preserves loading/empty/error and local comparison selection.

- [x] Add a failing UI/fixture check for loading, empty, error, filter and unverified labeling.
- [x] Implement the smallest responsive Explorer view without embedding model data.
- [x] Verify `npm run build`, bundle secret scan and local HTTP fixture behavior.
- [x] Reviewer checks accessibility and no internal registry/provenance strings in bundle.

### Task 5: Quota observations and change detection

**Files:** Add `backend/app/radar/changes.py`, `backend/app/radar/quota.py`; add `backend/tests/test_radar_changes.py`.

**Interfaces:** `record_observation(...)` persists snapshots; `detect_changes(before, after)` emits only allowed event types; timeout never emits `MODEL_REMOVED`.

- [x] Write failing tests for FREE↔PAID, quota, offer expiry, terms, new/removed provider/model and timeout.
- [x] Implement deterministic snapshot diff and idempotent event persistence.
- [x] Verify SQLite events and stale/expired transitions with fixed timestamps.
- [x] Reviewer reproduces the timeout counterexample.

### Task 6: Admin auth and server-owned review workflow

**Files:** Add `backend/app/auth.py`; modify `backend/app/main.py`; add `backend/tests/test_admin_workflow.py` and related importer tests.

**Interfaces:** All `/api/admin/*` routes require constant-time comparison against runtime `ADMIN_TOKEN`; transitions use the existing schema-owned `PENDING_REVIEW`, `REJECTED`, and `PUBLISHED` states, with publish requiring an authenticated pending-review ledger step.

- [x] Write failing tests for missing/wrong token, public leakage, unauthorized publish/verify and invalid state transitions.
- [x] Implement auth dependency and explicit admin serializers; preserve localhost operation when token is configured.
- [x] Verify 401/403 responses, public response key scans and no token in source/bundle/logs.
- [x] Reviewer checks route coverage, timing-safe comparison and default-deny behavior.

### Task 7: Admin review UI

**Files:** Add `src/components/AdminRadar.jsx`, `src/components/ReviewDialog.jsx`; modify `src/App.jsx`, `src/styles.css`.

**Interfaces:** Runtime token input only; review list/dialog displays safe status and errors; UI cannot bypass server-side publication rules.

- [x] Add failing UI checks for 401/403/empty/loading and keyboard-close behavior.
- [x] Implement review controls that call authenticated APIs without embedding token.
- [x] Verify build and bundle scan for secrets/internal fields.

### Task 8: Server-only source registry and collection runs

**Files:** Add `source-registry/sources.json`, `backend/app/collectors/__init__.py`, `backend/app/collectors/registry.py`, `backend/app/collectors/runs.py`; add tests.

**Interfaces:** `SourceConfig` validates `source_id,name,type,url,collection_method,priority,status,last_checked_at`; registry is not imported by frontend.

- [x] Write failing registry/schema and bundle-exclusion tests.
- [x] Implement server-side loading and `collection_runs` persistence; mark unavailable sources manual.
- [x] Verify registry fields, database run records and bundle scan.

### Task 9: Bounded RSS/Atom collector

**Files:** Add `backend/app/collectors/rss.py`; add local feed fixtures and tests. No `main.py` route was required by the contract tests.

**Interfaces:** `collect_feed(source, client=...) -> CollectionResult` with bounded timeout/retry/backoff, redirect/host policy and duplicate handling.

- [x] Write failing tests for valid local feed, malformed XML, timeout, unsafe redirect/private host and duplicate item.
- [x] Implement a stdlib bounded RSS/Atom adapter without external access-control bypass.
- [x] Persist raw items and collection runs transactionally.
- [x] Verify only with local fixtures; mark external freshness NOT_VERIFIED unless actually observed.

### Task 10: Rule-based editorial schema and fallback

**Files:** Add `backend/app/editorial/__init__.py`, `backend/app/editorial/schema.py`, `backend/app/editorial/rules.py`; add tests.

**Interfaces:** `EditorialDraft` validates category, summary, risk, recommendation and status; `classify_rule_based(raw_item)` always returns DRAFT/PENDING_REVIEW.

- [x] Write failing tests for empty fields, invalid enums, prompt-injection text and no gateway.
- [x] Implement deterministic classification that treats article text as data.
- [x] Verify no file/command side effects and schema rejection.

### Task 11: OpenAI-compatible editorial gateway

**Files:** Add `backend/app/editorial/gateway.py`; modify `backend/app/main.py`; add fake-gateway tests.

**Interfaces:** Reads `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` only from environment; bounded request; schema-valid output only; fallback on timeout/malformed response.

- [x] Write failing tests for valid fake gateway, malformed output, timeout, missing key and malicious content.
- [x] Implement redacted logging, validation and no auto-publish/auto-verify.
- [x] Verify fake gateway journey, logs and bundle have no secrets.

### Task 12: Daily Radar and stale status

**Files:** Add `backend/app/radar.py`; modify `backend/app/main.py`; add tests.

**Interfaces:** `GET /api/radar?window=today|7d|30d|all`, `POST /api/admin/radar/refresh`; current/stale state and `SIGNAL_WEAK` for empty evidence only.

- [x] Write failing tests for windows, stale threshold, empty output and manual refresh.
- [x] Implement aggregation from published articles/change events only; schedule 07:00 Asia/Ho_Chi_Minh while backend runs.
- [x] Verify HTTP and SQLite output with SAMPLE excluded.

### Task 13: One-command startup

**Files:** Add `scripts/dev.ps1`, `.env.example`; modify `scripts/**` only as required.

**Interfaces:** `scripts/dev.ps1 -Check` validates prerequisites/ports/dependencies; normal mode migrates DB and starts backend/frontend on localhost.

- [x] Add failing PowerShell checks for missing prerequisite, busy port and backend failure.
- [x] Implement bounded process startup and clear cleanup guidance.
- [x] Verify `./scripts/dev.ps1 -Check` and a real localhost startup outside sandbox.

### Task 14: Release documentation

**Files:** Add `README_LOCAL.md`, `docs/ARCHITECTURE.md`, `docs/DATA_SOURCES.md`, `docs/DATA_SCHEMA.md`, `docs/PHASE_REPORT.md`, `docs/QA_REPORT.md`.

- [x] Build a documentation checklist against observed commands and API journeys.
- [x] Document only verified claims, with SAMPLE/REAL and BLOCKED/NOT_VERIFIED labels.
- [x] Verify commands are copy-pasteable and no secret appears.

### Task 15: v2 taxonomy and search

**Files:** Modify `backend/app/main.py`, `backend/app/explorer.py`, `src/data/groups.js`, `src/App.jsx`, `src/components/**`, `src/styles.css`; add tests.

**Interfaces:** Six public categories and `GET /api/search?q=&category=&window=` returning published-only records.

- [x] Write failing search/category/empty/error/SAMPLE-exclusion tests.
- [x] Implement parameterized search and shared accessible UI state.
- [x] Verify build and HTTP fixture responses.

### Task 16: Bookmark migration and article dialog

**Files:** Modify `src/App.jsx`; add `src/hooks/useBookmarks.js`, `src/components/ArticleDialog.jsx`; add browser/component tests as available.

- [x] Write focused contract coverage for legacy-key migration, duplicate bookmark, reload persistence and dialog keyboard/close behavior.
- [x] Implement defensive localStorage migration and stable article IDs.
- [ ] Verify desktop/mobile browser smoke and no console errors — NOT_VERIFIED (browser tooling unavailable in this run).

### Task 17: GitHub repository and AI news paths

**Files:** Modify `backend/app/collectors/**`, `backend/app/main.py`, `src/components/**`, `source-registry/**` only for permitted definitions; add fixtures/tests.

- [x] Keep GitHub/news paths in the server-only registry/manual-import boundary; no live adapter is enabled without verified access.
- [x] Preserve manual import and UNVERIFIED/NOT_VERIFIED labeling rather than inventing external freshness.
- [x] Verify existing local registry/collector fixtures; external freshness remains NOT_VERIFIED.

### Task 18: Security and invalid-input audit

**Files:** Modify `backend/app/**`, `src/**`, `scripts/**` only where a failing test proves a defect; add backend tests.

- [x] Add coverage for SQL injection-shaped search filters, SSRF/private-host guards, script/HTML text, wrong auth and bounded collector/gateway failures.
- [x] Implement/retain parameterized queries, allowlists, escaped React rendering and bounded retries.
- [x] Verify full backend suite, source scans and bundle scans.

### Task 19: SQLite backup/restore smoke

**Files:** Add `scripts/backup_db.ps1`, `scripts/restore_db.ps1`; add tests/fixtures.

- [x] Add contract tests for missing DB, invalid restore and preservation of the original target.
- [x] Implement explicit validated targets and preserve the original DB as a `.pre-restore-*.db` copy.
- [x] Verify PowerShell parse, script contract tests and full suite.

### Task 20: Full acceptance and final reports

**Files:** Modify only report/docs and `.team/ledger.md` after all worker/reviewer verdicts.

- [ ] Run `checks/p1.py`–`checks/p5.py`, all focused tests, build, startup, import, collector fixture, API journeys and browser smoke.
- [ ] Run an independent integration review on exact HEAD.
- [ ] Map every Mission/Definition-of-Done item to PASS/FAIL/BLOCKED/NOT_VERIFIED.
- [ ] Do not call the candidate release-ready while any required gate remains unverified.

## Dependency order

`1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20`

Each task is dispatched only after its predecessor’s focused verify and reviewer verdict are recorded in `.team/ledger.md`.
