# TASK 017 — Release and local documentation

## Prompt basis

Adapt the prompt-librarian Code Review Assistant pattern: derive docs from observed repository behavior and verification outputs, never invent external freshness or secrets, and mark SAMPLE/REAL/BLOCKED/NOT_VERIFIED explicitly.

## Contract

Create the six release/local docs from the plan:
- `README_LOCAL.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_SCHEMA.md`
- `docs/PHASE_REPORT.md`
- `docs/QA_REPORT.md`

Document only verified local behavior:
- Windows PowerShell startup via `pwsh -File scripts/dev.ps1 -Check` and normal mode; localhost binds only.
- Backend FastAPI/SQLite, frontend Vite proxy, server-owned auth/editorial/radar/collectors boundaries.
- Real vs SAMPLE data origins; external freshness/live gateway/network as NOT_VERIFIED where applicable.
- Exact commands and observed results: backend 325 pre-startup / 312 after Daily Radar, startup focused 13/13, Daily Radar 27/27, gateway 9/9, P3/P4/P5 PASS, npm build exit 0 with Node 22.11 warning, override-port startup smoke PASS; default-port/browser smoke NOT_VERIFIED due sibling servers/browser not run.
- Safe environment variables and no hardcoded secrets. Include troubleshooting for busy ports and ADMIN_TOKEN configuration.
- Do not claim deployment, GitHub/production, live external feed freshness, or browser rendering that was not verified.

## Files allowed

- Only the six docs above.
- Do not edit `docs/MISSION.md`, `PLAN.md`, checks, product source, or `.env.example`.

## Verify

- Check all referenced paths/commands exist, scan docs for obvious secret-looking values, run `git diff --check`, and report exact files.
- Commit only the six docs and report exact commit.
