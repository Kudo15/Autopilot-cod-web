import React from 'react';

// Panel registry nguồn: đọc GET /api/admin/sources và hiển thị CHỈ các cột an
// toàn mà backend khai báo (ADMIN_SOURCE_FIELDS). Không bao giờ render payload
// thô, provenance hay nội dung nội bộ của nguồn.
import { AdminEmpty, AdminError, AdminLoading } from './AdminStates.jsx';

//: Chỉ mở link http(s) ra tab mới; URL lạ bị coi là văn bản thường.
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

function OriginBadge({ origin }) {
  const isSample = origin === 'SAMPLE';
  return (
    <span className={`badge ${isSample ? 'badge-unknown' : 'verif-verified'}`}>
      {isSample ? 'SAMPLE' : origin || 'REAL'}
    </span>
  );
}

export function SourcePanel({ resource }) {
  const rows = Array.isArray(resource.data) ? resource.data : [];

  return (
    <section className="admin-panel" aria-label="Registry nguồn">
      <div className="admin-panel-header">
        <h3>Registry nguồn</h3>
        <span className="admin-panel-count">{rows.length} nguồn</span>
        <button type="button" className="btn btn-small btn-secondary" onClick={resource.reload}>
          Tải lại
        </button>
      </div>

      <p className="state-hint">
        Chỉ hiển thị thông tin đăng ký/trạng thái của nguồn. Không hiển thị payload thô hay nội bộ.
      </p>

      {resource.status === 'loading' && <AdminLoading label="Đang tải registry nguồn từ /api/admin/sources…" />}
      {resource.status === 'error' && (
        <AdminError
          error={resource.error}
          onRetry={resource.reload}
          label="Không tải được registry nguồn."
        />
      )}

      {resource.status === 'ready' && rows.length === 0 && (
        <AdminEmpty icon="🗂️" title="Chưa có nguồn nào trong registry." />
      )}

      {resource.status === 'ready' && rows.length > 0 && (
        <div className="admin-table-wrap">
          <table className="admin-table" aria-label="Danh sách nguồn">
            <thead>
              <tr>
                <th>source_id</th>
                <th>Tên</th>
                <th>Loại</th>
                <th>URL</th>
                <th>Thu thập</th>
                <th>Ưu tiên</th>
                <th>Trạng thái</th>
                <th>Kiểm tra lần cuối</th>
                <th>Nguồn gốc</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const url = safeExternalUrl(row.url);
                return (
                  <tr key={row.source_id}>
                    <td><code className="api-id">{row.source_id}</code></td>
                    <td>{row.name}</td>
                    <td>{row.type}</td>
                    <td>
                      {url ? (
                        <a className="explorer-cta" href={url} target="_blank" rel="noreferrer">
                          mở ↗
                        </a>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{row.collection_method || <span className="muted">—</span>}</td>
                    <td>{row.priority ?? <span className="muted">—</span>}</td>
                    <td>{row.status || <span className="muted">—</span>}</td>
                    <td className="admin-time-cell">{row.last_checked_at || <span className="muted">—</span>}</td>
                    <td><OriginBadge origin={row.data_origin} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
