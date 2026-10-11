"""Trong tai PHASE 2 — vo ung dung: dieu huong 7 nhom, dark/light, 3 trang thai.

Bang chung that: nhan nhom noi dung co trong MA NGUON va trong BUNDLE DA BUILD + build van xanh.
Chay: python checks/p2.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib as L  # noqa: E402

L.header(2, "vo ung dung: 7 nhom noi dung, dark/light, loading/empty/error")

# 7 nhom noi dung theo MISSION muc 2
GROUPS = [
    ("Tip & Trick", r"tip\s*&\s*trick"),
    ("AI & Model", r"ai\s*(&|va|và)?\s*model"),
    ("Chinh sach & Quota", r"ch[íi]nh\s*s[áa]ch|quota"),
    ("Free Model Explorer", r"free\s*model"),
    ("AI Deals & Promotions", r"deal|promo"),
    ("Provider Comparison", r"provider"),
    ("Admin Radar", r"admin"),
]

src = L.src_text()
found = [name for name, pat in GROUPS if re.search(pat, src, re.I)]
L.check(len(found) >= 6,
        f"ma nguon co {len(found)}/7 nhom noi dung: {found}",
        f"moi co {len(found)}/7 nhom trong ma nguon (can >= 6): {found}")

# dark/light
L.check(bool(re.search(r"theme", src, re.I)), "co co che doi theme", "KHONG thay 'theme' trong ma nguon")
L.check(bool(re.search(r"dark", src, re.I)), "co che do dark", "KHONG thay 'dark' trong ma nguon")
L.check(bool(re.search(r"localstorage|localStorage", src)), "theme duoc luu lai (localStorage)",
        "khong thay localStorage (chua luu lua chon theme)")

# 3 trang thai
for label, pat in (("loading", r"loading|dang tai|đang tải"),
                   ("empty", r"empty|trong|trống|khong co du lieu|không có dữ liệu"),
                   ("error", r"error|loi|lỗi")):
    L.check(bool(re.search(pat, src, re.I)), f"co trang thai {label}",
            f"KHONG thay trang thai {label} trong ma nguon")

# build van xanh + nhan co trong bundle that
rc, out = L.run("npm run build", timeout=900)
L.check(rc == 0, "npm run build exit 0", f"npm run build FAIL (exit {rc}): {L.tail(out, 700)}")

dist = L.dist_text()
d_found = [name for name, pat in GROUPS if re.search(pat, dist, re.I)]
L.check(len(d_found) >= 6, f"bundle da build chua {len(d_found)}/7 nhan nhom: {d_found}",
        f"bundle chi chua {len(d_found)}/7 nhan nhom (can >= 6): {d_found}")

L.finish()
