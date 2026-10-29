# Scheduled Radar Inbox — design contract

**Date:** 2026-10-25  
**Status:** Proposed — requires owner approval before implementation

## Intent

Use the two existing daily Codex reports as editorial discovery inputs:

- **Provider & Harness Radar**: model, provider, route, quota, policy and offer changes.
- **Tip & Trick Radar**: tools, benchmarks, guides, operational practices and deals.

Each report is converted into several short Vietnamese article drafts. The owner selects, edits and explicitly publishes individual drafts. The public site never receives a scheduled report, an AI draft or an unverified claim directly.

The public-facing visual direction is the existing `pages.dev` site. The local Radar application remains the editorial back office and the source of truth for article lifecycle and provenance.

## Goals

- Accept a predictable, auditable inbox artifact from each scheduled run.
- Preserve the original report and per-finding source links for authenticated review.
- Create a separate draft for each usable finding, rather than publishing a long daily digest.
- Let optional AI produce concise original editorial copy in Vietnamese without copying source articles.
- Keep the existing lifecycle: `DRAFT → PENDING_REVIEW → PUBLISHED`.
- Expose only approved, non-SAMPLE articles to the public-facing frontend.
- Make the same contract usable later by a VPS worker instead of a Codex desktop schedule.

## Non-goals

- No automatic publication, automatic verification, quota claim or price claim.
- No scraping around logins, CAPTCHAs, paywalls, rate limits or source terms.
- No copying or paraphrasing a full external article as a substitute for the original.
- No production deployment, Cloudflare configuration, or scheduled-task modification in this design step.
- No claim that Codex Desktop schedules are a VPS runtime; they require the local project, computer and app to remain available.

## Selected approach

### A. Manual report paste

An editor pastes Markdown into Admin Radar and starts import. It is simplest, but creates daily manual work and makes report provenance/error recovery less reliable.

### B. Structured inbox files (selected)

Each scheduled run writes one validated JSON artifact into a local editorial inbox. The backend imports only completed files, records each raw finding, deduplicates it, then generates drafts. The original artifact remains private for review. This provides a stable local workflow and can later be produced by a VPS collector without changing the editorial workflow.

### C. Scheduled task calls the admin API directly

This removes the inbox, but requires the unattended task to hold an admin secret and couples scheduled-task availability to the API. It is not selected for the first release.

## Architecture

```text
Codex scheduled report
  → structured inbox artifact (atomic write)
  → admin-only importer + schema validation
  → raw finding + provenance + duplicate check
  → optional AI editorial draft / deterministic fallback
  → DRAFT
  → owner checks source and edits
  → PENDING_REVIEW
  → owner publishes
  → PUBLISHED API
  → pages.dev public UI
```

The existing manual Markdown/CSV/JSON import path remains available. It is a fallback, not replaced by the inbox.

## Inbox contract

The scheduled prompt will produce one JSON file per run, with a new UUID-like `run_id`, a fixed schema version, and an atomically renamed final file. Incomplete `*.tmp` files are ignored.

```json
{
  "schema_version": "1",
  "run_id": "provider-radar-2026-10-25T07-00-00+07-00",
  "report_kind": "provider_harness_radar",
  "observed_at": "2026-10-25T07:00:00+07:00",
  "timezone": "Asia/Ho_Chi_Minh",
  "findings": [
    {
      "external_id": "stable-id-within-run",
      "title": "Short factual finding title",
      "category": "AI & Model",
      "summary": "Source-grounded observation, not an instruction.",
      "canonical_urls": ["https://official.example/path"],
      "source_type": "official|community|account_probe",
      "verification_status": "VERIFIED|UNVERIFIED|NEEDS_REVIEW",
      "evidence_note": "How the claim was observed.",
      "valid_until": null,
      "risk_note": null
    }
  ]
}
```

The importer rejects unknown top-level fields, oversized payloads, invalid URLs, absent source links, invalid status values and malformed timestamps. Report/finding text is always untrusted data: it is never interpreted as a command, prompt override, filename or SQL.

