# Reviewer Pack q2-browser-e2e-retry-review

## Role
Independent senior reviewer. Read-only: do not modify files, do not commit.

## Scope
Review only the Q2 Hermes GUI worker changes:
- `package.json`
- `package-lock.json`
- `playwright.config.js`
- `e2e/public-shell.js`
- `e2e/public-desktop.spec.js`
- `e2e/public-mobile.spec.js`
- `e2e/admin-boundary.spec.js`

Reference app files may be inspected read-only to validate selectors/endpoints, but must not be edited.

## Acceptance and evidence to verify
1. Tests are real Playwright browser tests, localhost-only, with no fake PASS or external network dependency.
2. Desktop public journey checks branding, seven groups, `/api/articles`, and absence of internal registry/provenance fields.
3. Mobile journey checks navigation and `scrollWidth <= clientWidth + 1`.
4. Admin boundary checks unauthenticated protected endpoints return 401 without leaking credentials.
5. Config uses bounded web servers, local Chromium, and scoped output handling without hiding failures.
6. Independently inspect the recorded worker evidence: Playwright exit 1 with 2 passed/1 failed because mobile overflow `440 > 391`; build exit 0; diff-check exit 0. Confirm this is an honest blocker, not a test bug.
7. Confirm only allowed Q2 files changed; no edits to `src/`, backend, checks, PLAN, MISSION, DB, or reference project.

## Required review output
Run independent checks where practical (`npx playwright test`, `npm run build`, scoped `git diff --check`) and report exact exit codes. End with:
- `VERDICT: APPROVED` if harness and evidence are correct even though the product mobile criterion is a known failing blocker;
- or `VERDICT: CHANGES_REQUESTED` if the tests/config/evidence are unsound.
Include findings, severity, scope confirmation, and the next action. Do not claim the overall app is ready while mobile remains red.
