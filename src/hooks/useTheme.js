import { useEffect, useState } from 'react';

export const THEME_STORAGE_KEY = 'vu-hoc-ai-radar-theme';
export const THEMES = ['dark', 'light'];

function readStoredTheme() {
  try {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') return saved;
  } catch {
    // localStorage có thể bị chặn (private mode) — dùng mặc định
  }
  return 'dark';
}

export function useTheme() {
  const [theme, setTheme] = useState(readStoredTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // bỏ qua nếu không lưu được
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'));
  }

  return { theme, toggleTheme };
}
