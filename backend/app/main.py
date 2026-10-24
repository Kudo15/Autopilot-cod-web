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

from .auth import require_admin
from .database import ARTICLES_COLUMNS, get_connection, init_db
from .ingest.importers import ImportValidationError, MAX_UPLOAD_BYTES, parse_upload, persist_import
from .migrate import VERIFICATION_STATUS

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
    require_admin(request)
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


# --- Phase 8b: ranh giới admin (ADMIN_TOKEN) + workflow duyệt/xác minh --------
# Mọi route /api/admin/* gọi require_admin() ở dòng ĐẦU handler, TRƯỚC khi chạm DB.
# Public API không bao giờ trả raw/provenance/registry/admin field nào.

#: Cột nội bộ DUY NHẤT trả về từ GET /api/admin/sources.
ADMIN_SOURCE_FIELDS = (
    "source_id", "name", "type", "url", "collection_method",
    "priority", "status", "last_checked_at", "data_origin", "created_at",
)

#: Cột nội bộ DUY NHẤT trả về từ GET /api/admin/reviews (kèm trạng thái bài).
ADMIN_REVIEW_FIELDS = (
    "review_id", "article_id", "article_status", "review_status", "reviewer_note",
    "ranking_suggestion", "content_safety", "reviewed_at", "data_origin", "created_at",
)

#: Hành động duyệt bài hợp lệ (allowlist — DRAFT không phải hành động của editor).
ARTICLE_REVIEW_ACTIONS = ("PENDING_REVIEW", "REJECTED", "PUBLISHED")

#: Trạng thái xác minh hợp lệ — lấy từ MỘT nguồn duy nhất (hằng số schema, P4),
#: nên không thể lệch khỏi CHECK constraint của verification_records.
VERIFICATION_STATUSES = VERIFICATION_STATUS

#: Bảng chuyển trạng thái duyệt: {trạng thái hiện tại: {hành động: trạng thái mới}}.
#: articles.article_status CHECK chỉ cho (DRAFT, PENDING_REVIEW, PUBLISHED) nên
#: REJECTED = quay về DRAFT; lý do + trạng thái REJECTED nằm ở editorial_reviews.
_REVIEW_TRANSITIONS: dict[str, dict[str, str]] = {
    "DRAFT": {"PENDING_REVIEW": "PENDING_REVIEW"},
    "PENDING_REVIEW": {"PUBLISHED": "PUBLISHED", "REJECTED": "DRAFT"},
    "PUBLISHED": {},
}

#: SELECT tường minh cho bản ghi duyệt + trạng thái bài (không SELECT *).
_ADMIN_REVIEWS_SELECT = """
SELECT r.id AS review_id,
       r.article_id AS article_id,
       a.article_status AS article_status,
       r.review_status AS review_status,
       r.reviewer_note AS reviewer_note,
       r.ranking_suggestion AS ranking_suggestion,
       r.content_safety AS content_safety,
       r.reviewed_at AS reviewed_at,
       r.data_origin AS data_origin,
       r.created_at AS created_at
FROM editorial_reviews AS r
LEFT JOIN articles AS a ON a.id = r.article_id
ORDER BY r.id DESC
"""


async def _json_object(request: Request) -> dict:
    """Đọc body JSON dạng object; mọi hình dạng khác -> 422."""
    try:
        payload = await request.json()
    except ValueError as error:  # json.JSONDecodeError, body rỗng, ...
        raise HTTPException(status_code=422, detail="request body must be a JSON object") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="request body must be a JSON object")
    return payload


def _require_body_keys(payload: dict, allowed: tuple[str, ...]) -> None:
    """Chỉ cho phép đúng các field đã khai báo của một body admin."""
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown fields: {', '.join(unknown)}")


