# O1 bounded preflight + operations evidence

Use Hermes GUI worker. Allowed files only:

- `scripts/dev.ps1`
- `backend/tests/test_startup_script.py` (only focused regression test)
- `docs/README_LOCAL.md` or `README_LOCAL.md` and `docs/agent-team/**` for observed evidence/runbook
- `.team/results/**`

Do not edit checks, PLAN.md, docs/MISSION.md, backend/data/radar.db, frontend,
reference project, or kill any process.

Observed host facts to preserve truthfully:
- `uv python find 3.13` fails because uv cache permission is denied;
- `.venv/Scripts/python.exe` is Python 3.13.15 and imports fastapi/uvicorn;
- port 8000 is LISTEN by PID 17468; do not stop it.

Fix `dev.ps1 -Check` preflight so a valid project `.venv` fallback can satisfy
the Python 3.13 prerequisite when `uv python find` is unavailable, while still
reporting a clear warning/problem if neither uv nor venv proves Python 3.13.
Keep no-install behavior, localhost-only binding, and child-only shutdown.
Add a static test for the fallback contract if appropriate. Run focused startup
tests, full backend suite, `scripts/dev.ps1 -Check` (record exit truthfully),
build and diff-check. Do not claim CHECK OK while port 8000 is occupied.

End with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and `## Bước tiếp theo`.
