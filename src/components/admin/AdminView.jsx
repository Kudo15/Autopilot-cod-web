import React from 'react';

// AdminView — bề mặt điều hành local cho luồng duyệt/xác minh (task 011).
//
// Tổ chức:
// - Nếu phiên chưa có token admin -> hiện AdminTokenForm. Token CHỈ nằm trong
//   state của component này (phiên), không ghi vào localStorage/sessionStorage.
// - Khi có token -> hai hook useAdminResource tải GET /api/admin/reviews và
//   GET /api/admin/sources; token là tham số của từng lời gọi adminClient.
// - Mỗi panel tự giữ trạng thái loading/empty/error/retry của mình, nên không có
//   spinner toàn trang che mất dữ liệu đã tải được.
import { useState } from 'react';
import { hasToken, loadReviews, loadSources } from './adminClient.js';
import { useAdminResource } from './useAdminResource.js';
import { AdminTokenForm } from './AdminTokenForm.jsx';
import { ReviewPanel } from './ReviewPanel.jsx';
import { SourcePanel } from './SourcePanel.jsx';
import { VerificationPanel } from './VerificationPanel.jsx';

export function AdminView() {
  //: Token admin runtime — bắt đầu rỗng ở mỗi lần mount; không đọc từ bất kỳ
  //: nơi lưu trữ bền nào và không có giá trị mặc định nào trong mã nguồn.
  const [token, setToken] = useState('');
  const reviews = useAdminResource(token, loadReviews);
  const sources = useAdminResource(token, loadSources);

  if (!hasToken(token)) {
    return (
      <section className="admin-view">
        <div className="group-view-header">
          <h2>Admin Radar</h2>
        </div>
        <p className="state-hint">
          Khu vực điều hành nội bộ. Nhập token admin để bắt đầu — token chỉ giữ trong phiên hiện
          tại và không bao giờ được lưu vào trình duyệt.
        </p>
        <AdminTokenForm initialToken="" onTokenChange={setToken} />
      </section>
    );
  }

  return (
    <section className="admin-view">
      <div className="group-view-header">
        <h2>Admin Radar</h2>
        <div className="state-controls">
          <span className="badge verif-verified">Phiên admin đã mở</span>
          <button
            type="button"
            className="btn btn-small btn-secondary"
            onClick={() => setToken('')}
          >
            Đăng xuất
          </button>
        </div>
      </div>

      <p className="state-hint">
        Token đang dùng cho mọi lời gọi <code>/api/admin/*</code> — chỉ tồn tại trong bộ nhớ phiên này.
      </p>

      <ReviewPanel resource={reviews} token={token} />
      <SourcePanel resource={sources} />
      <VerificationPanel token={token} />
    </section>
  );
}
