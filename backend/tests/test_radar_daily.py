"""Focused tests for the Daily Radar service and routes (task 015).

Contract under test:
- Allowed windows are EXACTLY today/7d/30d/all; anything else raises ValueError
  and the public route maps it to 422.
- 'today' uses Asia/Ho_Chi_Minh local calendar boundaries; '7d'/'30d' use a
  UTC-aware rolling lower bound; 'all' has no lower bound.
- Queries read explicit columns with '?' parameters only; only published
  non-SAMPLE articles and non-SAMPLE change events are included; raw
  snapshots/content are never returned.
- Newest qualifying timestamp drives CURRENT vs STALE (>30 days); no evidence
  is SIGNAL_WEAK; unknown/undated timestamps never become fresh evidence.
- Radars carry bounded counts/items and generated_at; no secrets, no execution.
- POST /api/admin/radar/refresh calls require_admin BEFORE opening the DB, then
  recomputes locally only.
- RadarSchedule is an in-memory marker at 07:00 Asia/Ho_Chi_Minh with explicit
  'deferred-to-request' state (no background thread / sleep / network).
"""
from __future__ import annotations

import os
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from fastapi import HTTPException, Request

from backend.app import main as app_main
from backend.app.radar.daily import (
    MAX_ITEMS,
    RADAR_TIMEZONE_NAME,
    RadarSchedule,
    daily_radar,
    parse_timestamp,
    validate_window,
    window_bounds,
)

#: Header admin duy nhất được phép trong test — value luôn được sinh mới.
ADMIN_TOKEN_ENV = "ADMIN_TOKEN"

#: Múi giờ chuẩn hoá để test tất định (Asia/Ho_Chi_Minh = UTC+7, không DST).
VN_TZ = timezone(timedelta(hours=7))


def fresh_token() -> str:
    return "unit-" + __import__("secrets").token_hex(16)


def make_vn(timestamp: str) -> str:
    """Chuyển timestamp '+07:00' đã biết thành str (helper ngắn cho dữ liệu test)."""
    return timestamp


def fresh_today_vn_timestamp() -> str:
    """Mốc PUBLISHED 'hôm nay' giờ VN, hợp lệ cho BẤT KỲ đồng hồ chạy test nào.

    Fixture cũ hardcode ``2026-10-25T00:30:00+07:00``: bài đúng là REAL/PUBLISHED
    tươi, nhưng khi test chạy sau ngày đó thì mốc 2 ngày tuổi KHÔNG thuộc cửa sổ
    'today' -> SIGNAL_WEAK (hành vi production ĐÚNG, fixture lỗi). Mốc này luôn nằm
    trong [nửa đêm VN hôm nay +1s .. now] và tối đa ~10 phút tuổi.
    """
    now_vn = datetime.now(timezone.utc).astimezone(VN_TZ)
    day_start = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
    moment = max(now_vn - timedelta(minutes=10), day_start + timedelta(seconds=1))
    return moment.isoformat()


def make_request(
    query: str = "",
    token: str | None = None,
    method: str = "GET",
    path: str = "/api/radar",
) -> Request:
    """Request tối thiểu đủ để handler đọc query + header admin như qua HTTP thật."""
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    state = {"read": False}

    async def receive() -> dict:
        if state["read"]:
            return {"type": "http.disconnect"}
        state["read"] = True
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "headers": headers,
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 50000),
        },
        receive,
    )


def make_db() -> sqlite3.Connection:
    """DB in-memory mirroring đúng các cột mà daily.py đọc (tách biệt khỏi DB thật)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            category TEXT,
            published_at TEXT,
            data_origin TEXT NOT NULL DEFAULT 'REAL',
            article_status TEXT
        );
        CREATE TABLE change_events (
            id INTEGER PRIMARY KEY,
            event_type TEXT NOT NULL,
            detected_at TEXT,
            data_origin TEXT NOT NULL DEFAULT 'REAL'
        );
        """
    )
    conn.commit()
    return conn


def add_article(
    conn: sqlite3.Connection,
    id: int,
    *,
    title: str,
    url: str | None = None,
    source: str = "editorial",
    category: str = "tip-trick",
    published_at: str | None = None,
    data_origin: str = "REAL",
    article_status: str = "PUBLISHED",
) -> None:
    conn.execute(
        "INSERT INTO articles (id, title, url, source, category, published_at,"
        " data_origin, article_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (id, title, url, source, category, published_at, data_origin, article_status),
    )


