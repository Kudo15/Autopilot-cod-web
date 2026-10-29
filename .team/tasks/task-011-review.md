# REVIEW TASK 011 — OpenAI-compatible editorial gateway

Review exact candidate commit `e2b1422` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_4604c7e5` against `.team/tasks/task-011.md`.

Do not edit product files. Return APPROVED or CHANGES_REQUESTED with concrete findings.

## Review questions

1. Are AI env values read only at request time, with the key never in URL/body/log/bundle or persisted, and with redacted bounded errors?
2. Are endpoint/redirect/private-host, timeout, body, retry/backoff and 4xx/5xx policies bounded and revalidated?
3. Does valid fake output pass strict editorial validation while malformed/timeout/missing config/unsafe endpoint/unsafe model text safely fall back to rule classification?
4. Are fallback and gateway results always DRAFT/PENDING_REVIEW, NEEDS_REVIEW and NOT_VERIFIED, with no auto-publish/auto-verify or side effects?
5. Are changes task-scoped and compatible with existing gates, with no frontend/migration/check/PLAN/MISSION edits? (No main route was added because direct module tests covered the contract.)

## Evidence

- Inspect exact diff and changed-file scope.
- Re-run focused gateway tests, full backend suite with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, source/bundle secret scans and `git diff --check`.
- Independently probe missing key, fake success, malformed response, retry cap, unsafe redirect/host, API-key redaction, model injection, and open/subprocess/socket/env side effects.
- Mark external gateway freshness and live external network as NOT_VERIFIED.

## Output

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```
