# REVIEW TASK 013 — Bounded RSS/Atom collector

Review exact candidate commit `232a38b` in `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_f87d5461` against `.team/tasks/task-013.md`.

Do not edit product files. Return APPROVED or CHANGES_REQUESTED with concrete findings.

## Review questions

1. Does `rss.py` expose an injected-client `collect_feed` and parse RSS 2.0/Atom as untrusted text without executing content?
2. Are HTTP(S), private/loopback/link-local/metadata/CGNAT, credentials, redirect, body, item, timeout, retry and backoff policies bounded and revalidated on every hop?
3. Are malformed XML, entity declarations, unsafe redirects, timeout and non-success responses bounded failures that never claim success?
4. Does transactional persistence use the existing schema/helpers, preserve `source_id`/`data_origin`, deduplicate repeated observations including SAMPLE, rollback the run and raw rows on mid-batch failure, and never publish articles?
5. Are local fixtures explicitly SAMPLE, external freshness NOT_VERIFIED, frontend/bundle isolation preserved, and changed files task-scoped?

## Evidence

- Inspect exact diff and changed-file scope.
- Re-run focused RSS/Atom tests, full backend suite with generated `ADMIN_TOKEN`, build, source/bundle scans, P3/P4/P5 and `git diff --check`.
- Independently probe unsafe hosts/redirects, entity rejection, retry cap/backoff, duplicate persistence and rollback.
- Mark external network freshness and private-localhost browser limitations as NOT_VERIFIED; do not turn fixture evidence into REAL evidence.

## Output

```
[RULING] APPROVED | CHANGES_REQUESTED
[FINDINGS]
[EVIDENCE]
[RESIDUAL_RISK]
```
