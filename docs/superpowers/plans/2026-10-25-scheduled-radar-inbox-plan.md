# Scheduled Radar Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the two daily Codex Radar reports into safe, structured inbox files that create separate Vietnamese article drafts for owner review, without any automatic publication.

**Architecture:** A local inbox scanner accepts only complete, schema-versioned JSON artifacts and records each run idempotently. It normalizes each finding through the existing raw-item/provenance boundary, asks the existing optional editorial gateway for a strictly validated short draft (or uses a deterministic fallback), and leaves every resulting article in `DRAFT`. Authenticated Admin Radar users scan the inbox, inspect individual drafts and use the current review transition before any public API can return an article.

**Tech Stack:** Python 3.13, FastAPI, SQLite, Pydantic, React 19, Vite, existing `unittest`/Node UI harnesses.

**Spec:** `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`

## Global Constraints

- Keep the current React 19/Vite and FastAPI/SQLite stack; add no unnecessary dependency.
- Treat schedule artifacts and all source text as untrusted data, never commands, paths, instructions or model-policy overrides.
- Default to local files and `127.0.0.1`; do not deploy, push or configure Cloudflare/VPS.
- `ADMIN_TOKEN` remains server-side/runtime-only; it never enters an inbox file, browser storage, URL or bundle.
- Only authenticated review transitions can publish; importer and AI must always create `DRAFT`.
- Preserve manual Markdown/CSV/JSON import and its existing deduplication behavior.
- No code task edits `checks/`, `PLAN.md` or `docs/MISSION.md`; preserve unrelated dirty changes.
- The root checkout is dirty: workers use their Hermes worktree and commit only their scoped files there; the coordinator never commits or stages unrelated root-checkout changes and records verification in `.team/ledger.md`.

## Review Focus

- A partial `*.tmp` artifact must be ignored, never parsed or quarantined; Task 1 pins this behavior.
- A reused `run_id` with altered contents must be rejected without overwriting the prior run or its reviews; Task 1 pins this behavior.
- An injection-shaped title, summary or evidence note must stay inert text and never choose a file/command/API action; Task 1 pins this behavior.
- AI output that is malformed, elevates verification, or asks to publish must fall back safely to a `DRAFT`; Task 2 pins this behavior.
- Admin/public responses must keep raw report text, provenance, quarantine paths and draft records out of public endpoints; Tasks 3 and 4 pin this behavior.

---

## File structure and ownership

| Path | Responsibility |
|---|---|
| `backend/app/inbox/schema.py` | Strict Pydantic models and pure validation for schema-versioned scheduled artifacts. |
| `backend/app/inbox/service.py` | Safe directory scan, atomic-file filtering, idempotency, quarantine metadata and transactional raw/article persistence. |
| `backend/app/inbox/__init__.py` | Inbox package marker/exports only. |
| `backend/app/migrate.py` | Additive `scheduled_inbox_runs` table and indexes. |
| `backend/app/editorial/inbox.py` | Transform one validated finding into a short, source-grounded article draft using gateway-or-rules. |
| `backend/app/main.py` | Authenticated scan/list/detail admin endpoints with explicit response allowlists. |
| `backend/tests/test_scheduled_inbox.py` | Scanner/schema/idempotency/quarantine and no-side-effect tests. |
| `backend/tests/test_inbox_editorial.py` | Draft-generation/fallback/lifecycle tests. |
| `backend/tests/test_inbox_admin_api.py` | Auth and public/private-boundary API tests. |
| `src/components/admin/InboxPanel.jsx` | Accessible inbox scan and per-draft review context UI. |
| `src/components/admin/AdminView.jsx` | Compose the Inbox Panel into the existing token-gated Admin Radar screen. |
| `src/components/admin/adminClient.js` | Narrow client calls for inbox admin endpoints; token only in Authorization header. |
| `src/styles.css` | Minimal styles for inbox status/evidence rendering. |
| `backend/tests/admin_inbox_ui_harness.mjs` | Browserless Node contract tests for the new admin client/UI output. |
| `docs/SCHEDULED_RADAR_INBOX.md` | Exact artifact schema, scheduled-prompt output instructions, local pilot and VPS handoff guidance. |
| `.env.example` | Optional inbox directory configuration, with no token value. |

