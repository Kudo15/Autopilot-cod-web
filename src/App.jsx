import React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Header } from './components/Header.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { GroupView } from './components/GroupView.jsx';
import { ExplorerView } from './components/ExplorerView.jsx';
import { PromotionView } from './components/PromotionView.jsx';
import { AdminView } from './components/admin/AdminView.jsx';
import { SearchView } from './components/SearchView.jsx';
import { RepositoryView } from './components/RepositoryView.jsx';
import { ArticleDialog } from './components/ArticleDialog.jsx';
import { CONTENT_GROUPS, DEFAULT_GROUP_ID } from './data/groups.js';
import { useTheme } from './hooks/useTheme.js';
import { useBookmarks } from './hooks/useBookmarks.js';

//: Nhóm dùng API Explorer (GET /api/models) thay cho feed bài viết.
const EXPLORER_GROUP_ID = 'free-model-explorer';

//: Nhóm Promotion Radar (GET /api/offers) — ưu đãi AI thật, đã xác minh.
const PROMOTION_GROUP_ID = 'ai-deals';

//: Nhóm Admin Radar dùng API admin (P8b) — token nhập runtime, không nằm trong bundle.
const ADMIN_GROUP_ID = 'admin-radar';
const REPOSITORY_GROUP_ID = 'repository-explorer';

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [activeId, setActiveId] = useState(DEFAULT_GROUP_ID);
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState('loading');
  const [articles, setArticles] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArticle, setSelectedArticle] = useState(null);
  const { isBookmarked, toggleBookmark } = useBookmarks();

  const activeGroup = useMemo(
    () => CONTENT_GROUPS.find((g) => g.id === activeId) ?? CONTENT_GROUPS[0],
    [activeId]
  );

  // Nhóm Explorer tự gọi /api/models; Admin Radar tự gọi /api/admin/*;
  // các nhóm còn lại giữ nguyên feed bài viết.
  const isExplorer = activeGroup.id === EXPLORER_GROUP_ID;
  const isAdmin = activeGroup.id === ADMIN_GROUP_ID;
  const isPromotion = activeGroup.id === PROMOTION_GROUP_ID;
  const isRepository = activeGroup.id === REPOSITORY_GROUP_ID;

  useEffect(() => {
    if (isExplorer || isAdmin || isPromotion || isRepository) return undefined;

    const controller = new AbortController();

    setStatus('loading');
    fetch('/api/articles', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Article feed request failed: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!Array.isArray(data)) {
          throw new Error('Article feed response must be an array');
        }
        setArticles(data);
        setStatus('empty');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setStatus('error');
        }
      });

    return () => controller.abort();
  }, [activeId, reloadKey, isExplorer, isAdmin, isPromotion, isRepository]);

  function handleSelectGroup(id) {
    setActiveId(id);
    setSidebarOpen(false);
  }

  return (
    <div className="app-shell">
      <Header
        theme={theme}
        onToggleTheme={toggleTheme}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
        onSearch={setSearchQuery}
      />
      <div className="app-body">
        <Sidebar
          groups={CONTENT_GROUPS}
          activeId={activeId}
          onSelect={handleSelectGroup}
          open={sidebarOpen}
        />
        <main className="app-main">
                  {searchQuery ? (
                    <SearchView query={searchQuery} onClose={() => setSearchQuery('')} />
                  ) : isAdmin ? (
                    <AdminView />
                  ) : isExplorer ? (
                    <ExplorerView group={activeGroup} />
                  ) : isPromotion ? (
                    <PromotionView />
                  ) : isRepository ? (
                    <RepositoryView />
                  ) : (
            <GroupView
              group={activeGroup}
              status={status}
              articles={articles}
              onRetry={() => setReloadKey((key) => key + 1)}
              isBookmarked={isBookmarked}
              onToggleBookmark={toggleBookmark}
              onOpenArticle={setSelectedArticle}
            />
          )}
        </main>
      </div>
      {selectedArticle && <ArticleDialog article={selectedArticle} onClose={() => setSelectedArticle(null)} />}
    </div>
  );
}
