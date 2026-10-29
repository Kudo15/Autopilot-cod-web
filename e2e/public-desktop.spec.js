// Journey 1 — Public desktop: branded shell, 7 nhóm điều hướng, public feed
// sạch marker registry/provenance (UI + response).
import { expect, test } from '@playwright/test';

import {
  expectAllNavigationGroups,
  expectBrandedShell,
  expectFeedRenderedInDom,
  expectNoProvenanceInVisibleUi,
  expectPublicFeedClean,
} from './public-shell.js';

test.describe('Public desktop', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('branded shell, 7 navigation groups, clean public feed', async ({ page }) => {
    await page.goto('/');

    await expectBrandedShell(page);

    // 7 nhóm điều hướng hiển thị trong sidebar desktop.
    const items = page.locator('.sidebar .sidebar-item');
    await expect(items.first()).toBeVisible();
    await expectAllNavigationGroups(items);

    // Public feed request + integrity của response.
    const articles = await expectPublicFeedClean(page);

    // Feed render thật trong DOM (bài PUBLISHED của nhóm mặc định).
    await expectFeedRenderedInDom(page, articles);

    // UI visible không lộ registry/provenance.
    await expectNoProvenanceInVisibleUi(page);

    // Điều hướng công khai: chuyển sang nhóm khác, feed không báo lỗi.
    await page.locator('.sidebar-item', { hasText: 'Chính sách & Quota' }).click();
    await expect(page.locator('.group-view h2')).toHaveText('Chính sách & Quota');
    await expect(page.locator('.state-error')).toHaveCount(0);
  });
});
