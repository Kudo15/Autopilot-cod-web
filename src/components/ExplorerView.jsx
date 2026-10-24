// ExplorerView — nhóm "Free Model Explorer" (Phase 7, phần UI).
//
// Gọi GET /api/models và hiển thị đúng những gì backend trả về. Mọi text từ
// API là dữ liệu KHÔNG tin cậy — chỉ render thành React text node, không dựng
// HTML từ chuỗi. Trạng thái xác minh được hiển thị nguyên trạng: UNKNOWN /
// UNVERIFIED / NULL không bao giờ bị nâng cấp thành một sự thật.
//
// KHÔNG có dữ liệu seed provider/model trong src/. Kho dữ liệu thật có thể
// đang rỗng (chỉ có bản ghi SAMPLE) — trạng thái đó được GIẢI THÍCH, không
// bịa ra card.

import { useEffect, useMemo, useState } from 'react';

const EXPLORER_API = '/api/models';

//: Nhãn hiển thị cho các giá trị free_status hợp lệ (MISSION mục 5).
const FREE_STATUS_LABELS = {
  FREE_API: 'Miễn phí qua API',
  FREE_CREDIT: 'Credit miễn phí',
  FREE_TRIAL: 'Dùng thử miễn phí',
  FREE_WEB_ONLY: 'Miễn phí (web)',
  PROMO: 'Khuyến mãi',
  PAID: 'Trả phí',
  UNKNOWN: 'Chưa rõ',
};

const CAPABILITIES = [
  { key: 'vision', name: 'Vision' },
  { key: 'tools', name: 'Tools' },
  { key: 'json', name: 'JSON' },
];

const CARD_OPTIONS = [
  { value: '', label: 'Tất cả' },
  { value: '0', label: 'Không cần thẻ' },
  { value: '1', label: 'Cần thẻ' },
];

const CAPABILITY_OPTIONS = [
  { value: '', label: 'Mọi khả năng' },
  { value: 'text', label: 'Text' },
  { value: 'vision', label: 'Vision' },
  { value: 'tools', label: 'Tools' },
  { value: 'json', label: 'JSON' },
];

function rowKey(row) {
  return `${row.model_id}|${row.provider_id}`;
}

//: Chỉ cho mở link http(s) ra tab mới — chặn scheme lạ (vd. javascript:).
function safeExternalUrl(value) {
  if (typeof value !== 'string' || value.trim() === '') return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return value;
  } catch {
    return null;
  }
  return null;
}

function formatCount(value) {
  if (value === null || value === undefined || value === '') return 'Chưa rõ';
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString('vi-VN') : String(value);
}

function matchesFilters(row, filters) {
  if (filters.freeStatus && row.free_status !== filters.freeStatus) return false;

  if (filters.provider) {
    const query = filters.provider.trim().toLowerCase();
    if (query) {
      const name = (row.provider_name ?? '').toLowerCase();
      const id = (row.provider_id ?? '').toLowerCase();
      if (!name.includes(query) && !id.includes(query)) return false;
    }
  }

  if (filters.cardRequired) {
    // NULL không thoả điều kiện 0 lẫn 1 — cùng luật với API công khai.
    if (row.card_required !== Number(filters.cardRequired)) return false;
  }

  if (filters.capability && filters.capability !== 'text') {
    // NULL tuyệt đối không được coi là "có khả năng".
    if (row[`supports_${filters.capability}`] !== 1) return false;
  }

  return true;
}

function VerificationBadge({ status }) {
  let label = 'Chưa rõ (UNKNOWN)';
  let className = 'verif-unknown';
  switch (status) {
    case 'VERIFIED':
      label = 'Đã xác minh';
      className = 'verif-verified';
      break;
    case 'UNVERIFIED':
      label = 'Chưa xác minh (UNVERIFIED)';
      className = 'verif-unverified';
      break;
    case 'STALE':
      label = 'Dữ liệu cũ (STALE)';
      className = 'verif-stale';
      break;
    case 'EXPIRED':
      label = 'Hết hạn (EXPIRED)';
      className = 'verif-expired';
      break;
    case 'NEEDS_REVIEW':
      label = 'Cần xem lại (NEEDS_REVIEW)';
      className = 'verif-review';
      break;
    default:
      break;
  }
  return <span className={`badge ${className}`}>{label}</span>;
}

