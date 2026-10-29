# Task Pack q2-browser-e2e-retry — real local Playwright smoke

## Context
The prior Q2 worker installed `@playwright/test` but stalled before creating tests. Continue in a fresh Hermes GUI worker session. Do not touch the reference project.

## Allowed files
- `package.json`
- `package-lock.json`
- `playwright.config.js`
- `e2e/**`
- `scripts/e2e/**` only if a tiny localhost startup helper is strictly necessary
- `.team/results/**` only via normal route output; do not hand-edit result JSONL

Do not edit `checks/`, `PLAN.md`, `docs/MISSION.md`, backend code, frontend source, database files, `.team/scripts/**`, or reference project files.

## Acceptance criteria
1. Create a bounded Playwright config and real tests using `@playwright/test` against localhost only. Reuse the already installed local Chromium if available; do not download browsers unless unavoidable.
2. Start backend/Vite with bounded webServer commands or document an exact BLOCKED/NOT_VERIFIED reason if startup cannot be made reliable.
3. Desktop test: branded `VŨ HỌC`/`AI Radar` shell, all seven public navigation groups visible, `/api/articles` request succeeds, and no `registry`/`provenance` marker appears in public page text or article response payload.
4. Mobile test: open the navigation and assert `document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1`.
5. Admin boundary test: unauthenticated `GET /api/admin/sources` returns 401.
6. Run the Playwright suite, `npm run build`, and scoped `git diff --check`; report exact exit codes. Never claim PASS without real test output.
7. End with the required markers `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and `## Bước tiếp theo`.

## Important execution guidance
Keep the implementation small. If a command would hang, stop it with a bounded timeout and record the exact blocker rather than waiting indefinitely. Do not create fake tests or fake output.
