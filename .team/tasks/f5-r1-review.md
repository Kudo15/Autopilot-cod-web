# TASK f5-r1-review | minimal Promotion Radar review | harness: hermes-gui

## CONTEXT

Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`.
Read-only review. Never edit files, never run `execute_code`, never invoke skills, never start/stop processes, never touch databases, and do not inspect the reference project.

## REVIEW SCOPE

Read only these files with `read_file` (no other tool is required):

- `backend/app/main.py` (the `/api/offers` and admin offer-verification portions)
- `backend/app/migrate.py` (offers/verification schema additions)
- `backend/tests/test_promotion_radar.py`
- `src/components/PromotionView.jsx`
- relevant `src/App.jsx` routing lines
- `.team/audit.md` and `docs/agent-team/REMAINING_GAPS.md` R1 entries

Check: public allowlist excludes SAMPLE/unverified/expired offers; official URL/CTA safety; admin auth-before-DB and verification linkage; additive/idempotent migration; UI does not invent data; no network side effects. Treat the existing focused tests as evidence only as described in the files.

## OUTPUT

Write a short two-layer review (spec compliance then code quality), with concrete file:line findings only. End exactly with either:

`VERDICT: APPROVED — <one-line reason>`

or

`VERDICT: CHANGES_REQUESTED — <severity-ranked findings>`

If evidence is insufficient, say `NOT_VERIFIED` in the findings and choose `CHANGES_REQUESTED`. Do not perform any other action.
