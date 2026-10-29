# Task R1 Report — Promotion Radar Lifecycle + Public Allowlist

## 1. Summary of Changes
- `backend/app/migrate.py`:
  - Additive migration for `offers`: added `official_url TEXT` column idempotently via PRAGMA check.
- `backend/app/main.py`:
  - Added public `GET /api/offers` with bounded query parameter allowlist (`q`, `provider`, `offer_type`, `status`, `limit`). Unknown parameters return 422.
  - Strict public allowlist columns (`PUBLIC_OFFER_FIELDS`): `id`, `title`, `provider_id`, `provider_name`, `offer_type`, `description`, `terms`, `starts_at`, `ends_at`, `account_required`, `card_required`, `verification_status`, `last_verified`, `valid_until`, `official_url`, `is_active`. Promo `code`, internal snapshots, reviewer notes, and secrets are strictly excluded.
  - Default status `active` strictly returns `data_origin = 'REAL'`, `verification_status = 'VERIFIED'`, not expired at `now` (`ends_at`/`valid_until`), and valid `https://` or `http://` official CTA URL.
  - Added authenticated admin `GET /api/admin/offers` and `POST /api/admin/offers/{id}/verification`.
  - Admin endpoint enforces `require_admin` at the first line before touching DB, validates status/evidence/note/method, rejects SAMPLE rows (409), writes linked `verification_records`, updates `offers.verification_status`, and sets `last_verified` only when VERIFIED without touching quotas or fabricating credits.
- `src/components/admin/adminClient.js` & `src/components/admin/VerificationPanel.jsx`:
  - Added `offerVerification` endpoint and `submitOfferVerification`.
  - Updated `VerificationPanel` to allow choosing target between `provider_model` and `offer`.
- `src/components/PromotionView.jsx`:
  - Connected to `/api/offers`.
  - Supports keyword search `q`, status filter (default `active`, plus historical `VERIFIED`, `UNVERIFIED`, `EXPIRED`, `STALE`, `NEEDS_REVIEW`), and `offer_type` filter.
  - Displays full eligibility (`account_required`, `card_required`), expiration deadline, verification badge, and safe official CTA link (`target="_blank" rel="noreferrer"`).
  - Handles loading, error, and empty states gracefully.
- `src/styles.css`:
  - Styled `promotion-view`, `offer-grid`, `offer-card`, eligibility badges, and CTA button matching the existing design system.
- `backend/tests/test_promotion_radar.py`:
  - 15 unit tests covering public allowlist, SAMPLE/expiry/CTA boundaries, unknown queries, admin auth ordering, and verification lifecycle using isolated temporary SQLite DBs.
- `e2e/promotion-radar.spec.js`:
  - Playwright browser test verifying navigation to `AI Deals & Promotions`, `/api/offers` public allowlist, clean UI without promo codes or SAMPLE markers, and 422 on unknown query params.

## 2. Verification Results
- Focused tests: `uv run python -m unittest backend.tests.test_promotion_radar -v` -> 15 passed, exit code 0
- Full backend discover: `uv run python -m unittest discover -s backend/tests -p "test_*.py" -v` -> 453 passed, exit code 0
- Frontend build: `npm run build` -> exit code 0
- Playwright E2E: `npx playwright test e2e/promotion-radar.spec.js` -> 1 passed, exit code 0
- Full Playwright E2E: `npx playwright test` -> 4 passed, exit code 0
- `git diff --check` -> exit code 0