## Task 1: Strict artifact schema, safe scan, persistence, and quarantine

**Files:**
- Create: `backend/app/inbox/__init__.py`
- Create: `backend/app/inbox/schema.py`
- Create: `backend/app/inbox/service.py`
- Create: `backend/tests/test_scheduled_inbox.py`
- Modify: `backend/app/migrate.py`
- Modify: `backend/app/database.py`

**Interfaces:**
- Consumes: existing `normalize_item()`, `raw_items`, `articles`, `sources`, migration transaction conventions.
- Produces: `scan_inbox(directory: Path, conn: sqlite3.Connection) -> InboxScanResult`; `list_inbox_runs(conn: sqlite3.Connection) -> list[dict]`; Pydantic `ScheduledReport` and `ScheduledFinding` models.
- Persistence: additive `scheduled_inbox_runs(run_id TEXT PRIMARY KEY, report_kind TEXT, content_hash TEXT, observed_at TEXT, status TEXT, finding_count INTEGER, accepted_count INTEGER, skipped_count INTEGER, error_message TEXT, processed_at TEXT, data_origin TEXT DEFAULT 'REAL')`; status is allowlisted to `IMPORTED|QUARANTINED`.

- [ ] **Step 1: Write focused failing schema/scanner tests**

```python
def test_scan_valid_report_creates_one_raw_item_and_one_draft_per_finding():
    result = scan_inbox(pending_dir, conn)
    assert (result.imported_runs, result.accepted_findings) == (1, 3)
    assert scalar(conn, "SELECT COUNT(*) FROM articles WHERE article_status = 'DRAFT'") == 3

def test_scan_is_idempotent_and_rejects_reused_run_id_with_new_hash():
    scan_inbox(pending_dir, conn)
    assert scan_inbox(pending_dir, conn).skipped_runs == 1
    replace_artifact_with_same_run_id_different_content(pending_dir)
    assert scan_inbox(pending_dir, conn).quarantined_runs == 1
```

Include tests for missing canonical URLs, unknown fields, invalid timestamp/status, `*.tmp`, injection-shaped text, and a batch with one invalid file that leaves no partial rows for that file.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_scheduled_inbox -v`  
Expected: FAIL because the inbox package/interfaces do not exist.

- [ ] **Step 3: Implement strict schema and safe scanner**

Implement only schema version `1`, report kinds `provider_harness_radar` and `tip_trick_radar`, and the fields specified by the approved design. Resolve the inbox directory from a safe application default plus one explicit environment override; do not accept a request-supplied directory/path. Process only final `.json` files, use content hashes and `run_id` to enforce idempotency, and move failures to a generated safe quarantine name without executing or interpolating artifact text. Each valid artifact must commit as one transaction and create only `REAL/DRAFT` records with private provenance.

- [ ] **Step 4: Run focused and migration verification**

Run: `uv run python -m unittest backend.tests.test_scheduled_inbox -v`  
Expected: PASS.

Run: `uv run python -m backend.app.migrate`  
Expected: exit code 0; second run remains idempotent.

- [ ] **Step 5: Record result without committing**

Append to `.team/ledger.md`: task ID, touched files, exact test commands/exit codes, and ruling that `run_id + content_hash` blocks altered replays.

## Task 2: Source-grounded short-draft enrichment

**Files:**
- Create: `backend/app/editorial/inbox.py`
- Create: `backend/tests/test_inbox_editorial.py`
- Modify: `backend/app/editorial/gateway.py`
- Modify: `backend/app/inbox/service.py`

**Interfaces:**
- Consumes: `ScheduledFinding`, existing `EditorialDraft`, rule classifier and optional gateway configuration.
- Produces: `create_inbox_article_draft(finding: ScheduledFinding) -> EditorialDraft`; persistence uses its `title`, `summary_vi`, `category`, `risk` and `verification_status` but always writes `article_status='DRAFT'`.

- [ ] **Step 1: Write failing tests for deterministic and gateway paths**

```python
def test_missing_gateway_creates_short_draft_with_source_link_and_draft_lifecycle():
    draft = create_inbox_article_draft(valid_finding)
    assert draft.lifecycle == "DRAFT"
    assert "https://official.example/news" in draft.summary_vi