def add_event(
    conn: sqlite3.Connection,
    id: int,
    *,
    event_type: str = "NEW_MODEL",
    detected_at: str | None = None,
    data_origin: str = "REAL",
) -> None:
    conn.execute(
        "INSERT INTO change_events (id, event_type, detected_at, data_origin)"
        " VALUES (?, ?, ?, ?)",
        (id, event_type, detected_at, data_origin),
    )


def commit(conn: sqlite3.Connection) -> None:
    conn.commit()


class WindowValidationTests(unittest.TestCase):
    """Chỉ today/7d/30d/all là hợp lệ; sai -> ValueError (route -> 422)."""

    def test_validate_window_accepts_exactly_the_four_windows(self) -> None:
        self.assertEqual(validate_window("today"), "today")
        self.assertEqual(validate_window("7d"), "7d")
        self.assertEqual(validate_window("30d"), "30d")
        self.assertEqual(validate_window("all"), "all")

    def test_validate_window_rejects_everything_else(self) -> None:
        for bad in ("week", "todayx", "TODAY", " 7d", "90d", "", "all-time"):
            with self.subTest(window=bad):
                with self.assertRaises(ValueError):
                    validate_window(bad)

    def test_daily_radar_rejects_invalid_window(self) -> None:
        conn = make_db()
        try:
            with self.assertRaises(ValueError):
                daily_radar(conn, window="yesterday", now="2026-10-25T09:00:00Z")
        finally:
            conn.close()

    def test_public_route_invalid_window_is_422_before_touching_db(self) -> None:
        guard = Mock(side_effect=AssertionError("db opened"))
        with patch.object(app_main, "get_connection", guard):
            with self.assertRaises(HTTPException) as ctx:
                app_main.public_radar(make_request(query="window=bogus"))
        self.assertEqual(ctx.exception.status_code, 422)
        guard.assert_not_called()