def _opt_text(value: object, field: str) -> str | None:
    """Trường text tuỳ chọn: None/chuỗi rỗng -> None; không phải chuỗi -> 422."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field} must be a string")
    text = value.strip()
    return text or None


def _has_real_pending_review(conn, article_id: int) -> bool:
    """Bài đã có bước PENDING_REVIEW xác thực (bản ghi thật) chưa."""
    row = conn.execute(
        """SELECT 1 FROM editorial_reviews
           WHERE article_id = ?
             AND review_status = 'PENDING_REVIEW'
             AND (data_origin IS NULL OR data_origin != 'SAMPLE')
           LIMIT 1""",
        (article_id,),
    ).fetchone()
    return row is not None


@app.get("/api/admin/sources")
def admin_sources(request: Request) -> list[dict]:
    """Registry nguồn nội bộ — chỉ cho request đã xác thực (gồm cả row SAMPLE)."""
    require_admin(request)
    columns = ", ".join(ADMIN_SOURCE_FIELDS)
    conn = get_connection()
    try:
        rows = conn.execute(f"SELECT {columns} FROM sources ORDER BY source_id").fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.get("/api/admin/reviews")
def admin_reviews(request: Request) -> list[dict]:
    """Bản ghi duyệt + trạng thái bài tương ứng — chỉ cho request đã xác thực."""
    require_admin(request)
    conn = get_connection()
    try:
        rows = conn.execute(_ADMIN_REVIEWS_SELECT).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.post("/api/admin/articles/{article_id}/review")
async def admin_article_review(article_id: int, request: Request) -> dict:
    """Ghi một bước duyệt bài đã xác thực: PENDING_REVIEW / REJECTED / PUBLISHED."""
    require_admin(request)
    payload = await _json_object(request)
    _require_body_keys(payload, ("action", "note"))
    action = payload.get("action")
    if action not in ARTICLE_REVIEW_ACTIONS:
        raise HTTPException(status_code=422, detail=f"invalid action: {action!r}")
    note = _opt_text(payload.get("note"), "note")
    conn = get_connection()
    try:
        return _apply_article_review(conn, article_id, action, note)
    finally:
        conn.close()


def _apply_article_review(conn, article_id: int, action: str, note: str | None) -> dict:
    """Chuyển trạng thái duyệt trong MỘT transaction; lỗi -> rollback sạch."""
    row = conn.execute(
        "SELECT id, article_status, data_origin FROM articles WHERE id = ?",
        (article_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"article {article_id} does not exist")
    if (row["data_origin"] or "REAL") == "SAMPLE":
        raise HTTPException(
            status_code=409, detail="SAMPLE articles cannot be reviewed or published"
        )

    current = row["article_status"] or "DRAFT"
    new_status = _REVIEW_TRANSITIONS.get(current, {}).get(action)
    if new_status is None:
        raise HTTPException(
            status_code=409, detail=f"cannot {action} an article in state {current}"
        )
    # Xuất bản chỉ sau một bước PENDING_REVIEW có xác thực đã tồn tại trong sổ duyệt.
    if action == "PUBLISHED" and not _has_real_pending_review(conn, article_id):
        raise HTTPException(
            status_code=409,
            detail="publish requires an authenticated PENDING_REVIEW step first",
        )

    reviewed_at = datetime.now(timezone.utc).isoformat()
    data_origin = row["data_origin"] or "REAL"
    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE articles SET article_status = ? WHERE id = ?", (new_status, article_id)
        )
        if action == "PUBLISHED":
            # Ghi mốc xuất bản THẬT chỉ khi chưa có (không viết lại lịch sử).
            conn.execute(
                "UPDATE articles SET published_at = COALESCE(published_at, ?) WHERE id = ?",
                (reviewed_at, article_id),
            )
        cursor = conn.execute(
            """INSERT INTO editorial_reviews
               (article_id, review_status, reviewer_note, reviewed_at, data_origin)
               VALUES (?, ?, ?, ?, ?)""",
            (article_id, action, note, reviewed_at, data_origin),
        )
        review_id = cursor.lastrowid
        if own_transaction:
            conn.commit()
    except Exception:
        if own_transaction:
            conn.rollback()
        raise
    return {
        "review_id": review_id,
        "article_id": article_id,
        "article_status": new_status,
        "review_status": action,
        "reviewer_note": note,
        "reviewed_at": reviewed_at,
        "data_origin": data_origin,
    }


@app.post("/api/admin/provider-models/{provider_model_id}/verification")
async def admin_provider_model_verification(provider_model_id: int, request: Request) -> dict:
    """Ghi một bản xác minh đã xác thực — không bao giờ bịa quota hay freshness."""
    require_admin(request)
    payload = await _json_object(request)
    _require_body_keys(payload, ("status", "evidence", "note", "method"))
    status = payload.get("status")
    if status not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=422, detail=f"invalid verification status: {status!r}")
    evidence = _opt_text(payload.get("evidence"), "evidence")
    note = _opt_text(payload.get("note"), "note")
    if evidence is None and note is None:
        raise HTTPException(
            status_code=422, detail="verification requires explicit evidence or note"
        )
    method = _opt_text(payload.get("method"), "method") or "manual"
    conn = get_connection()
    try:
        return _apply_verification(conn, provider_model_id, status, evidence, note, method)
    finally:
        conn.close()


def _apply_verification(
    conn,
    provider_model_id: int,
    status: str,
    evidence: str | None,
    note: str | None,
    method: str,
) -> dict:
    """Ghi bản xác minh + cập nhật trạng thái, không đụng quota/rate limit."""
    row = conn.execute(
        """SELECT id, data_origin, verification_status, last_verified, daily_quota, rate_limit
           FROM provider_models WHERE id = ?""",
        (provider_model_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"provider_model {provider_model_id} does not exist"
        )
    if (row["data_origin"] or "REAL") == "SAMPLE":
        raise HTTPException(status_code=409, detail="SAMPLE provider_models cannot be verified")

    verified_at = datetime.now(timezone.utc).isoformat()
    # Chỉ VERIFIED mới gắn mốc xác minh MỚI; trạng thái khác giữ nguyên last_verified
    # hiện có (không bịa freshness). daily_quota/rate_limit tuyệt đối không bị đụng tới.
    last_verified = verified_at if status == "VERIFIED" else row["last_verified"]
    data_origin = row["data_origin"] or "REAL"

    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE provider_models SET verification_status = ?, last_verified = ? WHERE id = ?",
            (status, last_verified, provider_model_id),
        )
        cursor = conn.execute(
            """INSERT INTO verification_records
               (provider_model_id, offer_id, verification_status, method, evidence,
                note, verified_at, data_origin)
               VALUES (?, NULL, ?, ?, ?, ?, ?, ?)""",
            (provider_model_id, status, method, evidence, note, verified_at, data_origin),
        )
        record_id = cursor.lastrowid
        if own_transaction:
            conn.commit()
    except Exception:
        if own_transaction:
            conn.rollback()
        raise
    return {
        "verification_record_id": record_id,
        "provider_model_id": provider_model_id,
        "verification_status": status,
        "last_verified": last_verified,
        "evidence": evidence,
        "note": note,
        "verified_at": verified_at,
        "data_origin": data_origin,
    }
