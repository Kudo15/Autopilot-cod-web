# Task Q2-MOBILE-FIX-RETRY — repair confirmed 390px overflow

## Scope

Work only in this repository. Do not inspect, edit, or run commands in the reference project `Vu-Agent-Room-PC`.
Allowed product file: `src/styles.css` only. Route output may be written under `.team/results/`.
Do not edit `e2e/`, `package.json`, `playwright.config.js`, backend, checks, PLAN.md, docs/MISSION.md, or the database.

## Context and confirmed failure

The real Playwright suite already exists and must remain strict. At viewport 390px, the public mobile journey failed with `scrollWidth=440`, `clientWidth=390`. Diagnostic evidence identified `.header-search` as the overflowing element. A first attempted `min-width: 0` change alone did not resolve the browser failure. Inspect the existing flex layout and make the smallest correct CSS-only fix that lets the mobile header/search layout fit within the viewport. Do not weaken or skip the assertion.

## Required work

1. Inspect current `src/styles.css` and the existing mobile Playwright spec/config read-only first.
2. Apply the minimal CSS fix in `src/styles.css` only. Preserve all unrelated styling.
3. Run the real bounded browser suite: `npx playwright test` (localhost only, no external network). It must report all 3 tests passed; do not convert failures to expected failures.
4. Run `npm run build`.
5. Run `git diff --check -- src/styles.css` and confirm the diff is minimal.
6. Confirm no files outside the allowed product file changed (apart from existing route/evidence outputs).

## Output markers (required)

End with these exact markers:

- `[ĐÃ LÀM]` — file and minimal CSS change.
- `[BẰNG CHỨNG]` — exact commands, exit codes, and browser result.
- `[RULING]` — `PASS` only if Playwright is 3/3, build is 0, and diff-check is 0; otherwise `BLOCKED` with the exact failure.
- `## Bước tiếp theo` — one concise next step.

Never claim PASS without the command output proving it. Do not create fake evidence or change tests to hide a product failure.
