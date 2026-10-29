# REVIEW TASK 008 — independent P7 Explorer UI review | role: reviewer | harness: hermes-kanban

## CANDIDATE

- Candidate worktree: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web\\.worktrees\\t_ec077e6b`
- Exact candidate commit: `17f96c7`
- Parent: `c1985ba`
- Files: `src/App.jsx`, `src/styles.css`, `src/components/ExplorerView.jsx`

Use the Code Review Agent template. Review the exact commit; do not edit product files.

## REVIEW QUESTIONS

1. Does the active Explorer group call `/api/models` and preserve existing article groups/states?
2. Are model/provider/API-id/free/quota/capability/verification fields rendered as returned, with UNKNOWN/UNVERIFIED/NULL clearly labeled?
3. Are filters and session-local compare selection functional without embedding provider/model claims or adding dependencies?
4. Are external links safe (`target=_blank`, `rel=noreferrer`) and is untrusted text rendered as React text rather than HTML?
5. Are loading/empty/error/retry states accessible and responsive; are SAMPLE-only live data and unavailable browser smoke recorded honestly?

## REQUIRED EVIDENCE

- Inspect exact diff and allowed-file scope.
- Run `npm run build`, `git diff --check`, bundle secret/provenance/registry scan and the worker's static/DOM harness checks.
- Run a localhost runtime smoke if possible; otherwise mark browser DOM NOT_VERIFIED.
- Verify no backend/check/PLAN/MISSION files changed.

## VERDICT FORMAT

```
VERDICT: APPROVED | CHANGES_REQUESTED
FINDINGS:
- [P0/P1/P2/P3] file:line — concrete evidence and required fix
EVIDENCE:
- command → exit code and measured result
```
