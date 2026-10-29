# REVIEW TASK 015B — Daily Radar final ruling

Review exact candidate commit `9fb92f5` at `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_d1b6b6b2`. Do not edit product files.

This is a final independent review. Inspect the three changed files and run the focused suite. Existing candidate evidence is: focused 27/27, full backend 312 OK, npm build exit 0, P3 13/13, P4 15/15, P5 11/11, diff-check clean. The earlier full-suite reviewer invocation used a non-exported bash assignment and produced an unrelated ADMIN_TOKEN 500; do not repeat that artifact. If rerunning full tests, use PowerShell `$env:ADMIN_TOKEN=[guid]::NewGuid().ToString('N'); uv run python -m unittest discover -s backend/tests` or an equivalent exported environment.

Check these concrete invariants: exact windows and VN today boundary; explicit parameterized SQL; only PUBLISHED non-SAMPLE articles and non-SAMPLE events; no raw snapshot/content output; stale/current/SIGNAL_WEAK; auth-before-DB for admin refresh; no network/publish/verify/thread; honest deferred 07:00 marker; exact scope and no secret leakage.

Return exactly:

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```

External freshness/live network is NOT_VERIFIED by design.
