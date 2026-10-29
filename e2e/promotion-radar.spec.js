// E2E test cho Promotion Radar (Task R1): UI navigation, API allowlist, và exclusion của SAMPLE/code.
import { expect, test } from '@playwright/test';

import { expectBrandedShell } from './public-shell.js';

test.describe('Promotion Radar (AI Deals & Promotions)', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('navigates to ai-deals, calls /api/offers, never leaks code or SAMPLE', async ({ page }) => {
    await page.goto('/');
    await expectBrandedShell(page);

    // Chuyển sang nhóm "AI Deals & Promotions"
    const dealsNav = page.locator('.sidebar-item', { hasText: 'AI Deals & Promotions' });
    await expect(dealsNav).toBeVisible();
    await dealsNav.click();

    // Header của PromotionView hiển thị đúng
    await expect(page.locator('.promotion-view h2')).toHaveText('AI Deals & Promotions');
    await expect(page.locator('.promotion-view')).toBeVisible();

    // Không rơi vào trạng thái error
    await expect(page.locator('.state-error')).toHaveCount(0);

    // Body không chứa mã promo nội bộ hay dữ liệu SAMPLE
    const bodyText = await page.innerText('body');
    expect(bodyText).not.toContain('SAMPLE_CODE_DEMO');
    expect(bodyText).not.toContain('SAMPLE_SECRET');

    // Kiểm tra trực tiếp API /api/offers qua proxy browser
    const response = await page.request.get('/api/offers');
    expect(response.status()).toBe(200);

    const data = await response.json();
    const offers = Array.isArray(data) ? data : data.offers;
    expect(Array.isArray(offers)).toBe(true);

    for (const offer of offers) {
      expect(offer).not.toHaveProperty('code');
      expect(offer).not.toHaveProperty('data_origin');
      expect(offer.verification_status).toBe('VERIFIED');
      expect(offer.is_active).toBe(true);
      expect(offer.official_url).toMatch(/^https?:\/\//);
    }

    // Unknown query param bị chặn 422
    const badResponse = await page.request.get('/api/offers?unknown_param=1');
    expect(badResponse.status()).toBe(422);
  });
});
