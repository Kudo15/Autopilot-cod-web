# Review package — Task 001

BASE: 0bd5620
HEAD: 5b5c1737f20ff2a91e23cac941de239c41517651

## Commit list
5b5c173 (HEAD -> autopilot/run-live) feat: connect public article feed

## Stat
 backend/app/main.py                   | 16 +++++++--
 backend/tests/__init__.py             |  1 +
 backend/tests/test_public_articles.py | 63 +++++++++++++++++++++++++++++++++++
 src/App.jsx                           | 38 ++++++++++++++-------
 src/components/GroupView.jsx          | 39 ++++++++++++----------
 src/styles.css                        | 38 +++++++++++++++++++++
 vite.config.js                        |  8 ++++-
 7 files changed, 170 insertions(+), 33 deletions(-)

## Full diff
diff --git a/backend/app/main.py b/backend/app/main.py
index dd5646c..1ca805e 100644
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -25,20 +25,32 @@ async def lifespan(_: FastAPI):
 app = FastAPI(title="Vũ Học AI Radar", version="1.0.0", lifespan=lifespan)
 
 
 @app.get("/api/health")
 def health() -> dict[str, str]:
     return {"status": "ok", "service": "vu-hoc-ai-radar"}
 
 
 @app.get("/api/articles")
 def list_articles() -> list[dict]:
-    """Đọc danh sách bài viết từ bảng articles (rỗng trong Phase 3)."""
+    """Trả các bài viết đã xuất bản, không gồm dữ liệu SAMPLE hay nội bộ."""
     conn = get_connection()
     try:
         columns = ", ".join(ARTICLES_COLUMNS)
+        available_columns = {
+            row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
+        }
+        filters: list[str] = []
+        params: list[str] = []
+        if "article_status" in available_columns:
+            filters.append("article_status = ?")
+            params.append("PUBLISHED")
+        if "data_origin" in available_columns:
+            filters.append("data_origin != ?")
+            params.append("SAMPLE")
+        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
         rows = conn.execute(
-            f"SELECT {columns} FROM articles ORDER BY id DESC"
+            f"SELECT {columns} FROM articles{where_clause} ORDER BY id DESC", params
         ).fetchall()
         return [dict(row) for row in rows]
     finally:
         conn.close()
diff --git a/backend/tests/__init__.py b/backend/tests/__init__.py
new file mode 100644
index 0000000..4d88bb3
--- /dev/null
+++ b/backend/tests/__init__.py
@@ -0,0 +1 @@
+"""Focused backend regression tests."""
diff --git a/backend/tests/test_public_articles.py b/backend/tests/test_public_articles.py
new file mode 100644
index 0000000..e428d68
--- /dev/null
+++ b/backend/tests/test_public_articles.py
@@ -0,0 +1,63 @@
+"""Regression tests for the public article feed boundary."""
+from __future__ import annotations
+
+import sqlite3
+import unittest
+from unittest.mock import patch
+
+from backend.app.main import list_articles
+
+
+class PublicArticleFeedTests(unittest.TestCase):
+    def test_list_articles_returns_only_real_published_public_fields(self) -> None:
+        connection = sqlite3.connect(":memory:")
+        connection.row_factory = sqlite3.Row
+        connection.execute(
+            """
+            CREATE TABLE articles (
+                id INTEGER PRIMARY KEY,
+                title TEXT,
+                url TEXT,
+                source TEXT,
+                category TEXT,
+                summary TEXT,
+                published_at TEXT,
+                created_at TEXT,
+                data_origin TEXT,
+                article_status TEXT,
+                internal_note TEXT
+            )
+            """
+        )
+        connection.executemany(
+            """
+            INSERT INTO articles (
+                id, title, url, source, category, summary, published_at,
+                created_at, data_origin, article_status, internal_note
+            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
+            """,
+            [
+                (1, "Published", "https://example.test/published", "editorial", "tip-trick",
+                 "Public summary", "2026-10-24T00:00:00Z", "2026-10-24T00:00:00Z",
+                 "REAL", "PUBLISHED", "do not expose"),
+                (2, "Draft", "https://example.test/draft", "editorial", "tip-trick",
+                 "Private draft", None, "2026-10-24T00:00:00Z", "REAL", "DRAFT", "private"),
+                (3, "Sample", "https://example.test/sample", "SAMPLE", "tip-trick",
+                 "Sample", None, "2026-10-24T00:00:00Z", "SAMPLE", "PUBLISHED", "private"),
+            ],
+        )
+        connection.commit()
+
+        with patch("backend.app.main.get_connection", return_value=connection):
+            articles = list_articles()
+
+        self.assertEqual([article["title"] for article in articles], ["Published"])
+        self.assertEqual(
+            set(articles[0]),
+            {"id", "title", "url", "source", "category", "summary", "published_at", "created_at"},
+        )
+        connection.close()
+
+
+if __name__ == "__main__":
+    unittest.main()
diff --git a/src/App.jsx b/src/App.jsx
index 16a0db0..b9b8732 100644
--- a/src/App.jsx
+++ b/src/App.jsx
@@ -1,40 +1,55 @@
 import { useEffect, useMemo, useState } from 'react';
 import { Header } from './components/Header.jsx';
 import { Sidebar } from './components/Sidebar.jsx';
 import { GroupView } from './components/GroupView.jsx';
 import { CONTENT_GROUPS, DEFAULT_GROUP_ID } from './data/groups.js';
 import { useTheme } from './hooks/useTheme.js';
 
