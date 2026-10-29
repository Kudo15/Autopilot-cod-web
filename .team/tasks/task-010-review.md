# REVIEW TASK 010 — Rule-based editorial schema and fallback

Review exact candidate commit `807cc23` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_0e9d59cd` against `.team/tasks/task-010.md`.

Do not edit product files. Return APPROVED or CHANGES_REQUESTED with concrete findings.

## Review questions

1. Is `EditorialDraft` immutable, strict about bounded text/enums/unknown keys/ranking evidence, and limited to DRAFT/PENDING_REVIEW rather than publication?
2. Is `classify_rule_based(raw_item)` deterministic, side-effect-free, and explicit about unknown category, risk, recommendation and missing verification/freshness evidence?
3. Does prompt-injection-shaped article text remain plain data/signals without becoming a command, file operation, network request, secret read or publish action?
4. Are quota/freshness/verification/ranking claims conservative and not fabricated when no evidence exists?
5. Are changes exactly task-scoped (editorial package plus focused tests) and compatible with the existing backend/frontend gates?

## Evidence

- Inspect exact diff and changed-file scope.
- Run focused editorial tests, full backend suite with generated `ADMIN_TOKEN`, `npm run build`, P3/P4/P5, source/bundle scans and `git diff --check`.
- Independently probe immutability, invalid enum/unknown key rejection, deterministic output, prompt injection and no I/O/env/network side effects.
- Mark external freshness as NOT_VERIFIED and browser limitations as NOT_VERIFIED.

## Output

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```