def test_gateway_cannot_publish_or_upgrade_unverified_finding():
    draft = create_inbox_article_draft(unverified_finding, fake_gateway_publish_response)
    assert draft.lifecycle == "DRAFT"
    assert draft.verification_status == "NEEDS_REVIEW"
```

Also test malformed gateway output and injection-shaped content produce the deterministic safe fallback, with no filesystem/network side effect beyond the explicitly mocked gateway call.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run python -m unittest backend.tests.test_inbox_editorial -v`  
Expected: FAIL because `create_inbox_article_draft` is missing.

- [ ] **Step 3: Implement the inbox editorial adapter**

Reuse the existing gateway validation rather than add a second unconstrained LLM protocol. Construct a bounded data-only prompt/adapter from allowlisted finding fields. Require source-grounded Vietnamese title/summary and uncertainty wording; preserve source URL and observed time in the private provenance and a reader-safe source link. On gateway absence/error/invalid output, use deterministic rules. Override lifecycle and verification state after every path so it cannot publish or elevate evidence.

- [ ] **Step 4: Run focused regression tests**

Run: `uv run python -m unittest backend.tests.test_inbox_editorial backend.tests.test_editorial_rules backend.tests.test_editorial_gateway -v`  
Expected: PASS.

- [ ] **Step 5: Record result without committing**

Append verification and the ruling that AI output is editorial assistance only to `.team/ledger.md`.

## Task 3: Authenticated inbox API and private/public boundary

**Files:**
- Create: `backend/tests/test_inbox_admin_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/inbox/service.py`

**Interfaces:**
- Consumes: `scan_inbox`, `list_inbox_runs`, existing `require_admin()` and article review workflow.
- Produces: `POST /api/admin/inbox/scan`, `GET /api/admin/inbox/runs`, and `GET /api/admin/inbox/articles` with explicit admin-only fields.

- [ ] **Step 1: Write failing admin API contract tests**

```python
def test_scan_requires_admin_before_opening_database():
    with raises_http(401):
        admin_inbox_scan(make_request_without_token())

def test_public_articles_exclude_all_unpublished_inbox_drafts():
    admin_inbox_scan(make_authenticated_request())
    assert list_articles() == []
```

Test allowed response keys, 403 with wrong token, no raw artifact/provenance/quarantine path in any public endpoint, and successful review through existing `PENDING_REVIEW → PUBLISHED` semantics.

- [ ] **Step 2: Run focused tests to verify failure**

Run: `uv run python -m unittest backend.tests.test_inbox_admin_api -v`  
Expected: FAIL because inbox endpoints do not exist.

- [ ] **Step 3: Implement the narrow admin routes**

Call `require_admin()` as the first handler action. The scan route has no caller-controlled path or artifact body. List/detail payloads use explicit field allowlists and may show title, category, status, evidence label, source URL, observed time and a safe error summary; raw report/provenance/quarantine filesystem location stay internal. Reuse existing article-review route unchanged for state transitions.

- [ ] **Step 4: Run boundary regression suite**

Run: `uv run python -m unittest backend.tests.test_inbox_admin_api backend.tests.test_admin_workflow backend.tests.test_public_articles -v`  
Expected: PASS.

- [ ] **Step 5: Record result without committing**

Append commands and confirmation that public endpoints see only published, non-SAMPLE content to `.team/ledger.md`.

## Task 4: Admin Radar inbox panel

**Files:**
- Create: `src/components/admin/InboxPanel.jsx`
- Create: `backend/tests/admin_inbox_ui_harness.mjs`
- Modify: `src/components/admin/AdminView.jsx`
- Modify: `src/components/admin/adminClient.js`
- Modify: `src/styles.css`
- Modify: `backend/tests/test_admin_ui.py`

**Interfaces:**
- Consumes: `POST /api/admin/inbox/scan`, `GET /api/admin/inbox/runs`, `GET /api/admin/inbox/articles`; `ADMIN_TOKEN` passed only as the existing component prop.
- Produces: a token-gated Vietnamese Inbox section that scans, lists non-public drafts, exposes evidence/source link and sends users to the existing review actions.

- [ ] **Step 1: Write failing Node/UI harness assertions**

```javascript
assert.equal(ADMIN_ENDPOINTS.inboxScan, '/api/admin/inbox/scan');
assert.match(renderedInbox, /Hộp thư biên tập/);
assert.doesNotMatch(source, /localStorage.*token|token.*localStorage/);
```

