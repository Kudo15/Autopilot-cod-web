"""TDD — process-safe Daily Radar scheduler ledger (s1-process-safe-scheduler).

Hợp đồng:
- Ledger bền (SQLite) với run identity DUY NHẤT cho mỗi mốc 07:00
  Asia/Ho_Chi_Minh theo lịch địa phương ('YYYY-MM-DD') — sống qua restart.
- Hai kết nối/quá trình đua nhau claim: TỐI ĐA MỘT owner (lease đang hiệu lực)
  được chạy cho cùng một identity.
- Lease hữu hạn: lease hết hạn có thể bị reclaim; số lần thử có chặn
  (max_attempts) -> EXHAUSTED, không reclaim nữa.
- Identity đã COMPLETED không bao giờ chạy lại sau restart.
- Đồng hồ giả (datetime truyền vào) — không sleep, không thread nền, không mạng.
- Scheduler chỉ TÍNH LẠI CỤC BỘ (daily_radar): không publish, không verify,
  không sửa DRAFT/SAMPLE, không gọi bộ thu thập ngoài.
- Manual refresh (POST /api/admin/radar/refresh): require_admin TRƯỚC khi mở DB,
  sau đó ghi dấu durable (additive) cho identity hôm nay.

Tất cả test chạy trên SQLite tạm — không đụng backend/data/radar.db.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import HTTPException

from backend.app import database, migrate
from backend.app import main as app_main
from backend.app.migrate import apply_migration
from backend.app.radar import scheduler
from backend.app.radar.daily import RADAR_TIMEZONE_NAME
from backend.tests.test_radar_daily import (
    commit,
    fresh_token,
    make_db,
    make_request,
)

#: Múi giờ cố định UTC+7 (Việt Nam không DST) — test tất định, không cần tzdata.
VN = timezone(timedelta(hours=7))

#: Đồng hồ giả quanh mốc 07:00 2026-10-25 (giờ VN).
IDENTITY = "2026-10-25"
BEFORE_DUE = datetime(2026, 10, 25, 6, 59, 59, tzinfo=VN)
EXACT_DUE = datetime(2026, 10, 25, 7, 0, 0, tzinfo=VN)
DUE = datetime(2026, 10, 25, 7, 30, 0, tzinfo=VN)
LEASE_SECONDS = 300
AFTER_LEASE = DUE + timedelta(seconds=LEASE_SECONDS + 1)


class TempDbTests(unittest.TestCase):
    """Fixture: DB tạm + monkeypatch DB_PATH — không đụng radar.db thật."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_db_path = self.temp_data_dir / "radar.db"
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(migrate, "DB_PATH", self.temp_db_path))

    def _connect(self) -> sqlite3.Connection:
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.temp_db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        self.addCleanup(conn.close)
        return conn

    def _run_row(self, conn: sqlite3.Connection, identity: str = IDENTITY):
        return conn.execute(
            "SELECT * FROM radar_schedule_runs WHERE run_identity = ?", (identity,)
        ).fetchone()


class LedgerSchemaTests(TempDbTests):
    """Migration additive tạo radar_schedule_runs idempotent."""

    def test_migration_creates_run_ledger_with_contract_columns(self) -> None:
        apply_migration()
        conn = self._connect()
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertIn("radar_schedule_runs", tables)
        actual = [
            (row[1], row[2].upper(), row[3], row[5])
            for row in conn.execute("PRAGMA table_info(radar_schedule_runs)")
        ]
        expected = [
            ("run_identity", "TEXT", 0, 1),
            ("status", "TEXT", 1, 0),
            ("owner", "TEXT", 0, 0),
            ("attempts", "INTEGER", 1, 0),
            ("claimed_at", "TEXT", 0, 0),
            ("lease_expires_at", "TEXT", 0, 0),
            ("completed_at", "TEXT", 0, 0),
            ("last_error", "TEXT", 0, 0),
            ("summary", "TEXT", 0, 0),
            ("data_origin", "TEXT", 1, 0),
        ]
        self.assertEqual(actual, expected)

    def test_status_check_rejects_bogus_value(self) -> None:
        apply_migration()
        conn = self._connect()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO radar_schedule_runs (run_identity, status, attempts)"
                " VALUES (?, 'BOGUS', 1)",
                (IDENTITY,),
            )

    def test_migration_is_idempotent_and_preserves_rows(self) -> None:
        apply_migration()
        conn = self._connect()
        scheduler.ensure_ledger(conn)
        scheduler.claim_run(conn, IDENTITY, "owner-a", DUE,
                            lease_seconds=LEASE_SECONDS, max_attempts=3)
        apply_migration()  # chạy lần hai — additive, không đụng dữ liệu
        row = self._run_row(conn)
        self.assertIsNotNone(row)
        self.assertEqual(row["owner"], "owner-a")
        self.assertEqual(row["attempts"], 1)


