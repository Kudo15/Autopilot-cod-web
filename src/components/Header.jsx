import { useState } from 'react';

export function Header({ theme, onToggleTheme, onToggleSidebar, onSearch }) {
  const [query, setQuery] = useState('');

  function submit(event) {
    event.preventDefault();
    if (query.trim()) onSearch(query.trim());
  }

  return (
    <header className="app-header">
      <button
        type="button"
        className="sidebar-toggle"
        onClick={onToggleSidebar}
        aria-label="Mở/đóng thanh điều hướng"
      >
        ☰
      </button>
      <div className="brand">
        <span className="brand-badge">VŨ HỌC</span>
        <h1 className="brand-title">AI Radar</h1>
        <span className="brand-version">v1.0</span>
      </div>
      <form className="header-search" onSubmit={submit} role="search">
        <label className="sr-only" htmlFor="header-search-input">Tìm kiếm bài viết</label>
        <input id="header-search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm bài viết" />
        <button type="submit" className="btn btn-small">Tìm</button>
      </form>
      <button
        type="button"
        className="theme-toggle"
        onClick={onToggleTheme}
        aria-label="Chuyển giao diện dark/light"
      >
        {theme === 'dark' ? '☀️ Chế độ sáng' : '🌙 Chế độ tối'}
      </button>
    </header>
  );
}
