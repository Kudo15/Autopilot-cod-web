"""Trọng tài PHASE 5 — nối FE↔BE: vite proxy /api + feed lấy từ SQLite thật.

Bằng chứng thật: BẬT backend (uvicorn :8000) + BẬT vite dev, rồi gọi `/api/articles` QUA PROXY và
so với gọi trực tiếp backend — dữ liệu phải giống nhau và không rỗng. Không đọc code để đoán.

Hợp đồng (ghi trong PLAN.md phase 5):
    backend:  uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
    vite dev: npm run dev   (proxy /api -> http://127.0.0.1:8000)
Chạy: python checks/p5.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib as L  # noqa: E402

BACKEND_PORT = 8000          # hợp đồng: proxy trỏ đúng cổng này

L.header(5, "nối FE↔BE: proxy /api + feed từ SQLite thật")

# --- 1. proxy trong vite.config.js
cfg = L.read("vite.config.js")
L.check(bool(cfg.strip()), "có vite.config.js", "THIẾU vite.config.js")
proxy_entry = re.search(r"['\"]?/api['\"]?\s*:", cfg) is not None
L.check(proxy_entry and str(BACKEND_PORT) in cfg,
        f"vite.config.js có proxy '/api' trỏ cổng {BACKEND_PORT}",
        "vite.config.js thiếu proxy '/api' -> 127.0.0.1:8000")

# --- 2. frontend gọi API (không nhúng dữ liệu giả)
src = L.src_text()
L.check("/api/articles" in src, "mã nguồn frontend có gọi /api/articles",
        "frontend không thấy gọi /api/articles (dữ liệu có thể đang nhúng cứng)")
has_error_ui = bool(re.search(r"(catch|error|failed|thất bại|lỗi)", src, re.I))
L.check(has_error_ui, "mã nguồn có xử lý trạng thái lỗi (catch/error state)",
        "không thấy xử lý lỗi khi API chết -> trắng trang")

# --- 3. BẬT backend + vite dev rồi đo qua proxy
vite_port = L.free_port()
backend = L.Proc(f"uv run --project . uvicorn backend.app.main:app --host 127.0.0.1 --port {BACKEND_PORT}")
vite = None
try:
    ok_be = L.wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health", deadline_s=150)
    L.check(ok_be, f"backend lên ở 127.0.0.1:{BACKEND_PORT}",
            "backend không lên được ở cổng 8000 (proxy sẽ trỏ vào hư không)")

    if ok_be:
        vite = L.Proc(f"npm run dev -- --port {vite_port} --strictPort")
        ok_v = L.wait_http(f"http://127.0.0.1:{vite_port}/", deadline_s=180)
        L.check(ok_v, f"vite dev lên ở 127.0.0.1:{vite_port}", "vite dev không lên được")

        if ok_v:
            code_d, body_d = L.http_get(f"http://127.0.0.1:{BACKEND_PORT}/api/articles")
            code_p, body_p = L.http_get(f"http://127.0.0.1:{vite_port}/api/articles")
            L.check(code_p == 200, "gọi /api/articles QUA PROXY trả 200",
                    f"qua proxy trả {code_p} (body: {body_p[:120]})")
            if code_p == 200:
                try:
                    j = json.loads(body_p)
                    L.check(isinstance(j, list) and len(j) > 0,
                            f"proxy trả mảng JSON có dữ liệu ({len(j)} bài)",
                            "proxy trả mảng RỖNG -> chưa lấy từ DB (hoặc DB chưa seed)")
                except Exception:
                    L.fail(f"qua proxy không phải JSON: {body_p[:120]}")
                same = body_p.strip() == body_d.strip()
                L.check(same, "dữ liệu qua proxy GIỐNG gọi trực tiếp backend (chứng minh lấy từ DB)",
                        "dữ liệu qua proxy KHÁC backend -> FE đang tự bịa dữ liệu")
finally:
    if vite is not None:
        vite.stop()
    backend.stop()

# --- 4. build + bundle không lộ secret
rc, out = L.fresh_build()
L.check(rc == 0, "npm run build exit 0", f"npm run build exit {rc}: {L.tail(out, 400)}")
bad = [k for k in ("sk-", "BEGIN PRIVATE KEY", "AI_API_KEY=") if k in L.dist_text()]
L.check(not bad, "bundle không chứa chuỗi giống API key", f"bundle chứa: {bad}")

L.finish()
