"""Failing-first tests for the radar observation core (Phase 8, task 009).

Contract under test:
- The change detector compares before/after provider-model and offer snapshots
  and emits ONLY the allowed event types (NEW_PROVIDER, NEW_MODEL, MODEL_REMOVED,
  FREE_TO_PAID, PAID_TO_FREE, QUOTA_CHANGED, OFFER_STARTED, OFFER_EXPIRED,
  TERMS_CHANGED).
- A missing/timeout/unavailable observation signals a collection failure and is
  NEVER reported as MODEL_REMOVED.
- Comparisons are deterministic and unchanged snapshots emit no events at all.
- Quota observation persistence appends timestamped rows transactionally, never
  overwrites a prior observation and never invents a quota value.
- The freshness evaluator maps explicit timestamps/validity only to
  VERIFIED/UNVERIFIED/STALE/EXPIRED/NEEDS_REVIEW; NULL/unknown stays UNVERIFIED.

Snapshot text is untrusted data: it is compared, never executed and never used to
build SQL.
"""
from __future__ import annotations

from collections import Counter
import sqlite3
from datetime import datetime, timedelta, timezone
import unittest

from backend.app.radar.changes import (
    EVENT_TYPES,
    ChangeEvent,
    CollectionUnavailable,
    detect_offer_changes,
    detect_provider_model_changes,
    evaluate_verification,
)
from backend.app.radar.quota import quota_history, record_quota_observation


