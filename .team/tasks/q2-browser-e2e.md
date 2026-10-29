# TASK q2-browser-e2e | harness: Hermes GUI | role: worker

## Context

The fresh audit found no Playwright harness in this repository and no browser
journey evidence. The machine has a local Chromium runtime under
`%LOCALAPPDATA%\\ms-playwright` (`chromium-1243`), but `package.json` currently
does not declare Playwright. Q1 has already made the backend regression suite
green (405/405).

## Allowed files

- `package.json`
- `package-lock.json`
- `playwright.config.js`
- `e2e/**`
- `scripts/e2e/**` only if a tiny localhost-only helper is required
- `.team/results/**` only for the Hermes result stream (do not hand-edit)

Do not modify `checks/`, `PLAN.md`, `docs/MISSION.md`, backend production code,
backend tests, frontend source, database files, `.team/scripts/`, or the
reference project `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Vu-Agent-Room-PC`.
Preserve all pre-existing dirty worktree edits.

## Task

Act as a browser test automation worker. Implement the smallest real Playwright
smoke harness for the current localhost app and run it against the actual Vite
frontend plus FastAPI backend. Do not fake browser results or replace browser
assertions with string/file checks.

Required journeys:

1. Public desktop: load the app, verify branded shell and all seven navigation
   groups, exercise a public article/feed request, and assert no private source
   registry/provenance marker is exposed in visible UI or page response data.
2. Public mobile: run the same public shell/feed check at a mobile viewport and
   assert no horizontal overflow (`scrollWidth <= clientWidth + 1`).
3. Admin boundary: request a protected admin endpoint without credentials and
   assert HTTP 401; do not put any real token in source, config, screenshots,
   logs, or reports.

Use a localhost-only webServer setup with bounded startup/shutdown. Prefer the
existing local Chromium executable; if installing `@playwright/test` or using
the local browser is impossible, report `BLOCKED`/`NOT_VERIFIED` with the exact
command and error rather than claiming PASS. Do not access external websites.

## Verification contract

Run and record exact exit codes for:

1. focused Playwright smoke command (for example `npx playwright test`),
2. `npm run build`,
3. `git diff --check` on the allowed files.

Run P1–P5 only if the package/config changes make that useful; never edit the
referee checks. End the report with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and
`## Bước tiếp theo`, clearly separating PASS, BLOCKED, and NOT_VERIFIED.
