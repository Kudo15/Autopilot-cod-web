"""TDD cho Repository Explorer (task r2).

Hợp đồng:
- migrate tạo bảng repositories (additive, idempotent) trên DB tạm — không
  đụng backend/data/radar.db, không seed row nào (kể cả SAMPLE).
- GET /api/repositories: parameterized SQL, query params allowlist
  (q/difficulty/license/verification_status/limit), bounded limit;
  public default LOẠI row SAMPLE + URL không phải https://github.com +
  không VERIFIED + provenance rỗng + license rỗng; response chỉ trả đúng
  cột allowlist (không provenance, không data_origin).
- Không có cuộc gọi mạng tới GitHub: mọi test chỉ chạm DB tạm.
"""
from __future__ import annotations

import sqlite3
import socket
import tempfile
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request

from backend.app import database, main, migrate


def catalog_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE repositories (
        id INTEGER PRIMARY KEY, canonical_url TEXT, name TEXT, purpose TEXT,
        use_case TEXT, tradeoffs TEXT, license TEXT, updated_at TEXT,
        difficulty TEXT, provenance TEXT, verification_status TEXT, data_origin TEXT
    )""")
    conn.executemany("INSERT INTO repositories VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        (1, "https://github.com/example/real", "Real Repo", "purpose", "use", "tradeoff", "MIT", "2026-10-27", "BEGINNER", "official", "VERIFIED", "REAL"),
        (2, "https://github.com/example/sample", "Sample Repo", "", "", "", "MIT", "", "UNKNOWN", "sample", "VERIFIED", "SAMPLE"),
        (3, "javascript:bad", "Bad URL", "", "", "", "MIT", "", "BEGINNER", "unknown", "VERIFIED", "REAL"),
        (4, "https://github.com/example/unverified", "Unverified", "", "", "", "MIT", "", "BEGINNER", "source", "UNVERIFIED", "REAL"),
        (5, "https://github.com.example.com/lookalike", "Lookalike", "", "", "", "MIT", "", "BEGINNER", "checked", "VERIFIED", "REAL"),
        (6, "https://github.com/example/noprovenance", "No Provenance", "", "", "", "MIT", "", "BEGINNER", "   ", "VERIFIED", "REAL"),
        (7, "https://github.com/example/nolicense", "No License", "", "", "", "", "", "BEGINNER", "checked", "VERIFIED", "REAL"),
        (8, "https://github.com/example/sample-unverified", "Sample Unverified", "", "", "", "MIT", "", "UNKNOWN", "sample", "UNVERIFIED", "SAMPLE"),
    ])
    conn.commit()
    return conn


def _request(query: str = "") -> Request:
    return Request({
        "type": "http", "http_version": "1.1", "method": "GET",
        "path": "/api/repositories", "raw_path": b"/api/repositories",
        "query_string": query.encode(), "root_path": "", "headers": [],
        "scheme": "http", "server": ("testserver", 80), "client": ("127.0.0.1", 1),
    })


class RepositoryExplorerTests(unittest.TestCase):
    def test_default_public_catalogue_is_verified_real_and_allowlisted(self) -> None:
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            rows = main.list_repositories()
        self.assertEqual([row["id"] for row in rows], [1])
        self.assertNotIn("provenance", rows[0])
        self.assertNotIn("data_origin", rows[0])

    def test_limit_and_unknown_query_boundaries(self) -> None:
        with self.assertRaises(HTTPException) as too_large:
            main.list_repositories(limit="101")
        self.assertEqual(too_large.exception.status_code, 422)
        request = type("R", (), {"query_params": type("Q", (), {"multi_items": lambda self: [("oops", "1")]})()})()
        with self.assertRaises(HTTPException) as unknown:
            main.public_repositories(request)
        self.assertEqual(unknown.exception.status_code, 422)

    def test_status_filter_can_show_history_but_never_sample(self) -> None:
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            rows = main.list_repositories(verification_status="UNVERIFIED")
        self.assertEqual([row["name"] for row in rows], ["Unverified"])

    def test_response_is_exactly_the_public_field_allowlist(self) -> None:
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            rows = main.list_repositories()
        self.assertEqual(set(rows[0]), set(main.PUBLIC_REPOSITORY_FIELDS))
        for forbidden in ("provenance", "data_origin", "created_at"):
            self.assertNotIn(forbidden, rows[0])

    def test_q_filter_is_bound_parameter_not_sql(self) -> None:
        """q chứa injection nguyên si vẫn chỉ là bind parameter; bảng nguyên vẹn."""
        with patch.object(main, "get_connection", return_value=catalog_db()):
            self.assertEqual(main.list_repositories(q="'; DROP TABLE repositories; --"), [])
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            rows = main.list_repositories(q="Real")
        self.assertEqual([row["id"] for row in rows], [1])

    def test_difficulty_and_license_filters(self) -> None:
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            by_difficulty = main.list_repositories(difficulty="BEGINNER")
        self.assertEqual([row["id"] for row in by_difficulty], [1])
        with patch.object(main, "get_connection", return_value=catalog_db()):
            with self.assertRaises(HTTPException) as ctx:
                main.list_repositories(difficulty="HARD")
        self.assertEqual(ctx.exception.status_code, 422)
        with patch.object(main, "get_connection", return_value=catalog_db()):
            with self.assertRaises(HTTPException) as ctx:
                main.list_repositories(license="   ")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_invalid_values_rejected(self) -> None:
        for kwargs in (
            {"verification_status": "CERTIFIED"},
            {"limit": "0"},
            {"limit": "abc"},
            {"q": "x" * 201},
        ):
            with self.assertRaises(HTTPException) as ctx:
                main.list_repositories(**kwargs)
            self.assertEqual(ctx.exception.status_code, 422)

    def test_endpoint_allows_only_allowlisted_params(self) -> None:
        conn = catalog_db()
        with patch.object(main, "get_connection", return_value=conn):
            rows = main.public_repositories(_request("q=Real&difficulty=BEGINNER&license=MIT&limit=10"))
        self.assertEqual([row["id"] for row in rows], [1])
        with patch.object(main, "get_connection", return_value=catalog_db()):
            with self.assertRaises(HTTPException) as ctx:
                main.public_repositories(_request("order_by=provenance"))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_no_network_calls_made(self) -> None:
        """Catalogue chỉ đọc DB tạm; không có socket/network nào được mở."""
        with patch.object(main, "get_connection", return_value=catalog_db()) as getter, \
             patch.object(socket, "socket") as fake_socket:
            main.public_repositories(_request(""))
        getter.assert_called_once()
        fake_socket.assert_not_called()

    def test_limit_bounded(self) -> None:
        conn = catalog_db()
        for i in range(60):
            conn.execute(
                """INSERT INTO repositories VALUES (?, ?, 'bulk', '', '', '', 'MIT',
                   '', 'BEGINNER', 'checked', 'VERIFIED', 'REAL')""",
                (100 + i, f"https://github.com/example/bulk-{i}"),
            )
        conn.commit()
        # Mỗi lần gọi tự đóng connection — cần DB mới cho từng truy vấn.
        with patch.object(main, "get_connection", return_value=conn):
            default = main.list_repositories()
        conn = catalog_db()
        for i in range(60):
            conn.execute(
                """INSERT INTO repositories VALUES (?, ?, 'bulk', '', '', '', 'MIT',
                   '', 'BEGINNER', 'checked', 'VERIFIED', 'REAL')""",
                (100 + i, f"https://github.com/example/bulk-{i}"),
            )
        conn.commit()
        with patch.object(main, "get_connection", return_value=conn):
            small = main.list_repositories(limit="3")
        self.assertLessEqual(len(default), main.REPOSITORIES_DEFAULT_LIMIT)
        self.assertEqual(len(small), 3)


class RepositoryMigrationTests(unittest.TestCase):
    """Migration tạo repositories idempotent trên DB tạm (không đụng DB thật)."""

    #: (tên, kiểu, notnull, pk) theo đúng schema r2.
    EXPECTED_COLUMNS = (
        ("id", "INTEGER", 0, 1),
        ("canonical_url", "TEXT", 1, 0),
        ("name", "TEXT", 1, 0),
        ("purpose", "TEXT", 0, 0),
        ("use_case", "TEXT", 0, 0),
        ("tradeoffs", "TEXT", 0, 0),
        ("license", "TEXT", 0, 0),
        ("updated_at", "TEXT", 0, 0),
        ("difficulty", "TEXT", 0, 0),
        ("provenance", "TEXT", 0, 0),
        ("verification_status", "TEXT", 1, 0),
        ("data_origin", "TEXT", 1, 0),
        ("created_at", "TEXT", 0, 0),
    )

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

    def test_fresh_db_has_repositories_with_exact_columns(self) -> None:
        migrate.apply_migration()
        conn = sqlite3.connect(str(self.temp_db_path))
        self.addCleanup(conn.close)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        self.assertIn("repositories", tables)
        actual = [
            (row[1], row[2], row[3], row[5])
            for row in conn.execute("PRAGMA table_info(repositories)")
        ]
        self.assertEqual(actual, list(self.EXPECTED_COLUMNS))

    def test_migration_is_idempotent_and_keeps_rows(self) -> None:
        migrate.apply_migration()
        conn = sqlite3.connect(str(self.temp_db_path))
        conn.execute(
            "INSERT INTO repositories (canonical_url, name) VALUES (?, ?)",
            ("https://github.com/example/keep", "keep"),
        )
        conn.commit()
        conn.close()
        migrate.apply_migration()  # lần hai — không được DROP/XÓA
        conn = sqlite3.connect(str(self.temp_db_path))
        self.addCleanup(conn.close)
        count = conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
        self.assertEqual(count, 1)

    def test_fresh_db_has_no_seeded_rows(self) -> None:
        """Không seed row nào (kể cả SAMPLE) — catalogue bắt đầu rỗng."""
        migrate.apply_migration()
        conn = sqlite3.connect(str(self.temp_db_path))
        self.addCleanup(conn.close)
        count = conn.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
