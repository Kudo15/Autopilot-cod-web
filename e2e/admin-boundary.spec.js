// Journey 3 — Admin boundary: request /api/admin/* KHÔNG kèm credential
// phải trả 401. Test không giữ, không gửi, không log token nào (không có
// ADMIN_TOKEN trong source/config của harness).
import { expect, test } from '@playwright/test';

const PROTECTED_ADMIN_ENDPOINTS = [
  { method: 'GET', path: '/api/admin/sources' },
  { method: 'GET', path: '/api/admin/reviews' },
  { method: 'GET', path: '/api/admin/inbox/runs' },
  { method: 'POST', path: '/api/admin/radar/refresh' },
];

test.describe('Admin boundary', () => {
  test('unauthenticated admin requests are rejected with 401', async ({ page }) => {
    await page.goto('/');

    for (const { method, path } of PROTECTED_ADMIN_ENDPOINTS) {
      // page.request dùng network stack của chính context (cùng origin,
      // không có cookie/header credential nào).
      const response = await page.request.fetch(path, { method });

      expect(response.status(), `${method} ${path} phải trả 401 khi thiếu token`).toBe(401);
      // Không leak trạng thái cấu hình server (500) hay data.
      const body = await response.text();
      expect(body.length).toBeGreaterThan(0);
      const detail = JSON.parse(body)?.detail ?? '';
      expect(detail).not.toMatch(/ADMIN_TOKEN=|token is:|expected token/i);
    }
  });
});
