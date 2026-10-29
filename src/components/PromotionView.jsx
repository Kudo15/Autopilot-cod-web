import React from 'react';
import { useEffect, useState } from 'react';

//: Nhãn hiển thị loại ưu đãi (offer_type).
const OFFER_TYPE_LABELS = {
  FREE_API: 'Miễn phí API',
  FREE_CREDIT: 'Free Credits',
  FREE_TRIAL: 'Dùng thử miễn phí',
  FREE_WEB_ONLY: 'Miễn phí (web)',
  PROMO: 'Khuyến mãi đặc biệt',
  PAID: 'Trả phí',
  UNKNOWN: 'Chưa rõ',
};

//: Các lựa chọn trạng thái hiển thị: active là mặc định.
const STATUS_OPTIONS = [
  { value: 'active', label: 'Đang hoạt động (VERIFIED + còn hạn)' },
  { value: 'VERIFIED', label: 'Tất cả đã xác minh (lịch sử)' },
  { value: 'UNVERIFIED', label: 'Chưa xác minh' },
  { value: 'EXPIRED', label: 'Đã hết hạn' },
  { value: 'STALE', label: 'Dữ liệu cũ' },
  { value: 'NEEDS_REVIEW', label: 'Cần xem lại' },
];

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

function VerificationBadge({ status, isActive }) {
  let label = 'Chưa rõ';
  let className = 'verif-unknown';
  switch (status) {
    case 'VERIFIED':
      label = isActive ? 'Đã xác minh · Active' : 'Đã xác minh (hết hạn / không CTA)';
      className = isActive ? 'verif-verified' : 'verif-stale';
      break;
    case 'UNVERIFIED':
      label = 'Chưa xác minh (UNVERIFIED)';
      className = 'verif-unverified';
      break;
    case 'EXPIRED':
      label = 'Hết hạn (EXPIRED)';
      className = 'verif-expired';
      break;
    case 'STALE':
      label = 'Dữ liệu cũ (STALE)';
      className = 'verif-stale';
      break;
    case 'NEEDS_REVIEW':
      label = 'Cần xem lại';
      className = 'verif-review';
      break;
    default:
      label = status || 'Chưa rõ';
      break;
  }
  return <span className={`badge ${className}`}>{label}</span>;
}

function formatDeadline(timestamp) {
  if (!timestamp) return null;
  try {
    const d = new Date(timestamp);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return null;
  }
}

function OfferCard({ offer }) {
  const ctaUrl = safeExternalUrl(offer.official_url);
  const providerDisplay = offer.provider_name || offer.provider || offer.provider_id || 'Nhà cung cấp';
  const typeLabel = OFFER_TYPE_LABELS[offer.offer_type] || offer.offer_type || 'Ưu đãi';
  const endsText = formatDeadline(offer.ends_at || offer.valid_until);

  return (
    <article className="offer-card" aria-labelledby={`offer-title-${offer.id}`}>
      <div className="offer-card-top">
        <span className="offer-provider">{providerDisplay}</span>
        <span className="badge badge-free">{typeLabel}</span>
      </div>

      <h3 id={`offer-title-${offer.id}`} className="offer-title">
        {offer.title}
      </h3>

      {offer.description && (
        <p className="offer-description">{offer.description}</p>
      )}

      {offer.terms && (
        <div className="offer-terms">
          <strong>Điều kiện:</strong> {offer.terms}
        </div>
      )}

      <div className="offer-meta">
        <div className="offer-eligibility">
          <span className={`eligibility-tag ${offer.account_required === 0 ? 'eligibility-free' : ''}`}>
            {offer.account_required === 1 ? 'Cần tài khoản' : offer.account_required === 0 ? 'Không cần tài khoản' : 'Tài khoản: chưa rõ'}
          </span>
          <span className={`eligibility-tag ${offer.card_required === 0 ? 'eligibility-free' : ''}`}>
            {offer.card_required === 1 ? 'Cần thẻ tín dụng' : offer.card_required === 0 ? 'Không cần thẻ' : 'Thẻ: chưa rõ'}
          </span>
        </div>

        <div className="offer-status-line">
          <VerificationBadge status={offer.verification_status} isActive={offer.is_active} />
          {endsText && (
            <span className="offer-deadline">
              Hạn dùng: {endsText}
            </span>
          )}
        </div>
      </div>

      <div className="offer-card-actions">
        {ctaUrl && offer.is_active ? (
          <a
            className="btn btn-small offer-cta-btn"
            href={ctaUrl}
            target="_blank"
            rel="noreferrer"
          >
            Nhận ưu đãi chính thức ↗
          </a>
        ) : (
          <span className="muted offer-no-cta">
            {!ctaUrl ? 'Không có link CTA chính thức' : 'Ưu đãi không còn hiệu lực'}
          </span>
        )}
      </div>
    </article>
  );
}

