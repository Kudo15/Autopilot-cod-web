# REVIEW TASK 016 — localhost startup helper

Review exact commit `e653ef0` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_c3c1eefe`; do not edit product files.

Check exact scope (`scripts/dev.ps1`, `.env.example`, `backend/tests/test_startup_script.py`), no secrets/remote/deploy/destructive broad cleanup, only 127.0.0.1 binds, -Check prerequisite/port failure behavior, migration invocation, bounded child process cleanup, and safe placeholder env values. Run the 13 focused tests, inspect `git diff --check`, and use the existing evidence: full backend 325 OK with ADMIN_TOKEN, npm build 0, -Check green/negative, and live startup on override ports 8123/5273 with HTTP 200 and clean shutdown. Default 8000/5173 live run was NOT_VERIFIED because sibling processes hold those ports; browser smoke NOT_VERIFIED.

Return:
```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```
