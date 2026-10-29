# Scoped review package — Task 001 fix round 1

FIX_BASE: 5b5c1737f20ff2a91e23cac941de239c41517651
HEAD: 4f9684b884b8fe469a9b9e8fd88303c7215c9aca

## Commit list
4f9684b (HEAD -> autopilot/run-live) fix: retain legacy public articles

## Stat
 backend/app/main.py                   | 2 +-
 backend/tests/test_public_articles.py | 8 +++++++-
 2 files changed, 8 insertions(+), 2 deletions(-)

## Fix diff
diff --git a/backend/app/main.py b/backend/app/main.py
index 1ca805e..a9d2840 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -33,24 +33,24 @@ def health() -> dict[str, str]:
 @app.get("/api/articles")
 def list_articles() -> list[dict]:
     """Trả các bài viết đã xuất bản, không gồm dữ liệu SAMPLE hay nội bộ."""
     conn = get_connection()
     try:
         columns = ", ".join(ARTICLES_COLUMNS)
         available_columns = {
             row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
         }
         filters: list[str] = []
         params: list[str] = []
         if "article_status" in available_columns:
             filters.append("article_status = ?")
             params.append("PUBLISHED")
         if "data_origin" in available_columns:
-            filters.append("data_origin != ?")
+            filters.append("(data_origin IS NULL OR data_origin != ?)")
             params.append("SAMPLE")
         where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
         rows = conn.execute(
             f"SELECT {columns} FROM articles{where_clause} ORDER BY id DESC", params
         ).fetchall()
         return [dict(row) for row in rows]
     finally:
         conn.close()
diff --git a/backend/tests/test_public_articles.py b/backend/tests/test_public_articles.py
index e428d68..912817f 100644
--- a/backend/tests/test_public_articles.py
+++ b/backend/tests/test_public_articles.py
@@ -32,32 +32,38 @@ class PublicArticleFeedTests(unittest.TestCase):
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
+                (4, "Legacy published", "https://example.test/legacy", "editorial", "tip-trick",
+                 "Legacy public summary", "2026-10-24T00:00:00Z", "2026-10-24T00:00:00Z",
+                 None, "PUBLISHED", "do not expose"),
             ],
         )
         connection.commit()
 
         with patch("backend.app.main.get_connection", return_value=connection):
             articles = list_articles()
 
-        self.assertEqual([article["title"] for article in articles], ["Published"])
+        self.assertEqual(
+            [article["title"] for article in articles],
+            ["Legacy published", "Published"],
+        )
         self.assertEqual(
             set(articles[0]),
             {"id", "title", "url", "source", "category", "summary", "published_at", "created_at"},
         )
         connection.close()
 
 
 if __name__ == "__main__":
     unittest.main()