export function PromotionView() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('active');
  const [offerType, setOfferType] = useState('');
  const [offers, setOffers] = useState([]);
  const [fetchState, setFetchState] = useState('loading');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (status) params.set('status', status);
    if (offerType) params.set('offer_type', offerType);
    params.set('limit', '50');

    setFetchState('loading');
    fetch(`/api/offers?${params.toString()}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Promotion request failed: ${response.status}`);
        }
        return response.json();
      })
      .then((data) => {
        const list = Array.isArray(data) ? data : Array.isArray(data.offers) ? data.offers : [];
        setOffers(list);
        setFetchState('ready');
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setFetchState('error');
        }
      });

    return () => controller.abort();
  }, [query, status, offerType, reloadKey]);

  return (
    <section className="promotion-view" aria-label="Promotion Radar">
      <div className="group-view-header">
        <h2>AI Deals &amp; Promotions</h2>
      </div>

      <p className="state-hint">
        Theo dõi khuyến mãi, free credits, trial và ưu đãi AI đã được xác minh.
        Dữ liệu mẫu (SAMPLE), ưu đãi hết hạn hoặc thiếu link chính thức tuyệt đối không được xuất hiện như ưu đãi active.
      </p>

      <div className="explorer-filters">
        <label className="explorer-filter">
          Tìm kiếm ưu đãi
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tên ưu đãi, mô tả hoặc điều kiện…"
          />
        </label>

        <label className="explorer-filter">
          Trạng thái
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        <label className="explorer-filter">
          Loại ưu đãi
          <select value={offerType} onChange={(event) => setOfferType(event.target.value)}>
            <option value="">Tất cả loại ưu đãi</option>
            {Object.entries(OFFER_TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <span className="explorer-filter-count">{offers.length} ưu đãi</span>

        {(query || status !== 'active' || offerType) && (
          <button
            type="button"
            className="btn btn-small btn-secondary"
            onClick={() => {
              setQuery('');
              setStatus('active');
              setOfferType('');
            }}
          >
            Mặc định (Active)
          </button>
        )}
      </div>

      {fetchState === 'loading' && (
        <div className="state state-loading" role="status">
          <div className="spinner" aria-hidden="true"></div>
          <p>Đang tải ưu đãi từ Promotion Radar…</p>
        </div>
      )}

      {fetchState === 'error' && (
        <div className="state state-error" role="alert">
          <div className="state-icon" aria-hidden="true">⚠️</div>
          <p>Không tải được dữ liệu ưu đãi từ /api/offers.</p>
          <p className="state-hint">Kiểm tra kết nối tới backend localhost rồi thử lại.</p>
          <button type="button" className="btn" onClick={() => setReloadKey((k) => k + 1)}>
            Thử lại
          </button>
        </div>
      )}

      {fetchState === 'ready' && offers.length === 0 && (
        <div className="state state-empty">
          <div className="state-icon" aria-hidden="true">🎁</div>
          <p>
            {status === 'active'
              ? 'Hiện chưa có ưu đãi VERIFIED đang hoạt động trong hệ thống.'
              : 'Không tìm thấy ưu đãi nào khớp với bộ lọc hiện tại.'}
          </p>
          <p className="state-hint">
            Hệ thống chỉ hiển thị ưu đãi thật (REAL) có bằng chứng xác minh và link chính thức.
            Các bản ghi mẫu (SAMPLE) hoặc đã hết hạn bị loại bỏ để đảm bảo thông tin chính xác.
          </p>
        </div>
      )}

      {fetchState === 'ready' && offers.length > 0 && (
        <div className="offer-grid">
          {offers.map((offer) => (
            <OfferCard key={offer.id} offer={offer} />
          ))}
        </div>
      )}
    </section>
  );
}
