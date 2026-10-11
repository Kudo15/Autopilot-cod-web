// GroupView: hiển thị nội dung của nhóm đang chọn qua 3 trạng thái
// loading / empty / error — được quản lý bằng React state trong App.
// Phase 2: chưa có backend, nên trạng thái dữ liệu thật là empty (chưa có nội dung).
// Hai nút "Kiểm thử giao diện" chỉ dùng để quan sát trạng thái, không tạo dữ liệu giả.

function LoadingState({ groupName }) {
  return (
    <div className="state state-loading" role="status">
      <div className="spinner" aria-hidden="true"></div>
      <p>Đang tải nhóm {groupName}…</p>
    </div>
  );
}

function EmptyState({ groupName }) {
  return (
    <div className="state state-empty">
      <div className="state-icon" aria-hidden="true">📭</div>
      <p>
        Nhóm <strong>{groupName}</strong> hiện chưa có nội dung.
      </p>
      <p className="state-hint">Bài viết sẽ xuất hiện ở đây sau khi bộ thu thập hoạt động.</p>
    </div>
  );
}

function ErrorState({ groupName, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon" aria-hidden="true">⚠️</div>
      <p>
        Không tải được nội dung nhóm <strong>{groupName}</strong>.
      </p>
      <p className="state-hint">Kiểm tra kết nối hoặc thử lại sau ít phút.</p>
      <button type="button" className="btn" onClick={onRetry}>
        Thử lại
      </button>
    </div>
  );
}

export function GroupView({ group, status, onRetry, onSimulateError, onReset }) {
  return (
    <section className="group-view">
      <div className="group-view-header">
        <h2>{group.name}</h2>
        <div className="state-controls" aria-label="Kiểm thử giao diện">
          <span className="state-controls-label">Kiểm thử giao diện:</span>
          {status === 'error' ? (
            <button type="button" className="btn btn-small" onClick={onReset}>
              Về trang trống
            </button>
          ) : (
            <button type="button" className="btn btn-small" onClick={onSimulateError}>
              Mô phỏng lỗi
            </button>
          )}
        </div>
      </div>

      {status === 'loading' && <LoadingState groupName={group.name} />}
      {status === 'empty' && <EmptyState groupName={group.name} />}
      {status === 'error' && <ErrorState groupName={group.name} onRetry={onRetry} />}
    </section>
  );
}
