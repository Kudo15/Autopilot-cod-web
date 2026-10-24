// Harness Node: RENDER THẬT các component admin (React 19 + react-dom/server) sau
// khi được esbuild biên dịch JSX — bằng chứng cho trạng thái loading/empty/error,
// việc escape text (không dựng HTML), và việc UI không nhận link/URL nguy hiểm.
//
// Chạy: node backend/tests/admin_ui_render_harness.mjs   (exit 0 = tất cả pass)
//
// Không có trình duyệt nào tham gia: đây là render phía server của đúng các
// component trong src/components/admin/. Hành vi tương tác (click/Escape) cần DOM
// thật nên KHÔNG được khẳng định ở đây.
import { build } from 'esbuild';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HARNESS_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HARNESS_DIR, '..', '..');
const ADMIN = path.join(ROOT, 'src', 'components', 'admin');

const TOKEN = 'render-harness-token-not-a-secret';

const entry = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AdminTokenForm } from ${JSON.stringify(path.join(ADMIN, 'AdminTokenForm.jsx'))};
import { ReviewPanel } from ${JSON.stringify(path.join(ADMIN, 'ReviewPanel.jsx'))};
import { SourcePanel } from ${JSON.stringify(path.join(ADMIN, 'SourcePanel.jsx'))};
import { VerificationPanel } from ${JSON.stringify(path.join(ADMIN, 'VerificationPanel.jsx'))};
import { AdminError, AdminEmpty, AdminLoading } from ${JSON.stringify(path.join(ADMIN, 'AdminStates.jsx'))};
import { AdminRequestError } from ${JSON.stringify(path.join(ADMIN, 'adminClient.js'))};

const noop = () => {};
const html = {};
const R = (element) => renderToStaticMarkup(element);

html.tokenForm = R(React.createElement(AdminTokenForm, { initialToken: '', onTokenChange: noop }));
html.tokenFormWithClose = R(React.createElement(AdminTokenForm, { initialToken: '', onTokenChange: noop, onClose: noop }));
html.reviewLoading = R(React.createElement(ReviewPanel, {
  resource: { status: 'loading', data: null, error: null, reload: noop }, token: ${JSON.stringify(TOKEN)},
}));
html.reviewError401 = R(React.createElement(ReviewPanel, {
  resource: { status: 'error', data: null, error: new AdminRequestError('unauthorized', 401, 'x'), reload: noop },
  token: ${JSON.stringify(TOKEN)},
}));
html.reviewError403 = R(React.createElement(ReviewPanel, {
  resource: { status: 'error', data: null, error: new AdminRequestError('forbidden', 403, 'x'), reload: noop },
  token: ${JSON.stringify(TOKEN)},
}));
html.reviewErrorNetwork = R(React.createElement(ReviewPanel, {
  resource: { status: 'error', data: null, error: new AdminRequestError('network', 0, 'x'), reload: noop },
  token: ${JSON.stringify(TOKEN)},
}));
html.reviewEmpty = R(React.createElement(ReviewPanel, {
  resource: { status: 'ready', data: [], error: null, reload: noop }, token: ${JSON.stringify(TOKEN)},
}));
html.reviewReadyRow = R(React.createElement(ReviewPanel, {
  resource: {
    status: 'ready', error: null, reload: noop,
    data: [{
      review_id: 9, article_id: 7, article_status: 'PENDING_REVIEW', review_status: 'PENDING_REVIEW',
      reviewer_note: '<img src=x onerror=alert(1)> & "quoted"', ranking_suggestion: null,
      content_safety: null, reviewed_at: '2026-10-25T00:00:00+00:00', data_origin: 'REAL', created_at: null,
    }],
  },
  token: ${JSON.stringify(TOKEN)},
}));
html.sourceReadyRow = R(React.createElement(SourcePanel, {
  resource: {
    status: 'ready', error: null, reload: noop,
    data: [{
      source_id: 'src-<b>1</b>', name: '<script>alert(1)</script>', type: 'rss',
      url: 'javascript:alert(1)', collection_method: 'rss', priority: 3, status: 'active',
      last_checked_at: null, data_origin: 'SAMPLE', created_at: '2026-10-25T00:00:00Z',
    }],
  },
}));
html.sourceEmpty = R(React.createElement(SourcePanel, {
  resource: { status: 'ready', data: [], error: null, reload: noop },
}));
html.verificationForm = R(React.createElement(VerificationPanel, { token: ${JSON.stringify(TOKEN)} }));
html.states = R(React.createElement('div', null,
  React.createElement(AdminLoading, { label: 'ĐANG TẢI' }),
  React.createElement(AdminEmpty, { icon: 'x', title: 'TRỐNG', hint: 'gợi ý' }),
  React.createElement(AdminError, { error: new AdminRequestError('server', 500, 'boom'), onRetry: noop, label: 'LỖI' }),
));
globalThis.__ssrHtml = html;
`;

let passed = 0;
const failures = [];

function check(label, condition) {
  if (condition) {
    passed += 1;
    console.log(`  ok   ${label}`);
  } else {
    failures.push(label);
    console.log(`  FAIL ${label}`);
  }
}

function count(text, needle) {
  return text.split(needle).length - 1;
}

async function main() {
  const workdir = await fs.mkdtemp(path.join(os.tmpdir(), 'ssr-admin-'));
  const outfile = path.join(workdir, 'render.cjs');
  await build({
    stdin: { contents: entry, resolveDir: ROOT, loader: 'jsx', sourcefile: 'ssr-admin-entry.jsx' },
    bundle: true,
    format: 'cjs',
    platform: 'node',
    jsx: 'automatic',
    outfile,
    logLevel: 'silent',
  });
  await import(pathToFileURL(outfile).href);
  const html = globalThis.__ssrHtml;
  check('esbuild đã render được các component admin', html && typeof html.tokenForm === 'string');

  console.log('--- 1. khung nhập token ---');
  check('có input type=password (che token)', html.tokenForm.includes('type="password"'));
  //: React SSR giữ nguyên camelCase autoComplete="off" — HTML không phân biệt hoa/thường.
  check('autocomplete tắt', /autocomplete="off"/i.test(html.tokenForm));
  check('không có giá trị token nào trong markup khi khung rỗng',
    !html.tokenForm.includes('value="') || html.tokenForm.includes('value=""'));
  check('nêu rõ token chỉ giữ trong phiên', html.tokenForm.includes('phiên'));
  check('có aria-label cho vùng đăng nhập admin', html.tokenForm.includes('aria-label="Đăng nhập khu vực admin"'));

  console.log('--- 2. ReviewPanel: bốn trạng thái ---');
  check('loading: role=status', html.reviewLoading.includes('role="status"'));
  check('loading: thông báo đang tải endpoint reviews', html.reviewLoading.includes('/api/admin/reviews'));
  check('error 401: role=alert', html.reviewError401.includes('role="alert"'));
  check('error 401: nêu mã 401', html.reviewError401.includes('401'));
  check('error 403: nêu mã 403', html.reviewError403.includes('403'));
  check('error 403: nhắc nhập lại token', html.reviewError403.includes('Nhập lại token'));
  check('error network: hướng dẫn kiểm tra backend', html.reviewErrorNetwork.includes('127.0.0.1:8000'));
  check('error: có nút Thử lại', html.reviewError403.includes('Thử lại'));
  check('empty: có trạng thái trống', html.reviewEmpty.includes('Chưa có bản ghi duyệt nào'));
  check('ready: bảng có aria-label', html.reviewReadyRow.includes('aria-label="Bản ghi duyệt bài"'));
  check('ready: hiện mã bài và bước duyệt', html.reviewReadyRow.includes('#7') && html.reviewReadyRow.includes('PENDING_REVIEW'));
  check('ready: có 3 nút hành động', ['Đưa vào duyệt', 'Từ chối', 'Xuất bản'].every((l) => html.reviewReadyRow.includes(l)));
  check('ready: có form thao tác theo mã bài', html.reviewReadyRow.includes('Thao tác theo mã bài'));
  check('empty cũng có form thao tác theo mã bài (không kẹt khi sổ rỗng)',
    html.reviewEmpty.includes('Thao tác theo mã bài'));

  console.log('--- 3. text không tin cậy được render thành TEXT, không phải HTML ---');
  //: Chuỗi độc hại phải xuất hiện DƯỚI DẠNG ĐÃ ESCAPE, và không được tạo thẻ HTML thật.
  check('reviewer_note bị escape (&lt;img)', html.reviewReadyRow.includes('&lt;img src=x'));
  check('chuỗi độc hại xuất hiện nguyên vẹn dạng escape', html.reviewReadyRow.includes('&lt;img src=x onerror=alert(1)&gt;'));
  check('reviewer_note không tạo thẻ img thật', !/<img\s/.test(html.reviewReadyRow));
  check('không có thuộc tính onerror thật ngoài văn bản đã escape',
    (/onerror=/.test(html.reviewReadyRow)) === html.reviewReadyRow.includes('&lt;img src=x onerror=alert(1)&gt;'));
  check('dấu ngoặc kép trong note bị escape', html.reviewReadyRow.includes('&quot;quoted&quot;'));
  check('tên nguồn độc hại bị escape (&lt;script&gt;)', html.sourceReadyRow.includes('&lt;script&gt;'));
  check('source_id độc hại bị escape', html.sourceReadyRow.includes('src-&lt;b&gt;1&lt;/b&gt;'));
  check('không thẻ script thật nào trong markup nguồn', !html.sourceReadyRow.includes('<script>'));

  console.log('--- 4. URL nguy hiểm không thành link ---');
  check('javascript: không tạo href', !html.sourceReadyRow.includes('javascript:'));
  check('URL không hợp lệ hiển thị dấu —', html.sourceReadyRow.includes('—'));
  check('không có target=_blank cho URL nguy hiểm', !html.sourceReadyRow.includes('target="_blank"'));

  console.log('--- 5. panel xác minh: allowlist + không bịa quota/freshness ---');
  const optionValues = (html.verificationForm.match(/<option[^>]*value="([A-Z_]+)"/g) || [])
    .map((tag) => tag.split('value="')[1].replace('"', ''));
  check('select chỉ có 5 trạng thái allowlist', JSON.stringify(optionValues) === JSON.stringify(
    ['VERIFIED', 'UNVERIFIED', 'STALE', 'EXPIRED', 'NEEDS_REVIEW']));
  check('form yêu cầu mã provider_model', html.verificationForm.includes('Mã provider_model'));
  check('form yêu cầu bằng chứng/ghi chú tường minh', html.verificationForm.includes('Bằng chứng'));
  //: Từ "quota" chỉ xuất hiện trong GIẢI THÍCH "không gửi quota", không có input quota.
  const quotaCtx = html.verificationForm.toLowerCase();
  check('nói rõ không gửi quota (giải thích, không phải input)',
    quotaCtx.includes('không gửi quota') || quotaCtx.includes('không gửi quota hay mốc'));
  check('không có trường nhập quota/rate/freshness',
    !/<input[^>]*name="(daily_quota|rate_limit|last_verified|valid_until)"/.test(html.verificationForm));
  check('không có label quota trong form xác minh',
    !html.verificationForm.includes('label') || !/<label[^>]*>[^<]*quota/i.test(html.verificationForm));
  check('nói rõ không gửi mốc freshness tự nghĩ ra', html.verificationForm.includes('tự nghĩ ra'));

  console.log('--- 6. token không xuất hiện trong markup render ---');
  const all = Object.values(html).join('\n');
  check('markup không chứa giá trị token dùng để render', !all.includes(TOKEN));

  console.log('--- 7. trạng thái dùng chung ---');
  check('AdminLoading có role=status', html.states.includes('role="status"'));
  check('AdminEmpty hiển thị tiêu đề', html.states.includes('TRỐNG'));
  check('AdminError có role=alert và nút thử lại',
    html.states.includes('role="alert"') && html.states.includes('Thử lại'));

  await fs.rm(workdir, { recursive: true, force: true });

  console.log('');
  const total = passed + failures.length;
  if (failures.length === 0) {
    console.log(`ALL PASS — ${passed}/${total} kiểm tra render`);
    process.exit(0);
  }
  console.log(`FAILED — ${failures.length}/${total} kiểm tra render hỏng:`);
  for (const label of failures) console.log(`  - ${label}`);
  process.exit(1);
}

main().catch((error) => {
  console.error('harness render lỗi:', error);
  process.exit(2);
});
