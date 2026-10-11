export function Header({ theme, onToggleTheme, onToggleSidebar }) {
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
