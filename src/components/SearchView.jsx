import { useEffect, useState } from 'react';

const CATEGORIES = [
  ['', 'Mọi chủ đề'], ['tip-trick', 'Tip & Trick'], ['ai-model', 'AI & Model'],
  ['policy-quota', 'Chính sách & Quota'], ['free-model-explorer', 'Free Model Explorer'],
  ['ai-deals', 'AI Deals & Promotions'], ['provider-comparison', 'Provider Comparison'],
];

export function SearchView({ query, onClose }) {
  const [category, setCategory] = useState('');
  const [windowName, setWindowName] = useState('all');
  const [state, setState] = useState({ status: 'loading', rows: [] });

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading', rows: [] });
    const params = new URLSearchParams({ q: query, window: windowName });
    if (category) params.set('category', category);
    fetch(`/api/search?${params}`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error('search failed'); return response.json(); })
      .then((rows) => { if (!Array.isArray(rows)) throw new Error('invalid response'); setState({ status: rows.length ? 'ready' : 'empty', rows }); })
      .catch((error) => { if (error.name !== 'AbortError') setState({ status: 'error', rows: [] }); });
    return () => controller.abort();
  }, [query, category, windowName]);

  return (
    <section className="search-view" aria-labelledby="search-title">
      <div className="group-view-header">
        <div><h2 id="search-title">Tìm kiếm</h2><p className="muted">Kết quả cho: <strong>{query}</strong></p></div>
        <button type="button" className="btn btn-secondary" onClick={onClose}>Đóng tìm kiếm</button>
      </div>
      <div className="explorer-filters">
        <label className="explorer-filter">Chủ đề<select value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="explorer-filter">Thời gian<select value={windowName} onChange={(event) => setWindowName(event.target.value)}><option value="all">Tất cả</option><option value="today">Hôm nay</option><option value="7d">7 ngày</option><option value="30d">30 ngày</option></select></label>
      </div>
      {state.status === 'loading' && <div className="state" role="status"><p>Đang tìm kiếm…</p></div>}
      {state.status === 'error' && <div className="state state-error" role="alert"><p>Không thể tìm kiếm lúc này.</p></div>}
      {state.status === 'empty' && <div className="state state-empty"><p>Không có bài viết phù hợp.</p></div>}
      {state.status === 'ready' && <div className="article-feed" aria-label="Kết quả tìm kiếm">{state.rows.map((article) => <article className="article-card" key={article.id}><p className="article-meta">{article.source || 'Biên tập'}{article.published_at ? ` · ${article.published_at}` : ''}</p><h3>{article.title}</h3>{article.summary && <p>{article.summary}</p>}{article.url && <a href={article.url}>Đọc bài viết</a>}</article>)}</div>}
    </section>
  );
}
