"""Regression tests for the public article feed boundary."""
from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.main import list_articles


class PublicArticleFeedTests(unittest.TestCase):
    def test_list_articles_returns_only_real_published_public_fields(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                url TEXT,
                source TEXT,
                category TEXT,
                summary TEXT,
                published_at TEXT,
                created_at TEXT,
                data_origin TEXT,
                article_status TEXT,
                internal_note TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO articles (
                id, title, url, source, category, summary, published_at,
                created_at, data_origin, article_status, internal_note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "Published", "https://example.test/published", "editorial", "tip-trick",
                 "Public summary", "2026-10-24T00:00:00Z", "2026-10-24T00:00:00Z",
                 "REAL", "PUBLISHED", "do not expose"),
                (2, "Draft", "https://example.test/draft", "editorial", "tip-trick",
                 "Private draft", None, "2026-10-24T00:00:00Z", "REAL", "DRAFT", "private"),
                (3, "Sample", "https://example.test/sample", "SAMPLE", "tip-trick",
                 "Sample", None, "2026-10-24T00:00:00Z", "SAMPLE", "PUBLISHED", "private"),
                (4, "Legacy published", "https://example.test/legacy", "editorial", "tip-trick",
                 "Legacy public summary", "2026-10-24T00:00:00Z", "2026-10-24T00:00:00Z",
                 None, "PUBLISHED", "do not expose"),
            ],
        )
        connection.commit()

        with patch("backend.app.main.get_connection", return_value=connection):
            articles = list_articles()

        self.assertEqual(
            [article["title"] for article in articles],
            ["Legacy published", "Published"],
        )
        self.assertEqual(
            set(articles[0]),
            {"id", "title", "url", "source", "category", "summary", "published_at", "created_at"},
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
