# TASK f4-o1-review | independent O1 operations review | harness: hermes-gui

## NGỮ CẢNH

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`
- This is read-only. Do not edit files, do not start or stop any server/process, do not touch SQLite databases, and do not inspect the reference project.
- Use the Code Reviewer pattern: first verify the task/spec contract, then review correctness, safety, and evidence.

## TÁC VỤ

Review only O1 operations/preflight artifacts:

- `scripts/dev.ps1`
- `scripts/backup_db.ps1`
- `scripts/restore_db.ps1`
- `backend/tests/test_startup_script.py`
- `.team/audit.md`, `docs/agent-team/REMAINING_GAPS.md`, and `.team/ops-drill` evidence

Verify that `-Check` is localhost-only, truthful about Python 3.13/uv fallback and occupied ports, does not install/start/kill unexpectedly, and that backup/restore scripts are bounded and do not overwrite the real DB during the fixture drill. Use only `read_file`, `search_files`, or `terminal` tools; never use `execute_code`, arbitrary Python, network, or destructive commands. Run at most the read-only focused startup tests and inspect existing evidence. Do not change files.

## OUTPUT

Report file:line findings with severity and actual commands/exit codes. End exactly with:

`VERDICT: APPROVED — <one-line reason>`

or

`VERDICT: CHANGES_REQUESTED — <severity-ranked findings>`

If evidence is insufficient, mark the item `NOT_VERIFIED` and do not infer approval.