def _utc(days: float) -> str:
    """ISO-8601 timestamp `days` away from now (negative = in the past)."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _pm(provider_id, model_id, **overrides) -> dict:
    snapshot = {
        "provider_id": provider_id,
        "model_id": model_id,
        "free_status": "FREE_API",
        "rate_limit": "10 rpm/min",
        "daily_quota": 1000,
    }
    snapshot.update(overrides)
    return snapshot


def _offer(offer_id, provider_model_id, **overrides) -> dict:
    snapshot = {
        "offer_id": offer_id,
        "provider_model_id": provider_model_id,
        "title": "Local Test Offer",
        "offer_type": "PROMO",
        "terms": "First 1000 requests free",
        "starts_at": _utc(-1),
        "ends_at": _utc(30),
    }
    snapshot.update(overrides)
    return snapshot


def _types(events) -> list[str]:
    return [e.event_type for e in events]


def _find(events, event_type):
    return [e for e in events if e.event_type == event_type]


def make_quota_db() -> sqlite3.Connection:
    """Isolated in-memory DB mirroring the migrated quota_observations table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE quota_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_model_id INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            rate_limit TEXT,
            daily_quota INTEGER,
            observed_value TEXT,
            note TEXT,
            data_origin TEXT NOT NULL DEFAULT 'REAL'
                CHECK (data_origin IN ('REAL', 'SAMPLE')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


class ProviderModelChangeTests(unittest.TestCase):
    """Sinh đúng loại sự kiện từ cặp snapshot before/after."""

    def test_new_provider_and_new_model_from_empty_before(self) -> None:
        events = detect_provider_model_changes(
            [],
            [_pm("prov-new", "m-1"), _pm("prov-new", "m-2")],
        )

        self.assertEqual(
            sorted(_types(events)),
            ["NEW_MODEL", "NEW_MODEL", "NEW_PROVIDER"],
        )
        self.assertEqual(
            [e.key for e in _find(events, "NEW_PROVIDER")],
            [("prov-new",)],
        )
        # Sự kiện NEW_PROVIDER mang bằng chứng quan sát thật, không bịa tên provider.
        new_provider = _find(events, "NEW_PROVIDER")[0]
        self.assertIsNotNone(new_provider.after)
        self.assertEqual(new_provider.after["provider_id"], "prov-new")
        self.assertEqual(new_provider.after["model_ids"], ["m-1", "m-2"])
        self.assertEqual(
            sorted(e.key for e in _find(events, "NEW_MODEL")),
            [("prov-new", "m-1"), ("prov-new", "m-2")],
        )
        for event in events:
            self.assertIsNone(event.before)
            self.assertIsNotNone(event.after)

    def test_model_removed_only_when_after_observation_succeeded(self) -> None:
        before = [_pm("prov-a", "m-1"), _pm("prov-a", "m-2")]
        after = [_pm("prov-a", "m-2")]  # quan sát thành công, m-1 biến mất thật

        events = detect_provider_model_changes(before, after)

        removed = _find(events, "MODEL_REMOVED")
        self.assertEqual([e.key for e in removed], [("prov-a", "m-1")])
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(removed[0].before)
        self.assertIsNone(removed[0].after)

    def test_missing_after_observation_is_collection_failure_not_removal(self) -> None:
        before = [_pm("prov-a", "m-1"), _pm("prov-a", "m-2")]

        for unavailable in (None, [], ()):
            with self.subTest(after=unavailable):
                with self.assertRaises(CollectionUnavailable):
                    detect_provider_model_changes(before, unavailable)

    def test_timeout_marker_is_collection_failure_not_removal(self) -> None:
        before = [_pm("prov-a", "m-1")]

        with self.assertRaises(CollectionUnavailable):
            detect_provider_model_changes(
                before, {"status": "TIMEOUT", "items": [], "error": "read timed out"}
            )

    def test_unchanged_snapshot_emits_no_events(self) -> None:
        snapshot = [_pm("prov-a", "m-1", daily_quota=1000), _pm("prov-a", "m-2")]
        before = [dict(row) for row in snapshot]
        after = [dict(row) for row in snapshot]

        self.assertEqual(detect_provider_model_changes(before, after), [])
        # So sánh lại vẫn rỗng: không sinh sự kiện trùng cho snapshot không đổi.
        self.assertEqual(detect_provider_model_changes(before, after), [])

    def test_free_to_paid_and_back(self) -> None:
        went_paid = detect_provider_model_changes(
            [_pm("prov-a", "m-1", free_status="FREE_API")],
            [_pm("prov-a", "m-1", free_status="PAID")],
        )
        went_free = detect_provider_model_changes(
            [_pm("prov-a", "m-1", free_status="PAID")],
            [_pm("prov-a", "m-1", free_status="FREE_CREDIT")],
        )

        self.assertEqual(_types(went_paid), ["FREE_TO_PAID"])
        self.assertEqual(_types(went_free), ["PAID_TO_FREE"])

    def test_unknown_free_status_never_claims_a_transition(self) -> None:
        to_unknown = detect_provider_model_changes(
            [_pm("prov-a", "m-1", free_status="FREE_API")],
            [_pm("prov-a", "m-1", free_status="UNKNOWN")],
        )
        from_unknown = detect_provider_model_changes(
            [_pm("prov-a", "m-1", free_status="UNKNOWN")],
            [_pm("prov-a", "m-1", free_status="PAID")],
        )

        self.assertEqual(to_unknown, [])
        self.assertEqual(from_unknown, [])

    def test_quota_changed_requires_two_known_differing_values(self) -> None:
        changed = detect_provider_model_changes(
            [_pm("prov-a", "m-1", daily_quota=1000)],
            [_pm("prov-a", "m-1", daily_quota=500)],
        )
        same_number_different_notation = detect_provider_model_changes(
            [_pm("prov-a", "m-1", daily_quota=1000)],
            [_pm("prov-a", "m-1", daily_quota="1000")],
        )
        newly_observed = detect_provider_model_changes(
            [_pm("prov-a", "m-1", daily_quota=None, rate_limit=None)],
            [_pm("prov-a", "m-1", daily_quota=1000, rate_limit="10 rpm/min")],
        )

        self.assertEqual(_types(changed), ["QUOTA_CHANGED"])
        self.assertEqual(same_number_different_notation, [])
        # Chưa từng biết quota cũ -> không được bịa "quota cũ" để báo thay đổi.
        self.assertEqual(newly_observed, [])

    def test_rate_limit_change_is_quota_changed(self) -> None:
        events = detect_provider_model_changes(
            [_pm("prov-a", "m-1", rate_limit="10 rpm/min")],
            [_pm("prov-a", "m-1", rate_limit="3 rpm/min")],
        )

        self.assertEqual(_types(events), ["QUOTA_CHANGED"])

    def test_multiple_changes_are_deterministic_and_only_allowed_types(self) -> None:
        before = [
            _pm("prov-a", "m-1", free_status="FREE_API", daily_quota=1000),
            _pm("prov-a", "m-gone"),
            _pm("prov-a", "m-stable"),
        ]
        after = [
            _pm("prov-a", "m-1", free_status="PAID", daily_quota=200),
            _pm("prov-a", "m-stable"),
            _pm("prov-b", "m-new"),
        ]

        first = detect_provider_model_changes(before, after)
        second = detect_provider_model_changes(before, after)

        self.assertEqual(first, second)
        self.assertEqual(
            Counter(_types(first)),
            Counter(
                ["FREE_TO_PAID", "QUOTA_CHANGED", "MODEL_REMOVED", "NEW_PROVIDER", "NEW_MODEL"]
            ),
        )
        self.assertTrue({e.event_type for e in first} <= EVENT_TYPES)
        # m-1 đổi trạng thái -> đúng 1 FREE_TO_PAID + 1 QUOTA_CHANGED, không trùng.
        self.assertEqual(len([e for e in first if e.key == ("prov-a", "m-1")]), 2)

    def test_duplicate_identity_in_one_observation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            detect_provider_model_changes(
                [_pm("prov-a", "m-1")],
                [_pm("prov-a", "m-1"), _pm("prov-a", "m-1", daily_quota=5)],
            )

    def test_snapshot_without_identity_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            detect_provider_model_changes([], [{"model_id": "m-1"}])

    def test_snapshot_text_is_not_executed_or_used_as_sql(self) -> None:
        injection = "'; DROP TABLE change_events; --"
        events = detect_provider_model_changes(
            [_pm("prov-a", "m-1", free_status="FREE_API", rate_limit=injection)],
            [
                _pm("prov-a", "m-1", free_status="PAID", rate_limit=injection),
                _pm("prov-a", "m-injected", free_status=injection),
            ],
        )

        # Text lạ chỉ là dữ liệu: nó đi vào snapshot của sự kiện, không sinh SQL.
        self.assertEqual(sorted(_types(events)), ["FREE_TO_PAID", "NEW_MODEL"])
        injected = _find(events, "NEW_MODEL")[0]
        self.assertEqual(injected.after["free_status"], injection)


class OfferChangeTests(unittest.TestCase):
    """So sánh snapshot offer: bắt đầu, hết hạn, đổi điều khoản."""

    def test_offer_started_when_it_appears_in_the_after_snapshot(self) -> None:
        events = detect_offer_changes([], [_offer(7, 1)])

        self.assertEqual(_types(events), ["OFFER_STARTED"])
        self.assertEqual(events[0].key, ("offer", 7))
        self.assertIsNone(events[0].before)
        self.assertIsNotNone(events[0].after)

    def test_offer_expired_when_it_disappears_from_a_successful_collection(self) -> None:
        events = detect_offer_changes(
            [_offer(7, 1), _offer(8, 1)],
            [_offer(8, 1)],
        )

        self.assertEqual(_types(events), ["OFFER_EXPIRED"])
        self.assertEqual(events[0].key, ("offer", 7))

    def test_terms_changed_requires_two_known_differing_terms(self) -> None:
        changed = detect_offer_changes(
            [_offer(7, 1, terms="First 1000 requests free")],
            [_offer(7, 1, terms="First 100 requests free")],
        )
        unknown_before = detect_offer_changes(
            [_offer(7, 1, terms=None)],
            [_offer(7, 1, terms="First 100 requests free")],
        )
        unchanged = detect_offer_changes(
            [_offer(7, 1, terms="Same terms")],
            [_offer(7, 1, terms="Same terms")],
        )

        self.assertEqual(_types(changed), ["TERMS_CHANGED"])
        self.assertEqual(unknown_before, [])
        self.assertEqual(unchanged, [])

    def test_offer_type_free_paid_transition(self) -> None:
        went_paid = detect_offer_changes(
            [_offer(7, 1, offer_type="FREE_TRIAL")],
            [_offer(7, 1, offer_type="PAID")],
        )
        went_free = detect_offer_changes(
            [_offer(7, 1, offer_type="PAID")],
            [_offer(7, 1, offer_type="PROMO")],
        )

        self.assertEqual(_types(went_paid), ["FREE_TO_PAID"])
        self.assertEqual(_types(went_free), ["PAID_TO_FREE"])

    def test_unavailable_offer_observation_is_collection_failure(self) -> None:
        with self.assertRaises(CollectionUnavailable):
            detect_offer_changes([_offer(7, 1)], None)

    def test_expired_collection_never_reports_offer_expired(self) -> None:
        before = [_offer(7, 1)]
        with self.assertRaises(CollectionUnavailable) as ctx:
            detect_offer_changes(before, [])
        self.assertNotIn("OFFER_EXPIRED", str(ctx.exception.event_type if hasattr(ctx.exception, "event_type") else ""))

    def test_offer_events_are_deterministic(self) -> None:
        before = [_offer(7, 1, terms="old"), _offer(9, 1)]
        after = [_offer(7, 1, terms="new"), _offer(8, 1)]

        first = detect_offer_changes(before, after)
        second = detect_offer_changes(before, after)
        self.assertEqual(first, second)
        self.assertEqual(sorted(_types(first)), ["OFFER_EXPIRED", "OFFER_STARTED", "TERMS_CHANGED"])


class VerificationFreshnessTests(unittest.TestCase):
    """VERIFIED/UNVERIFIED/STALE/EXPIRED/NEEDS_REVIEW chỉ từ timestamp rõ ràng."""

    def test_null_or_unknown_verification_stays_unverified(self) -> None:
        self.assertEqual(evaluate_verification(None, _utc(30)), "UNVERIFIED")
        self.assertEqual(evaluate_verification(None, None), "UNVERIFIED")
        self.assertEqual(evaluate_verification("", None), "UNVERIFIED")
        self.assertEqual(evaluate_verification("not-a-timestamp", _utc(30)), "UNVERIFIED")

    def test_recently_verified_with_future_validity_is_verified(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-1), _utc(60), now=_utc(0)), "VERIFIED"
        )

    def test_past_validity_is_expired(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-1), _utc(-1), now=_utc(0)), "EXPIRED"
        )

    def test_validity_inside_review_lead_is_needs_review(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-1), _utc(3), now=_utc(0)), "NEEDS_REVIEW"
        )

    def test_old_last_verified_is_stale(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-31), _utc(200), now=_utc(0)), "STALE"
        )

    def test_approaching_staleness_is_needs_review(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-25), _utc(200), now=_utc(0)), "NEEDS_REVIEW"
        )

    def test_thresholds_are_explicit_and_configurable(self) -> None:
        self.assertEqual(
            evaluate_verification(
                _utc(-10), None, now=_utc(0), stale_after_days=30, review_lead_days=7
            ),
            "VERIFIED",
        )
        self.assertEqual(
            evaluate_verification(
                _utc(-10), None, now=_utc(0), stale_after_days=5, review_lead_days=1
            ),
            "STALE",
        )

    def test_expiry_outranks_staleness_but_never_outranks_missing_proof(self) -> None:
        # Có last_verified cũ + validity đã hết -> EXPIRED (validity quyết định).
        self.assertEqual(
            evaluate_verification(_utc(-90), _utc(-2), now=_utc(0)), "EXPIRED"
        )
        # Không có last_verified -> UNVERIFIED, kể cả validity đã hết.
        self.assertEqual(evaluate_verification(None, _utc(-2), now=_utc(0)), "UNVERIFIED")

    def test_unparseable_validity_is_treated_as_unknown(self) -> None:
        self.assertEqual(
            evaluate_verification(_utc(-1), "whenever", now=_utc(0)), "VERIFIED"
        )

    def test_invalid_thresholds_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_verification(_utc(-1), None, now=_utc(0), stale_after_days=0)
        with self.assertRaises(ValueError):
            evaluate_verification(_utc(-1), None, now=_utc(0), review_lead_days=-1)


