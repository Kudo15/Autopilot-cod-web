"""Ứng dụng FastAPI — Vũ Học AI Radar v1.0 (Phase 3).

Khởi động từ thư mục gốc repo:
    uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Phase 3: chỉ /api/health và /api/articles (đọc từ SQLite, ban đầu rỗng).
Chưa có bộ thu thập dữ liệu — không có bài viết thật nào trong DB.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import ARTICLES_COLUMNS, get_connection, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Tự khởi tạo database + schema khi ứng dụng bắt đầu.
    init_db()
    yield


app = FastAPI(title="Vũ Học AI Radar", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vu-hoc-ai-radar"}


@app.get("/api/articles")
def list_articles() -> list[dict]:
    """Đọc danh sách bài viết từ bảng articles (rỗng trong Phase 3)."""
    conn = get_connection()
    try:
        columns = ", ".join(ARTICLES_COLUMNS)
        rows = conn.execute(
            f"SELECT {columns} FROM articles ORDER BY id DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
