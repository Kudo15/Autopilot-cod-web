"""Ứng dụng FastAPI — Vũ Học AI Radar v1.0 (Phase 3).

Khởi động từ thư mục gốc repo:
    uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Phase 3: chỉ /api/health và /api/articles (đọc từ SQLite, ban đầu rỗng).
Chưa có bộ thu thập dữ liệu — không có bài viết thật nào trong DB.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from .database import ARTICLES_COLUMNS, get_connection, init_db
from .ingest.importers import ImportValidationError, MAX_UPLOAD_BYTES, parse_upload, persist_import


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
    """Trả các bài viết đã xuất bản, không gồm dữ liệu SAMPLE hay nội bộ."""
    conn = get_connection()
    try:
        columns = ", ".join(ARTICLES_COLUMNS)
        available_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        filters: list[str] = []
        params: list[str] = []
        if "article_status" in available_columns:
            filters.append("article_status = ?")
            params.append("PUBLISHED")
        if "data_origin" in available_columns:
            filters.append("(data_origin IS NULL OR data_origin != ?)")
            params.append("SAMPLE")
        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
        rows = conn.execute(
            f"SELECT {columns} FROM articles{where_clause} ORDER BY id DESC", params
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _multipart_fields(content_type: str, body: bytes) -> tuple[str, str, bytes]:
    """Extract the required multipart fields without treating upload text as code."""
    if not content_type.startswith("multipart/form-data") or "boundary=" not in content_type:
        raise ImportValidationError("request must be multipart/form-data")
    boundary = content_type.split("boundary=", 1)[1].strip().strip('"').encode("ascii")
    if not boundary:
        raise ImportValidationError("multipart boundary is missing")
    source_id: str | None = None
    filename: str | None = None
    file_content: bytes | None = None
    for part in body.split(b"--" + boundary):
        if not part or part in (b"--\r\n", b"--"):
            continue
        try:
            headers, value = part.lstrip(b"\r\n").split(b"\r\n\r\n", 1)
        except ValueError as error:
            raise ImportValidationError("multipart body is malformed") from error
        value = value.rstrip(b"\r\n")
        header_text = headers.decode("utf-8", errors="strict")
        if 'name="source_id"' in header_text:
            source_id = value.decode("utf-8", errors="strict")
        elif 'name="file"' in header_text and 'filename="' in header_text:
            filename = header_text.split('filename="', 1)[1].split('"', 1)[0]
            file_content = value
    if source_id is None or filename is None or file_content is None:
        raise ImportValidationError("multipart upload requires source_id and file")
    return source_id, filename, file_content


@app.post("/api/admin/import")
async def import_file(request: Request) -> dict[str, int]:
    """Import a manual Markdown, CSV or JSON upload as DRAFT records."""
    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload exceeds the 1 MB limit")
    try:
        source_id, filename, file_bytes = _multipart_fields(request.headers.get("content-type", ""), body)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ImportValidationError("upload exceeds the 1 MB limit")
        text = file_bytes.decode("utf-8")
        items, extension = parse_upload(filename, text)
        conn = get_connection()
        try:
            return persist_import(conn, items, source_id, f"text/{extension}")
        finally:
            conn.close()
    except (ImportValidationError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
