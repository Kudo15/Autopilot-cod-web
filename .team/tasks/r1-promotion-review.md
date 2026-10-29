# R1 independent review — read-only

Review only the R1 Promotion Radar changes currently in the worktree. Do not
edit files, do not start/stop servers, do not change DB. Inspect the diff,
`backend/tests/test_promotion_radar.py`, and evidence outputs.

Acceptance checks:
- public `/api/offers` query and response are bounded/allowlisted;
- SAMPLE, expired, unverified, missing/non-http CTA cannot appear as active;
- no code/raw/reviewer/provenance leakage;
- admin verification calls auth before DB, rejects SAMPLE, records offer ledger
  transactionally and does not mutate quota;
- UI only renders safe fields, explicit eligibility/expiry, and official CTA;
- no edits outside the intended R1 files and no real DB mutation.

Run only read-only checks if needed. End with exactly:
`VERDICT: APPROVED` or `VERDICT: CHANGES_REQUESTED` or `VERDICT: NOT_VERIFIED`,
then severity-ranked findings and a short evidence list.
