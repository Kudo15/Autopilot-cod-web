// Journey 2 — Public mobile: shell + feed như desktop, sidebar qua nút ☰,
// không horizontal overflow.
import { expect, test } from '@playwright/test';

import {
  expectAllNavigationGroups,
  expectBrandedShell,
  expectFeedRenderedInDom,
  expectNoProvenanceInVisibleUi,
  expectPublicFeedClean,
} from './public-shell.js';

test.describe('Public mobile', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('public shell + feed without horizontal overflow', async ({ page }) => {
    await page.goto('/');

    await expectBrandedShell(page);

    // Sidebar mobile ẩn theo default, mở qua nút ☰.
    await expect(page.locator('.sidebar')).toBeHidden();
    await page.locator('button.sidebar-toggle').click();

    const items = page.locator('.sidebar .sidebar-item');
    await expect(items.first()).toBeVisible();
    await expectAllNavigationGroups(items);

    const articles = await expectPublicFeedClean(page);
    await expectFeedRenderedInDom(page, articles);
    await expectNoProvenanceInVisibleUi(page);

    // Đóng lại sidebar (như thao tác chọn nhóm) rồi kiểm tra overflow.
    // LƯU Ý (q2-browser-e2e, 27/10/2026): assertion overflow hiện FAIL vì
    // BUG THẬT ở frontend: form .header-search tràn phải (right=440px ở
    // viewport 390px) — .app-header flex thiếu flex-wrap; media query
    // ≤760px đặt .header-search { order: 3; width: 100% } mong xuống hàng
    // nhưng không có flex-wrap. Fix (src/styles.css, ngoài files_allowed
    // của task này): thêm `.app-header { flex-wrap: wrap; }` vào media
    // query (max-width: 760px). Sau khi sửa: test này phải PASS.
    await page.locator('.sidebar-item').first().click();
    await expect(page.locator('.sidebar')).toBeHidden();

    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth, `horizontal overflow: scrollWidth=${scrollWidth} > clientWidth=${clientWidth} + 1`).toBeLessThanOrEqual(
      clientWidth + 1
    );
  });
});
