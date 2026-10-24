"""Ứng dụng FastAPI — Vũ Học AI Radar v1.0 (Phase 3).

Khởi động từ thư mục gốc repo:
    uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Phase 3: chỉ /api/health và /api/articles (đọc từ SQLite, ban đầu rỗng).
Chưa có bộ thu thập dữ liệu — không có bài viết thật nào trong DB.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request

from .database import ARTICLES_COLUMNS, get_connection, init_db
from .ingest.importers import ImportValidationError, MAX_UPLOAD_BYTES, parse_upload, persist_import

# --- Phase 7: Model/Provider Explorer — hợp đồng public read-only ------------
#: Tập free_status hợp lệ theo MISSION (khớp CHECK constraint của provider_models).
FREE_STATUS_VALUES = (
    "FREE_API", "FREE_CREDIT", "FREE_TRIAL", "FREE_WEB_ONLY", "PROMO", "PAID", "UNKNOWN"
)

#: capability -> cột nullable tương ứng. 'text' không có cột riêng (mọi model
#: đều là model văn bản) nên KHÔNG thêm ràng buộc; các giá trị còn lại chỉ khớp
#: khi cột IS NOT NULL AND = 1 (NULL tuyệt đối không được coi là true).
CAPABILITY_COLUMNS: dict[str, str | None] = {
    "text": None,
    "vision": "supports_vision",
    "tools": "supports_tools",
    "json": "supports_json",
}

#: Các query parameter DUY NHẤT được phép trên GET /api/models.
MODELS_QUERY_PARAMS = frozenset(
    {
        "free_status", "access", "provider", "card_required",
        "capability", "context_min", "quota_min", "verified_within_days",
    }
)

#: Cột public DUY NHẤT của một row Explorer (không SELECT *, không dữ liệu nội bộ).
PUBLIC_MODEL_FIELDS = (
    "model_id", "model_name", "organization",
    "provider_id", "provider_name", "website", "official_url",
    "api_model_id", "free_status", "rate_limit", "daily_quota",
    "account_required", "card_required", "context_window",
    "supports_vision", "supports_tools", "supports_json",
    "verification_status", "last_verified", "valid_until",
)

#: SELECT tường minh — join một model với nhiều provider row (quota/trạng thái
#: riêng biệt), loại bỏ SAMPLE ở cả ba bảng. Không truy vấn raw/provenance/
#: registry/ghi chú nội bộ.
_MODELS_SELECT = """
SELECT m.model_id AS model_id,
       m.model_name AS model_name,
       m.organization AS organization,
       p.provider_id AS provider_id,
       p.name AS provider_name,
       p.website AS website,
       pm.official_url AS official_url,
       pm.api_model_id AS api_model_id,
       pm.free_status AS free_status,
       pm.rate_limit AS rate_limit,
       pm.daily_quota AS daily_quota,
       pm.account_required AS account_required,
       pm.card_required AS card_required,
       pm.context_window AS context_window,
       pm.supports_vision AS supports_vision,
       pm.supports_tools AS supports_tools,
       pm.supports_json AS supports_json,
       pm.verification_status AS verification_status,
       pm.last_verified AS last_verified,
       pm.valid_until AS valid_until
FROM models AS m
JOIN provider_models AS pm ON pm.model_id = m.model_id
JOIN providers AS p ON p.provider_id = pm.provider_id
WHERE m.data_origin != 'SAMPLE'
  AND pm.data_origin != 'SAMPLE'
  AND p.data_origin != 'SAMPLE'
