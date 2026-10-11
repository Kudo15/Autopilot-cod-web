import { useEffect, useMemo, useState } from 'react';
import { Header } from './components/Header.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { GroupView } from './components/GroupView.jsx';
import { CONTENT_GROUPS, DEFAULT_GROUP_ID } from './data/groups.js';
import { useTheme } from './hooks/useTheme.js';

const LOADING_DURATION_MS = 450;

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [activeId, setActiveId] = useState(DEFAULT_GROUP_ID);
  const [reloadKey, setReloadKey] = useState(0);
  const [status, setStatus] = useState('loading'); // 'loading' | 'empty' | 'error'
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const activeGroup = useMemo(
    () => CONTENT_GROUPS.find((g) => g.id === activeId) ?? CONTENT_GROUPS[0],
    [activeId]
  );

  // Vào trạng thái loading khi chọn nhóm (hoặc bấm "Thử lại"),
  // sau đó chuyển sang empty — Phase 2 chưa có backend nên mọi
  // nhóm đều chưa có nội dung, không tạo dữ liệu giả.
  useEffect(() => {
    setStatus('loading');
    const timer = setTimeout(() => {
      setStatus((current) => (current === 'loading' ? 'empty' : current));
    }, LOADING_DURATION_MS);
    return () => clearTimeout(timer);
  }, [activeId, reloadKey]);

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
      />
      <div className="app-body">
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
            onRetry={() => setReloadKey((key) => key + 1)}
            onSimulateError={() => setStatus('error')}
            onReset={() => setStatus('empty')}
          />
        </main>
      </div>
    </div>
  );
}
