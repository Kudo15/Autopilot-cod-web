// Khung nhập token admin. Token CHỈ nằm trong state phiên của component cha:
// không ghi localStorage/sessionStorage/cookie, không đưa vào bundle, không hiện
// trong bất kỳ render JSON/error nào. Khi cấu hình đã có sẵn (phiên admin) thì
// ẩn khung để giữ trải nghiệm gọn; người dùng vẫn có thể thoát ra và nhập lại.
import React from 'react';
import { useState } from 'react';
import { hasToken } from './adminClient.js';

export function AdminTokenForm({ initialToken, onTokenChange, onClose }) {
  const [value, setValue] = useState(initialToken);

  function submit() {
    onTokenChange(value.trim());
  }

  return (
    <div className="admin-token-panel" role="region" aria-label="Đăng nhập khu vực admin">
      <label className="explorer-filter">
        Token admin (chỉ giữ trong phiên, không lưu trình duyệt)
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="Nhập token admin…"
          aria-required="true"
        />
      </label>
      <div className="admin-token-actions">
        <button type="button" className="btn" onClick={submit} disabled={!hasToken(value)}>
          Mở bảng điều khiển
        </button>
        {typeof onClose === 'function' ? (
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Đóng
          </button>
        ) : null}
      </div>
      <p className="state-hint">
        Token chỉ tồn tại trong phiên trình duyệt này và được gửi qua header
        <code> Authorization: Bearer</code> cho các endpoint admin. Không bao giờ lưu vào trình duyệt.
      </p>
    </div>
  );
}
