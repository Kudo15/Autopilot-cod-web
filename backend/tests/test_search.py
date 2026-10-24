from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.main import search_articles


class PublicSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, title TEXT, url TEXT, source TEXT,
                category TEXT, summary TEXT, published_at TEXT, created_at TEXT,
                data_origin TEXT, article_status TEXT
            );
            INSERT INTO articles VALUES
              (1, 'Quota mới cho API', 'https://example.test/1', 'source',
               'policy-quota', 'Tóm tắt quota', '2026-10-24T12:00:00+00:00', '2026-10-24T12:00:00+00:00', 'REAL', 'PUBLISHED'),
              (2, 'Bản nháp', 'https://example.test/2', 'source',
               'policy-quota', 'private', '2026-10-24T12:00:00+00:00', '2026-10-24T12:00:00+00:00', 'REAL', 'DRAFT'),
              (3, 'Sample quota', 'https://example.test/3', 'SAMPLE',
               'policy-quota', 'sample', '2026-10-24T12:00:00+00:00', '2026-10-24T12:00:00+00:00', 'SAMPLE', 'PUBLISHED');
            """
        )
        self.connection.commit()
        self.patch = patch("backend.app.main.get_connection", return_value=self.connection)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.connection.close)

    def test_search_returns_published_real_rows_for_category_and_window(self) -> None:
        rows = search_articles(q="quota", category="policy-quota", window="7d")
        self.assertEqual([row["id"] for row in rows], [1])
        self.assertNotIn("data_origin", rows[0])

    def test_search_treats_injection_shaped_query_as_text(self) -> None:
        rows = search_articles(q="' OR 1=1 --", category="policy-quota", window="all")
        self.assertEqual(rows, [])

    def test_search_rejects_unknown_window_and_category(self) -> None:
        with self.assertRaises(ValueError):
            search_articles(window="tomorrow")
        with self.assertRaises(ValueError):
            search_articles(category="admin-radar")


if __name__ == "__main__":
    unittest.main()
