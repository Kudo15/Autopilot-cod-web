// Panel xác minh model/provider: ghi POST
// /api/admin/provider-models/{id}/verification.
//
// Nguyên tắc:
// - CHỈ gửi status (allowlist) + evidence/note tường minh. Không bao giờ gửi
//   quota, rate limit hay mốc freshness tự nghĩ ra — server từ chối field lạ 422.
// - Trạng thái/mốc thời gian hiển thị là dữ liệu THẬT server trả về; UI không
//   nâng cấp UNVERIFIED/NULL thành "đã xác minh".
// - UI không tự suy ra mã provider_model: người vận hành nhập mã, server là bên
//   quyết định bản ghi có tồn tại và có phải SAMPLE hay không (404/409).
import { useState } from 'react';
import {
  describeAdminOutcome,
  inputError,
  submitProviderModelVerification,
  VERIFICATION_STATUSES,
} from './adminClient.js';

const STATUS_LABELS = {
  VERIFIED: 'Đã xác minh',
  UNVERIFIED: 'Chưa xác minh',
  STALE: 'Dữ liệu cũ',
  EXPIRED: 'Hết hạn',
  NEEDS_REVIEW: 'Cần xem lại',
};

export function VerificationPanel({ token }) {
  const [providerModelId, setProviderModelId] = useState('');
  const [status, setStatus] = useState(VERIFICATION_STATUSES[0]);
  const [evidence, setEvidence] = useState('');
  const [note, setNote] = useState('');
  const [pending, setPending] = useState(false);
  const [outcome, setOutcome] = useState(null);

  async function submit() {
    setPending(true);
    setOutcome(null);
    try {
      const trimmedId = providerModelId.trim();
      if (!/^\d+$/.test(trimmedId) || Number(trimmedId) <= 0) {
        throw inputError('Mã provider_model phải là số nguyên dương.');
      }
      const id = Number(trimmedId);
      const result = await submitProviderModelVerification(token, id, status, evidence, note);
      setOutcome({
        level: 'ok',
        text:
          `Đã ghi bản xác minh #${result?.verification_record_id ?? '?'} cho provider_model #${id}` +
          ` (trạng thái: ${result?.verification_status ?? status}).`,
      });
      setEvidence('');
      setNote('');
    } catch (error) {
      setOutcome(describeAdminOutcome(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="admin-panel" aria-label="Xác minh model/provider">
      <div className="admin-panel-header">
        <h3>Xác minh model/provider</h3>
      </div>

      <p className="state-hint">
        Ghi một bản xác minh đã xác thực. Chỉ gửi trạng thái + bằng chứng/ghi chú tường minh — không
        gửi quota hay mốc thời gian tự nghĩ ra (máy chủ từ chối field lạ bằng 422).
      </p>

      <form
        className="admin-verif-form"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label className="explorer-filter">
          Mã provider_model (bắt buộc)
          <input
            type="number"
            min="1"
            step="1"
            value={providerModelId}
            onChange={(event) => setProviderModelId(event.target.value)}
            placeholder="vd. 1"
            required
          />
        </label>
        <label className="explorer-filter">
          Trạng thái xác minh (allowlist)
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {VERIFICATION_STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value] ?? value}
              </option>
            ))}
          </select>
        </label>
        <label className="explorer-filter admin-evidence-field">
          Bằng chứng (URL/nguồn — bắt buộc nếu chưa có ghi chú)
          <input
            type="text"
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            placeholder="https://…/pricing (tài liệu đã xem)"
          />
        </label>
        <label className="explorer-filter admin-evidence-field">
          Ghi chú (bắt buộc nếu chưa có bằng chứng)
          <input
            type="text"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Đã kiểm trang chính thức…"
          />
        </label>
        <button type="submit" className="btn" disabled={pending || providerModelId.trim() === ''}>
          {pending ? 'Đang ghi…' : 'Ghi bản xác minh'}
        </button>
      </form>

      {outcome ? (
        <p
          className={`admin-result admin-result-${outcome.level}`}
          role={outcome.level === 'ok' ? 'status' : 'alert'}
        >
          {outcome.text}
        </p>
      ) : null}
    </section>
  );
}
