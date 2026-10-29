import React from 'react';
import { useEffect, useMemo, useState } from 'react';

const DIFFICULTIES = ['BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'UNKNOWN'];
const STATUSES = ['VERIFIED', 'UNVERIFIED', 'STALE', 'EXPIRED', 'NEEDS_REVIEW'];

function safeGithubUrl(value) {
  // Chỉ liên kết khi canonical URL đúng dạng https://github.com/... —
  // dữ liệu từ DB là untrusted, không bao giờ href nguyên si.
  if (typeof value !== 'string') return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== 'https:' || parsed.hostname !== 'github.com' || !parsed.pathname.startsWith('/')) {
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

function RepositoryCard({ repo }) {
  const url = safeGithubUrl(repo.canonical_url);
  return (
    <article className="repo-card">
      <div className="repo-card__meta">
        <span className="repo-card__difficulty">{repo.difficulty || 'UNKNOWN'}</span>
        <span className="repo-card__status">{repo.verification_status}</span>
        {repo.license && <span className="repo-card__license">{repo.license}</span>}
      </div>
      <h2>{repo.name}</h2>
      {repo.purpose && <p>{repo.purpose}</p>}
      {repo.use_case && <p className="repo-card__usecase">Use case: {repo.use_case}</p>}
      {repo.tradeoffs && <p className="repo-card__tradeoffs">Tradeoffs: {repo.tradeoffs}</p>}
      <div className="repo-card__footer">
        {repo.updated_at && <span className="repo-card__updated">Updated: {repo.updated_at}</span>}
        {url && (
          <a className="button repo-card__link" href={url} target="_blank" rel="noreferrer noopener">
            Mở repository
          </a>
        )}
      </div>
    </article>
  );
}

export function RepositoryView() {
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [license, setLicense] = useState('');
  const [status, setStatus] = useState('');
  const [repos, setRepos] = useState([]);
  const [state, setState] = useState('loading');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: '50' });
    if (query.trim()) params.set('q', query.trim());
    if (difficulty) params.set('difficulty', difficulty);
    if (license.trim()) params.set('license', license.trim());
    if (status) params.set('verification_status', status);
    setState('loading');
    fetch(`/api/repositories?${params}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Repository request failed: ${response.status}`);
        return response.json();
      })
      .then((data) => {
        setRepos(Array.isArray(data) ? data : []);
        setState('ready');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setState('error');
      });
    return () => controller.abort();
  }, [query, difficulty, license, status, reloadKey]);

  const emptyMessage = useMemo(() => {
    if (status) return `Chưa có repository ở trạng thái ${status}.`;
    return 'Chưa có repository VERIFIED nào trong catalogue.';
  }, [status]);

  return (
    <section className="group-view repository-view" aria-labelledby="repository-title">
      <div className="group-heading">
        <p className="eyebrow">Repository Explorer</p>
        <h1 id="repository-title">GitHub Repository Catalogue</h1>
        <p>Các repository đã xác minh kèm purpose, use case, tradeoffs và license.</p>
      </div>
      <div className="repository-filters">
        <label className="promotion-search">Tìm repository
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tên, mục đích hoặc use case" />
        </label>
        <label>Độ khó
          <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
            <option value="">Tất cả</option>
            {DIFFICULTIES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>License
          <input value={license} onChange={(event) => setLicense(event.target.value)} placeholder="MIT, Apache-2.0..." />
        </label>
        <label>Trạng thái
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">Mặc định (VERIFIED)</option>
            {STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
      </div>
      {state === 'loading' && <p>Đang tải repository…</p>}
      {state === 'error' && (
        <div role="alert" className="repository-error">
          <p>Không tải được danh sách repository.</p>
          <button type="button" className="button" onClick={() => setReloadKey((key) => key + 1)}>Thử lại</button>
        </div>
      )}
      {state === 'ready' && repos.length === 0 && <p>{emptyMessage}</p>}
      <div className="repo-grid">
        {repos.map((repo) => <RepositoryCard key={repo.id} repo={repo} />)}
      </div>
    </section>
  );
}
