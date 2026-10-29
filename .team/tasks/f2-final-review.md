# TASK f2-final-review | independent final acceptance review | harness: hermes-gui

## NGỮ CẢNH

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`
- Stack: React/Vite frontend, FastAPI/SQLite backend, Hermes GUI worker/reviewer routing.
- Review current worktree only. Do not edit files, do not start or stop servers, do not touch either database, and do not inspect or modify `Vu-Agent-Room-PC`.
- Review the mission contracts in `docs/MISSION.md`, `PLAN.md`, `.team/CHARTER.md`, and the implementation/evidence in `.team/audit.md`, `docs/agent-team/REMAINING_GAPS.md`, and `AI_HANDOFF.md`.

## TÁC VỤ

Act as an independent Code Review Agent. Assess the current implementation for correctness, security, scope compliance, and evidence quality. Check both (1) spec compliance and (2) code quality. Use read-only inspection and bounded verification only.

Required focus:

1. Verify Hermes GUI routing is real (`.team/scripts/route.mjs`, `.team/routing.json`) and does not dispatch Kanban.
2. Review Q1/Q2, S1 scheduler, R1 Promotion Radar, R2 Repository Explorer, and O1 startup/backup changes against their tests and mission constraints.
3. Inspect the duplicate-declaration fix in `src/App.jsx` and confirm build/test evidence is current.
4. Check public/admin data boundaries, localhost-only behavior, no secrets, no external-network claims without evidence, and additive/idempotent SQLite migrations.
5. Treat live RSS, occupied port 8000, and missing prior reviewer verdicts as gates unless current evidence proves them resolved.

Run read-only commands as needed, preferably: `uv run python -m unittest discover -s backend/tests -p 'test_*.py'`, `npm run build`, `npx playwright test`, `git diff --check`, and inspect relevant files. Do not change files to make tests pass.

## OUTPUT (mandatory)

Write a concise report to stdout and end with exactly one of:

`VERDICT: APPROVED — <one-line reason>`

or

`VERDICT: CHANGES_REQUESTED — <severity-ranked findings>`

If evidence is insufficient for approval, use `VERDICT: CHANGES_REQUESTED` and explicitly mark the unresolved gates as NOT_VERIFIED rather than inventing a pass. Include file:line evidence for every finding and list commands actually run with exit codes.

## RULING

No product edits are authorized in this review task. If a finding is outside the current safe scope or requires operator action, record it as a Human Gate rather than changing the system.
