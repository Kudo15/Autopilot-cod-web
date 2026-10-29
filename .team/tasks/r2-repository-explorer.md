# Task R2 — GitHub repository explorer (bounded, safe metadata)

Implement a minimal repository catalog/explorer without live network calls.

Allowed files only: `backend/app/main.py`, `backend/app/migrate.py`,
`backend/tests/test_repository_explorer.py`, `src/data/groups.js`, `src/App.jsx`,
`src/components/RepositoryView.jsx`, `src/styles.css`, `.team/results/**`.

Requirements:
- Add additive SQLite table only if needed; schema fields must cover canonical_url,
  repo name, purpose, use case, tradeoffs, license, updated_at, difficulty,
  provenance, verification_status, data_origin. Do not seed invented active
  public rows; SAMPLE rows must never be public.
- GET `/api/repositories` with bounded limit and allowlisted q/difficulty/license/
  verification_status filters, parameterized SQL, explicit response columns only.
  Public default excludes SAMPLE and requires canonical https://github.com URL,
  VERIFIED status, and non-empty provenance/license fields. No GitHub network call.
- UI group `provider-comparison` or a new repository group calls the API and has
  search/filter/loading/error/empty, shows metadata and canonical URL safely.
- Temporary DB tests for query allowlist, SAMPLE/invalid URL exclusion, field
  allowlist and bounded limit. No real DB mutation, no external network.
- Run focused/full backend, npm build, git diff --check. End markers `[ĐÃ LÀM]`,
  `[BẰNG CHỨNG]`, `[RULING]`, `## Bước tiếp theo`.
