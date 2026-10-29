# Task 002 — Fix round 1 re-review

Fix round: 1

## Verdict

**ADDRESSED** — prior finding `[P2] backend/app/ingest/normalize.py:53-62`.

The fix preserves bracketed IPv6 hosts during canonicalization at `backend/app/ingest/normalize.py:58-62`. The regression test `test_canonical_url_preserves_brackets_for_ipv6_host` at `backend/tests/test_normalize.py:24-31` verifies the canonical result `https://[2001:db8::1]/news`.

The fix explicitly rejects URLs containing user-info at `backend/app/ingest/normalize.py:56-57` with `ValueError("url user-info is not supported")`, rather than silently dropping credentials. The regression test `test_canonical_url_rejects_user_info_instead_of_discarding_it` at `backend/tests/test_normalize.py:33-39` verifies the rejection and message.

## Verification

- `python -m unittest backend.tests.test_normalize -v` — exit 0; 7 tests ran and passed, including both new regression tests.
- `git diff --check` — exit 0.
- `python -m unittest discover -v` — exit 1 / NOT_VERIFIED for the pre-existing `backend.tests.test_public_articles` import because `fastapi` is unavailable; the focused normalization tests still passed.

## New breakage in fix

None found within the reviewed scope. The implementation remains deterministic and does not broaden URL query/path normalization.

## Out-of-scope observations

- Full-suite verification remains NOT_VERIFIED because the environment lacks `fastapi`.
- The worker reports commit creation was BLOCKED by permission denied creating `.git/index.lock`; this does not affect the uncommitted files reviewed here.

