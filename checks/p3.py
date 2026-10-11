"""Trọng tài PHASE 3 — backend FastAPI chạy được: uv + SQLite + /api/health, /api/articles.

Bằng chứng thật: khởi động uvicorn ở cổng trống, gọi HTTP thật, mở SQLite thật, rồi tắt.
Hợp đồng (ghi trong PLAN.md phase 3): app phải import được bằng
    uv run uvicorn backend.app.main:app --host 127.0.0.1 --port <cổng>
Chạy: python checks/p3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib as L  # noqa: E402

L.header(3, "backend FastAPI + uv + SQLite + health/articles")

# --- 1. khai bao dependency bằng uv
py = L.read("pyproject.toml") or L.read("backend/pyproject.toml")
L.check(bool(py.strip()), "có pyproject.toml (uv quản lý dependency)", "THIẾU pyproject.toml")
low = py.lower()
L.check("fastapi" in low, "pyproject có fastapi", "pyproject thiếu fastapi")
L.check("uvicorn" in low, "pyproject có uvicorn", "pyproject thiếu uvicorn")
L.check(L.exists(".python-version") or "requires-python" in low,
        "có .python-version hoặc requires-python", "thiếu .python-version / requires-python")

# --- 2. app theo hợp đồng
app_file = L.ROOT / "backend" / "app" / "main.py"
L.check(app_file.exists(), "có backend/app/main.py (hợp đồng phase 3)",
        "THIẾU backend/app/main.py — xem acceptance phase 3 trong PLAN.md")
if app_file.exists():
    src = L.read("backend/app/main.py")
    L.check("FastAPI(" in src, "main.py có FastAPI(", "main.py không thấy khởi tạo FastAPI(")

# --- 3. khởi động THẬT rồi gọi HTTP THẬT
port = L.free_port()
cmd = f"uv run --project . uvicorn backend.app.main:app --host 127.0.0.1 --port {port}"
L.note(f"chạy: {cmd}")
proc = L.Proc(cmd)
try:
    up = L.wait_http(f"http://127.0.0.1:{port}/api/health", deadline_s=150)
    if not up:
        L.fail(f"không gọi được /api/health sau 150s. Output:\n{L.tail(proc.out(), 700)}")
    else:
        L.ok(f"uvicorn lên được ở 127.0.0.1:{port} và /api/health trả 200")
        code, body = L.http_get(f"http://127.0.0.1:{port}/api/health")
        try:
            j = json.loads(body)
            L.check(isinstance(j, dict) and bool(j), f"/api/health trả JSON: {str(j)[:110]}",
                    "/api/health không trả JSON object khác rỗng")
        except Exception:
            L.fail(f"/api/health không phải JSON: {body[:90]}")

    code2, body2 = L.http_get(f"http://127.0.0.1:{port}/api/articles")
    L.check(code2 == 200, "/api/articles trả 200", f"/api/articles trả {code2}: {body2[:90]}")
    if code2 == 200:
        try:
            j2 = json.loads(body2)
            L.check(isinstance(j2, list), f"/api/articles trả mảng JSON ({len(j2)} phần tử)",
                    f"/api/articles không phải mảng JSON: {str(j2)[:80]}")
        except Exception:
            L.fail(f"/api/articles không phải JSON: {body2[:90]}")
finally:
    proc.stop()

# --- 4. SQLite THẬT
db = L.find_db()
L.check(db is not None, f"có file SQLite ({db.name if db else '-'})",
        "KHÔNG thấy file SQLite nào trong repo")
if db:
    tables = L.sqlite_tables(db)
    L.check(len(tables) >= 1, f"SQLite có {len(tables)} bảng: {tables[:6]}",
            "SQLite không có bảng nào")

# --- 5. không lộ secret vào mã nguồn backend
bad = [k for k in ("sk-", "BEGIN PRIVATE KEY") if k in L.read("backend/app/main.py")]
L.check(not bad, "main.py không chứa secret", f"main.py chứa chuỗi nghi secret: {bad}")

L.finish()
