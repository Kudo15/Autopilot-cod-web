# Reviewer Pack q2-browser-e2e-review2

You are an independent read-only reviewer. Do not call any write/edit/patch/delete tool and do not modify any file. If a check would modify output, skip it and report NOT_RUN.

Review only:
- `package.json`, `package-lock.json`, `playwright.config.js`
- `e2e/public-shell.js`, `e2e/public-desktop.spec.js`, `e2e/public-mobile.spec.js`, `e2e/admin-boundary.spec.js`

The current mobile test must remain a normal assertion (never use `test.fail`, `test.skip`, expected-failure markers, or any mechanism that converts a real failure into a pass). The known product failure is evidence: Playwright previously ran 2 passed/1 failed with `scrollWidth=440`, `clientWidth=390`. Do not “fix” or weaken that test.

Read-only review requirements:
1. Confirm selectors, seven groups, public field allowlist, provenance markers, and admin 401 checks are meaningful and localhost-only.
2. Inspect `playwright.config.js` for bounded local web servers, explicit local Chromium, and honest failure behavior.
3. Confirm only allowed Q2 files changed and that `src/`, backend, checks, PLAN, MISSION, DB, and reference project are untouched by this task.
4. Use existing recorded evidence; do not rerun commands that create output directories. If you do run a read-only command, use a temporary output path outside the repo and report the exact exit code.
5. Note the real mobile blocker and the exact suggested product fix, but do not apply it.

End with exactly one of:
- `VERDICT: APPROVED` — harness/evidence are sound; overall product remains blocked by the honest mobile failure.
- `VERDICT: CHANGES_REQUESTED` — test/config/evidence is unsound.

Include concise findings with severity and a next action. Do not create `TODO_code-reviewer.md` or any other artifact.
