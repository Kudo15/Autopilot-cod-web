"""Regression tests for the public article feed boundary."""
from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from backend.app.database import DB_PATH
from backend.app.main import list_articles
from backend.app.migrate import apply_migration
from backend.app.seed import run_seed

#: Trường public duy nhất được phép xuất hiện trong GET /api/articles.
PUBLIC_FIELDS = {"id", "title", "url", "source", "category", "summary", "published_at", "created_at"}

#: URL public chính thức của bài viết kế thừa (Vũ Học AI v0.3.1, pages.dev còn live).
LEGACY_LIVE_URL = "https://1c469d4b.ai-news-200.pages.dev/"


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


class ProvenanceBackedShapeContractTests(unittest.TestCase):
    """Định nghĩa hình dạng BẮT BUỘC của một bản ghi REAL/PUBLISHED có provenance.

    Một bài chỉ được coi là nguồn hợp lệ cho feed công khai khi:
    - articles.data_origin = 'REAL' và articles.article_status = 'PUBLISHED';
    - articles.url là URL công khai http(s) của nguồn chính thức;
    - có bản ghi provenance tương ứng trong raw_items (canonical_url + provenance + content_hash).
    Response công khai chỉ được chứa PUBLIC_FIELDS: không raw_content, không provenance.
    """

    def test_real_published_row_with_official_url_and_provenance_is_served_with_public_fields(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT, source TEXT,
                category TEXT, summary TEXT, published_at TEXT, created_at TEXT,
                data_origin TEXT, article_status TEXT
            );
            CREATE TABLE raw_items (
                id INTEGER PRIMARY KEY, source_id TEXT, canonical_url TEXT,
                normalized_title TEXT, content_hash TEXT, raw_content TEXT,
                provenance TEXT, data_origin TEXT
            );
            """
        )
        connection.execute(
            """INSERT INTO raw_items (id, source_id, canonical_url, normalized_title,
               content_hash, raw_content, provenance, data_origin)
               VALUES (1, 'LEGACY_v031', ?, ?, 'sha256-test', 'raw body',
                       'internal provenance note', 'REAL')""",
            (LEGACY_LIVE_URL, "Đọc quota trong 60 giây: request khác token"),
        )
        connection.execute(
            """INSERT INTO articles (id, title, url, source, category, summary,
               published_at, created_at, data_origin, article_status)
               VALUES (1, 'Đọc quota trong 60 giây: request khác token', ?, 'LEGACY_v031',
                       'tip-trick', 'Chưa dùng hết quota ngày nhưng vẫn bị giới hạn?',
                       '2026-10-10T00:00:00+07:00', '2026-10-10T00:00:00+07:00',
                       'REAL', 'PUBLISHED')""",
            (LEGACY_LIVE_URL,),
        )
        connection.commit()

        with patch("backend.app.main.get_connection", return_value=connection):
            articles = list_articles()

        self.assertEqual(len(articles), 1)
        self.assertEqual(set(articles[0]), PUBLIC_FIELDS)
        self.assertEqual(articles[0]["url"], LEGACY_LIVE_URL)
        self.assertTrue(articles[0]["url"].startswith("https://"))
        self.assertNotIn("provenance", articles[0])
        self.assertNotIn("raw_content", articles[0])
        connection.close()


class LivePublicFeedContractTests(unittest.TestCase):
    """Trọng tài P5 ở mức đơn vị: DB thật đã seed PHẢI phục vụ ít nhất một bài REAL/PUBLISHED.

    Trước khi có fixture kế thừa, test này đỏ vì `backend/data/radar.db` chỉ có
    bản ghi SAMPLE/DRAFT — đúng lý do `checks/p5.py` trả mảng rỗng.
    """

    def test_seeded_database_serves_at_least_one_real_published_article(self) -> None:
        apply_migration()
        run_seed()

        articles = list_articles()
        served = [a for a in articles if a.get("url")]

        self.assertGreaterEqual(
            len(served), 1,
            "Feed công khai rỗng: DB chưa có bài REAL/PUBLISHED nào có URL công khai "
            "(SAMPLE/DRAFT bị loại đúng luật, nhưng chưa có nguồn thật nào thay thế).",
        )
        self.assertEqual(set(served[0]), PUBLIC_FIELDS)
        self.assertTrue(served[0]["url"].startswith("https://"))

        with sqlite3.connect(str(DB_PATH)) as connection:
            row = connection.execute(
                "SELECT data_origin, article_status FROM articles WHERE url = ?",
                (served[0]["url"],),
            ).fetchone()
            legacy = connection.execute(
                "SELECT COUNT(*) FROM raw_items WHERE canonical_url = ? AND provenance IS NOT NULL",
                (served[0]["url"],),
            ).fetchone()[0]

        self.assertIsNotNone(row, "bài phục vụ công khai phải tồn tại trong articles")
        self.assertEqual(row[0], "REAL", "data_origin phải là REAL, không được gán nhãn lại SAMPLE")
        self.assertEqual(row[1], "PUBLISHED", "article_status phải là PUBLISHED")
        self.assertGreaterEqual(legacy, 1, "phải có provenance trong raw_items cho bài công khai")


if __name__ == "__main__":
    unittest.main()
