# Task R1 API retry — bounded Promotion Radar backend

Implement ONLY the backend Promotion Radar contract. Do not touch frontend.

## Allowed files

- `backend/app/main.py`
- `backend/tests/test_promotion_radar.py` (new)
- `.team/results/**` output only

Never edit checks, PLAN.md, docs/MISSION.md, real DB, reference project, or any
frontend file.

## Required behavior

- GET `/api/offers`: bounded `limit`, optional `q`, `provider`, `offer_type`,
  `status`; unknown query -> 422. Default public result contains only REAL,
  VERIFIED, not expired offers with a non-empty `official_url` (additive schema
  is forbidden in this retry; use existing columns and return `website` as the
  official CTA only when it is an http(s) URL). Explicit allowlisted response
  fields only; never return `code`, snapshots, reviewer notes, raw content, or
  SAMPLE rows.
- POST `/api/admin/offers/{offer_id}/verification`: `require_admin` before DB,
  validate status/evidence/note/method, reject SAMPLE, insert verification_records
  with offer_id and update offer verification_status; update last_verified only
  for VERIFIED. Preserve transactions and parameterized SQL.
- Use current UTC time, deterministic safe URL check, bounded SQL, and existing
  auth/status conventions. Do not add external network calls.
- Add temporary-DB unit tests proving allowlist, SAMPLE/expiry/CTA exclusion,
  unknown query and auth ordering, plus verification lifecycle.

## Verify and markers

Run focused test, full backend unittest, and `git diff --check`; report exact
exit codes. End with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, and `## Bước tiếp theo`.
