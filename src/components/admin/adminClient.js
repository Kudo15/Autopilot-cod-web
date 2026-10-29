// Client thuần cho các API admin đã có ở backend (P8b). Không có JSX, không phụ
// thuộc React/DOM, nên chạy được cả trong trình duyệt lẫn Node (harness test).
//
// Hợp đồng an toàn (task 011):
// - Token admin CHỈ được truyền vào từng lời gọi (tham số), lấy từ state của
//   phiên. Module này không đọc/ghi localStorage, sessionStorage hay cookie, và
//   không giữ token ở đâu ngoài tham số của lời gọi.
// - Token chỉ đi vào header `Authorization: Bearer <token>`; không bao giờ vào
//   URL hay body JSON.
// - Thông báo lỗi không bao giờ chứa giá trị token; 401/403 chỉ trả về thông báo
//   chung, không echo nội dung server.
// - UI KHÔNG tự suy diễn luật publish/verify: hành động không hợp lệ vẫn được gửi
//   (hoặc bị chặn bằng allowlist phía client) và server là bên phán quyết; lý do
//   an toàn của server được hiển thị nguyên văn.

//: Ba hành động duyệt bài UI được phép hiển thị — khớp allowlist của backend.
export const ADMIN_REVIEW_ACTIONS = ['PENDING_REVIEW', 'REJECTED', 'PUBLISHED'];

//: Trạng thái xác minh hợp lệ — khớp CHECK constraint của verification_records.
export const VERIFICATION_STATUSES = [
  'VERIFIED',
  'UNVERIFIED',
  'STALE',
  'EXPIRED',
  'NEEDS_REVIEW',
];

//: Bốn endpoint admin đã có. UI chỉ là client, không tự nghĩ ra endpoint khác.
export const ADMIN_ENDPOINTS = {
  reviews: '/api/admin/reviews',
  sources: '/api/admin/sources',
  articleReview: (articleId) => `/api/admin/articles/${encodeURIComponent(String(articleId))}/review`,
  providerModelVerification: (providerModelId) =>
    `/api/admin/provider-models/${encodeURIComponent(String(providerModelId))}/verification`,
  offerVerification: (offerId) =>
    `/api/admin/offers/${encodeURIComponent(String(offerId))}/verification`,
};

//: Chi tiết lỗi server tối đa được hiển thị (không cắt giữa ký tự).
const MAX_DETAIL_LENGTH = 200;

export class AdminRequestError extends Error {
  constructor(kind, status, message) {
    super(message);
    this.name = 'AdminRequestError';
    this.kind = kind;
    //: 0 = lỗi phía client (chưa gọi mạng hoặc lỗi mạng), ngược lại là HTTP status.
    this.status = status;
  }
}

//: Lỗi nhập liệu phía client (chưa gọi mạng) — dùng chung một hình dạng lỗi để UI
//: xử lý thống nhất và không bao giờ hiển thị nội dung lạ.
export function inputError(message) {
  return new AdminRequestError('invalid-input', 0, message);
}

export function hasToken(token) {
  return typeof token === 'string' && token.trim() !== '';
}

//: Header chuẩn: token CHỈ nằm trong Authorization, không nơi nào khác.
export function adminHeaders(token, withJson = false) {
  const headers = {};
  if (hasToken(token)) headers.Authorization = `Bearer ${token.trim()}`;
  if (withJson) headers['Content-Type'] = 'application/json';
  return headers;
}

//: Chỉ đọc `detail` dạng chuỗi (lý do an toàn của server), đã cắt ngắn. Không
//: bao giờ trả nguyên body thô — tránh render cấu trúc nội bộ ra UI.
async function safeServerDetail(response) {
  try {
    const text = await response.text();
    if (!text) return '';
    try {
      const parsed = JSON.parse(text);
      const detail = parsed && typeof parsed.detail === 'string' ? parsed.detail : '';
      return detail.slice(0, MAX_DETAIL_LENGTH);
    } catch {
      return '';
    }
  } catch {
    return '';
  }
}

async function requestJson(path, options = {}) {
  const { token, method = 'GET', body, fetchImpl } = options;
  if (!hasToken(token)) {
    throw new AdminRequestError(
      'missing-token',
      0,
      'Chưa có token admin trong phiên này.'
    );
  }
  const doFetch = fetchImpl ?? globalThis.fetch;
  if (typeof doFetch !== 'function') {
    throw new AdminRequestError('unavailable', 0, 'Không có hàm fetch để gọi API admin.');
  }

  const hasBody = body !== undefined;
  let response;
  try {
    response = await doFetch(path, {
      method,
      headers: adminHeaders(token, hasBody),
      body: hasBody ? JSON.stringify(body) : undefined,
    });
  } catch {
    //: Không đưa nội dung lỗi mạng thô lên UI (có thể chứa URL/chi tiết nội bộ).
    throw new AdminRequestError('network', 0, 'Không gọi được API admin.');
  }

  if (response.status === 401) {
    throw new AdminRequestError('unauthorized', 401, 'API admin yêu cầu token.');
  }
  if (response.status === 403) {
    throw new AdminRequestError('forbidden', 403, 'Token admin bị từ chối.');
  }
  if (!response.ok) {
    const detail = await safeServerDetail(response);
    throw new AdminRequestError('server', response.status, detail);
  }
  try {
    return await response.json();
  } catch {
    throw new AdminRequestError('malformed', response.status, 'Phản hồi admin không phải JSON.');
  }
}

