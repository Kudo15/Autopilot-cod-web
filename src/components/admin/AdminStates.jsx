// Các trạng thái dùng chung cho panel admin: loading / error+retry / empty.
// Mọi text từ API được render như text node của React (không dựng HTML).
import { describeAdminError } from './adminClient.js';

export function AdminLoading({ label }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true"></div>
      <p>{label}</p>
    </div>
  );
}

export function AdminError({ error, onRetry, label }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon" aria-hidden="true">⚠️</div>
      <p>{label}</p>
      <p className="state-hint">{describeAdminError(error)}</p>
      <button type="button" className="btn" onClick={onRetry}>
        Thử lại
      </button>
    </div>
  );
}

export function AdminEmpty({ icon, title, hint }) {
  return (
    <div className="state state-empty">
      <div className="state-icon" aria-hidden="true">{icon}</div>
      <p>{title}</p>
      {hint ? <p className="state-hint">{hint}</p> : null}
    </div>
  );
}
