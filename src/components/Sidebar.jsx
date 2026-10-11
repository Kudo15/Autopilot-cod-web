export function Sidebar({ groups, activeId, onSelect, open }) {
  return (
    <nav className={`sidebar${open ? ' sidebar-open' : ''}`} aria-label="Điều hướng nhóm nội dung">
      <ul className="sidebar-list">
        {groups.map((group) => (
          <li key={group.id}>
            <button
              type="button"
              className={`sidebar-item${group.id === activeId ? ' sidebar-item-active' : ''}`}
              onClick={() => onSelect(group.id)}
              aria-current={group.id === activeId ? 'page' : undefined}
            >
              {group.name}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