-const LOADING_DURATION_MS = 450;
-
 export default function App() {
   const { theme, toggleTheme } = useTheme();
   const [activeId, setActiveId] = useState(DEFAULT_GROUP_ID);
   const [reloadKey, setReloadKey] = useState(0);
-  const [status, setStatus] = useState('loading'); // 'loading' | 'empty' | 'error'
+  const [status, setStatus] = useState('loading');
+  const [articles, setArticles] = useState([]);
   const [sidebarOpen, setSidebarOpen] = useState(false);
 
   const activeGroup = useMemo(
     () => CONTENT_GROUPS.find((g) => g.id === activeId) ?? CONTENT_GROUPS[0],
     [activeId]
   );
 
-  // Vào trạng thái loading khi chọn nhóm (hoặc bấm "Thử lại"),
-  // sau đó chuyển sang empty — Phase 2 chưa có backend nên mọi
-  // nhóm đều chưa có nội dung, không tạo dữ liệu giả.
   useEffect(() => {
+    const controller = new AbortController();
+
     setStatus('loading');
-    const timer = setTimeout(() => {
-      setStatus((current) => (current === 'loading' ? 'empty' : current));
-    }, LOADING_DURATION_MS);
-    return () => clearTimeout(timer);
+    fetch('/api/articles', { signal: controller.signal })
+      .then((response) => {
+        if (!response.ok) {
+          throw new Error(`Article feed request failed: ${response.status}`);
+        }
+        return response.json();
+      })
+      .then((data) => {
+        if (!Array.isArray(data)) {
+          throw new Error('Article feed response must be an array');
+        }
+        setArticles(data);
+        setStatus('empty');
+      })
+      .catch((error) => {
+        if (error.name !== 'AbortError') {
+          setStatus('error');
+        }
+      });
+
+    return () => controller.abort();
   }, [activeId, reloadKey]);
 
   function handleSelectGroup(id) {
     setActiveId(id);
     setSidebarOpen(false);
   }
 
   return (
     <div className="app-shell">
       <Header
@@ -46,19 +61,18 @@ export default function App() {
         <Sidebar
           groups={CONTENT_GROUPS}
           activeId={activeId}
           onSelect={handleSelectGroup}
           open={sidebarOpen}
         />
         <main className="app-main">
           <GroupView
             group={activeGroup}
             status={status}
+            articles={articles}
             onRetry={() => setReloadKey((key) => key + 1)}
-            onSimulateError={() => setStatus('error')}
-            onReset={() => setStatus('empty')}
           />
         </main>
       </div>
     </div>
   );
 }
diff --git a/src/components/GroupView.jsx b/src/components/GroupView.jsx
index 1ac6c35..1e524dd 100644
--- a/src/components/GroupView.jsx
+++ b/src/components/GroupView.jsx
@@ -1,14 +1,11 @@
-// GroupView: hiển thị nội dung của nhóm đang chọn qua 3 trạng thái
-// loading / empty / error — được quản lý bằng React state trong App.
-// Phase 2: chưa có backend, nên trạng thái dữ liệu thật là empty (chưa có nội dung).
-// Hai nút "Kiểm thử giao diện" chỉ dùng để quan sát trạng thái, không tạo dữ liệu giả.
+// GroupView renders the public article feed through loading, empty and error states.
 
 function LoadingState({ groupName }) {
   return (
     <div className="state state-loading" role="status">
       <div className="spinner" aria-hidden="true"></div>
       <p>Đang tải nhóm {groupName}…</p>
     </div>
   );
 }
 
@@ -17,50 +14,56 @@ function EmptyState({ groupName }) {
     <div className="state state-empty">
       <div className="state-icon" aria-hidden="true">📭</div>
       <p>
         Nhóm <strong>{groupName}</strong> hiện chưa có nội dung.
       </p>
       <p className="state-hint">Bài viết sẽ xuất hiện ở đây sau khi bộ thu thập hoạt động.</p>
     </div>
   );
 }
 