class ClaimRaceTests(TempDbTests):
    """Hai kết nối đua claim cùng identity: tối đa một owner."""

    def setUp(self) -> None:
        super().setUp()
        apply_migration()
        self.conn1 = self._connect()
        self.conn2 = self._connect()
        scheduler.ensure_ledger(self.conn1)

    def test_first_claim_creates_running_owner(self) -> None:
        result = scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(result["claimed"])
        self.assertEqual(result["reason"], "new")
        row = self._run_row(self.conn1)
        self.assertEqual(row["status"], "RUNNING")
        self.assertEqual(row["owner"], "owner-a")
        self.assertEqual(row["attempts"], 1)
        self.assertIsNotNone(row["claimed_at"])
        self.assertIsNotNone(row["lease_expires_at"])
        self.assertIsNone(row["completed_at"])

    def test_second_connection_denied_while_lease_active(self) -> None:
        scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        result = scheduler.claim_run(
            self.conn2, IDENTITY, "owner-b", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"], "active_lease")
        row = self._run_row(self.conn2)
        self.assertEqual(row["owner"], "owner-a")  # ownership không đổi
        self.assertEqual(row["attempts"], 1)

    def test_expired_lease_is_reclaimed_after_finite_timeout(self) -> None:
        scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        # Chưa hết hạn: conn2 bị từ chối.
        denied = scheduler.claim_run(
            self.conn2, IDENTITY, "owner-b", DUE + timedelta(seconds=LEASE_SECONDS - 1),
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertFalse(denied["claimed"])
        self.assertEqual(denied["reason"], "active_lease")
        # Hết hạn: conn2 reclaim, attempts tăng, lease mới.
        reclaimed = scheduler.claim_run(
            self.conn2, IDENTITY, "owner-b", AFTER_LEASE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(reclaimed["claimed"])
        self.assertEqual(reclaimed["reason"], "reclaimed")
        row = self._run_row(self.conn2)
        self.assertEqual(row["owner"], "owner-b")
        self.assertEqual(row["attempts"], 2)
        self.assertEqual(row["status"], "RUNNING")

    def test_failed_run_is_reclaimable_within_bound(self) -> None:
        claimed = scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(claimed["claimed"])
        failure = scheduler.fail_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            error="local recompute blew up", max_attempts=3,
        )
        self.assertTrue(failure["failed"])
        self.assertEqual(failure["status"], "FAILED")
        row = self._run_row(self.conn1)
        self.assertEqual(row["status"], "FAILED")
        self.assertIn("local recompute", row["last_error"])
        # Chưa chạm trần: reclaim được.
        reclaimed = scheduler.claim_run(
            self.conn2, IDENTITY, "owner-b", DUE + timedelta(minutes=1),
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(reclaimed["claimed"])
        self.assertEqual(self._run_row(self.conn2)["attempts"], 2)

    def test_bounded_retries_reach_exhausted_and_stop(self) -> None:
        # max_attempts=2: attempt 1 fail, attempt 2 fail -> EXHAUSTED.
        claimed = scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=2,
        )
        self.assertTrue(claimed["claimed"])
        scheduler.fail_run(self.conn1, IDENTITY, "owner-a", DUE, error="boom", max_attempts=2)
        claimed2 = scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE + timedelta(minutes=5),
            lease_seconds=LEASE_SECONDS, max_attempts=2,
        )
        self.assertTrue(claimed2["claimed"])
        self.assertEqual(self._run_row(self.conn1)["attempts"], 2)
        scheduler.fail_run(self.conn1, IDENTITY, "owner-a", DUE, error="boom again", max_attempts=2)
        row = self._run_row(self.conn1)
        self.assertEqual(row["status"], "EXHAUSTED")
        # Từ đây không bao giờ reclaim được nữa (kể cả từ kết nối khác).
        denied = scheduler.claim_run(
            self.conn2, IDENTITY, "owner-b", DUE + timedelta(hours=2),
            lease_seconds=LEASE_SECONDS, max_attempts=2,
        )
        self.assertFalse(denied["claimed"])
        self.assertEqual(denied["reason"], "attempts_exhausted")

    def test_wrong_owner_cannot_complete(self) -> None:
        scheduler.claim_run(
            self.conn1, IDENTITY, "owner-a", DUE,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        result = scheduler.complete_run(
            self.conn2, IDENTITY, "owner-b", DUE + timedelta(minutes=1), summary="sneaky"
        )
        self.assertFalse(result["completed"])
        row = self._run_row(self.conn1)
        self.assertEqual(row["status"], "RUNNING")
        self.assertIsNone(row["completed_at"])


class CompletedIdempotenceTests(TempDbTests):
    """Identity COMPLETED không chạy lại — kể cả sau 'restart' (kết nối mới)."""

    def test_completed_identity_never_runs_again_after_restart(self) -> None:
        apply_migration()
        conn1 = self._connect()
        scheduler.ensure_ledger(conn1)
        result = scheduler.run_daily_radar_once(
            conn1, owner="worker-1", now=DUE, window="today", tz=VN,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(result["ran"])
        self.assertEqual(result["reason"], "completed")
        row_before = self._run_row(conn1)
        self.assertEqual(row_before["status"], "COMPLETED")
        conn1.close()  # 'restart': đóng hết kết nối

        conn2 = self._connect()  # tiến trình mới
        denied = scheduler.claim_run(
            conn2, IDENTITY, "worker-2", DUE + timedelta(hours=1),
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertFalse(denied["claimed"])
        self.assertEqual(denied["reason"], "already_completed")
        again = scheduler.run_daily_radar_once(
            conn2, owner="worker-2", now=DUE + timedelta(hours=1),
            window="today", tz=VN, lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertFalse(again["ran"])
        self.assertEqual(again["reason"], "already_completed")
        row_after = self._run_row(conn2)
        self.assertEqual(row_after["completed_at"], row_before["completed_at"])
        self.assertEqual(row_after["owner"], row_before["owner"])
        self.assertEqual(row_after["attempts"], row_before["attempts"])

    def test_complete_missing_or_completed_identity_is_noop(self) -> None:
        apply_migration()
        conn = self._connect()
        scheduler.ensure_ledger(conn)
        missing = scheduler.complete_run(conn, "1999-01-01", "owner-a", DUE)
        self.assertFalse(missing["completed"])
        scheduler.claim_run(conn, IDENTITY, "owner-a", DUE,
                            lease_seconds=LEASE_SECONDS, max_attempts=3)
        scheduler.complete_run(conn, IDENTITY, "owner-a", DUE)
        again = scheduler.complete_run(conn, IDENTITY, "owner-a", DUE)
        self.assertFalse(again["completed"])
        self.assertEqual(self._run_row(conn)["status"], "COMPLETED")


class FakeClockBoundaryTests(TempDbTests):
    """Ranh giới 07:00 Asia/Ho_Chi_Minh theo lịch ĐỊA PHƯƠNG, đồng hồ giả."""

    def _seeded_conn(self) -> sqlite3.Connection:
        conn = self._connect()
        apply_migration()
        scheduler.ensure_ledger(conn)
        return conn

    def test_not_due_one_second_before_local_seven(self) -> None:
        conn = self._seeded_conn()
        result = scheduler.run_daily_radar_once(
            conn, owner="w", now=BEFORE_DUE, window="today", tz=VN,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertFalse(result["ran"])
        self.assertEqual(result["reason"], "not_due")
        self.assertEqual(result["run_identity"], IDENTITY)
        self.assertIsNone(self._run_row(conn))  # không tạo dòng ledger

    def test_due_at_exactly_local_seven(self) -> None:
        conn = self._seeded_conn()
        result = scheduler.run_daily_radar_once(
            conn, owner="w", now=EXACT_DUE, window="today", tz=VN,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(result["ran"])
        self.assertEqual(result["reason"], "completed")
        row = self._run_row(conn)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["owner"], "w")

    def test_identity_uses_local_calendar_not_utc(self) -> None:
        # 2026-10-25T03:00+07:00 == 2026-10-24T20:00Z — ngày UTC lệch ngày VN.
        moment = datetime(2026, 10, 25, 3, 0, 0, tzinfo=VN)
        self.assertEqual(scheduler.run_identity_for(moment, tz=VN), "2026-10-25")
        # Và đúng UTC+7: 2026-10-24T18:00Z là 01:00 VN của ngày 25.
        utc_moment = datetime(2026, 10, 24, 18, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(scheduler.run_identity_for(utc_moment, tz=VN), "2026-10-25")

    def test_claimed_run_recomputes_local_radar_only(self) -> None:
        conn = self._seeded_conn()
        conn.execute(
            "INSERT INTO articles (id, title, url, source, category, published_at,"
            " data_origin, article_status) VALUES (1, 'Fresh local', NULL, 'editorial',"
            " 'tip-trick', ?, 'REAL', 'PUBLISHED')",
            ("2026-10-25T07:15:00+07:00",),
        )
        conn.commit()
        result = scheduler.run_daily_radar_once(
            conn, owner="w", now=DUE, window="today", tz=VN,
            lease_seconds=LEASE_SECONDS, max_attempts=3,
        )
        self.assertTrue(result["ran"])
        radar = result["radar"]
        self.assertEqual(radar["counts"]["articles"], 1)
        self.assertEqual(radar["status"], "CURRENT")
        self.assertEqual(radar["window"], "today")
        self.assertEqual(self._run_row(conn)["summary"], "window=today;status=CURRENT")


class NoPublishSafetyTests(TempDbTests):
    """Scheduler chỉ đọc + tính lại cục bộ: không publish/verify, không sửa
    DRAFT/SAMPLE, không mở socket (không gọi bộ thu thập ngoài)."""

    TABLES = ("articles", "change_events", "editorial_reviews",
              "verification_records", "collection_runs")

    def _seed(self, conn: sqlite3.Connection) -> None:
        conn.executemany(
            "INSERT INTO articles (id, title, url, source, category, published_at,"
            " data_origin, article_status)"
            " VALUES (?, ?, NULL, 'editorial', 'tip-trick', ?, ?, ?)",
            [
                (1, "Draft stays draft", None, "REAL", "DRAFT"),
                (2, "Pending stays pending", None, "REAL", "PENDING_REVIEW"),
                (3, "Published stays as-is", None, "REAL", "PUBLISHED"),
                (4, "Sample untouched", None, "SAMPLE", "PUBLISHED"),
            ],
        )
        conn.execute(
            "INSERT INTO change_events (id, event_type, detected_at, data_origin)"
            " VALUES (1, 'NEW_MODEL', '2026-10-25T06:00:00+07:00', 'REAL')"
        )
        conn.commit()

    def _snapshot(self, conn: sqlite3.Connection) -> dict[str, list[dict]]:
        return {
            table: [dict(row) for row in conn.execute(
                f"SELECT * FROM {table} ORDER BY 1").fetchall()]
            for table in self.TABLES
        }

    def test_scheduler_never_mutates_public_data_or_touches_network(self) -> None:
        conn = self._connect()
        apply_migration()
        self._seed(conn)
        before = self._snapshot(conn)
        with patch("socket.socket", side_effect=AssertionError("network used")):
            result = scheduler.run_daily_radar_once(
                conn, owner="w", now=DUE, window="today", tz=VN,
                lease_seconds=LEASE_SECONDS, max_attempts=3,
            )
        self.assertTrue(result["ran"])
        after = self._snapshot(conn)
        self.assertEqual(before, after)  # mọi bảng dữ liệu NGUYÊN VẸN
        # Bài DRAFT vẫn DRAFT, published_at vẫn NULL.
        row = conn.execute(
            "SELECT article_status, published_at FROM articles WHERE id = 1"
        ).fetchone()
        self.assertEqual(row["article_status"], "DRAFT")
        self.assertIsNone(row["published_at"])


class ManualRefreshDurableTests(TempDbTests):
    """POST /api/admin/radar/refresh: auth trước DB; durable mark additive."""

    def test_refresh_401_without_token_before_db(self) -> None:
        guard = Mock(side_effect=AssertionError("db opened"))
        with patch.dict("os.environ", {"ADMIN_TOKEN": fresh_token()}):
            with patch.object(app_main, "get_connection", guard):
                with self.assertRaises(HTTPException) as ctx:
                    app_main.admin_radar_refresh(make_request())
        self.assertEqual(ctx.exception.status_code, 401)
        guard.assert_not_called()

    def test_refresh_records_durable_completed_run_when_due(self) -> None:
        token = fresh_token()
        conn = self._connect()
        apply_migration()
        conn.execute(
            "INSERT INTO articles (id, title, url, source, category, published_at,"
            " data_origin, article_status)"
            " VALUES (1, 'Fresh', NULL, 'editorial', 'tip-trick', ?,'REAL','PUBLISHED')",
            (datetime.now(timezone.utc).astimezone(VN).isoformat(),),
        )
        conn.commit()
        connection = Mock(wraps=conn)
        connection.close = Mock()
        with patch.dict("os.environ", {"ADMIN_TOKEN": token}):
            with patch.object(app_main, "get_connection", return_value=connection):
                response = app_main.admin_radar_refresh(
                    make_request(token=token), window="today"
                )
        # Hợp đồng cũ giữ nguyên.
        self.assertEqual(response["status"], "REFRESHED")
        self.assertTrue(response["deferred_to_request"])
        self.assertIsNotNone(response["refreshed_at"])
        self.assertIsNotNone(response["schedule"]["last_marker_at"])
        # Durable mark additive.
        self.assertIn("ledger", response)
        ledger = response["ledger"]
        now_vn = datetime.now(timezone.utc).astimezone(VN)
        identity = now_vn.date().isoformat()
        self.assertEqual(ledger["run_identity"], identity)
        if now_vn.hour * 60 >= 7 * 60:  # sau 07:00 VN: identity hôm nay đã đóng
            self.assertTrue(ledger["due"])
            row = self._run_row(conn, identity)
            self.assertIsNotNone(row)
            self.assertIn(row["status"], ("COMPLETED", "RUNNING"))
            if row["status"] == "COMPLETED":
                self.assertEqual(ledger["reason"], "completed")
        else:  # trước 07:00 VN: không đóng dấu hôm nay
            self.assertFalse(ledger["due"])
            self.assertEqual(ledger["reason"], "not_due")
            self.assertIsNone(self._run_row(conn, identity))

    def test_public_radar_schedule_exposes_durable_state(self) -> None:
        conn = self._connect()
        apply_migration()
        with patch.object(app_main, "get_connection", return_value=conn):
            response = app_main.public_radar(make_request(query="window=today"))
        schedule = response["schedule"]
        self.assertEqual(schedule["execution_mode"], "deferred-to-request")
        self.assertEqual(schedule["timezone"], RADAR_TIMEZONE_NAME)
        durable = schedule["durable"]
        self.assertIn("run_identity", durable)
        self.assertIn("status", durable)
        self.assertIn("due", durable)
        self.assertIn("next_local_run", durable)


if __name__ == "__main__":
    unittest.main()
