"""Trong tai PHASE 1 — khung frontend Vite + React 19 build duoc.

Bang chung that: tep ton tai + khai bao dung + `npm run build` exit 0 + dist co bundle that.
Chay: python checks/p1.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib as L  # noqa: E402

L.header(1, "khung frontend Vite + React 19, npm run build")

# --- 1. tep toi thieu
for rel in ("package.json", "index.html", "src/main.jsx", "src/App.jsx", ".gitignore"):
    L.check(L.exists(rel), f"co {rel}", f"THIEU {rel}")

# --- 2. khai bao dung stack
p = L.pkg()
deps = {**p.get("dependencies", {}), **p.get("devDependencies", {})}
react_v = str(deps.get("react", ""))
vite_v = str(deps.get("vite", ""))
L.check(L.major(react_v) == 19, f"react major 19 (thay: {react_v or 'khong co'})",
        f"react phai la major 19 (thay: {react_v or 'khong co'})")
L.check(L.major(vite_v) >= 7, f"vite >= 7 (thay: {vite_v or 'khong co'})",
        f"vite phai >= 7 (thay: {vite_v or 'khong co'})")
L.check(bool(p.get("scripts", {}).get("build")), "co script build",
        "package.json thieu script 'build'")
L.check(bool(p.get("scripts", {}).get("dev")), "co script dev",
        "package.json thieu script 'dev'")

# --- 3. da cai dependency
L.check(L.exists("node_modules"), "da co node_modules (npm install da chay)",
        "CHUA co node_modules -> phai chay npm install truoc khi ket thuc phase")

# --- 4. build that
rc, out = L.fresh_build()
L.check(rc == 0, "npm run build exit 0", f"npm run build FAIL (exit {rc}): {L.tail(out, 700)}")

# --- 5. dist that
if L.exists("dist/index.html"):
    L.ok("dist/index.html duoc tao")
    html = L.read("dist/index.html")
    L.check(("root" in html), "dist/index.html co phan tu goc root", "dist/index.html KHONG co 'root'")
else:
    L.fail("KHONG co dist/index.html sau build")

assets = [p for p in (L.ROOT / "dist").glob("assets/*.js")] if (L.ROOT / "dist").exists() else []
L.check(len(assets) >= 1, f"dist co {len(assets)} bundle .js", "dist khong co bundle .js nao")

# --- 6. khong lot secret vao bundle (luat MISSION)
bundle = L.dist_text()
leaks = [k for k in ("AI_API_KEY", "sk-", "BEGIN PRIVATE KEY") if k in bundle]
L.check(not leaks, "bundle khong chua secret", f"bundle co chuoi nghi secret: {leaks}")

L.finish()