class SampleExclusionTests(unittest.TestCase):
    """Chỉ bài PUBLISHED không-SAMPLE và change_events không-SAMPLE mới nằm trong radar."""

    def test_sample_rows_are_excluded_from_counts_and_items(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Real fresh", published_at="2026-10-25T00:30:00+07:00")
            add_article(
                conn, 2, title="Sample", published_at="2026-10-25T01:00:00+07:00",
                data_origin="SAMPLE",
            )
            add_article(
                conn, 3, title="Draft real", published_at="2026-10-25T02:00:00+07:00",
                article_status="DRAFT",
            )
            add_event(conn, 1, event_type="NEW_MODEL", detected_at="2026-10-25T00:10:00+07:00")
            add_event(
                conn, 2, event_type="NEW_PROVIDER", detected_at="2026-10-25T00:20:00+07:00",
                data_origin="SAMPLE",
            )
            commit(conn)

            result = daily_radar(conn, window="today", now="2026-10-25T09:00:00+07:00", tz=VN_TZ)
        finally:
            conn.close()

        self.assertEqual([a["title"] for a in result["articles"]], ["Real fresh"])
        self.assertEqual([e["event_type"] for e in result["change_events"]], ["NEW_MODEL"])
        self.assertEqual(result["counts"], {"articles": 1, "change_events": 1})
        self.assertEqual(result["status"], "CURRENT")

    def test_response_never_exposes_raw_content_or_snapshots(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Clean", published_at="2026-10-25T00:30:00+07:00")
            commit(conn)
            result = daily_radar(conn, window="all", now="2026-10-25T09:00:00+07:00", tz=VN_TZ)
            raw = str(result)
        finally:
            conn.close()

        for forbidden in ("before_snapshot", "after_snapshot", "raw_content", "content_hash"):
            self.assertNotIn(forbidden, raw)


class InjectionSafetyTests(unittest.TestCase):
    """Text kiểu injection chỉ là dữ liệu: trả nguyên văn, không sinh SQL, không phá bảng."""

    def test_injection_shaped_text_is_returned_verbatim_and_tables_survive(self) -> None:
        injection = "'; DROP TABLE change_events; --"
        conn = make_db()
        try:
            add_article(
                conn, 1,
                title=injection,
                url="https://example.test/" + injection,
                published_at="2026-10-25T00:30:00+07:00",
            )
            add_event(conn, 1, event_type="NEW_MODEL", detected_at="2026-10-25T00:10:00+07:00")
            commit(conn)

            result = daily_radar(conn, window="today", now="2026-10-25T09:00:00+07:00", tz=VN_TZ)
        finally:
            conn.close()

        self.assertEqual(result["articles"][0]["title"], injection)
        self.assertEqual(result["articles"][0]["url"], "https://example.test/" + injection)
        self.assertEqual(result["counts"]["change_events"], 1)
        # Bảng vẫn còn nguyên trước/trong/sau truy vấn (đã đóng nhưng bảng = :memory: rỗng,
        # ta kiểm tra việc không còn bằng chứng nào bị mất đi khi mở lại cùng toàn bộ row).
        conn = make_db()
        try:
            add_event(conn, 1, event_type="NEW_MODEL", detected_at="2026-10-25T00:10:00+07:00")
            commit(conn)
            alive = conn.execute("SELECT COUNT(*) FROM change_events").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(alive, 1)


class TimezoneBoundaryTests(unittest.TestCase):
    """'today' theo lịch địa phương Asia/Ho_Chi_Minh; '7d'/'30d' rolling theo UTC."""

    NOW = "2026-10-25T00:30:00+07:00"  # 2026-10-24T17:30:00Z — ngày UTC lệch ngày VN.

    def test_today_uses_vn_calendar_not_utc(self) -> None:
        conn = make_db()
        try:
            # 2026-10-24T18:00:00Z = 2026-10-25T01:00 VN -> thuộc HÔM NAY (lịch VN).
            add_article(conn, 1, title="Today VN", published_at="2026-10-24T18:00:00+00:00")
            # 2026-10-24T15:00:00Z = 2026-10-24T22:00 VN -> HÔM QUA theo lịch VN.
            add_article(conn, 2, title="Yesterday VN", published_at="2026-10-24T15:00:00+00:00")
            commit(conn)

            lower, upper = window_bounds(
                "today", now=datetime.fromisoformat(self.NOW), tz=VN_TZ
            )
            self.assertEqual(lower.isoformat(), "2026-10-24T17:00:00+00:00")
            self.assertEqual(upper.isoformat(), "2026-10-25T17:00:00+00:00")

            result = daily_radar(conn, window="today", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()

        self.assertEqual([a["title"] for a in result["articles"]], ["Today VN"])
        self.assertEqual(result["counts"]["articles"], 1)
        self.assertEqual(result["window_start"], "2026-10-24T17:00:00+00:00")
        self.assertEqual(result["window_end"], "2026-10-25T17:00:00+00:00")

    def test_today_excludes_exactly_at_end_boundary(self) -> None:
        conn = make_db()
        try:
            # 2026-10-25T17:00:00Z = 2026-10-26T00:00 VN -> NGÀY MAI, loại khỏi 'today'.
            add_article(conn, 1, title="Next day", published_at="2026-10-25T17:00:00+00:00")
            commit(conn)
            result = daily_radar(conn, window="today", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual(result["articles"], [])

    def test_7d_and_30d_use_utc_rolling_lower_bound(self) -> None:
        now = datetime(2026, 10, 25, 9, 0, 0, tzinfo=timezone.utc)
        cases = {
            "7d": ("2026-10-18T09:00:00+00:00", "2026-10-18T08:59:00+00:00"),
            "30d": ("2026-09-25T09:00:00+00:00", "2026-09-25T08:59:00+00:00"),
        }
        for window, (inside, outside) in cases.items():
            with self.subTest(window=window):
                conn = make_db()
                try:
                    add_article(conn, 1, title="Inside", published_at=inside)
                    add_article(conn, 2, title="Outside", published_at=outside)
                    commit(conn)
                    result = daily_radar(conn, window=window, now=now, tz=VN_TZ)
                finally:
                    conn.close()
                self.assertEqual([a["title"] for a in result["articles"]], ["Inside"])
                self.assertEqual(result["window_start"], inside)
                self.assertIsNone(result["window_end"])

    def test_all_has_no_lower_bound(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Ancient", published_at="2020-01-01T00:00:00+00:00")
            commit(conn)
            result = daily_radar(conn, window="all", now="2026-10-25T09:00:00+00:00", tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual([a["title"] for a in result["articles"]], ["Ancient"])
        self.assertIsNone(result["window_start"])
        self.assertIsNone(result["window_end"])


class FreshnessStateTests(unittest.TestCase):
    """Trạng thái chỉ từ bằng chứng tươi mới nhất; không bằng chứng -> SIGNAL_WEAK."""

    NOW = "2026-10-25T09:00:00+00:00"

    def test_empty_database_is_signal_weak(self) -> None:
        conn = make_db()
        try:
            result = daily_radar(conn, window="today", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual(result["status"], "SIGNAL_WEAK")
        self.assertFalse(result["is_stale"])
        self.assertIsNone(result["newest_evidence_at"])
        self.assertEqual(result["counts"], {"articles": 0, "change_events": 0})
        self.assertEqual(result["articles"], [])
        self.assertEqual(result["change_events"], [])

    def test_fresh_evidence_is_current(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Fresh", published_at="2026-10-24T20:00:00+00:00")
            commit(conn)
            result = daily_radar(conn, window="7d", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual(result["status"], "CURRENT")
        self.assertEqual(result["newest_evidence_at"], "2026-10-24T20:00:00+00:00")

    def test_evidence_older_than_30_days_is_stale(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Old", published_at="2026-09-20T00:00:00+00:00")
            commit(conn)
            # 'all' không có biên dưới nên bằng chứng cũ vẫn được ĐÁNH GIÁ độ tươi.
            result = daily_radar(conn, window="all", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual(result["status"], "STALE")
        self.assertTrue(result["is_stale"])

    def test_undated_rows_never_become_fresh_evidence(self) -> None:
        conn = make_db()
        try:
            # 'all' không có biên dưới -> row undated vẫn được LIỆT KÊ...
            add_article(conn, 1, title="Undated", published_at=None)
            add_event(conn, 1, event_type="NEW_MODEL", detected_at=None)
            commit(conn)
            result = daily_radar(conn, window="all", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        # ...nhưng KHÔNG BAO GIỜ là bằng chứng freshness: không mốc hợp lệ -> SIGNAL_WEAK.
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(len(result["change_events"]), 1)
        self.assertIsNone(result["newest_evidence_at"])
        self.assertEqual(result["status"], "SIGNAL_WEAK")

    def test_unparseable_timestamp_string_is_never_fresh(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Broken stamp", published_at="whenever")
            commit(conn)
            result = daily_radar(conn, window="all", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertIsNone(result["newest_evidence_at"])
        self.assertEqual(result["status"], "SIGNAL_WEAK")

    def test_dated_evidence_outranks_undated_scan(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Dated", published_at="2026-10-24T20:00:00+00:00")
            add_event(conn, 1, event_type="NEW_MODEL", detected_at=None)
            commit(conn)
            result = daily_radar(conn, window="all", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertEqual(result["status"], "CURRENT")
        self.assertEqual(result["newest_evidence_at"], "2026-10-24T20:00:00+00:00")

    def test_bounded_items_and_generated_at_present(self) -> None:
        conn = make_db()
        try:
            for index in range(1, MAX_ITEMS + 3):
                add_article(
                    conn, index, title=f"A{index}",
                    published_at=f"2026-10-2{index % 4}T08:00:00+00:00",
                )
            commit(conn)
            result = daily_radar(conn, window="7d", now=self.NOW, tz=VN_TZ)
        finally:
            conn.close()
        self.assertLessEqual(len(result["articles"]), MAX_ITEMS)
        self.assertIn("generated_at", result)
        self.assertTrue(result["truncated"])
        self.assertIsNotNone(parse_timestamp(result["generated_at"]))


class ScheduleMarkerTests(unittest.TestCase):
    """RadarSchedule: mốc 07:00 Asia/Ho_Chi_Minh, trong bộ nhớ, hoãn sang request."""

    def test_defaults_match_contract(self) -> None:
        schedule = RadarSchedule()
        self.assertEqual(schedule.refresh_hour_local, 7)
        self.assertEqual(schedule.refresh_minute_local, 0)
        self.assertEqual(schedule.timezone_name, "Asia/Ho_Chi_Minh")
        self.assertEqual(schedule.execution_mode, "deferred-to-request")
        self.assertIsNone(schedule.last_marker_at)

    def test_snapshot_exposes_deferred_state_and_next_local_run(self) -> None:
        snapshot = RadarSchedule().snapshot("2026-10-25T08:00:00+07:00")
        self.assertEqual(snapshot["refresh_local_time"], "07:00")
        self.assertEqual(snapshot["timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(snapshot["execution_mode"], "deferred-to-request")
        self.assertTrue(snapshot["deferred_to_request"])
        self.assertTrue(snapshot["due"])
        self.assertEqual(snapshot["next_local_run"], "2026-10-26T07:00:00+07:00")

    def test_due_and_mark_cycle(self) -> None:
        schedule = RadarSchedule()
        # Trước 07:00 -> chưa đến giờ.
        self.assertFalse(schedule.is_due("2026-10-25T06:59:00+07:00"))
        # Sau 07:00, chưa có mốc -> đến giờ.
        self.assertTrue(schedule.is_due("2026-10-25T07:01:00+07:00"))
        # Đóng dấu mốc: hôm nay không còn đến giờ...
        schedule.mark("2026-10-25T07:30:00+07:00")
        self.assertFalse(schedule.is_due("2026-10-25T08:00:00+07:00"))
        self.assertIsNotNone(schedule.last_marker_at)
        # ...nhưng ngày mai sau 07:00 lại đến giờ.
        self.assertTrue(schedule.is_due("2026-10-26T07:01:00+07:00"))

    def test_no_background_thread_implied(self) -> None:
        # Dataclass thuần: không field nào là thread/timer/sleep.
        schedule = RadarSchedule()
        fields = {f for f, _ in schedule.__dataclass_fields__.items()}  # type: ignore[attr-defined]
        self.assertTrue(
            fields <= {"refresh_hour_local", "refresh_minute_local", "timezone_name",
                       "execution_mode", "last_marker_at"}
        )


class RadarRoutesTests(unittest.TestCase):
    """GET /api/radar public chỉ-đọc; POST refresh gọi require_admin TRƯỚC khi mở DB."""

    def setUp(self) -> None:
        # Mốc bài PUBLISHED tươi tính theo giờ chạy test — không hardcode ngày.
        self.UPDATE_ARTICLE = fresh_today_vn_timestamp()

    def test_admin_refresh_requires_auth_before_opening_db(self) -> None:
        guard = Mock(side_effect=AssertionError("db opened"))
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: fresh_token()}):
            with patch.object(app_main, "get_connection", guard):
                with self.assertRaises(HTTPException) as no_token:
                    app_main.admin_radar_refresh(make_request())
        self.assertEqual(no_token.exception.status_code, 401)
        guard.assert_not_called()

    def test_admin_refresh_wrong_token_is_403_before_db(self) -> None:
        guard = Mock(side_effect=AssertionError("db opened"))
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: fresh_token()}):
            with patch.object(app_main, "get_connection", guard):
                with self.assertRaises(HTTPException) as bad:
                    app_main.admin_radar_refresh(make_request(token=fresh_token()))
        self.assertEqual(bad.exception.status_code, 403)
        guard.assert_not_called()

    def test_admin_refresh_invalid_window_is_422_before_db(self) -> None:
        token = fresh_token()
        guard = Mock(side_effect=AssertionError("db opened"))
        with patch.dict(os.environ, {ADMIN_TOKEN_ENV: token}):
            with patch.object(app_main, "get_connection", guard):
                with self.assertRaises(HTTPException) as bad_window:
                    app_main.admin_radar_refresh(
                        make_request(token=token), window="bogus"
                    )
        self.assertEqual(bad_window.exception.status_code, 422)
        guard.assert_not_called()

    def test_admin_refresh_with_valid_token_recomputes_locally_and_marks(self) -> None:
        token = fresh_token()
        conn = make_db()
        try:
            add_article(conn, 1, title="Fresh", published_at=self.UPDATE_ARTICLE)
            commit(conn)
            with patch.dict(os.environ, {ADMIN_TOKEN_ENV: token}):
                with patch.object(app_main, "get_connection", return_value=conn):
                    response = app_main.admin_radar_refresh(
                        make_request(token=token), window="today"
                    )
        finally:
            conn.close()

        self.assertEqual(response["status"], "REFRESHED")
        self.assertTrue(response["deferred_to_request"])
        self.assertEqual(response["window"], "today")
        self.assertEqual(response["radar"]["status"], "CURRENT")
        schedule = response["schedule"]
        self.assertEqual(schedule["execution_mode"], "deferred-to-request")
        self.assertTrue(schedule["deferred_to_request"])
        self.assertIsNotNone(schedule["last_marker_at"])

    def test_public_radar_returns_schedule_with_current_default_window(self) -> None:
        conn = make_db()
        try:
            add_article(conn, 1, title="Fresh", published_at=self.UPDATE_ARTICLE)
            commit(conn)
            with patch.object(app_main, "get_connection", return_value=conn):
                response = app_main.public_radar(make_request(query="window=today"))
        finally:
            conn.close()

        self.assertEqual(response["window"], "today")
        self.assertEqual(response["status"], "CURRENT")
        self.assertEqual(response["schedule"]["execution_mode"], "deferred-to-request")
        self.assertEqual(response["schedule"]["timezone"], RADAR_TIMEZONE_NAME)


if __name__ == "__main__":
    unittest.main()