The scheduled reports may include a human-readable Markdown companion, but JSON is the import contract. Tracked URLs are canonicalized and query-only tracking parameters are removed when safe; source links are retained privately.

## Draft generation and editorial policy

For every accepted finding, create a `DRAFT` article with provenance to the inbox run and source URLs. Dedupe uses the existing canonical URL, normalized title and content-hash contract; a duplicate is recorded/skipped without overwriting prior editorial decisions.

If the optional AI gateway is configured, it may produce a short original Vietnamese draft containing:

- a plain-language headline and concise summary;
- why the finding matters to a Vietnamese AI user;
- explicit evidence/uncertainty language;
- a source link and, for offers/quota, observed time and expiry when supplied.

Without the gateway, deterministic rules create a safe draft shell. Neither path may assign `PUBLISHED`, turn `UNVERIFIED` into `VERIFIED`, or invent a quota, price, expiry, availability or free status.

The reviewer sees the original finding, evidence note and source URLs next to the article preview. The reviewer can edit copy, submit it to `PENDING_REVIEW`, reject it, or publish only after the existing authenticated review gate succeeds.

## Public frontend boundary

`pages.dev` is the chosen public presentation. It must read only the existing published-only article API (or an equivalent server-side publication export with the same explicit field allowlist). It must not access inbox files, raw reports, source registry, reviewer notes, admin endpoints, drafts, token values or SAMPLE records.

Initial implementation will add a public-content adapter/API contract before a visual port. Connecting the actual `pages.dev` source and deployment is a later deployment task: it needs the site source location, build ownership and an explicit public API URL/CORS decision. No deployment work is implied by this contract.

## Operational model

- **Local pilot:** Codex schedules write inbox artifacts while the computer, Codex app and project are available. An authenticated editor opens Admin Radar and reviews drafts.
- **VPS production:** a scheduler/collector creates the same inbox schema or invokes a server-side importer. It has its own health check, retries, logging, retention and backup; it does not depend on Codex Desktop.
- **Failure:** invalid artifacts remain quarantined with a clear admin-visible error; no partial article writes and no public output occur.

## Acceptance criteria

1. A valid provider report containing three findings produces three non-public drafts with source provenance.
2. A valid Tip & Trick report does the same, preserving category and risk/evidence labels.
3. Re-importing the same run is idempotent and does not duplicate articles or overwrite an existing review.
4. Invalid, incomplete or injection-shaped input is rejected/quarantined without database side effects.
5. Missing AI configuration still creates reviewable deterministic drafts.
6. AI gateway output is schema-validated and cannot publish or elevate verification status.
7. Public endpoints/UI cannot reveal inbox artifacts, raw content, reviewer notes, tokens or unpublished drafts.
8. The owner can inspect, edit, reject and publish individual drafts through the existing authenticated workflow.

## Planned delivery order

1. Confirm inbox schema and map the two current scheduled prompts to it.
2. Add importer, idempotency/quarantine storage and focused tests.
3. Add AI/deterministic short-draft transformation and tests.
4. Extend Admin Radar into a per-finding review inbox.
5. Define a published-content contract for the selected `pages.dev` frontend.
6. Run a local pilot with one captured report from each schedule.
7. Design VPS scheduler, persistence, backup and deployment separately after the pilot is accepted.

## Risks and controls

- **Source freshness:** retain `observed_at`, source type and verification state; never present a scheduled report as a live probe.
- **Copyright/attribution:** generate original summaries and analysis; link to the original source rather than reproducing it.
- **Misleading free/deal claims:** require source URL, explicit uncertainty labels, observed time and expiry where known.
- **Prompt injection:** treat all report/source text as data; do not pass it to shell, filesystem actions or privileged tool instructions.
- **Schedule reliability:** inbox is only a hand-off format; production health cannot depend on a desktop schedule.
- **Duplicate/noisy reports:** stable run IDs plus existing content dedupe and owner review prevent duplicate publication.
