# Vũ Học AI Radar — Finish-All Implementation Plan

> **For agentic workers:** use the repository task-pack workflow and a fresh worker plus independent reviewer for every task.

**Goal:** Turn the current localhost candidate into an evidence-backed release candidate, while preserving the public/private data boundary and never presenting SAMPLE or unverified information as live fact.

**Architecture:** The existing React/Vite frontend consumes a FastAPI/SQLite API. Work starts by making the existing suite deterministic, then adds only independently verifiable production paths: browser E2E, live-permitted collection, a process-safe daily scheduler, repository catalog, promotion data, and operations evidence. Each task must operate from a clean Hermes worktree and be cherry-picked only after independent review.

**Tech Stack:** React 19, Vite 7, Python 3.13 via uv, FastAPI, SQLite, unittest, Playwright (if installed through the project lockfile).

**Spec:** `docs/MISSION.md`, the pasted MASTER MISSION, `AGENTS.md`, and `.team/CHARTER.md`.

## Global Constraints

- Never modify `checks/`, `PLAN.md`, or `docs/MISSION.md`; never push, deploy, merge shared branches, or create a remote.
- Only change task-pack `files_allowed`; preserve all pre-existing dirty-root changes.
- Bind network services only to `127.0.0.1`; use `uv`, never global pip; do not put secrets in source, output, or bundles.
- External text is untrusted data; no CAPTCHA/login/paywall/rate-limit bypass; failures are recorded, never converted into invented signals.
- Public endpoints must exclude SAMPLE, raw source registry, provenance, reviewer notes, and secrets; editorial ingestion remains DRAFT/PENDING_REVIEW until a human review action.
- Every worker demonstrates RED → GREEN, records exact commands/exit codes, and commits only its scoped files. Every reviewer checks specification compliance and code quality against the exact candidate commit.

## Review Focus

1. Running the test suite from a clean checkout after a build must be deterministic; task Q1 owns this regression.
2. A daily-radar fixture with a fresh REAL signal must be `CURRENT`, while absent/invalid timestamps remain `SIGNAL_WEAK`; task Q1 owns this regression.
3. Browser flows must prove mobile and desktop public/private separation rather than merely check source text; task Q2 owns this.
4. Network collection must reject redirect/DNS/private-address and malformed-feed cases without persisting fictitious articles; task D1 owns this.
5. Scheduler concurrency/restart must not duplicate collection/publish work; task S1 owns this.

## File and dependency map

- `backend/tests/*`, `src/**`, `scripts/**`: baseline repair and E2E support (Q1/Q2).
- `backend/app/collectors/**`, `backend/app/**`, `source-registry/**`: registry and live-permitted collection (D1).
- `backend/app/radar/**`, `backend/app/main.py`, `backend/tests/**`: scheduler and Daily Radar (S1).
- `backend/app/**`, `src/**`, `backend/tests/**`: promotions and repository catalog API/UI (R1/R2).
- `scripts/**`, `backend/app/**`, `backend/tests/**`, `README*`, `docs/**`: backup/restore, local release evidence, and runbook (O1).
- `.team/**`, `docs/agent-team/**`, `AI_HANDOFF.md`: audit and human-facing evidence (A0/F1).

### Task A0: Current-state evidence audit and gap register

**Dependencies:** none. **Priority:** CRITICAL. **Assigned agent:** worker then reviewer.

**Files allowed:** `.team/audit.md`, `.team/plans/finish-all.md`, `docs/agent-team/CURRENT_PROGRESS_AUDIT.md`, `docs/agent-team/REMAINING_GAPS.md`.

**Acceptance:** independently reproduce Git state, P1–P5 referee checks, migration/seed, full test status, build, DB REAL/SAMPLE counts, available tests/E2E configuration, and security findings. Documents distinguish fresh evidence from historical claims and name every blocker.

**RED/GREEN:** Start from the exact audit commands in the task pack; a claim without output/exit code is treated as failing. Verify that each conclusion maps to a command result or read-only observation.

### Task Q1: Make baseline verification deterministic

**Dependencies:** A0. **Priority:** CRITICAL. **Assigned agent:** worker then reviewer.

**Files allowed:** `backend/app/radar/**`, `backend/tests/test_admin_ui.py`, `backend/tests/test_radar_daily.py`, `backend/tests/**` only when adding focused regression coverage, `scripts/**` only if a test entrypoint is required.

**Acceptance:** a clean, documented sequence builds frontend before bundle assertions and passes all backend tests; fixtures cannot leak state from `backend/data/radar.db`; fresh REAL evidence produces `CURRENT`; no-signal stays `SIGNAL_WEAK`. No weakening/skipping existing assertions.

**RED/GREEN:** Add/reproduce failing tests for build-order and fresh timestamp handling; make minimal isolation/service changes; run focused tests, entire backend discovery after build, P1–P5, and `git diff --check`.

### Task Q2: Browser E2E and responsive public/admin journeys

**Dependencies:** Q1. **Priority:** HIGH. **Assigned agent:** worker then reviewer.

**Files allowed:** `package.json`, `package-lock.json`, `playwright.config.*`, `e2e/**`, `backend/tests/**`, `scripts/**`, `src/**` only when a real browser defect is identified.

**Acceptance:** automated desktop/tablet/mobile smoke executes against temporary localhost ports and covers public feed/search/bookmarks/theme, explorer filters, no private registry on public routes, and admin token error/success states. Artifacts/screenshots and exact status are retained; unavailable browser runtime is explicitly BLOCKED, not passed.