+function ArticleFeed({ articles }) {
+  return (
+    <div className="article-feed" aria-label="Bài viết">
+      {articles.map((article) => (
+        <article className="article-card" key={article.id}>
+          <p className="article-meta">{article.source || 'Biên tập'}{article.published_at ? ` · ${article.published_at}` : ''}</p>
+          <h3>{article.title}</h3>
+          {article.summary && <p>{article.summary}</p>}
+          {article.url && <a href={article.url}>Đọc bài viết</a>}
+        </article>
+      ))}
+    </div>
+  );
+}
+
 function ErrorState({ groupName, onRetry }) {
   return (
     <div className="state state-error" role="alert">
       <div className="state-icon" aria-hidden="true">⚠️</div>
       <p>
         Không tải được nội dung nhóm <strong>{groupName}</strong>.
       </p>
       <p className="state-hint">Kiểm tra kết nối hoặc thử lại sau ít phút.</p>
       <button type="button" className="btn" onClick={onRetry}>
         Thử lại
       </button>
     </div>
   );
 }
 
-export function GroupView({ group, status, onRetry, onSimulateError, onReset }) {
+export function GroupView({ group, status, articles, onRetry }) {
+  const groupArticles = articles.filter((article) => article.category === group.id);
+
   return (
     <section className="group-view">
       <div className="group-view-header">
         <h2>{group.name}</h2>
-        <div className="state-controls" aria-label="Kiểm thử giao diện">
-          <span className="state-controls-label">Kiểm thử giao diện:</span>
-          {status === 'error' ? (
-            <button type="button" className="btn btn-small" onClick={onReset}>
-              Về trang trống
-            </button>
-          ) : (
-            <button type="button" className="btn btn-small" onClick={onSimulateError}>
-              Mô phỏng lỗi
-            </button>
-          )}
-        </div>
       </div>
 
       {status === 'loading' && <LoadingState groupName={group.name} />}
-      {status === 'empty' && <EmptyState groupName={group.name} />}
+      {status === 'empty' && groupArticles.length === 0 && <EmptyState groupName={group.name} />}
+      {status === 'empty' && groupArticles.length > 0 && <ArticleFeed articles={groupArticles} />}
       {status === 'error' && <ErrorState groupName={group.name} onRetry={onRetry} />}
     </section>
   );
 }
diff --git a/src/styles.css b/src/styles.css
index cf1d9bc..941af0e 100644
--- a/src/styles.css
+++ b/src/styles.css
@@ -193,20 +193,58 @@ body {
   gap: 12px;
   flex-wrap: wrap;
   margin-bottom: 16px;
 }
 
 .group-view-header h2 {
   margin: 0;
   font-size: 1.4rem;
 }
 
+.article-feed {
+  display: grid;
+  gap: 12px;
+}
+
+.article-card {
+  padding: 18px;
+  background: var(--bg-panel);
+  border: 1px solid var(--border);
+  border-radius: 12px;
+}
+
+.article-card h3,
+.article-card p {
+  margin: 0;
+}
+
+.article-card h3 {
+  margin-bottom: 8px;
+}
+
+.article-card p + p,
+.article-card p + a {
+  display: inline-block;
+  margin-top: 8px;
+}
+
+.article-meta {
+  color: var(--text-muted);
+  font-size: 0.82rem;
+  margin-bottom: 8px !important;
+}
+
+.article-card a {
+  color: var(--accent);
+  font-weight: 600;
+}
+
 .state-controls {
   display: flex;
   align-items: center;
   gap: 8px;
   font-size: 0.78rem;
   color: var(--text-muted);
 }
 
 /* ---------- 3 trạng thái ---------- */
 
diff --git a/vite.config.js b/vite.config.js
index 10315f7..f9cdda8 100644
--- a/vite.config.js
+++ b/vite.config.js
@@ -1,11 +1,17 @@
 import { defineConfig } from 'vite';
 
 export default defineConfig({
   server: {
     host: '127.0.0.1',
-    port: 5173
+    port: 5173,
+    proxy: {
+      '/api': {
+        target: 'http://127.0.0.1:8000',
+        changeOrigin: true
+      }
+    }
   },
   build: {
     outDir: 'dist'
   }
 });
