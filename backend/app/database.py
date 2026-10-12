"""Quản lý kết nối SQLite — Vũ Học AI Radar v1.0 (Phase 3).

Đường dẫn database ổn định: tính từ file này (backend/app/) lên backend/,
không phụ thuộc working directory khi khởi động uvicorn.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "radar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    source TEXT,
    category TEXT,
    summary TEXT,
    published_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

ARTICLES_COLUMNS = (
    "id", "title", "url", "source", "category", "summary", "published_at", "created_at"
)


def init_db() -> Path:
    """Khởi tạo schema đầy đủ (Phase 4: migration 12 bảng, idempotent).

    Giữ nguyên hành vi cũ (trả về đường dẫn DB) nhưng nâng cấp bảng
    articles của Phase 3 và tạo 12 bảng nghiệp vụ theo MISSION mục 5.
    Không bao giờ xóa dữ liệu có sẵn.
    """
    from .migrate import apply_migration

    return apply_migration()


def get_connection() -> sqlite3.Connection:
    """Mở một kết nối mới; người dùng PHẢI đóng sau khi sử dụng."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn
