// Harness Node (không framework) chạy THẬT module client admin
// src/components/admin/adminClient.js với một fetch giả: kiểm chứng header
// Authorization, xử lý 401/403, hình dạng body gửi lên server, và việc token
// không bao giờ lộ ra URL/body/thông báo lỗi.
//
// Chạy: node backend/tests/admin_client_harness.mjs   (exit 0 = tất cả pass)
//
// Đây là harness của test, KHÔNG phải mã nguồn sản phẩm: token dùng ở đây được
// sinh ngẫu nhiên trong tiến trình, không hardcode giá trị nào.
import crypto from 'node:crypto';

const clientUrl = new URL('../../src/components/admin/adminClient.js', import.meta.url);
const client = await import(clientUrl.href);
const {
  ADMIN_REVIEW_ACTIONS,
  VERIFICATION_STATUSES,
  ADMIN_ENDPOINTS,
  AdminRequestError,
  adminHeaders,
  describeAdminError,
  describeAdminOutcome,
  hasToken,
  inputError,
  loadReviews,
  loadSources,
  submitArticleReview,
  submitProviderModelVerification,
} = client;

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

function eq(label, actual, expected) {
  check(`${label} (nhận ${JSON.stringify(actual)})`, JSON.stringify(actual) === JSON.stringify(expected));
}

const TOKEN = `harness-${crypto.randomBytes(16).toString('hex')}`;

//: fetch giả: ghi lại mọi lời gọi và trả về response dựng sẵn.
function fakeFetch({ status = 200, body = [], rawText = null, throwError = null } = {}) {
  const calls = [];
  return {
    calls,
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      if (throwError) throw throwError;
      const text = rawText !== null ? rawText : JSON.stringify(body);
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => JSON.parse(text),
        text: async () => text,
      };
    },
  };
}

//: Nhận một thunk để lỗi đồng bộ (guard allowlist) cũng được bắt như lỗi async.
async function rejected(thunk) {
  try {
    await thunk();
    return null;
  } catch (error) {
    return error;
  }
}

async function main() {
  console.log(`client: ${clientUrl.pathname}`);
  console.log('--- 1. token chỉ tồn tại trong tham số lời gọi ---');
  check('hasToken("") == false', hasToken('') === false);
  check('hasToken("   ") == false', hasToken('   ') === false);
  check('hasToken("abc") == true', hasToken('abc') === true);
  eq('adminHeaders() rỗng khi không có token', adminHeaders(''), {});
  eq('adminHeaders(token) chỉ có Authorization', adminHeaders(TOKEN), {
    Authorization: `Bearer ${TOKEN}`,
  });
  eq('adminHeaders(token, true) thêm Content-Type', adminHeaders(TOKEN, true), {
    Authorization: `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  });

  console.log('--- 2. thiếu token: chặn trước khi gọi mạng ---');
  {
    const { calls, fetchImpl } = fakeFetch();
    const error = await rejected(() => loadReviews('', fetchImpl));
    check('loadReviews("") là AdminRequestError', error instanceof AdminRequestError);
    eq('kind = missing-token', error?.kind, 'missing-token');
    check('không gọi fetch', calls.length === 0);
  }

  console.log('--- 3. 401 / 403 là lỗi UI an toàn ---');
  {
    const { calls, fetchImpl } = fakeFetch({ status: 401, body: { detail: 'admin token is required' } });
    const error = await rejected(() => loadReviews(TOKEN, fetchImpl));
    eq('401 -> kind unauthorized', error?.kind, 'unauthorized');
    eq('401 -> status', error?.status, 401);
    eq('401 -> method GET', calls[0]?.init?.method, 'GET');
    eq('401 -> Authorization: Bearer', calls[0]?.init?.headers?.Authorization, `Bearer ${TOKEN}`);
    check('401 -> không gửi Content-Type', calls[0]?.init?.headers?.['Content-Type'] === undefined);
    check('401 -> URL không chứa token', !String(calls[0]?.url).includes(TOKEN));
    check(
      '401 -> thông báo chung, không echo body server',
      !describeAdminError(error).includes('admin token is required')
    );
  }
  {
    const { fetchImpl } = fakeFetch({ status: 403, body: { detail: 'invalid admin token' } });
    const error = await rejected(() => loadSources(TOKEN, fetchImpl));
    eq('403 -> kind forbidden', error?.kind, 'forbidden');
    eq('403 -> status', error?.status, 403);
    eq('403 -> describeAdminOutcome level=c auth', describeAdminOutcome(error).level, 'auth');
  }

  console.log('--- 4. luồng đọc thành công ---');
  {
    const rows = [{ review_id: 1, article_id: 7, article_status: 'DRAFT' }];
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: rows });
    const data = await loadReviews(TOKEN, fetchImpl);
    eq('loadReviews trả mảng', data, rows);
    eq('gọi đúng endpoint', calls[0]?.url, ADMIN_ENDPOINTS.reviews);
    eq('không gửi body khi GET', calls[0]?.init?.body, undefined);
  }
  {
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: [{ source_id: 'src-1' }] });
    const data = await loadSources(TOKEN, fetchImpl);
    eq('loadSources trả mảng', data, [{ source_id: 'src-1' }]);
    eq('gọi đúng endpoint sources', calls[0]?.url, ADMIN_ENDPOINTS.sources);
  }

  console.log('--- 5. phản hồi sai định dạng ---');
  {
    const { fetchImpl } = fakeFetch({ status: 200, rawText: 'not json' });
    const error = await rejected(() => loadReviews(TOKEN, fetchImpl));
    eq('body không phải JSON -> malformed', error?.kind, 'malformed');
  }
  {
    const { fetchImpl } = fakeFetch({ status: 200, body: { detail: 'an object, not a list' } });
    const error = await rejected(() => loadReviews(TOKEN, fetchImpl));
    eq('JSON không phải mảng -> malformed', error?.kind, 'malformed');
  }

  console.log('--- 6. lỗi mạng và lỗi server ---');
  {
    const { fetchImpl } = fakeFetch({ throwError: new TypeError('Failed to fetch') });
    const error = await rejected(() => loadReviews(TOKEN, fetchImpl));
    eq('lỗi mạng -> kind network', error?.kind, 'network');
    check('lỗi mạng -> không lộ chi tiết thô', !describeAdminError(error).includes('Failed to fetch'));
  }
  {
    const { fetchImpl } = fakeFetch({
      status: 500,
      body: { detail: 'server is missing required ADMIN_TOKEN environment variable' },
    });
    const error = await rejected(() => loadReviews(TOKEN, fetchImpl));
    eq('500 -> kind server', error?.kind, 'server');
    eq('500 -> status', error?.status, 500);
    check(
      '500 -> hiển thị lý do an toàn của server',
      describeAdminError(error).includes('ADMIN_TOKEN environment variable')
    );
  }

  console.log('--- 7. hành động duyệt: chỉ gửi field trong allowlist ---');
  eq('allowlist hành động', ADMIN_REVIEW_ACTIONS, ['PENDING_REVIEW', 'REJECTED', 'PUBLISHED']);
  {
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: { review_id: 3, article_status: 'PENDING_REVIEW' } });
    const result = await submitArticleReview(TOKEN, 7, 'PENDING_REVIEW', '  xem lại tiêu đề  ', fetchImpl);
    eq('trả kết quả server', result?.review_id, 3);
    eq('POST tới endpoint bài 7', calls[0]?.url, ADMIN_ENDPOINTS.articleReview(7));
    eq('method POST', calls[0]?.init?.method, 'POST');
    eq('Content-Type JSON', calls[0]?.init?.headers?.['Content-Type'], 'application/json');
    eq('body chỉ có action + note đã trim', JSON.parse(calls[0]?.init?.body), {
      action: 'PENDING_REVIEW',
      note: 'xem lại tiêu đề',
    });
    check('body không chứa token', !String(calls[0]?.init?.body).includes(TOKEN));
    check('URL không chứa token', !String(calls[0]?.url).includes(TOKEN));
  }
  {
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: { review_id: 4 } });
    await submitArticleReview(TOKEN, 9, 'PUBLISHED', '   ', fetchImpl);
    eq('note rỗng không được gửi', JSON.parse(calls[0]?.init?.body), { action: 'PUBLISHED' });
  }
  {
    const { calls, fetchImpl } = fakeFetch();
    let error = null;
    try {
      await submitArticleReview(TOKEN, 1, 'DRAFT', 'x', fetchImpl);
    } catch (caught) {
      error = caught;
    }
    eq('hành động ngoài allowlist -> invalid-action', error?.kind, 'invalid-action');
    check('hành động không hợp lệ không gọi mạng', calls.length === 0);
  }
  {
    //: 409 + detail của server: UI hiển thị nguyên văn lý do, không tự đoán luật.
    const detail = 'publish requires an authenticated PENDING_REVIEW step first';
    const { fetchImpl } = fakeFetch({ status: 409, body: { detail } });
    const error = await rejected(() => submitArticleReview(TOKEN, 7, 'PUBLISHED', '', fetchImpl));
    const outcome = describeAdminOutcome(error);
    eq('409 -> level conflict', outcome.level, 'conflict');
    check('409 -> hiện lý do của server', outcome.text.includes(detail));
    check('409 -> không chứa token', !outcome.text.includes(TOKEN));
  }
  {
    const { fetchImpl } = fakeFetch({ status: 404, body: { detail: 'article 42 does not exist' } });
    const outcome = describeAdminOutcome(await rejected(() => submitArticleReview(TOKEN, 42, 'REJECTED', '', fetchImpl)));
    eq('404 -> level error', outcome.level, 'error');
    check('404 -> hiện lý do của server', outcome.text.includes('article 42 does not exist'));
  }

  console.log('--- 8. xác minh: allowlist status + bằng chứng tường minh ---');
  eq('allowlist trạng thái xác minh', VERIFICATION_STATUSES, [
    'VERIFIED',
    'UNVERIFIED',
    'STALE',
    'EXPIRED',
    'NEEDS_REVIEW',
  ]);
  {
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: { verification_record_id: 5, verification_status: 'VERIFIED' } });
    await submitProviderModelVerification(TOKEN, 1, 'VERIFIED', ' https://prov.example.test/pricing ', '', fetchImpl);
    eq('POST tới endpoint xác minh provider_model 1', calls[0]?.url, ADMIN_ENDPOINTS.providerModelVerification(1));
    eq('body chỉ có status + evidence', JSON.parse(calls[0]?.init?.body), {
      status: 'VERIFIED',
      evidence: 'https://prov.example.test/pricing',
    });
  }
  {
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: { verification_record_id: 6 } });
    await submitProviderModelVerification(TOKEN, 2, 'NEEDS_REVIEW', '', 'trang đổi layout', fetchImpl);
    eq('có thể dùng note thay evidence', JSON.parse(calls[0]?.init?.body), {
      status: 'NEEDS_REVIEW',
      note: 'trang đổi layout',
    });
  }
  {
    let throwCount = 0;
    const cases = [
      [TOKEN, 1, 'VERIFIED', '', ''],
      [TOKEN, 1, 'VERIFIED', '   ', '   '],
    ];
    for (const args of cases) {
      const { calls, fetchImpl } = fakeFetch();
      const error = await rejected(() => submitProviderModelVerification(...args, fetchImpl));
      if (error?.kind === 'invalid-evidence' && calls.length === 0) throwCount += 1;
    }
    eq('thiếu evidence/note -> chặn cả 2 trường hợp', throwCount, 2);
  }
  {
    const { calls, fetchImpl } = fakeFetch();
    const error = await rejected(() => submitProviderModelVerification(TOKEN, 1, 'OK', 'x', '', fetchImpl));
    eq('status ngoài allowlist -> invalid-status', error?.kind, 'invalid-status');
    check('status sai không gọi mạng', calls.length === 0);
  }
  {
    //: Không bao giờ gửi quota/rate/freshness tự nghĩ ra.
    const { calls, fetchImpl } = fakeFetch({ status: 200, body: { verification_record_id: 7 } });
    await submitProviderModelVerification(TOKEN, 3, 'STALE', 'https://x.test', 'cũ', fetchImpl);
    const body = JSON.parse(calls[0]?.init?.body);
    eq('body keys đúng allowlist', Object.keys(body).sort(), ['evidence', 'note', 'status']);
    for (const forbidden of ['daily_quota', 'rate_limit', 'last_verified', 'valid_until', 'freshness']) {
      check(`body không có ${forbidden}`, body[forbidden] === undefined);
    }
  }
  {
    const { fetchImpl } = fakeFetch({ status: 422, body: { detail: 'unknown fields: daily_quota' } });
    const outcome = describeAdminOutcome(
      await rejected(() => submitProviderModelVerification(TOKEN, 3, 'VERIFIED', 'https://x.test', '', fetchImpl))
    );
    check('422 -> hiện lý do server', outcome.text.includes('unknown fields: daily_quota'));
  }

  console.log('--- 9. token không bao giờ xuất hiện trong thông báo lỗi ---');
  {
    const errorCases = [
      await rejected(() => loadReviews(TOKEN, fakeFetch({ status: 401 }).fetchImpl)),
      await rejected(() => loadReviews(TOKEN, fakeFetch({ status: 403 }).fetchImpl)),
      await rejected(() => loadReviews(TOKEN, fakeFetch({ status: 500, body: { detail: 'boom' } }).fetchImpl)),
      await rejected(() => loadReviews(TOKEN, fakeFetch({ status: 200, rawText: '<html>' }).fetchImpl)),
      await rejected(() => loadReviews(TOKEN, fakeFetch({ throwError: new Error('socket') }).fetchImpl)),
      await rejected(() => submitArticleReview(TOKEN, 1, 'NOPE', '', fakeFetch().fetchImpl)),
      await rejected(() => submitProviderModelVerification(TOKEN, 1, 'NOPE', 'x', '', fakeFetch().fetchImpl)),
      inputError('nhập liệu sai'),
    ];
    let clean = 0;
    for (const error of errorCases) {
      const text = `${describeAdminError(error)}|${error?.message ?? ''}`;
      if (!text.includes(TOKEN) && text.trim() !== '') clean += 1;
    }
    eq('mọi thông báo lỗi đều khác rỗng và không chứa token', clean, errorCases.length);
  }
  {
    const error = new Error('lỗi lạ có thể chứa token ' + TOKEN);
    const text = describeAdminError(error);
    check('lỗi không xác định -> câu chung, không lộ nội dung thô', !text.includes(TOKEN) && text.length > 0);
  }

  console.log('--- 10. không có API lưu trữ bền nào trong module ---');
  {
    const source = await (await import('node:fs/promises')).readFile(clientUrl, 'utf8');
    //: Kiểm tra LỆNH GỌI thật (localStorage.setItem/getItem/removeItem…), không phải
    //: từ khoá trong bình luận/chuỗi mô tả. Module có thể nhắc localStorage trong
    //: docstring để giải thích lý do KHÔNG dùng — đó không phải truy cập thật.
    const usagePatterns = {
      localStorage: /\blocalStorage\s*\.\s*(getItem|setItem|removeItem|clear|key|length)/,
      sessionStorage: /\bsessionStorage\s*\.\s*(getItem|setItem|removeItem|clear|key|length)/,
      indexedDB: /\bindexedDB\s*\.\s*(open|deleteDatabase)/,
      documentCookie: /\bdocument\s*\.\s*cookie\b/,
      caches: /\bcaches\s*\.\s*(open|match|put|delete|keys)/,
    };
    for (const [label, pattern] of Object.entries(usagePatterns)) {
      check(`nguồn client không dùng ${label}`, !pattern.test(source));
    }
    check('nguồn client dùng header Authorization: Bearer', source.includes('Bearer '));
    check('nguồn client không dùng dangerouslySetInnerHTML', !source.includes('dangerouslySetInnerHTML'));
  }

  console.log('');
  const total = passed + failures.length;
  if (failures.length === 0) {
    console.log(`ALL PASS — ${passed}/${total} kiểm tra`);
    process.exit(0);
  }
  console.log(`FAILED — ${failures.length}/${total} kiểm tra hỏng:`);
  for (const label of failures) console.log(`  - ${label}`);
  process.exit(1);
}

main().catch((error) => {
  console.error('harness lỗi không mong đợi:', error);
  process.exit(2);
});
