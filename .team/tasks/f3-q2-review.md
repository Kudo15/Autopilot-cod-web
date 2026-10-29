# TASK f3-q2-review | independent Q2 browser review | harness: hermes-gui

## NGỮ CẢNH

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`
- Review is read-only. Do not edit files, do not start/stop long-lived servers, do not touch SQLite databases, and do not inspect the reference project.
- Prompt basis: Code Reviewer / Code Review Agent — verify spec, correctness, security, and evidence with file:line findings.

## TÁC VỤ

Review only the Q2 browser harness and responsive public/admin boundary:

- `playwright.config.js`
- `e2e/public-desktop.spec.js`
- `e2e/public-mobile.spec.js`
- `e2e/admin-boundary.spec.js`
- relevant Q2 portions of `src/styles.css`, `src/App.jsx`, and `package.json`
- `.team/results` evidence and `docs/agent-team/REMAINING_GAPS.md`

Check that the tests exercise real localhost journeys, public/admin separation, mobile no-horizontal-overflow, and do not weaken assertions or expose secrets. Run only bounded read-only verification, preferably `npx playwright test` and `npm run build`; record actual exit codes. Do not treat prior reports as proof without checking current files/output.

## OUTPUT

Return a concise two-layer review (spec compliance, then code quality), with severity-ranked findings and file:line evidence. End with exactly one:

`VERDICT: APPROVED — <one-line reason>`

or

`VERDICT: CHANGES_REQUESTED — <severity-ranked findings>`

If something cannot be verified, mark it `NOT_VERIFIED` rather than guessing. Do not make changes.