class QuotaObservationTests(unittest.TestCase):
    """Ghi quota quan sát theo thời gian: append-only, transactional, không bịa."""

    def test_records_timestamped_row_and_returns_id(self) -> None:
        conn = make_quota_db()
        try:
            observed_at = _utc(-1)
            row_id = record_quota_observation(
                conn,
                provider_model_id=1,
                observed_at=observed_at,
                rate_limit="10 rpm/min",
                daily_quota=1000,
            )
            rows = quota_history(conn, provider_model_id=1)
        finally:
            conn.close()

        self.assertEqual(row_id, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["observed_at"], observed_at)
        self.assertEqual(rows[0]["daily_quota"], 1000)
        self.assertEqual(rows[0]["rate_limit"], "10 rpm/min")
        self.assertEqual(rows[0]["data_origin"], "REAL")

    def test_appends_instead_of_overwriting_prior_observations(self) -> None:
        conn = make_quota_db()
        try:
            for index, quota in enumerate((100, 200, 150)):
                record_quota_observation(
                    conn,
                    provider_model_id=1,
                    observed_at=_utc(-3 + index),
                    daily_quota=quota,
                )
            rows = quota_history(conn, provider_model_id=1)
        finally:
            conn.close()

        self.assertEqual([r["daily_quota"] for r in rows], [100, 200, 150])
        self.assertEqual([r["observed_at"] for r in rows], sorted(r["observed_at"] for r in rows))

    def test_history_is_scoped_per_provider_model(self) -> None:
        conn = make_quota_db()
        try:
            record_quota_observation(conn, provider_model_id=1, observed_at=_utc(-1), daily_quota=10)
            record_quota_observation(conn, provider_model_id=2, observed_at=_utc(-1), daily_quota=20)
            first = quota_history(conn, provider_model_id=1)
            everything = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual([r["daily_quota"] for r in first], [10])
        self.assertEqual(len(everything), 2)

    def test_refuses_to_invent_a_value_for_an_empty_observation(self) -> None:
        conn = make_quota_db()
        try:
            with self.assertRaises(ValueError):
                record_quota_observation(conn, provider_model_id=1, observed_at=_utc(-1))
            rows = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual(rows, [])

    def test_rejects_malformed_values_without_persisting(self) -> None:
        conn = make_quota_db()
        try:
            bad_calls = [
                dict(provider_model_id=1, observed_at=_utc(-1), daily_quota="many"),
                dict(provider_model_id=1, observed_at=_utc(-1), daily_quota=-5),
                dict(provider_model_id=1, observed_at=_utc(-1), daily_quota=True),
                dict(provider_model_id=1, observed_at=_utc(-1), rate_limit=""),
                dict(provider_model_id=1, observed_at="not-a-timestamp", daily_quota=1),
                dict(provider_model_id=0, observed_at=_utc(-1), daily_quota=1),
                dict(provider_model_id=1, observed_at=_utc(-1), daily_quota=1, data_origin="FAKE"),
            ]
            for call in bad_calls:
                with self.subTest(call=call):
                    with self.assertRaises(ValueError):
                        record_quota_observation(conn, **call)
            rows = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual(rows, [])

    def test_failed_insert_rolls_back_the_transaction(self) -> None:
        conn = make_quota_db()
        try:
            record_quota_observation(conn, provider_model_id=1, observed_at=_utc(-1), daily_quota=10)
            with self.assertRaises(ValueError):
                record_quota_observation(
                    conn, provider_model_id=1, observed_at=_utc(-1), daily_quota=20, data_origin="NOPE"
                )
            rows = quota_history(conn)
            # Kết nối vẫn dùng được sau rollback (transaction sạch).
            record_quota_observation(conn, provider_model_id=2, observed_at=_utc(0), daily_quota=30)
            after = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual([r["daily_quota"] for r in rows], [10])
        self.assertEqual([r["daily_quota"] for r in after], [10, 30])

    def test_does_not_commit_a_callers_open_transaction(self) -> None:
        conn = make_quota_db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO quota_observations (provider_model_id, observed_at, daily_quota)"
                " VALUES (1, ?, 111)",
                (_utc(-2),),
            )
            record_quota_observation(
                conn, provider_model_id=1, observed_at=_utc(-1), daily_quota=222
            )
            rows_inside = quota_history(conn)
            conn.rollback()
            rows_after_rollback = quota_history(conn)
        finally:
            conn.close()

        # Cả hai dòng nằm trong transaction của caller...
        self.assertEqual([r["daily_quota"] for r in rows_inside], [111, 222])
        # ...và rollback của caller phải xoá được TOÀN BỘ, không bị commit sớm.
        self.assertEqual(rows_after_rollback, [])

    def test_sample_origin_is_labelled_not_hidden(self) -> None:
        conn = make_quota_db()
        try:
            record_quota_observation(
                conn,
                provider_model_id=1,
                observed_at=_utc(-1),
                daily_quota=999999,
                note="SAMPLE data for tests",
                data_origin="SAMPLE",
            )
            rows = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual(rows[0]["data_origin"], "SAMPLE")
        self.assertEqual(rows[0]["note"], "SAMPLE data for tests")

    def test_observed_value_is_stored_verbatim(self) -> None:
        conn = make_quota_db()
        try:
            record_quota_observation(
                conn,
                provider_model_id=1,
                observed_at=_utc(-1),
                observed_value="X-RateLimit-Remaining: 42",
            )
            rows = quota_history(conn)
        finally:
            conn.close()

        self.assertEqual(rows[0]["observed_value"], "X-RateLimit-Remaining: 42")
        self.assertIsNone(rows[0]["daily_quota"])

    def test_history_limit_is_validated(self) -> None:
        conn = make_quota_db()
        try:
            record_quota_observation(conn, provider_model_id=1, observed_at=_utc(-2), daily_quota=10)
            record_quota_observation(conn, provider_model_id=1, observed_at=_utc(-1), daily_quota=20)
            with self.assertRaises(ValueError):
                quota_history(conn, limit=-1)
            limited = quota_history(conn, limit=1)
        finally:
            conn.close()

        self.assertEqual([r["daily_quota"] for r in limited], [10])


class EventTypeContractTests(unittest.TestCase):
    """Chỉ chín loại sự kiện được phép, đúng tên trong schema CHECK."""

    def test_allowed_event_types_are_exactly_the_schema_set(self) -> None:
        self.assertEqual(
            EVENT_TYPES,
            {
                "NEW_PROVIDER",
                "NEW_MODEL",
                "MODEL_REMOVED",
                "FREE_TO_PAID",
                "PAID_TO_FREE",
                "QUOTA_CHANGED",
                "OFFER_STARTED",
                "OFFER_EXPIRED",
                "TERMS_CHANGED",
            },
        )

    def test_change_event_carries_identity_and_snapshots(self) -> None:
        event = ChangeEvent(
            event_type="NEW_MODEL",
            key=("prov-a", "m-1"),
            before=None,
            after={"provider_id": "prov-a", "model_id": "m-1"},
        )

        self.assertEqual(event.event_type, "NEW_MODEL")
        self.assertEqual(event.key, ("prov-a", "m-1"))
        self.assertIsNone(event.before)
        self.assertEqual(event.after["model_id"], "m-1")


if __name__ == "__main__":
    unittest.main()
