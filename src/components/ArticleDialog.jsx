import { useEffect, useRef } from 'react';

export function ArticleDialog({ article, onClose }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    if (!article) return undefined;
    dialogRef.current?.focus();
    function onKeyDown(event) { if (event.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [article, onClose]);
  if (!article) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="article-dialog" role="dialog" aria-modal="true" aria-labelledby="article-dialog-title" tabIndex="-1" ref={dialogRef}>
        <button type="button" className="dialog-close" aria-label="Đóng bài viết" onClick={onClose}>×</button>
        <h3 id="article-dialog-title">{article.title}</h3>
        {article.summary && <p>{article.summary}</p>}
        {article.url && <a href={article.url} target="_blank" rel="noreferrer">Mở nguồn chính thức</a>}
      </section>
    </div>
  );
}
