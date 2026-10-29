# F1 final acceptance evidence and human handoff

Use Hermes GUI worker, but keep the inspection bounded and evidence-first. Read
only the current `.team/audit.md`, `.team/ledger.md`,
`docs/agent-team/REMAINING_GAPS.md`, `.team/results/**` filenames/summaries,
and relevant current git status. Do not read or modify checks/PLAN.md/docs/MISSION.md.

Allowed writes only:
- `.team/audit.md`
- `.team/ledger.md`
- `docs/agent-team/**`
- `AI_HANDOFF.md` (new/update)
- `README.md` or `README_LOCAL.md` only if a concise local limitation note is needed

Recreate the final checklist with exact current evidence: P1–P5, full backend
count, focused S1/R1/R2, Playwright, build, diff-check, backup/restore drill,
startup -Check, live RSS status, REAL/SAMPLE boundary, secret boundary, worker
and reviewer traces. Explicitly classify stale/unknown evidence as NOT_VERIFIED.
Because live external collection is unverified, port 8000 is occupied, and
independent Hermes reviewers for Q2/R1/S1+R2/O1 stalled, the only supported
final verdict is `NOT_READY` (or `PASS_WITH_WARNINGS` only if you justify why
all hard gates are cleared; do not do that here).

Do not claim a commit, deployment, push, or production readiness. End the
report with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING] NOT_READY`, and
`## Human Gate` listing the exact operator decisions needed.
