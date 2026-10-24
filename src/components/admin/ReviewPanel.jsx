// Panel duyệt bài: đọc GET /api/admin/reviews và ghi POST
// /api/admin/articles/{id}/review.
//
// Nguyên tắc:
// - UI không tự quyết định chuyển trạng thái nào hợp lệ. Cả ba hành động trong
//   allowlist đều hiển thị; server là bên từ chối (409/422) và lý do của server
//   được hiển thị nguyên văn, không suy diễn lại.
// - Ghi chú duyệt là dữ liệu admin gõ tay — render như text, không dựng HTML.
// - Vùng ghi chú đóng được bằng Escape hoặc nút Đóng (bàn phím dùng được).
import { useState } from 'react';
import {
  ADMIN_REVIEW_ACTIONS,
  describeAdminOutcome,
  inputError,
  submitArticleReview,
} from './adminClient.js';
import { AdminEmpty, AdminError, AdminLoading } from './AdminStates.jsx';

//: Nhãn tiếng Việt cho ba hành động — chỉ là nhãn hiển thị của allowlist.
const ACTION_LABELS = {
  PENDING_REVIEW: 'Đưa vào duyệt',
  REJECTED: 'Từ chối',
  PUBLISHED: 'Xuất bản',
};

function statusClass(status) {
  switch (status) {
    case 'PUBLISHED':
      return 'badge verif-verified';
    case 'PENDING_REVIEW':
      return 'badge verif-unverified';
    case 'REJECTED':
      return 'badge verif-expired';
    case 'DRAFT':
      return 'badge badge-unknown';
    default:
      return 'badge badge-unknown';
  }
}

function StatusBadge({ value }) {
  const label = typeof value === 'string' && value.trim() ? value : 'Chưa rõ';
  return <span className={statusClass(value)}>{label}</span>;
}