**RED/GREEN:** create one failing public-flow and one failing admin-boundary scenario; implement harness/config; run the full browser command at all viewports plus existing build/API checks.

### Task D1: Register and verify one permitted external collection path

**Dependencies:** Q1. **Priority:** HIGH. **Assigned agent:** worker then reviewer.

**Files allowed:** `backend/app/collectors/**`, `backend/app/**`, `backend/tests/test_collectors_*.py`, `source-registry/**`, `docs/DATA_SOURCES.md`.

**Acceptance:** add official/explicitly permitted source entries with collection method and provenance; demonstrate at least one real HTTP collection only if robots/terms/rate constraints permit it; otherwise retain manual/unavailable status with evidence. Persist raw item + collection run, deduplicate safely, redact errors, and preserve existing SSRF bounds.

**RED/GREEN:** add fixture tests for status/provenance/failed collection and a controlled live-proof command with bounded timeout; run focused and full collectors suite. Live results are recorded as REAL only when request evidence exists.

### Task S1: Process-safe Daily Radar scheduler

**Dependencies:** D1. **Priority:** HIGH. **Assigned agent:** worker then reviewer.

**Files allowed:** `backend/app/radar/**`, `backend/app/main.py`, `backend/app/**`, `backend/tests/test_radar_daily.py`, `backend/tests/**`, `scripts/**`, `docs/**`.

**Acceptance:** 07:00 Asia/Ho_Chi_Minh scheduling has a durable/idempotent run identity, bounded retry and lock; multiple processes cannot duplicate it; manual refresh remains authenticated; stale/SIGNAL_WEAK truthful; no DRAFT auto-publish. Include fake-clock tests and one safe localhost execution.

**RED/GREEN:** establish failing lock/restart/no-publish tests, implement minimal storage-backed scheduler boundary, run focused/full suite and a local smoke with logs.

### Task R1: Promotion Radar with verified lifecycle

**Dependencies:** Q1. **Priority:** HIGH. **Assigned agent:** worker then reviewer.

**Files allowed:** `backend/app/**`, `src/**`, `backend/tests/**`.

**Acceptance:** offers expose only verified public fields, accurate expiry/eligibility/card/account/region state, official CTA, search/filter and admin review. No referral, no invented active promo, no SAMPLE public leak.

**RED/GREEN:** fixture tests for expiry, invalid/admin authorization, empty/unknown state and public field allowlist; implement API/UI; run focused, build and public-boundary regression.

### Task R2: GitHub repository explorer with safe metadata path

**Dependencies:** Q1. **Priority:** MEDIUM. **Assigned agent:** worker then reviewer.

**Files allowed:** `backend/app/**`, `src/**`, `backend/tests/**`, `docs/**`.

**Acceptance:** catalog/imported repo data includes canonical URL, purpose, use case, tradeoffs, install guidance, license, updated timestamp, difficulty, provenance and verification; public UI has search/filter/bookmark; external retrieval only through permitted GitHub APIs with bounded failures.

**RED/GREEN:** prove schema/API validation, dedup, unavailable metadata, and public-private field boundary with tests; implement minimal UI and run build plus regression suite.

### Task O1: Operations, backup/restore and release documentation

**Dependencies:** Q2, D1, S1, R1, R2. **Priority:** HIGH. **Assigned agent:** worker then reviewer.

**Files allowed:** `scripts/**`, `backend/app/**`, `backend/tests/**`, `README.md`, `README_LOCAL.md`, `.env.example`, `docs/**`.

**Acceptance:** `dev.ps1` runs `-Check` without installing, diagnoses occupied ports/dependencies, preserves localhost-only binding; backup/restore is tested on a fixture DB; runbook includes scheduler, rollback and verified limitations. No service is deployed.

**RED/GREEN:** add failing backup/restore and `-Check` no-install tests; implement; run test suite, build, P1–P5, startup smoke on nondefault ports, and record outputs.

### Task F1: Final acceptance evidence and handoff

**Dependencies:** A0, Q1, Q2, D1, S1, R1, R2, O1. **Priority:** CRITICAL. **Assigned agent:** worker then independent reviewer.

**Files allowed:** `.team/**`, `docs/agent-team/**`, `AI_HANDOFF.md`, `README.md`, `docs/**`.

**Acceptance:** recreate the final acceptance checklist from fresh outputs: Git baseline/final HEAD, per-task worker/reviewer trace, real/sample inventory, raw test logs, browser artifact links, security audit, release readiness, and unresolved blockers. Verdict is `READY_FOR_RELEASE`, `PASS_WITH_WARNINGS`, or `NOT_READY` only as evidence supports.

**RED/GREEN:** treat missing command evidence, a failed suite, or an undocumented external dependency as an incomplete checklist item; run the named commands and write only their observed outcomes.

## Self-review

- Covers every known unverified Definition-of-Done area: deterministic baseline, browser runtime, live collection, scheduler, promotions, repository catalog, operations, and final evidence.
- Uses no task that changes locked files or silently resolves external authorization questions.
- Keeps coupled migrations/API/UI work serial; only D1/R1 can be dispatched in parallel after Q1 if their file scopes do not overlap.
- The unresolved Node floor and any absent Playwright/browser or live-source permission remain explicit gates, not assumed implementation work.