async function requestList(path, options = {}) {
  const data = await requestJson(path, options);
  if (!Array.isArray(data)) {
    throw new AdminRequestError('malformed', 200, 'Phản hồi admin không phải mảng.');
  }
  return data;
}

export function loadReviews(token, fetchImpl) {
  return requestList(ADMIN_ENDPOINTS.reviews, { token, fetchImpl });
}

export function loadSources(token, fetchImpl) {
  return requestList(ADMIN_ENDPOINTS.sources, { token, fetchImpl });
}

export function submitArticleReview(token, articleId, action, note, fetchImpl) {
  if (!ADMIN_REVIEW_ACTIONS.includes(action)) {
    throw new AdminRequestError('invalid-action', 0, `Hành động duyệt không được hỗ trợ: ${action}.`);
  }
  //: Chỉ gửi các field trong allowlist của backend (action, note).
  const payload = { action };
  const trimmedNote = typeof note === 'string' ? note.trim() : '';
  if (trimmedNote) payload.note = trimmedNote;
  return requestJson(ADMIN_ENDPOINTS.articleReview(articleId), {
    token,
    method: 'POST',
    body: payload,
    fetchImpl,
  });
}

export function submitProviderModelVerification(
  token,
  providerModelId,
  status,
  evidence,
  note,
  fetchImpl
) {
  if (!VERIFICATION_STATUSES.includes(status)) {
    throw new AdminRequestError('invalid-status', 0, `Trạng thái xác minh không hợp lệ: ${status}.`);
  }
  //: Chỉ gửi status/evidence/note — không bao giờ gửi quota, rate limit hay mốc
  //: thời gian "tự nghĩ ra" (server từ chối field lạ bằng 422).
  const payload = { status };
  const trimmedEvidence = typeof evidence === 'string' ? evidence.trim() : '';
  const trimmedNote = typeof note === 'string' ? note.trim() : '';
  if (trimmedEvidence) payload.evidence = trimmedEvidence;
  if (trimmedNote) payload.note = trimmedNote;
  if (!trimmedEvidence && !trimmedNote) {
    throw new AdminRequestError('invalid-evidence', 0, 'Cần bằng chứng hoặc ghi chú cụ thể.');
  }
  return requestJson(ADMIN_ENDPOINTS.providerModelVerification(providerModelId), {
    token,
    method: 'POST',
    body: payload,
    fetchImpl,
  });
}

export function submitOfferVerification(
  token,
  offerId,
  status,
  evidence,
  note,
  fetchImpl
) {
  if (!VERIFICATION_STATUSES.includes(status)) {
    throw new AdminRequestError('invalid-status', 0, `Trạng thái xác minh không hợp lệ: ${status}.`);
  }
  const payload = { status };
  const trimmedEvidence = typeof evidence === 'string' ? evidence.trim() : '';
  const trimmedNote = typeof note === 'string' ? note.trim() : '';
  if (trimmedEvidence) payload.evidence = trimmedEvidence;
  if (trimmedNote) payload.note = trimmedNote;
  if (!trimmedEvidence && !trimmedNote) {
    throw new AdminRequestError('invalid-evidence', 0, 'Cần bằng chứng hoặc ghi chú cụ thể.');
  }
  return requestJson(ADMIN_ENDPOINTS.offerVerification(offerId), {
    token,
    method: 'POST',
    body: payload,
    fetchImpl,
  });
}

//: Chuyển lỗi thành câu tiếng Việt an toàn để render. Không bao giờ chứa token;
//: với lỗi phía server thì kèm lý do đã cắt ngắn của server (không tự đoán).
export function describeAdminError(error) {
  if (!(error instanceof AdminRequestError)) {
    return 'Lỗi không xác định khi gọi API admin.';
  }
  switch (error.kind) {
    case 'missing-token':
      return 'Chưa có token admin trong phiên. Hãy nhập token ở khung trên.';
    case 'unavailable':
      return 'Trình duyệt không có hàm fetch để gọi API admin.';
    case 'network':
      return 'Không gọi được API admin (lỗi mạng). Kiểm tra backend 127.0.0.1:8000 rồi thử lại.';
    case 'unauthorized':
      return 'API admin yêu cầu token (401). Nhập token admin để tiếp tục.';
    case 'forbidden':
      return 'Token admin không đúng hoặc đã bị xoay (403). Nhập lại token.';
    case 'malformed':
      return 'Phản hồi admin không đúng định dạng JSON mong đợi.';
    case 'invalid-action':
    case 'invalid-status':
    case 'invalid-evidence':
    case 'invalid-input':
      return error.message;
    case 'server':
      return error.message
        ? `Máy chủ từ chối yêu cầu (${error.status}): ${error.message}`
        : `Máy chủ trả về lỗi ${error.status}.`;
    default:
      return 'Không thực hiện được yêu cầu admin.';
  }
}

//: Mô tả ngắn cho UI: 409 là "server từ chối chuyển trạng thái", 404 là thiếu
//: bản ghi, 422 là body sai — UI chỉ hiển thị, không tự suy diễn luật.
export function describeAdminOutcome(error) {
  if (error instanceof AdminRequestError && error.status === 409) {
    return { level: 'conflict', text: describeAdminError(error) };
  }
  if (error instanceof AdminRequestError && (error.status === 401 || error.status === 403)) {
    return { level: 'auth', text: describeAdminError(error) };
  }
  return { level: 'error', text: describeAdminError(error) };
}
