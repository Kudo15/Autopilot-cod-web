"""Xác minh nhanh SQLite của backend (dùng bằng: uv run python scripts/check_db.py).

Chỉ đọc — không sửa dữ liệu. In ra đường dẫn, kích thước và danh sách bảng.
"""
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
DB = BACKEND / "data" / "radar.db"

if not DB.exists():
    print("DB_MISSING:", DB)
    sys.exit(1)

print("DB_PATH:", DB)
print("DB_SIZE_BYTES:", DB.stat().st_size)

conn = sqlite3.connect(str(DB))
try:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print("TABLES:", tables)
    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        print(f"COLUMNS[{table}]:", cols)
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"ROWS[{table}]:", count)
finally:
    conn.close()
