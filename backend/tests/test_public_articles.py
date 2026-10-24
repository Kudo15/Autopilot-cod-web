"""Regression tests for the public article feed boundary."""
from __future__ import annotations

from contextlib import ExitStack, closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from backend.app import database, migrate, seed
from backend.app.ingest.importers import persist_import
from backend.app.ingest.normalize import normalize_item
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
    """Trọng tài P5 ở mức đơn vị trên DB tạm cô lập (không chạm backend/data/radar.db)."""

    def setUp(self) -> None:
        self._live_db_path = database.DB_PATH
        self._live_existed = self._live_db_path.exists()
        self._live_stat = self._live_db_path.stat() if self._live_existed else None

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_data_dir = Path(self._tmpdir.name) / "data"
        self.temp_db_path = self.temp_data_dir / "radar.db"
        self.temp_data_dir.mkdir(parents=True, exist_ok=True)

        # Khởi tạo baseline Phase 3 (bảng articles rỗng) trên DB tạm trước khi chạy migrate Phase 4.
        with closing(sqlite3.connect(str(self.temp_db_path))) as connection:
            connection.executescript(database.SCHEMA)
            connection.commit()

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(database, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(database, "DB_PATH", self.temp_db_path))
        stack.enter_context(patch.object(migrate, "DATA_DIR", self.temp_data_dir))
        stack.enter_context(patch.object(migrate, "DB_PATH", self.temp_db_path))

    def tearDown(self) -> None:
        self.assertEqual(
            self._live_db_path.exists(),
            self._live_existed,
            "Unit test không được tạo hay xoá backend/data/radar.db thật",
        )
        if self._live_existed and self._live_stat is not None:
            after_stat = self._live_db_path.stat()
            self.assertEqual(after_stat.st_size, self._live_stat.st_size)
            self.assertEqual(after_stat.st_mtime_ns, self._live_stat.st_mtime_ns)

    def test_seeded_database_serves_at_least_one_real_published_article(self) -> None:
        apply_migration()
        self.assertEqual(list_articles(), [], "DB tạm mới migrate phải rỗng trước khi seed")

        first_counts = run_seed()
        second_counts = run_seed()

        self.assertGreater(first_counts["_real_legacy_this_run"], 0)
        self.assertEqual(second_counts["_inserted_this_run"], 0)
        self.assertEqual(second_counts["_real_legacy_this_run"], 0)

        articles = list_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(set(articles[0]), PUBLIC_FIELDS)
        self.assertEqual(articles[0]["url"], LEGACY_LIVE_URL)

        expected = normalize_item(
            {
                "title": seed._REAL_LEGACY_TITLE,
                "url": seed._REAL_LEGACY_URL,
                "content": seed._REAL_LEGACY_BODY,
            },
            seed._REAL_LEGACY_SOURCE_ID,
            seed._REAL_LEGACY_PUBLISHED_AT,
        )
        with closing(sqlite3.connect(str(self.temp_db_path))) as connection:
            published_rows = connection.execute(
                """
                SELECT url, data_origin, article_status
                FROM articles
                WHERE data_origin = 'REAL' AND article_status = 'PUBLISHED'
                """
            ).fetchall()
            raw_rows = connection.execute(
                """
                SELECT canonical_url, normalized_title, content_hash, provenance
                FROM raw_items
                WHERE data_origin = 'REAL' AND canonical_url = ? AND provenance IS NOT NULL
                """,
                (LEGACY_LIVE_URL,),
            ).fetchall()

        self.assertEqual(published_rows, [(LEGACY_LIVE_URL, "REAL", "PUBLISHED")])
        self.assertEqual(len(raw_rows), 1)
        self.assertEqual(
            raw_rows[0][:3],
            (expected.canonical_url, expected.normalized_title, expected.content_hash),
        )
        self.assertTrue(raw_rows[0][3].strip())

    def test_legacy_seed_reuses_normalize_item_contract(self) -> None:
        apply_migration()
        expected = normalize_item(
            {
                "title": seed._REAL_LEGACY_TITLE,
                "url": seed._REAL_LEGACY_URL,
                "content": seed._REAL_LEGACY_BODY,
            },
            seed._REAL_LEGACY_SOURCE_ID,
            seed._REAL_LEGACY_PUBLISHED_AT,
        )

        with (
            patch.object(seed, "_REAL_LEGACY_URL", "HTTPS://1C469D4B.AI-NEWS-200.PAGES.DEV/#quota"),
            patch.object(
                seed,
                "_REAL_LEGACY_TITLE",
                f"  {seed._REAL_LEGACY_TITLE.replace(' ', '   ')}\n",
            ),
        ):
            run_seed()

        with closing(sqlite3.connect(str(self.temp_db_path))) as connection:
            raw_row = connection.execute(
                """
                SELECT canonical_url, normalized_title, content_hash
                FROM raw_items
                WHERE data_origin = 'REAL' AND source_id = ?
                """,
                (seed._REAL_LEGACY_SOURCE_ID,),
            ).fetchone()
            article_row = connection.execute(
                """
                SELECT title, url
                FROM articles
                WHERE data_origin = 'REAL' AND article_status = 'PUBLISHED'
                """
            ).fetchone()

        self.assertEqual(
            raw_row,
            (expected.canonical_url, expected.normalized_title, expected.content_hash),
        )
        self.assertEqual(article_row, (expected.normalized_title, expected.canonical_url))

    def test_real_draft_import_with_legacy_url_does_not_suppress_published_seed(self) -> None:
        apply_migration()
        with closing(database.get_connection()) as connection:
            imported = persist_import(
                connection,
                [
                    {
                        "title": "Draft note referencing legacy URL",
                        "url": LEGACY_LIVE_URL,
                        "content": "Unreviewed draft body imported before seed",
                    }
                ],
                "manual-draft",
                "text/markdown",
            )
        self.assertEqual(imported["inserted"], 1)
        self.assertEqual(list_articles(), [], "Bản nháp REAL/DRAFT không được lộ ra feed công khai")

        run_seed()
        second_counts = run_seed()
        self.assertEqual(second_counts["_real_legacy_this_run"], 0)

        articles = list_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["url"], LEGACY_LIVE_URL)
        self.assertEqual(articles[0]["source"], seed._REAL_LEGACY_SOURCE_ID)
        self.assertEqual(set(articles[0]), PUBLIC_FIELDS)

        expected = normalize_item(
            {
                "title": seed._REAL_LEGACY_TITLE,
                "url": seed._REAL_LEGACY_URL,
                "content": seed._REAL_LEGACY_BODY,
            },
            seed._REAL_LEGACY_SOURCE_ID,
            seed._REAL_LEGACY_PUBLISHED_AT,
        )
        with closing(sqlite3.connect(str(self.temp_db_path))) as connection:
            statuses = connection.execute(
                """
                SELECT source, article_status
                FROM articles
                WHERE data_origin = 'REAL' AND url = ?
                ORDER BY id ASC
                """,
                (LEGACY_LIVE_URL,),
            ).fetchall()
            raw_sources = connection.execute(
                """
                SELECT source_id, content_hash
                FROM raw_items
                WHERE data_origin = 'REAL' AND canonical_url = ?
                ORDER BY id ASC
                """,
                (LEGACY_LIVE_URL,),
            ).fetchall()

        self.assertEqual(
            statuses,
            [("manual-draft", "DRAFT"), (seed._REAL_LEGACY_SOURCE_ID, "PUBLISHED")],
        )
        self.assertEqual(len(raw_sources), 2)
        self.assertEqual(raw_sources[0][0], "manual-draft")
        self.assertEqual(raw_sources[1], (seed._REAL_LEGACY_SOURCE_ID, expected.content_hash))

    def test_identical_real_draft_import_still_seeds_published_article_without_overwriting_raw_item(self) -> None:
        apply_migration()
        with closing(database.get_connection()) as connection:
            persist_import(
                connection,
                [
                    {
                        "title": seed._REAL_LEGACY_TITLE,
                        "url": seed._REAL_LEGACY_URL,
                        "content": seed._REAL_LEGACY_BODY,
                    }
                ],
                "manual-same",
                "text/markdown",
            )
        self.assertEqual(list_articles(), [])

        run_seed()
        second_counts = run_seed()
        self.assertEqual(second_counts["_real_legacy_this_run"], 0)

        articles = list_articles()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"], seed._REAL_LEGACY_SOURCE_ID)

        with closing(sqlite3.connect(str(self.temp_db_path))) as connection:
            raw_rows = connection.execute(
                """
                SELECT source_id, provenance
                FROM raw_items
                WHERE data_origin = 'REAL' AND canonical_url = ?
                """,
                (LEGACY_LIVE_URL,),
            ).fetchall()

        self.assertEqual(len(raw_rows), 1)
        self.assertEqual(raw_rows[0][0], "manual-same")


if __name__ == "__main__":
    unittest.main()