"""


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


def _unknown_models_query_keys(filters: dict) -> list[str]:
    """Trả danh sách key không nằm trong danh sách cho phép (dùng cho 422)."""
    return sorted(k for k in filters if k not in MODELS_QUERY_PARAMS)


def _require_query_params(filters: dict) -> None:
    """Chặn tham số lạ / giá trị sai bằng 422. Imported/provider text là dữ
    liệu untrusted — chỉ dùng qua bind parameter, không bao giờ thành SQL."""
    unknown = _unknown_models_query_keys(filters)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}")

    free_status = filters.get("free_status")
    if free_status is not None and free_status not in FREE_STATUS_VALUES:
        raise HTTPException(status_code=422, detail=f"invalid free_status: {free_status!r}")

    access = filters.get("access")
    if access is not None and access not in ("api", "web_only"):
        raise HTTPException(status_code=422, detail=f"invalid access: {access!r}")

    card_required = filters.get("card_required")
    if card_required is not None and card_required not in ("0", "1"):
        raise HTTPException(status_code=422, detail=f"invalid card_required: {card_required!r}")

    capability = filters.get("capability")
    if capability is not None and capability not in CAPABILITY_COLUMNS:
        raise HTTPException(status_code=422, detail=f"invalid capability: {capability!r}")

    provider = filters.get("provider")
    if provider is not None and not provider.strip():
        raise HTTPException(status_code=422, detail="provider must not be empty")

    for name in ("context_min", "quota_min", "verified_within_days"):
        value = filters.get(name)
        if value is None:
            continue
        if not str(value).isdigit():
            raise HTTPException(
                status_code=422, detail=f"{name} must be a non-negative integer"
            )


def list_models(
    free_status: str | None = None,
    access: str | None = None,
    provider: str | None = None,
    card_required: str | None = None,
    capability: str | None = None,
    context_min: str | None = None,
    quota_min: str | None = None,
    verified_within_days: str | None = None,
) -> list[dict]:
    """Endpoint public Model/Provider Explorer — join model -> provider rows.

    Mọi giá trị untrusted (free_status, provider, ...) chỉ đi qua bind
    parameter; không bao giờ được nối vào SQL. Giá trị chưa biết giữ
    null/UNKNOWN/UNVERIFIED — không suy diễn free, quota, freshness, API.
    """
    filters = {
        "free_status": free_status,
        "access": access,
        "provider": provider,
        "card_required": card_required,
        "capability": capability,
        "context_min": context_min,
        "quota_min": quota_min,
        "verified_within_days": verified_within_days,
    }
    # Bỏ các filter None khỏi dict để không nhầm 'không lọc' với 'không hợp lệ'.
    present = {k: v for k, v in filters.items() if v is not None}
    _require_query_params(present)

    where: list[str] = []
    params: list[object] = []

    if "free_status" in present:
        where.append("pm.free_status = ?")
        params.append(present["free_status"])
    if "access" in present:
        if present["access"] == "api":
            where.append("pm.api_model_id IS NOT NULL")
        else:
            where.append("pm.api_model_id IS NULL")
    if "provider" in present:
        where.append("(p.provider_id = ? OR p.name = ?)")
        provider_val = present["provider"]
        params.extend((provider_val, provider_val))
    if "card_required" in present:
        # 0/1 exact; NULL không thoả điều kiện 0 lẫn 1.
        where.append("pm.card_required = ?")
        params.append(present["card_required"])
    if "capability" in present:
        column = CAPABILITY_COLUMNS[present["capability"]]
        if column is not None:
            # NULL tuyệt đối không được coi là true.
            where.append(f"pm.{column} IS NOT NULL AND pm.{column} = 1")
    if "context_min" in present:
        # NULL không thoả minimum; chỉ khớp khi có giá trị >= ngưỡng.
        where.append("pm.context_window IS NOT NULL AND pm.context_window >= ?")
        params.append(int(present["context_min"]))
    if "quota_min" in present:
        where.append("pm.daily_quota IS NOT NULL AND pm.daily_quota >= ?")
        params.append(int(present["quota_min"]))
    if "verified_within_days" in present:
        # Chỉ VERIFIED + last_verified không NULL. UNVERIFIED/NULL không bao
        # giờ được trình bày là đã xác minh. Dùng julianday() để so sánh đúng
        # cả khi timestamp có offset timezone.
        days = int(present["verified_within_days"])
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        where.append(
            "pm.verification_status = 'VERIFIED' "
            "AND pm.last_verified IS NOT NULL "
            "AND julianday(pm.last_verified) >= julianday(?)"
        )
        params.append(cutoff)

    sql = _MODELS_SELECT
    if where:
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY m.model_id, p.provider_id"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.get("/api/models")
def public_models(request: Request) -> list[dict]:
    """GET /api/models — chỉ nhận các query parameter đã khai báo, không SELECT *."""
    filters = dict(request.query_params.multi_items())
    unknown = _unknown_models_query_keys(filters)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}"
        )
    return list_models(**filters)


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