Cover empty/loading/error states, 401/403 display, disabled scan while pending, escaped text rendering, and a source link rendered as an ordinary external link rather than HTML injection.

- [ ] **Step 2: Run harness to verify failure**

Run: `node backend/tests/admin_inbox_ui_harness.mjs`  
Expected: FAIL because the client endpoints/component do not exist.

- [ ] **Step 3: Implement the smallest UI integration**

Follow existing `useAdminResource`, `AdminStates`, `ReviewPanel` and `adminClient` conventions. Keep scan an explicit button, never a page-load side effect. The panel displays only safe allowlisted admin DTO fields and uses React text rendering; it never receives raw reports or an admin token outside the existing in-memory prop flow.

- [ ] **Step 4: Run UI and build verification**

Run: `node backend/tests/admin_inbox_ui_harness.mjs`  
Expected: PASS.

Run: `npm run build`  
Expected: exit code 0.

- [ ] **Step 5: Record result without committing**

Append file list and verification output to `.team/ledger.md`.

## Task 5: Scheduled-output instructions, local pilot, and publication contract

**Files:**
- Create: `docs/SCHEDULED_RADAR_INBOX.md`
- Modify: `.env.example`
- Modify: `README_LOCAL.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DATA_SOURCES.md`
- Modify: `backend/tests/test_startup_script.py`

**Interfaces:**
- Consumes: final inbox schema/directory environment key/API endpoints from Tasks 1–4.
- Produces: a copyable scheduled-task output contract, local pilot commands, failure handling, and the published-only API contract required by the future `pages.dev` frontend.

- [ ] **Step 1: Write documentation/startup assertions first**

Add test assertions that the runtime configuration documents the inbox path without a secret and that documentation does not promise desktop schedules run on VPS or auto-publish content.

- [ ] **Step 2: Run focused documentation tests to verify failure**

Run: `uv run python -m unittest backend.tests.test_startup_script -v`  
Expected: FAIL until the documented configuration and references exist.

- [ ] **Step 3: Write the operator documentation**

Document both report kinds, a valid minimal JSON artifact, atomic write rule, artifact directory, Admin Radar scan/review/publish sequence, quarantine recovery, duplicate behavior, attribution/freshness labels, and the boundary between a local Codex pilot and a VPS scheduler. State that `pages.dev` integration consumes published-only data and requires the actual site source/build access as a separate deployment decision.

- [ ] **Step 4: Execute a captured-report local pilot and full regression**

Run: `uv run python -m unittest backend.tests.test_scheduled_inbox backend.tests.test_inbox_editorial backend.tests.test_inbox_admin_api backend.tests.test_admin_workflow backend.tests.test_importers backend.tests.test_editorial_gateway backend.tests.test_admin_ui backend.tests.test_startup_script -v`  
Expected: PASS.

Run: `npm run build`  
Expected: exit code 0.

Use a redacted fixture derived from the supplied reports; do not place the full report or private account claims in a committed/public sample.

- [ ] **Step 5: Record final task result without committing**

Append actual PASS/FAIL/BLOCKED evidence, remaining deployment prerequisite (the `pages.dev` source/build ownership), and no-publication confirmation to `.team/ledger.md`.

## Self-review

- **Spec coverage:** Tasks 1–2 cover structured inbox, atomic handling, idempotency, provenance, short drafts, fallback and AI limits. Task 3 protects admin/public boundary and existing review lifecycle. Task 4 provides the owner-facing review inbox. Task 5 documents schedule output, pilot, VPS handoff and `pages.dev` integration boundary.
- **Gaps:** Visual port/redeployment of the existing `pages.dev` frontend is intentionally out of scope until its source/build ownership is supplied; no deployment is authorized by the approved design.
- **Type consistency:** `ScheduledReport`/`ScheduledFinding` feed `scan_inbox`, which feeds `create_inbox_article_draft`; API and UI consume explicit DTOs from the same service layer.
- **Review focus:** Each of the five listed risk inputs has a named owning task/test.
- **Proportion:** Five dependency-ordered tasks keep migration/scanning, editorial transformation, admin API, UI and operator documentation independently reviewable.
