// Shared assertions cho journey "public" (desktop + mobile) — task q2-browser-e2e.
// Không có secret nào ở đây; chỉ kiểm tra dữ liệu public.
import { expect } from '@playwright/test';

import { CONTENT_GROUPS, DEFAULT_GROUP_ID } from '../src/data/groups.js';

// Marker của source registry / provenance nội bộ — không bao giờ được lộ ra
// UI public hay response /api/*. Nếu backend thêm field nội bộ mới, test phải
// cập nhật danh sách này.
export const PROVENANCE_MARKERS = [
  'source_id',
  'data_origin',
  'provenance',
  'registry',
  'quarantine',
  'sample_rss_demo',
  'sample_manual_demo',
];

export const ARTICLES_PUBLIC_FIELDS = new Set([
  'id', 'title', 'url', 'source', 'category', 'summary', 'published_at', 'created_at',
]);

export async function expectBrandedShell(page) {
  await expect(page).toHaveTitle('Vũ Học AI Radar v1.0');
  await expect(page.locator('.brand-badge')).toHaveText('VŨ HỌC');
  await expect(page.locator('h1.brand-title')).toHaveText('AI Radar');
}

export async function expectAllNavigationGroups(items) {
  expect(items).toHaveCount(CONTENT_GROUPS.length); // 7 nhóm
  const names = await items.allTextContents();
  expect(names.map((n) => n.trim())).toEqual(CONTENT_GROUPS.map((g) => g.name));
}

// Gọi public feed qua đúng origin của browser context (đi qua proxy Vite
// như người dùng thực), rồi kiểm tra: 200, array, chỉ có field public,
// không marker registry/provenance trong cả raw response.
export async function expectPublicFeedClean(page) {
  const response = await page.request.get('/api/articles');
  expect(response.status()).toBe(200);

  const raw = await response.text();
  const lowered = raw.toLowerCase();
  for (const marker of PROVENANCE_MARKERS) {
    expect(lowered, `marker nội bộ "${marker}" lộ trong /api/articles`).not.toContain(marker);
  }

  const articles = JSON.parse(raw);
  expect(Array.isArray(articles)).toBe(true);
  for (const article of articles) {
    const keys = Object.keys(article);
    const nonPublic = keys.filter((key) => !ARTICLES_PUBLIC_FIELDS.has(key));
    expect(nonPublic, `field nội bộ trong /api/articles: ${nonPublic.join(', ')}`).toEqual([]);
  }
  return articles;
}

// Mọi bài PUBLISHED thuộc nhóm đang hiển thị phải hiện thật trong DOM.
export async function expectFeedRenderedInDom(page, articles) {
  const visible = articles.filter((article) => article.category === DEFAULT_GROUP_ID);
  for (const article of visible) {
    await expect(
      page.locator('.article-card', { hasText: article.title }).first(),
      `bài "${article.title}" không hiển thị trong feed`
    ).toBeVisible();
  }
}

export async function expectNoProvenanceInVisibleUi(page) {
  const bodyText = (await page.innerText('body')).toLowerCase();
  for (const marker of PROVENANCE_MARKERS) {
    expect(bodyText, `marker nội bộ "${marker}" lộ trong UI public`).not.toContain(marker);
  }
}
