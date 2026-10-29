# REVIEW TASK 012 — Server-only source registry and collection runs

Review exact candidate commit `3be553c` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_063f1cf9` against `.team/tasks/task-012.md`.

Do not edit product files. Return APPROVED or CHANGES_REQUESTED with concrete findings.

## Review questions

1. Is the registry schema strict, deterministic and clearly labelled SAMPLE/manual/unavailable without fabricated freshness?
2. Are duplicate IDs, malformed types/statuses/methods, invalid priorities, non-HTTP(S) URLs and private/metadata/CGNAT hosts rejected safely?
3. Does `collection_runs` lifecycle use parameterized SQL, bounded/redacted error metadata, transactional semantics and explicit status transitions without destructive migration?
4. Is the registry server-only, absent from `src/` and the production bundle, with no external network/command execution or instruction interpretation?
5. Are tests task-scoped and do public/backend behavior remain compatible?

## Evidence

- Inspect exact diff and changed-file scope.
- Run focused registry/run tests and full backend suite with generated `ADMIN_TOKEN`, then build, source/bundle registry scan, P3/P4/P5 and `git diff --check`.
- Reproduce rollback, parameterization, error-bound and unsafe-host cases independently.
- Mark browser/private-localhost or stale-port limitations as NOT_VERIFIED, not PASS.

## Output

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```