function FreeStatusBadge({ status }) {
  const value = status ?? 'UNKNOWN';
  const label = FREE_STATUS_LABELS[value] ?? 'Chưa rõ';
  let className = 'badge-free';
  if (value === 'PAID') className = 'badge-paid';
  else if (value === 'UNKNOWN') className = 'badge-unknown';
  return <span className={`badge ${className}`}>{label}</span>;
}

function CapabilitiesCell({ row }) {
  return (
    <div className="cap-list">
      {CAPABILITIES.map(({ key, name }) => {
        const value = row[`supports_${key}`];
        let text = `${name}: chưa rõ`;
        let className = 'cap cap-unk';
        if (value === 1) {
          text = `${name}: có`;
          className = 'cap cap-yes';
        } else if (value === 0) {
          text = `${name}: không`;
          className = 'cap cap-no';
        }
        return (
          <span key={key} className={className}>
            {text}
          </span>
        );
      })}
    </div>
  );
}

function cardLabel(row) {
  if (row.card_required === 1) return 'Cần thẻ';
  if (row.card_required === 0) return 'Không cần thẻ';
  return 'Chưa rõ';
}

function ModelCells({ row }) {
  const url = safeExternalUrl(row.official_url);
  return (
    <>
      <td>
        <div className="model-name">{row.model_name}</div>
        <div className="provider-name">{row.provider_name}</div>
      </td>
      <td>{row.api_model_id ? <code className="api-id">{row.api_model_id}</code> : <span className="muted">—</span>}</td>
      <td>
        <FreeStatusBadge status={row.free_status} />
      </td>
      <td>
        <div>Rate: {row.rate_limit || 'Chưa rõ'}</div>
        <div>Quota: {formatCount(row.daily_quota)}</div>
      </td>
      <td>{formatCount(row.context_window)}</td>
      <td>
        <CapabilitiesCell row={row} />
      </td>
      <td>{cardLabel(row)}</td>
      <td>
        <VerificationBadge status={row.verification_status} />
        {row.last_verified ? <div className="verif-time">cập nhật: {row.last_verified}</div> : null}
      </td>
      <td>
        {url ? (
          <a className="explorer-cta" href={url} target="_blank" rel="noreferrer">
            Trang chính thức ↗
          </a>
        ) : (
          <span className="muted">—</span>
        )}
      </td>
    </>
  );
}

function LoadingState() {
  return (
    <div className="state state-loading" role="status">
      <div className="spinner" aria-hidden="true"></div>
      <p>Đang tải danh sách model/provider từ /api/models…</p>
    </div>
  );
}

function EmptyState({ hasAnyRows, onResetFilters }) {
  if (!hasAnyRows) {
    return (
      <div className="state state-empty">
        <div className="state-icon" aria-hidden="true">🔍</div>
        <p>Chưa có dữ liệu model/provider thật trong kho dữ liệu.</p>
        <p className="state-hint">
          Hiện tại chỉ có các bản ghi mẫu (SAMPLE) nên nhóm này đang trống — API công khai chỉ trả dữ liệu thật.
          Danh sách sẽ xuất hiện ở đây sau khi bộ thu thập dữ liệu và quy trình xác minh hoạt động.
        </p>
      </div>
    );
  }
  return (
    <div className="state state-empty">
      <div className="state-icon" aria-hidden="true">🔍</div>
      <p>Không có model nào khớp bộ lọc hiện tại.</p>
      <p className="state-hint">Thử nới lỏng bộ lọc ở phía trên.</p>
      <button type="button" className="btn" onClick={onResetFilters}>
        Bỏ bộ lọc
      </button>
    </div>
  );
}

function ErrorState({ onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon" aria-hidden="true">⚠️</div>
      <p>Không tải được danh sách model/provider từ /api/models.</p>
      <p className="state-hint">Kiểm tra kết nối backend hoặc thử lại sau ít phút.</p>
      <button type="button" className="btn" onClick={onRetry}>
        Thử lại
      </button>
    </div>
  );
}

