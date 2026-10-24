// Hook tải dữ liệu admin theo token phiên — quản lý 4 trạng thái: idle (chưa có
// token) / loading / ready / error, kèm retry. Loader phải là hàm module-level
// ổn định (loadReviews / loadSources) để effect không chạy lại mỗi lần render.
import { useEffect, useState } from 'react';
import { hasToken } from './adminClient.js';

const INITIAL = { status: 'idle', data: null, error: null };

export function useAdminResource(token, loader) {
  const [state, setState] = useState(INITIAL);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!hasToken(token)) {
      setState(INITIAL);
      return undefined;
    }
    let active = true;
    setState((previous) => ({ status: 'loading', data: previous.data, error: null }));

    loader(token)
      .then((data) => {
        if (active) setState({ status: 'ready', data, error: null });
      })
      .catch((error) => {
        if (active) setState({ status: 'error', data: null, error });
      });

    return () => {
      active = false;
    };
  }, [token, reloadKey, loader]);

  return {
    status: state.status,
    data: state.data,
    error: state.error,
    reload: () => setReloadKey((key) => key + 1),
  };
}
