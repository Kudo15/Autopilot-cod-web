# Task Pack q2-mobile-fix — fix confirmed mobile overflow

## Context
The real Hermes GUI Playwright smoke found a reproducible product bug at viewport 390px: `document.documentElement.scrollWidth=440` while `clientWidth=390`. Diagnosis identified the mobile header search flex item as the offender. The existing `e2e/public-mobile.spec.js` is a normal assertion and must remain unchanged.

## Allowed files
- `src/styles.css` only
- `.team/results/**` only through normal Hermes route output

Do not edit `e2e/**`, package files, backend, database, checks, PLAN, MISSION, `.team/scripts/**`, or reference project.

## Required change
Apply the minimal responsive CSS fix identified by browser evidence: allow `.header-search` to shrink within the mobile header by adding `min-width: 0` to the existing `@media (max-width: 760px)` `.header-search` rule. Do not hide overflow globally and do not weaken the Playwright assertion.

## Verification
1. Run `npx playwright test` against the existing bounded config. Record exact exit code and all test counts; success requires 3/3.
2. Run `npm run build`; record exact exit code.
3. Run scoped `git diff --check -- src/styles.css`; record exact exit code.
4. Confirm only `src/styles.css` changed for this task. End with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and `## Bước tiếp theo`.
