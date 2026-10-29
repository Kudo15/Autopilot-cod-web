# TASK 016 — One-command localhost startup

## Prompt basis

Adapt the prompt-librarian Code Review Assistant pattern: inspect the existing scripts/package/python commands, implement the smallest operational helper, and verify each branch with concrete command output.

## Contract

- Add `scripts/dev.ps1` with `-Check` and normal modes.
- `-Check` validates Node/npm/uv/Python availability, required files/dependencies, and whether localhost ports 8000/5173 are available; it must return non-zero with actionable text when a prerequisite is missing.
- Normal mode loads `.env.example` only as a template reference (never prints or invents secrets), runs idempotent DB migration, and starts backend on `127.0.0.1:8000` plus Vite on `127.0.0.1:5173`. Do not bind `0.0.0.0`, do not deploy, and do not push.
- Use PowerShell-native process handling, no destructive cleanup, and keep child process IDs visible/controlled. A `-NoInstall` or equivalent is acceptable if it avoids implicit network installs.
- Add `.env.example` with safe placeholders only (`ADMIN_TOKEN=`, optional AI vars) and comments that real secrets stay in environment; no actual keys.
- Add a narrowly scoped script test or static verification under `backend/tests/` only if needed; do not change frontend/backend product logic.

## Files allowed

- `scripts/dev.ps1`
- `.env.example`
- `scripts/**` only for a narrowly required helper
- `backend/tests/test_startup_script.py` only if needed

Never edit `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## Verify

- Run `pwsh -File scripts/dev.ps1 -Check` (or Windows PowerShell equivalent), static localhost/secret scan, full backend suite if tests added, `npm run build`, and `git diff --check`.
- Record any unavailable live long-running startup/browser smoke as `NOT_VERIFIED`; do not claim a server was left running.
- Commit only scoped files and report exact commit.
