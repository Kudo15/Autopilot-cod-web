import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'vu-hoc-ai-bookmarks';
const LEGACY_KEYS = ['bookmarks', 'bookmarkedArticles'];
const STORAGE_VERSION = 1;

function readIds() {
  if (typeof window === 'undefined') return [];
  for (const key of [STORAGE_KEY, ...LEGACY_KEYS]) {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(key) || '[]');
      const values = Array.isArray(parsed) ? parsed : (parsed?.version === STORAGE_VERSION && Array.isArray(parsed.ids) ? parsed.ids : null);
      if (values) {
        const ids = [...new Set(values.map((item) => (typeof item === 'object' ? item?.id : item)).filter((id) => id !== null && id !== undefined).map(String))];
        if (key !== STORAGE_KEY && ids.length) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
        return ids;
      }
    } catch { /* malformed legacy storage is ignored defensively */ }
  }
  return [];
}

export function useBookmarks() {
  const [ids, setIds] = useState(readIds);
  useEffect(() => { window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, ids })); }, [ids]);

  const toggle = useCallback((id) => {
    const stableId = String(id);
    setIds((current) => current.includes(stableId) ? current.filter((item) => item !== stableId) : [...current, stableId]);
  }, []);

  return { bookmarkIds: ids, isBookmarked: (id) => ids.includes(String(id)), toggleBookmark: toggle };
}
