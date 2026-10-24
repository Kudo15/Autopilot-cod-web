// GroupView renders the public article feed through loading, empty and error states.

function LoadingState({ groupName }) {
  return (
    <div className="state state-loading" role="status">
      <div className="spinner" aria-hidden="true"></div>
      <p>Đang tải nhóm {groupName}…</p>
    </div>
  );
}

function EmptyState({ groupName }) {
  return (
    <div className="state state-empty">
      <div className="state-icon" aria-hidden="true">📭</div>
      <p>
        Nhóm <strong>{groupName}</strong> hiện chưa có nội dung.
      </p>
      <p className="state-hint">Bài viết sẽ xuất hiện ở đây sau khi bộ thu thập hoạt động.</p>
    </div>
  );
}

function ArticleFeed({ articles, isBookmarked, onToggleBookmark, onOpenArticle }) {
  return (
    <div className="article-feed" aria-label="Bài viết">
      {articles.map((article) => (
        <article className="article-card" key={article.id}>
          <p className="article-meta">{article.source || 'Biên tập'}{article.published_at ? ` · ${article.published_at}` : ''}</p>
          <h3>{article.title}</h3>
          {article.summary && <p>{article.summary}</p>}
          <div className="article-actions">
            <button type="button" className="btn btn-small btn-secondary" onClick={() => onToggleBookmark(article.id)}>
              {isBookmarked(article.id) ? '★ Đã lưu' : '☆ Lưu bài'}
            </button>
            <button type="button" className="btn btn-small" onClick={() => onOpenArticle(article)}>Đọc nhanh</button>
            {article.url && <a href={article.url}>Nguồn chính thức</a>}
          </div>
        </article>
      ))}
    </div>
  );
}

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

export function GroupView({ group, status, articles, onRetry, isBookmarked, onToggleBookmark, onOpenArticle }) {
  const groupArticles = articles.filter((article) => article.category === group.id);

  return (
    <section className="group-view">
      <div className="group-view-header">
        <h2>{group.name}</h2>
      </div>

      {status === 'loading' && <LoadingState groupName={group.name} />}
      {status === 'empty' && groupArticles.length === 0 && <EmptyState groupName={group.name} />}
      {status === 'empty' && groupArticles.length > 0 && <ArticleFeed articles={groupArticles} isBookmarked={isBookmarked} onToggleBookmark={onToggleBookmark} onOpenArticle={onOpenArticle} />}
      {status === 'error' && <ErrorState groupName={group.name} onRetry={onRetry} />}
    </section>
  );
}
