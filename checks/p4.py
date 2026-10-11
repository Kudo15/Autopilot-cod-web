"""Trọng tài PHASE 4 — schema 12 bảng + migration idempotent + seed SAMPLE.

Bằng chứng thật: CHẠY migration/seed bằng đúng lệnh hợp đồng, rồi mở SQLite thật để đo
bảng/cột/số bản ghi — không đọc code để đoán.

Hợp đồng (ghi trong PLAN.md phase 4):
    uv run python -m backend.app.migrate    # tạo/cập nhật schema, chạy lại được nhiều lần
    uv run python -m backend.app.seed       # dữ liệu mẫu có nhãn SAMPLE, chạy lại không nhân bản
Chạy: python checks/p4.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _lib as L  # noqa: E402

TABLES_12 = ["sources", "raw_items", "articles", "providers", "models", "provider_models",
             "offers", "quota_observations", "verification_records", "change_events",
             "collection_runs", "editorial_reviews"]

COLS_CAN = ["last_verified", "valid_until", "account_required", "card_required",
            "context_window", "supports_vision", "supports_tools", "supports_json"]

# Tập giá trị trạng thái theo MISSION (constraint của phase 4)
STATUS_LITERALS = ["FREE_API", "FREE_CREDIT", "VERIFIED", "UNVERIFIED", "STALE", "EXPIRED",
                   "NEEDS_REVIEW", "SAFE_TO_TRY", "CAUTION", "INFO_ONLY"]

L.header(4, "schema 12 bảng + migration idempotent + seed SAMPLE")

# --- 0. hợp đồng: có module migrate/seed
mig = L.ROOT / "backend" / "app" / "migrate.py"
sed = L.ROOT / "backend" / "app" / "seed.py"
L.check(mig.exists(), "có backend/app/migrate.py (hợp đồng phase 4)",
        "THIẾU backend/app/migrate.py — xem hợp đồng phase 4 trong PLAN.md")
L.check(sed.exists(), "có backend/app/seed.py (hợp đồng phase 4)",
        "THIẾU backend/app/seed.py — xem hợp đồng phase 4 trong PLAN.md")

# --- 1. chạy migration THẬT (lần 1)
rc1, out1 = L.run("uv run python -m backend.app.migrate", timeout=600)
L.check(rc1 == 0, "migration lần 1 exit 0", f"migration lần 1 exit {rc1}: {L.tail(out1, 400)}")

db = L.find_db()
L.check(db is not None, f"có file SQLite ({db.name if db else '-'})",
        "KHÔNG thấy file SQLite nào sau migration")
if not db:
    L.finish()

tables = L.sqlite_tables(db)
thieu = [t for t in TABLES_12 if t not in tables]
L.check(not thieu, f"đủ 12 bảng (thấy {len([t for t in tables if t in TABLES_12])}/12)",
        f"THIẾU bảng: {thieu}")

# --- 2. các cột bắt buộc phải có ở nơi hợp lý
all_cols = {t: L.sqlite_cols(db, t) for t in tables}
flat = {c for cols in all_cols.values() for c in cols}
thieu_col = [c for c in COLS_CAN if c not in flat]
L.check(not thieu_col, "có đủ các cột last_verified/valid_until/account_required/card_required/"
                       "context_window/supports_vision/supports_tools/supports_json",
        f"THIẾU cột: {thieu_col}")

# --- 3. tập giá trị trạng thái xuất hiện trong schema hoặc dữ liệu
import sqlite3
hay = []
with sqlite3.connect(str(db)) as c:
    ddl = c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    hay += [r[0] or "" for r in ddl]
    for t in tables:
        try:
            rows = c.execute(f"SELECT * FROM {t} LIMIT 500").fetchall()
        except Exception:
            rows = []
        for r in rows:
            hay += [str(v) for v in r if isinstance(v, str)]
haystack = "\n".join(hay)
miss = [s for s in STATUS_LITERALS if s not in haystack]
L.check(not miss, "tập giá trị trạng thái theo MISSION có mặt (FREE_API/VERIFIED/SAFE_TO_TRY/…)",
        f"THIẾU giá trị trạng thái: {miss}")


# --- 4. đếm bản ghi từng bảng (để chứng minh idempotent)
def counts() -> dict:
    with sqlite3.connect(str(db)) as c:
        out = {}
        for t in tables:
            if t.startswith("sqlite_"):
                continue
            try:
                out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                out[t] = -1
        return out


c_before = counts()

# --- 5. chạy migration LẦN 2: phải vẫn exit 0 và không nhân bản
rc2, out2 = L.run("uv run python -m backend.app.migrate", timeout=600)
L.check(rc2 == 0, "migration lần 2 exit 0 (chạy lại được)", f"migration lần 2 exit {rc2}: {L.tail(out2, 400)}")
c_after = counts()
grew = {t: (c_before[t], c_after[t]) for t in c_before if c_after.get(t, -1) != c_before[t]}
L.check(not grew, f"migration lần 2 KHÔNG nhân bản dữ liệu ({sum(c_after.values())} bản ghi trước/sau)",
        f"migration lần 2 làm tăng bản ghi: {grew}")

# --- 6. seed THẬT (lần 1) + nhãn SAMPLE
rc3, out3 = L.run("uv run python -m backend.app.seed", timeout=600)
L.check(rc3 == 0, "seed lần 1 exit 0", f"seed lần 1 exit {rc3}: {L.tail(out3, 400)}")
c_seeded = counts()
total_seed = sum(v for v in c_seeded.values() if v > 0)
L.check(total_seed > 0, f"seed tạo được dữ liệu ({total_seed} bản ghi)", "seed không tạo bản ghi nào")

# nhãn SAMPLE: quét giá trị text trong DB
sample_hits = 0
with sqlite3.connect(str(db)) as c:
    for t in tables:
        if t.startswith("sqlite_"):
            continue
        try:
            rows = c.execute(f"SELECT * FROM {t}").fetchall()
        except Exception:
            continue
        for r in rows:
            for v in r:
                if isinstance(v, str) and "SAMPLE" in v.upper():
                    sample_hits += 1
L.check(sample_hits > 0, f"dữ liệu seed có nhãn SAMPLE ({sample_hits} ô chứa 'SAMPLE')",
        "KHÔNG thấy nhãn SAMPLE nào trong dữ liệu seed")

# --- 7. seed LẦN 2: idempotent
rc4, out4 = L.run("uv run python -m backend.app.seed", timeout=600)
L.check(rc4 == 0, "seed lần 2 exit 0 (chạy lại được)", f"seed lần 2 exit {rc4}: {L.tail(out4, 400)}")
c_seeded2 = counts()
grew2 = {t: (c_seeded[t], c_seeded2[t]) for t in c_seeded if c_seeded2.get(t, -1) != c_seeded[t]}
L.check(not grew2, f"seed lần 2 KHÔNG nhân bản dữ liệu ({total_seed} bản ghi trước/sau)",
        f"seed lần 2 làm tăng bản ghi: {grew2}")

# --- 8. không lộ secret trong mã backend
bad = [k for k in ("sk-", "BEGIN PRIVATE KEY") if k in L.src_text(("backend/**/*.py",))]
L.check(not bad, "mã backend không chứa secret", f"backend chứa chuỗi nghi secret: {bad}")

L.finish()
