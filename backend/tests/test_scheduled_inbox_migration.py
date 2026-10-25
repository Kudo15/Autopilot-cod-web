"""TDD cho migration bảng scheduled_inbox_runs (sri-001b).

Hợp đồng: ledger một dòng mỗi lần chạy inbox theo lịch — status
IMPORTED|QUARANTINED, ba bộ đếm không âm default 0, data_origin
REAL|SAMPLE default 'REAL', index trên processed_at và status.
Toàn bộ test chạy trên SQLite tạm (monkeypatch DB_PATH) — không đụng
backend/data/radar.db.
"""
from __future__ import annotations

import sqlite3
import tempfile
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.app import database, migrate
from backend.app.migrate import BUSINESS_TABLES, apply_migration

TABLE = "scheduled_inbox_runs"

#: (tên, kiểu khai báo, NOT NULL flag, PRIMARY KEY flag) theo đúng hợp đồng sri-001b.
#: run_id TEXT PRIMARY KEY khai báo không kèm NOT NULL => table_info trả (notnull=0, pk=1).
EXPECTED_COLUMNS = (
    ("run_id", "TEXT", 0, 1),
    ("report_kind", "TEXT", 1, 0),
    ("content_hash", "TEXT", 1, 0),
    ("observed_at", "TEXT", 1, 0),
    ("status", "TEXT", 1, 0),
    ("finding_count", "INTEGER", 1, 0),
    ("accepted_count", "INTEGER", 1, 0),
    ("skipped_count", "INTEGER", 1, 0),
    ("error_message", "TEXT", 0, 0),
    ("processed_at", "TEXT", 1, 0),
    ("data_origin", "TEXT", 1, 0),
)


class ScheduledInboxMigrationTests(unittest.TestCase):
    """migration tạo scheduled_inbox_runs idempotent trên DB tạm."""

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
        conn = sqlite3.connect(str(self.temp_db_path))
        self.addCleanup(conn.close)
        return conn

    def test_fresh_db_has_scheduled_inbox_runs_with_exact_columns(self) -> None:
        """DB mới sau apply_migration() có scheduled_inbox_runs đúng 11 cột hợp đồng."""
        apply_migration()
        conn = self._connect()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertIn(TABLE, tables)

        actual = [
            (row[1], row[2], row[3], row[5])
            for row in conn.execute(f"PRAGMA table_info({TABLE})")
        ]
        self.assertEqual(actual, list(EXPECTED_COLUMNS))

    def _insert(self, conn: sqlite3.Connection, **overrides: object) -> None:
        """Chèn một dòng ledger hợp lệ; overrides ghi đè từng trường."""
        values: dict[str, object] = {
            "run_id": "run-001",
            "report_kind": "provider_harness_radar",
            "content_hash": "a" * 64,
            "observed_at": "2026-10-25T09:00:00+07:00",
            "status": "IMPORTED",
            "processed_at": "2026-10-25T09:00:05+07:00",
        }
        values.update(overrides)
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(f"INSERT INTO {TABLE} ({columns}) VALUES ({marks})", tuple(values.values()))
        conn.commit()

    def test_migration_twice_succeeds_and_preserves_rows(self) -> None:
        """Chạy migration hai lần thành công; dòng ledger chèn trước vẫn còn."""
        apply_migration()
        conn = self._connect()
        self._insert(conn, run_id="run-keep")
        conn.close()

        apply_migration()

        conn2 = self._connect()
        self.assertEqual(
            conn2.execute(f"SELECT run_id, status FROM {TABLE} ORDER BY run_id").fetchall(),
            [("run-keep", "IMPORTED")],
        )

    def test_valid_row_roundtrip_and_defaults(self) -> None:
        """Dòng hợp lệ đọc lại đúng; bộ đếm default 0, data_origin default 'REAL'."""
        apply_migration()
        conn = self._connect()
        self._insert(conn)

        row = conn.execute(
            f"""SELECT run_id, report_kind, content_hash, observed_at, status,
                       finding_count, accepted_count, skipped_count, error_message,
                       processed_at, data_origin
                FROM {TABLE}"""
        ).fetchone()
        self.assertEqual(
            row,
            (
                "run-001",
                "provider_harness_radar",
                "a" * 64,
                "2026-10-25T09:00:00+07:00",
                "IMPORTED",
                0,
                0,
                0,
                None,
                "2026-10-25T09:00:05+07:00",
                "REAL",
            ),
        )

    def test_status_restricted_to_imported_or_quarantined(self) -> None:
        apply_migration()
        conn = self._connect()
        self._insert(conn, run_id="run-q", status="QUARANTINED")
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert(conn, run_id="run-bad-status", status="PENDING")

    def test_negative_counts_rejected(self) -> None:
        apply_migration()
        conn = self._connect()
        for column in ("finding_count", "accepted_count", "skipped_count"):
            with self.subTest(column=column):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert(conn, run_id=f"run-neg-{column}", **{column: -1})

    def test_data_origin_restricted_to_real_or_sample(self) -> None:
        apply_migration()
        conn = self._connect()
        self._insert(conn, run_id="run-sample", data_origin="SAMPLE")
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert(conn, run_id="run-bad-origin", data_origin="SUSPECT")

    def test_run_id_is_primary_key(self) -> None:
        apply_migration()
        conn = self._connect()
        self._insert(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert(conn)

    def test_required_columns_reject_null(self) -> None:
        # Lưu ý: run_id là TEXT PRIMARY KEY — SQLite cho phép NULL ở PK TEXT
        # (chỉ INTEGER PRIMARY KEY ép rowid), nên chỉ kiểm tra các cột NOT NULL
        # còn lại đúng theo hợp đồng.
        apply_migration()
        conn = self._connect()
        for column in ("report_kind", "content_hash", "observed_at", "status", "processed_at"):
            overrides: dict[str, object] = {"run_id": f"run-null-{column}"}
            overrides[column] = None
            with self.subTest(column=column):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert(conn, **overrides)

    def test_indexes_on_processed_at_and_status(self) -> None:
        apply_migration()
        conn = self._connect()
        indexed: dict[str, tuple] = {}
        for row in conn.execute(f"PRAGMA index_list({TABLE})"):
            indexed[row[1]] = tuple(r[2] for r in conn.execute(f"PRAGMA index_info({row[1]})"))
        self.assertIn(("processed_at",), indexed.values())
        self.assertIn(("status",), indexed.values())

    def test_preexisting_business_tables_still_present(self) -> None:
        """Đủ 12 bảng nghiệp vụ có sẵn sau migration (không thay đổi/hủy bỏ)."""
        apply_migration()
        apply_migration()
        conn = self._connect()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in BUSINESS_TABLES:
            with self.subTest(table=table):
                self.assertIn(table, tables)


if __name__ == "__main__":
    unittest.main()
