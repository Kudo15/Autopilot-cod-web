// Playwright smoke harness — localhost only (Vũ Học AI Radar v1.0, task q2-browser-e2e).
//
// Chạy: npx playwright test  (hoặc npm run test:e2e)
// - Backend: uvicorn 127.0.0.1:8137 (khởi tạo DB idempotent qua lifespan).
// - Frontend: Vite dev server 127.0.0.1:5193 (proxy /api -> 8137).
// - Trình duyệt: dùng Chromium local trong %LOCALAPPDATA%\ms-playwright (không tải
//   browser, không gọi external site). Có thể ghi đè bằng PLAYWRIGHT_CHROMIUM_EXECUTABLE.
// - Playwright tự kill cả hai webServer khi chạy xong (bounded shutdown).
// - Dùng port riêng 8137/5193 (rảnh tại thời điểm viết) thay vì 8000/5173:
//   máy này còn các server dev mồ côi từ các lần chạy pipeline trước đang
//   giữ port 8000 và handle cache node_modules/.vite; port riêng giúp test
//   chạy sạch, không phụ thuộc vào server nào khác, không giết tiến trình
//   của ai. reuseExistingServer=false: nếu port bận thì test fail rõ ràng
//   (bounded) thay vì âm thầm test nhầm server cũ.
import { existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { defineConfig } from '@playwright/test';

const BACKEND_PORT = 8137;
const FRONTEND_PORT = 5193;

const LOCAL_CHROMIUM =
  process.platform === 'win32'
    ? path.join(
        process.env.LOCALAPPDATA ?? '',
        'ms-playwright',
        'chromium-1243',
        'chrome-win64',
        'chrome.exe'
      )
    : '';

const executablePath =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ??
  (existsSync(LOCAL_CHROMIUM) ? LOCAL_CHROMIUM : undefined);

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  // Artifact (error-context, .last-run) để ngoài repo — thư mục tạm của OS.
  // Unique-per-run: Playwright chỉ rmdir outputDir NẾU đã tồn tại, và trên
  // máy này rmdir đó dính EPERM (handle/scan lock).
  outputDir: path.join(os.tmpdir(), `vu-hoc-e2e-${new Date().toISOString().replace(/[:.]/g, '-')}`),
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    headless: true,
    launchOptions: {
      executablePath,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    },
    screenshot: 'off',
    trace: 'off',
    video: 'off',
  },
  webServer: [
    {
      command: `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      reuseExistingServer: false,
      timeout: 180_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}/`,
      reuseExistingServer: false,
      timeout: 90_000,
      env: { VITE_BACKEND_PORT: String(BACKEND_PORT) },
    },
  ],
});