export function ReviewPanel({ resource, token }) {
  const [editingId, setEditingId] = useState(null);
  const [note, setNote] = useState('');
  const [pendingAction, setPendingAction] = useState(null);
  const [outcome, setOutcome] = useState(null);
  const [articleId, setArticleId] = useState('');

  const rows = Array.isArray(resource.data) ? resource.data : [];

  function closeEditor() {
    setEditingId(null);
    setNote('');
  }

  function openEditor(reviewId) {
    setEditingId(reviewId);
    setNote('');
    setOutcome(null);
  }

  async function submit(rawArticleId, action) {
    const trimmedId = String(rawArticleId).trim();
    if (!/^\d+$/.test(trimmedId) || Number(trimmedId) <= 0) {
      setOutcome({ level: 'error', text: inputError('Mã bài phải là số nguyên dương.').message });
      return;
    }
    const targetId = Number(trimmedId);
    setPendingAction(action);
    setOutcome(null);
    try {
      const result = await submitArticleReview(token, targetId, action, note);
      setOutcome({
        level: 'ok',
        text: `Đã ghi bước duyệt ${result?.review_status ?? action} cho bài #${targetId}` +
          ` (trạng thái bài: ${result?.article_status ?? 'không rõ'}).`,
      });
      closeEditor();
      setArticleId('');
      resource.reload();
    } catch (error) {
      setOutcome(describeAdminOutcome(error));
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <section className="admin-panel" aria-label="Duyệt bài">
      <div className="admin-panel-header">
        <h3>Duyệt bài</h3>
        <span className="admin-panel-count">{rows.length} bản ghi</span>
        <button type="button" className="btn btn-small btn-secondary" onClick={resource.reload}>
          Tải lại
        </button>
      </div>

      <p className="state-hint">
        Máy chủ quyết định bước duyệt hợp lệ (DRAFT → PENDING_REVIEW → PUBLISHED; REJECTED đưa bài về
        DRAFT). Bảng này chỉ gửi hành động và hiển thị lý do từ chối của máy chủ.
      </p>

      {resource.status === 'loading' && <AdminLoading label="Đang tải bản ghi duyệt từ /api/admin/reviews…" />}
      {resource.status === 'error' && (
        <AdminError
          error={resource.error}
          onRetry={resource.reload}
          label="Không tải được bản ghi duyệt."
        />
      )}

      {resource.status === 'ready' && rows.length === 0 && (
        <AdminEmpty
          icon="📋"
          title="Chưa có bản ghi duyệt nào."
          hint="Bản ghi xuất hiện sau khi một bài thật được đưa vào bước duyệt có xác thực."
        />
      )}

      {resource.status === 'ready' && rows.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table" aria-label="Bản ghi duyệt bài">
            <thead>
              <tr>
                <th>Bản ghi</th>
                <th>Bài</th>
                <th>Trạng thái bài</th>
                <th>Bước duyệt</th>
                <th>Ghi chú</th>
                <th>Thời điểm</th>
                <th>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isOpen = editingId === row.review_id;
                return (
                  <tr key={row.review_id}>
                    <td>#{row.review_id}</td>
                    <td>#{row.article_id}</td>
                    <td><StatusBadge value={row.article_status} /></td>
                    <td><StatusBadge value={row.review_status} /></td>
                    <td className="admin-note-cell">{row.reviewer_note || <span className="muted">—</span>}</td>
                    <td className="admin-time-cell">{row.reviewed_at || <span className="muted">—</span>}</td>
                    <td>
                      {isOpen ? (
                        <div
                          className="admin-action-editor"
                          role="group"
                          aria-label={`Hành động cho bài #${row.article_id}`}
                          onKeyDown={(event) => {
                            if (event.key === 'Escape') {
                              event.stopPropagation();
                              closeEditor();
                            }
                          }}
                        >
                          <label className="admin-note-label">
                            Ghi chú duyệt (không bắt buộc)
                            <input
                              type="text"
                              value={note}
                              onChange={(event) => setNote(event.target.value)}
                              placeholder="Lý do / ngữ cảnh cho bước duyệt"
                              autoFocus
                            />
                          </label>
                          <div className="admin-action-buttons">
                            {ADMIN_REVIEW_ACTIONS.map((action) => (
                              <button
                                key={action}
                                type="button"
                                className="btn btn-small"
                                disabled={pendingAction !== null}
                                onClick={() => submit(row.article_id, action)}
                              >
                                {pendingAction === action ? 'Đang gửi…' : ACTION_LABELS[action] ?? action}
                              </button>
                            ))}
                            <button
                              type="button"
                              className="btn btn-small btn-secondary"
                              onClick={closeEditor}
                              disabled={pendingAction !== null}
                            >
                              Đóng (Esc)
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-small btn-secondary"
                          onClick={() => openEditor(row.review_id)}
                          aria-expanded={false}
                        >
                          Thao tác…
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="admin-manual-action" role="group" aria-label="Thao tác theo mã bài">
        <label className="explorer-filter">
          Thao tác theo mã bài (khi bài chưa có trong sổ duyệt)
          <input
            type="number"
            min="1"
            step="1"
            value={articleId}
            onChange={(event) => setArticleId(event.target.value)}
            placeholder="vd. 1"
          />
        </label>
        <label className="explorer-filter admin-evidence-field">
          Ghi chú duyệt (không bắt buộc)
          <input
            type="text"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Lý do / ngữ cảnh cho bước duyệt"
          />
        </label>
        <div className="admin-action-buttons">
          {ADMIN_REVIEW_ACTIONS.map((action) => (
            <button
              key={action}
              type="button"
              className="btn btn-small"
              disabled={pendingAction !== null || articleId.trim() === ''}
              onClick={() => submit(articleId, action)}
            >
              {pendingAction === action ? 'Đang gửi…' : ACTION_LABELS[action] ?? action}
            </button>
          ))}
        </div>
      </div>

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