function CompareTable({ rows }) {
  return (
    <div className="explorer-table-wrap">
      <table className="explorer-table" aria-label="Bảng so sánh model/provider">
        <thead>
          <tr>
            <th>Model / Provider</th>
            <th>API model id</th>
            <th>Miễn phí</th>
            <th>Quota / Rate</th>
            <th>Context</th>
            <th>Khả năng</th>
            <th>Thẻ</th>
            <th>Xác minh</th>
            <th>Link</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              <ModelCells row={row} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExplorerView({ group }) {
  const [status, setStatus] = useState('loading');
  const [rows, setRows] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);

  const [freeStatus, setFreeStatus] = useState('');
  const [provider, setProvider] = useState('');
  const [cardRequired, setCardRequired] = useState('');
  const [capability, setCapability] = useState('');

  const [comparing, setComparing] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState(() => new Set());

  useEffect(() => {
    const controller = new AbortController();

    setStatus('loading');
    fetch(EXPLORER_API, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Model explorer request failed: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        if (!Array.isArray(data)) {
          throw new Error('Model explorer response must be an array');
        }
        setRows(data);
        setStatus('ready');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setStatus('error');
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  const filters = useMemo(
    () => ({ freeStatus, provider, cardRequired, capability }),
    [freeStatus, provider, cardRequired, capability]
  );

  const filteredRows = useMemo(
    () => rows.filter((row) => matchesFilters(row, filters)),
    [rows, filters]
  );

  const selectedRows = useMemo(
    () => rows.filter((row) => selectedKeys.has(rowKey(row))),
    [rows, selectedKeys]
  );

  function resetFilters() {
    setFreeStatus('');
    setProvider('');
    setCardRequired('');
    setCapability('');
  }

  function toggleCompareRow(row) {
    const key = rowKey(row);
    setSelectedKeys((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <section className="explorer-view">
      <div className="group-view-header">
        <h2>{group.name}</h2>
      </div>

      {status === 'loading' && <LoadingState />}
      {status === 'error' && <ErrorState onRetry={() => setReloadKey((key) => key + 1)} />}

      {status === 'ready' && (
        <>
          <div className="explorer-filters">
            <label className="explorer-filter">
              Trạng thái miễn phí
              <select value={freeStatus} onChange={(event) => setFreeStatus(event.target.value)}>
                <option value="">Tất cả</option>
                {Object.entries(FREE_STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="explorer-filter">
              Provider
              <input
                type="text"
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
                placeholder="Tên hoặc ID provider"
              />
            </label>
            <label className="explorer-filter">
              Yêu cầu thẻ
              <select value={cardRequired} onChange={(event) => setCardRequired(event.target.value)}>
                {CARD_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="explorer-filter">
              Khả năng
              <select value={capability} onChange={(event) => setCapability(event.target.value)}>
                {CAPABILITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <span className="explorer-filter-count">{filteredRows.length} kết quả</span>
            <button
              type="button"
              className="btn btn-small"
              onClick={() => setComparing((current) => !current)}
              aria-pressed={comparing}
            >
              {comparing ? 'Đóng so sánh' : 'So sánh model'}
            </button>
          </div>

          {comparing && (
            <div className="explorer-compare-bar">
              {selectedRows.length > 0 ? (
                <>
                  <strong>Đang so sánh {selectedRows.length} model</strong>
                  <button type="button" className="btn btn-small" onClick={() => setSelectedKeys(new Set())}>
                    Bỏ chọn tất cả
                  </button>
                </>
              ) : (
                <span>Tích chọn ở cột đầu để đưa model vào bảng so sánh (lựa chọn chỉ tồn tại trong phiên này).</span>
              )}
            </div>
          )}

          {filteredRows.length > 0 ? (
            <div className="explorer-table-wrap">
              <table className="explorer-table" aria-label="Bảng model/provider">
                <thead>
                  <tr>
                    {comparing && <th aria-label="Chọn so sánh"></th>}
                    <th>Model / Provider</th>
                    <th>API model id</th>
                    <th>Miễn phí</th>
                    <th>Quota / Rate</th>
                    <th>Context</th>
                    <th>Khả năng</th>
                    <th>Thẻ</th>
                    <th>Xác minh</th>
                    <th>Link</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr key={rowKey(row)}>
                      {comparing && (
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedKeys.has(rowKey(row))}
                            onChange={() => toggleCompareRow(row)}
                            aria-label={`Chọn so sánh ${row.model_name} / ${row.provider_name}`}
                          />
                        </td>
                      )}
                      <ModelCells row={row} />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState hasAnyRows={rows.length > 0} onResetFilters={resetFilters} />
          )}

          {comparing && selectedRows.length > 0 && <CompareTable rows={selectedRows} />}
        </>
      )}
    </section>
  );
}
