"""Ứng dụng FastAPI — Vũ Học AI Radar v1.0 (Phase 3).

Khởi động từ thư mục gốc repo:
    uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

Phase 3: chỉ /api/health và /api/articles (đọc từ SQLite, ban đầu rỗng).
Chưa có bộ thu thập dữ liệu — không có bài viết thật nào trong DB.
"""
from __future__ import annotations

import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Request

from .auth import require_admin
from .database import ARTICLES_COLUMNS, get_connection, init_db
from .ingest.importers import ImportValidationError, MAX_UPLOAD_BYTES, parse_upload, persist_import
from .inbox.service import (
    INBOX_DIR_ENV,
    list_inbox_articles,
    list_inbox_runs,
    resolve_inbox_dir,
    scan_inbox,
)
from .migrate import REPOSITORY_DIFFICULTY, VERIFICATION_STATUS
from .radar.daily import RADAR_TIMEZONE_NAME, RadarSchedule, daily_radar, validate_window
from .radar import scheduler as radar_scheduler

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


# --- Public search (task 015): published-only, parameterized article search --
SEARCH_QUERY_PARAMS = frozenset({"q", "category", "window"})
SEARCH_WINDOWS = frozenset({"today", "7d", "30d", "all"})
SEARCH_CATEGORIES = frozenset(
    {"tip-trick", "ai-model", "policy-quota", "free-model-explorer", "ai-deals", "provider-comparison"}
)


def search_articles(
    q: str | None = None,
    category: str | None = None,
    window: str = "all",
) -> list[dict]:
    """Search only REAL/PUBLISHED articles using bound SQL parameters."""
    if window not in SEARCH_WINDOWS:
        raise ValueError(f"invalid search window: {window!r}")
    if category is not None and category not in SEARCH_CATEGORIES:
        raise ValueError(f"invalid search category: {category!r}")
    query = (q or "").strip()
    if len(query) > 200:
        raise ValueError("q exceeds 200 characters")

    filters = ["article_status = ?", "(data_origin IS NULL OR data_origin != ?)"]
    params: list[object] = ["PUBLISHED", "SAMPLE"]
    if query:
        filters.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
        needle = f"%{query}%"
        params.extend((needle, needle, needle))
    if category is not None:
        filters.append("category = ?")
        params.append(category)
    if window != "all":
        days = {"today": 1, "7d": 7, "30d": 30}[window]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        filters.append("published_at IS NOT NULL AND julianday(published_at) >= julianday(?)")
        params.append(cutoff)

    columns = ", ".join(ARTICLES_COLUMNS)
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT {columns} FROM articles WHERE {' AND '.join(filters)} ORDER BY id DESC",
            params,
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.get("/api/search")
def public_search(request: Request) -> list[dict]:
    filters = dict(request.query_params.multi_items())
    unknown = sorted(key for key in filters if key not in SEARCH_QUERY_PARAMS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}")
    try:
        return search_articles(
            q=filters.get("q"), category=filters.get("category"), window=filters.get("window", "all")
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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


# --- Promotion Radar (task r1): public offers + admin offer verification ----
# Luật active: default CHỈ trả offer REAL + VERIFIED + chưa hết hạn tại now
# (ends_at/valid_until) + official CTA hợp lệ http(s). SAMPLE, UNVERIFIED,
# EXPIRED, thiếu CTA tuyệt đối không được trình bày như ưu đãi active.
# Filter status cho phép xem lịch sử: row vẫn gắn verification_status thật và
# cờ is_active tính riêng — UI không bao giờ gọi là active khi is_active != True.

#: Query parameter DUY NHẤT được phép trên GET /api/offers.
OFFERS_QUERY_PARAMS = frozenset({"q", "provider", "offer_type", "status", "limit"})

#: Trần limit bounded cho GET /api/offers: mặc định và tối đa rõ ràng.
OFFERS_DEFAULT_LIMIT = 50
OFFERS_MAX_LIMIT = 100

#: Độ dài tối đa của chuỗi tìm kiếm q.
OFFERS_MAX_Q_LENGTH = 200

#: Filter status: 'active' (mặc định) hoặc một trạng thái xác minh để xem
#: lịch sử (không bao giờ thay thế cho 'active').
OFFER_STATUS_FILTERS = frozenset({"active"}) | frozenset(VERIFICATION_STATUS)

#: Cột public DUY NHẤT của một row offer (SELECT tường minh — không code
#: khuyến mãi, không raw/provenance/reviewer note/snapshot nội bộ).
PUBLIC_OFFER_FIELDS = (
    "id", "title", "provider_id", "provider_name", "offer_type",
    "description", "terms", "starts_at", "ends_at",
    "account_required", "card_required",
    "verification_status", "last_verified", "valid_until",
    "official_url", "is_active",
)

#: SELECT tường minh offer + tên provider (join an toàn, loại SAMPLE ở cả hai
#: bảng). Cột `code` (mã khuyến mãi nội bộ) tuyệt đối không được SELECT.
_OFFERS_BASE_SELECT = """
SELECT o.id AS id,
       o.title AS title,
       o.provider_id AS provider_id,
       p.name AS provider_name,
       o.offer_type AS offer_type,
       o.description AS description,
       o.terms AS terms,
       o.starts_at AS starts_at,
       o.ends_at AS ends_at,
       o.account_required AS account_required,
       o.card_required AS card_required,
       o.verification_status AS verification_status,
       o.last_verified AS last_verified,
       o.valid_until AS valid_until,
       p.website AS website
FROM offers AS o
LEFT JOIN providers AS p ON p.provider_id = o.provider_id
WHERE (o.data_origin IS NULL OR o.data_origin = 'REAL')
  AND (p.data_origin IS NULL OR p.data_origin != 'SAMPLE')
"""


def _parse_offer_timestamp(value: str | None) -> datetime | None:
    """Parse mốc thời gian offer; rỗng/NULL/không parse được -> None."""
    if value is None or not str(value).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _valid_cta_url(value: str | None) -> bool:
    """Official CTA hợp lệ: http/https kèm domain. Scheme lạ/URL hỏng -> False."""
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not (candidate.startswith("https://") or candidate.startswith("http://")):
        return False
    try:
        parsed = urllib.parse.urlparse(candidate)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _offer_deadline_passed(value: str | None, now: datetime) -> bool:
    """Không có mốc hết hạn (NULL/rỗng) = chưa hết hạn.

    Mốc tồn tại nhưng không parse được bị coi là ĐÃ hết hạn (thận trọng):
    không bao giờ trình bày một offer hết hạn không kiểm tra được là active.
    """
    if value is None or not str(value).strip():
        return False
    parsed = _parse_offer_timestamp(value)
    if parsed is None:
        return True
    return parsed <= now


def _offer_is_active(row: dict, now: datetime) -> bool:
    """Luật active dùng chung cho cờ is_active của MỌI row public.

    VERIFIED + CTA http(s) hợp lệ + ends_at/valid_until chưa qua mốc now.
    """
    if (row.get("verification_status") or "") != "VERIFIED":
        return False
    if not _valid_cta_url(row.get("official_url")):
        return False
    if _offer_deadline_passed(row.get("ends_at"), now):
        return False
    if _offer_deadline_passed(row.get("valid_until"), now):
        return False
    return True


def list_offers(
    q: str | None = None,
    provider: str | None = None,
    offer_type: str | None = None,
    status: str | None = None,
    limit: str | None = None,
) -> list[dict]:
    """Promotion Radar public — cột allowlist tường minh, bind parameters.

    Default (status='active') chỉ trả ưu đãi THẬT SỰ active; status khác là
    chế độ xem lịch sử theo verification_status (vẫn chỉ dữ liệu REAL, mỗi
    row được gắn is_active tính riêng tại `now`).
    """
    effective_status = (status or "active").strip() or "active"
    if effective_status not in OFFER_STATUS_FILTERS:
        raise HTTPException(status_code=422, detail=f"invalid status: {effective_status!r}")
    query = (q or "").strip()
    if len(query) > OFFERS_MAX_Q_LENGTH:
        raise HTTPException(
            status_code=422, detail=f"q exceeds {OFFERS_MAX_Q_LENGTH} characters"
        )
    if provider is not None and not provider.strip():
        raise HTTPException(status_code=422, detail="provider must not be empty")
    if offer_type is not None and offer_type not in FREE_STATUS_VALUES:
        raise HTTPException(status_code=422, detail=f"invalid offer_type: {offer_type!r}")
    effective_limit = OFFERS_DEFAULT_LIMIT
    if limit is not None:
        if not str(limit).isdigit():
            raise HTTPException(
                status_code=422, detail="limit must be a positive integer"
            )
        value = int(limit)
        if value < 1 or value > OFFERS_MAX_LIMIT:
            raise HTTPException(
                status_code=422,
                detail=f"limit must be between 1 and {OFFERS_MAX_LIMIT}",
            )
        effective_limit = value

    now = datetime.now(timezone.utc)
    where: list[str] = []
    params: list[object] = []
    if effective_status == "active":
        # Chưa hết hạn tại now; mốc rỗng = mở; mốc hỏng (julianday NULL) bị loại.
        where.append("o.verification_status = 'VERIFIED'")
        where.append("p.website IS NOT NULL AND TRIM(p.website) != ''")
        where.append("(p.website LIKE 'https://%' OR p.website LIKE 'http://%')")
        where.append(
            "(o.ends_at IS NULL OR TRIM(o.ends_at) = '' "
            "OR julianday(o.ends_at) > julianday(?))"
        )
        where.append(
            "(o.valid_until IS NULL OR TRIM(o.valid_until) = '' "
            "OR julianday(o.valid_until) > julianday(?))"
        )
        params.extend((now.isoformat(), now.isoformat()))
    else:
        where.append("o.verification_status = ?")
        params.append(effective_status)
    if query:
        where.append("(o.title LIKE ? OR o.description LIKE ?)")
        needle = f"%{query}%"
        params.extend((needle, needle))
    if provider is not None and provider.strip():
        where.append("(o.provider_id = ? OR p.name = ?)")
        provider_val = provider.strip()
        params.extend((provider_val, provider_val))
    if offer_type is not None:
        where.append("o.offer_type = ?")
        params.append(offer_type)

    sql = _OFFERS_BASE_SELECT
    if where:
        sql += " AND " + " AND ".join(where)
    # Sắp xếp ưu đãi sắp hết hạn lên đầu; offer không có ends_at xuống cuối.
    sql += (
        " ORDER BY CASE WHEN o.ends_at IS NULL OR TRIM(o.ends_at) = '' "
        "THEN 99999999 ELSE julianday(o.ends_at) END ASC, o.id ASC"
    )
    sql += " LIMIT ?"
    params.append(effective_limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    result: list[dict] = []
    for row in rows:
        record = dict(row)
        website = record.pop("website", None)
        cta_url = website.strip() if _valid_cta_url(website) else None
        record["official_url"] = cta_url
        record["is_active"] = _offer_is_active(record, now)
        result.append({k: record.get(k) for k in PUBLIC_OFFER_FIELDS})
    return result


@app.get("/api/offers")
def public_offers(request: Request) -> dict:
    """GET /api/offers — Promotion Radar public.

    Chỉ nhận query parameter trong allowlist (tham số lạ -> 422); default
    chỉ trả ưu đãi thật, đã xác minh, còn hiệu lực và có official CTA.
    """
    filters = dict(request.query_params.multi_items())
    unknown = sorted(key for key in filters if key not in OFFERS_QUERY_PARAMS)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}"
        )
    offers = list_offers(**filters)
    return {"offers": offers, "count": len(offers)}


# Cột nội bộ DUY NHẤT trả về từ GET /api/admin/offers (kèm code khuyến mãi
# và data_origin để admin nhận biết SAMPLE) — không raw/provenance/snapshot.
ADMIN_OFFER_FIELDS = (
    "id", "provider_id", "provider_name", "title", "offer_type", "code",
    "description", "terms", "starts_at", "ends_at",
    "account_required", "card_required",
    "verification_status", "last_verified", "valid_until",
    "official_url", "data_origin", "created_at",
)

_ADMIN_OFFERS_SELECT = """
SELECT o.id AS id,
       o.provider_id AS provider_id,
       p.name AS provider_name,
       o.title AS title,
       o.offer_type AS offer_type,
       o.code AS code,
       o.description AS description,
       o.terms AS terms,
       o.starts_at AS starts_at,
       o.ends_at AS ends_at,
       o.account_required AS account_required,
       o.card_required AS card_required,
       o.verification_status AS verification_status,
       o.last_verified AS last_verified,
       o.valid_until AS valid_until,
       p.website AS website,
       o.data_origin AS data_origin,
       o.created_at AS created_at
FROM offers AS o
LEFT JOIN providers AS p ON p.provider_id = o.provider_id
ORDER BY o.id
"""


@app.get("/api/admin/offers")
def admin_offers(request: Request) -> list[dict]:
    """Danh sách offer nội bộ (gồm cả row SAMPLE, gắn nhãn) — chỉ đã xác thực."""
    require_admin(request)
    conn = get_connection()
    try:
        rows = conn.execute(_ADMIN_OFFERS_SELECT).fetchall()
    finally:
        conn.close()
    result: list[dict] = []
    for row in rows:
        rec = dict(row)
        website = rec.pop("website", None)
        rec["official_url"] = website.strip() if _valid_cta_url(website) else website
        result.append({k: rec.get(k) for k in ADMIN_OFFER_FIELDS})
    return result


@app.post("/api/admin/offers/{offer_id}/verification")
async def admin_offer_verification(offer_id: int, request: Request) -> dict:
    """Ghi bản xác minh offer đã xác thực — không bao giờ verify SAMPLE.

    require_admin() chạy ở dòng ĐẦU handler, TRƯỚC khi mở/kết nối DB.
    """
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
        return _apply_offer_verification(conn, offer_id, status, evidence, note, method)
    finally:
        conn.close()


def _apply_offer_verification(
    conn,
    offer_id: int,
    status: str,
    evidence: str | None,
    note: str | None,
    method: str,
) -> dict:
    """Ghi bản xác minh offer + cập nhật trạng thái trong MỘT transaction.

    Schema bắt buộc verification_records.provider_model_id NOT NULL, nên offer
    phải liên kết provider_model THẬT để ghi được — offer mồ côi bị 409 rõ
    ràng. `last_verified` chỉ cập nhật khi VERIFIED (không bịa freshness);
    không chạm quota/credit hay bất kỳ trường dữ liệu nào khác.
    """
    row = conn.execute(
        """SELECT o.id, o.data_origin, o.provider_id, o.provider_model_id,
                  o.verification_status, o.last_verified
           FROM offers AS o WHERE o.id = ?""",
        (offer_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"offer {offer_id} does not exist")
    if (row["data_origin"] or "REAL") == "SAMPLE":
        raise HTTPException(status_code=409, detail="SAMPLE offers cannot be verified")
    provider_model_id = row["provider_model_id"]
    if provider_model_id is not None:
        linked = conn.execute(
            "SELECT 1 FROM provider_models WHERE id = ?", (provider_model_id,)
        ).fetchone()
        if linked is None:
            pm = None
            if row["provider_id"]:
                pm = conn.execute(
                    "SELECT id FROM provider_models WHERE provider_id = ? ORDER BY id LIMIT 1",
                    (row["provider_id"],),
                ).fetchone()
            if pm is not None:
                provider_model_id = pm["id"]
            else:
                raise HTTPException(
                    status_code=409,
                    detail=f"linked provider_model {provider_model_id} does not exist",
                )
    elif row["provider_id"]:
        pm = conn.execute(
            "SELECT id FROM provider_models WHERE provider_id = ? ORDER BY id LIMIT 1",
            (row["provider_id"],),
        ).fetchone()
        if pm is not None:
            provider_model_id = pm["id"]

    verified_at = datetime.now(timezone.utc).isoformat()
    # Chỉ VERIFIED mới gắn mốc xác minh MỚI; các trạng thái khác giữ nguyên
    # last_verified hiện có. Không đụng quota/rate limit hay credit nào.
    last_verified = verified_at if status == "VERIFIED" else row["last_verified"]
    data_origin = row["data_origin"] or "REAL"

    own_transaction = not conn.in_transaction
    try:
        if own_transaction:
            conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE offers SET verification_status = ?, last_verified = ? WHERE id = ?",
            (status, last_verified, offer_id),
        )
        cursor = conn.execute(
            """INSERT INTO verification_records
               (provider_model_id, offer_id, verification_status, method, evidence,
                note, verified_at, data_origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (provider_model_id, offer_id, status, method, evidence, note,
             verified_at, data_origin),
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
        "offer_id": offer_id,
        "provider_model_id": provider_model_id,
        "verification_status": status,
        "last_verified": last_verified,
        "evidence": evidence,
        "note": note,
        "verified_at": verified_at,
        "data_origin": data_origin,
    }


# --- Daily Radar (task 014/015): đọc tín hiệu thật + refresh cục bộ có xác thực ---
#: Query parameter DUY NHẤT được phép trên GET /api/radar.
RADAR_QUERY_PARAMS = frozenset({"window"})

#: Mốc lịch 07:00 Asia/Ho_Chi_Minh — CHỈ trong bộ nhớ, hoãn sang request
#: ('deferred-to-request'): không thread nền, không sleep, không gọi mạng, không
#: publish/verify. Việc tính lại xảy ra khi có request (xem POST refresh bên dưới).
RADAR_SCHEDULE = RadarSchedule(timezone_name=RADAR_TIMEZONE_NAME)


def _durable_schedule_snapshot(conn, moment: datetime) -> dict:
    """Expose the durable scheduler state without leaking internal fields."""
    radar_scheduler.ensure_ledger(conn)
    identity = radar_scheduler.run_identity_for(moment, tz=RADAR_SCHEDULE.local_timezone())
    row = conn.execute(
        "SELECT status, attempts, completed_at, lease_expires_at FROM radar_schedule_runs WHERE run_identity = ?",
        (identity,),
    ).fetchone()
    now_local = moment.astimezone(RADAR_SCHEDULE.local_timezone())
    scheduled = RADAR_SCHEDULE.scheduled_time_local(moment)
    if now_local >= scheduled:
        scheduled += timedelta(days=1)
    return {
        "run_identity": identity,
        "status": row["status"] if row else None,
        "attempts": row["attempts"] if row else 0,
        "completed_at": row["completed_at"] if row else None,
        "lease_expires_at": row["lease_expires_at"] if row else None,
        "due": now_local >= RADAR_SCHEDULE.scheduled_time_local(moment),
        "next_local_run": scheduled.astimezone(RADAR_SCHEDULE.local_timezone()).isoformat(),
    }

@app.get("/api/radar")
def public_radar(request: Request) -> dict:
    """Daily Radar public chỉ-đọc: bài đã xuất bản + change event THẬT theo cửa sổ.

    Cửa sổ ngoài allowlist -> 422; không tham số nào của người gọi đi vào SQL.
    """
    filters = dict(request.query_params.multi_items())
    unknown = sorted(key for key in filters if key not in RADAR_QUERY_PARAMS)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}"
        )
    window = filters.get("window", "today")
    try:
        validate_window(window)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    conn = get_connection()
    now = datetime.now(timezone.utc)
    try:
        result = daily_radar(conn, window=window)
        durable = _durable_schedule_snapshot(conn, now)
    finally:
        conn.close()
    return {**result, "schedule": {**RADAR_SCHEDULE.snapshot(now), "durable": durable}}


@app.post("/api/admin/radar/refresh")
def admin_radar_refresh(request: Request, window: str = "today") -> dict:
    """Tính lại Daily Radar CỤC BỘ sau khi xác thực — không mạng, không publish/verify.

    require_admin() chạy ở dòng ĐẦU handler, TRƯỚC khi mở/kết nối DB.
    """
    require_admin(request)
    try:
        validate_window(window)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    conn = get_connection()
    now = datetime.now(timezone.utc)
    try:
        scheduled = radar_scheduler.run_daily_radar_once(
            conn, owner="manual-refresh", now=now, window=window,
            tz=RADAR_SCHEDULE.local_timezone(),
        )
        result = scheduled.get("radar") or daily_radar(conn, window=window)
        ledger = _durable_schedule_snapshot(conn, now)
    finally:
        conn.close()
    marked_at = RADAR_SCHEDULE.mark(now)
    return {
        "status": "REFRESHED",
        "deferred_to_request": True,
        "refreshed_at": marked_at,
        "window": window,
        "schedule": {**RADAR_SCHEDULE.snapshot(marked_at), "durable": ledger},
        "ledger": {**ledger, "reason": scheduled.get("reason", "manual")},
        "radar": result,
    }


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


# --- Inbox admin API (sri-003): ranh giới xác thực của scheduled inbox --------
# Mỗi handler gọi require_admin() ở dòng ĐẦU, TRƯỚC khi mở/kết nối DB.
# Scan chỉ dùng thư mục inbox do server self-quản (resolve_inbox_dir()); mọi
# response dùng allowlist tường minh — không raw report/provenance/quarantine
# path/token/registry config/reviewer note.

#: Các key DUY NHẤT của response scan — đúng bộ đếm InboxScanResult + mốc thời.
INBOX_SCAN_KEYS = (
    "status",
    "scanned_at",
    "imported_runs",
    "skipped_runs",
    "quarantined_runs",
    "accepted_findings",
    "skipped_findings",
)

#: Query parameter DUY NHẤT được phép trên GET /api/admin/inbox/runs & /articles.
INBOX_LIST_QUERY_PARAMS = frozenset({"limit"})

#: Trần limit (bounded) cho bất kỳ list endpoint inbox nào.
INBOX_MAX_LIMIT = 500


def _inbox_limit(request: Request) -> int | None:
    """Đọc và xác thực query parameter ``limit`` cho list endpoint inbox."""
    filters = dict(request.query_params.multi_items())
    unknown = sorted(key for key in filters if key not in INBOX_LIST_QUERY_PARAMS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}")
    limit = filters.get("limit")
    if limit is None:
        return None
    if not limit.isdigit():
        raise HTTPException(status_code=422, detail="limit must be a non-negative integer")
    value = int(limit)
    if value > INBOX_MAX_LIMIT:
        raise HTTPException(status_code=422, detail=f"limit must be at most {INBOX_MAX_LIMIT}")
    return value


@app.post("/api/admin/inbox/scan")
def admin_inbox_scan(request: Request) -> dict:
    """Quét thư mục inbox do server tự quản — không nhận dữ liệu từ request.

    Không có path/artifact body/source URLs/model instructions nào đến từ
    request: thư mục lấy từ cấu hình server (resolve_inbox_dir). require_admin
    chạy TRƯỚC khi mở DB hay ngó inbox. Mọi bài sinh ra là DRAFT.
    """
    require_admin(request)
    try:
        inbox_dir = resolve_inbox_dir()
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    conn = get_connection()
    try:
        try:
            result = scan_inbox(inbox_dir, conn)
        except NotADirectoryError as error:
            # Thư mục inbox thiếu/không hợp lệ → lỗi rõ ràng, không đổi state.
            raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        conn.close()
    return {
        "status": "SCANNED",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "imported_runs": result.imported_runs,
        "skipped_runs": result.skipped_runs,
        "quarantined_runs": result.quarantined_runs,
        "accepted_findings": result.accepted_findings,
        "skipped_findings": result.skipped_findings,
    }


@app.get("/api/admin/inbox/runs")
def admin_inbox_runs(request: Request) -> dict:
    """Danh sách ledger run inbox — chỉ các cột ledgger an toàn (allowlist)."""
    require_admin(request)
    limit = _inbox_limit(request)
    conn = get_connection()
    try:
        runs = list_inbox_runs(conn, limit=limit)
    finally:
        conn.close()
    return {"runs": runs, "count": len(runs)}


@app.get("/api/admin/inbox/articles")
def admin_inbox_articles(request: Request) -> dict:
    """Danh sách bài sinh bởi inbox — CHỈ các cột review an toàn (allowlist).

    Review/evidence label & thời điểm quan sát hiển thị qua workflow duyệt có
    sẵn; response này không bao giờ chứa raw/provenance/quarantine path.
    """
    require_admin(request)
    limit = _inbox_limit(request)
    conn = get_connection()
    try:
        articles = list_inbox_articles(conn, limit=limit)
    finally:
        conn.close()
    return {"articles": articles, "count": len(articles)}


# --- Repository Explorer (task r2): catalogue repo GitHub, bounded, no network ---
# Luật public default: CHỈ trả row REAL + canonical https://github.com +
# VERIFIED + provenance và license khác rỗng. SAMPLE, URL không phải GitHub,
# UNVERIFIED/STALE/EXPIRED, thiếu provenance/license tuyệt đối không hiện
# ở chế độ mặc định. Không có bất kỳ cuộc gọi GitHub API nào — đây là
# catalogue nội bộ chỉ-đọc.
#
#: Query parameter DUY NHẤT được phép trên GET /api/repositories.
REPOSITORIES_QUERY_PARAMS = frozenset(
    {"q", "difficulty", "license", "verification_status", "limit"}
)

#: Trần limit bounded cho GET /api/repositories.
REPOSITORIES_DEFAULT_LIMIT = 50
REPOSITORIES_MAX_LIMIT = 100

#: Độ dài tối đa của chuỗi tìm kiếm q.
REPOSITORIES_MAX_Q_LENGTH = 200

#: Cột public DUY NHẤT của một row repository — SELECT tường minh, không
#: provenance, không data_origin, không created_at nội bộ.
PUBLIC_REPOSITORY_FIELDS = (
    "id", "canonical_url", "name", "purpose", "use_case",
    "tradeoffs", "license", "updated_at", "difficulty", "verification_status",
)

#: SELECT tường minh, loại SAMPLE + chỉ canonical https://github.com.
_REPOSITORIES_BASE_SELECT = """
SELECT id AS id,
       canonical_url AS canonical_url,
       name AS name,
       purpose AS purpose,
       use_case AS use_case,
       tradeoffs AS tradeoffs,
       license AS license,
       updated_at AS updated_at,
       difficulty AS difficulty,
       verification_status AS verification_status
FROM repositories
WHERE (data_origin IS NULL OR data_origin != 'SAMPLE')
  AND canonical_url LIKE 'https://github.com/%'
"""


def list_repositories(
    q: str | None = None,
    difficulty: str | None = None,
    license: str | None = None,
    verification_status: str | None = None,
    limit: str | None = None,
) -> list[dict]:
    """Repository Explorer public — cột allowlist, bind parameters, bounded.

    Default (không có verification_status): chỉ VERIFIED + provenance và
    license khác rỗng. Có verification_status: chế độ xem lịch sử theo
    trạng thái (vẫn loại SAMPLE, vẫn yêu cầu canonical URL GitHub).
    Không có cuộc gọi mạng nào tới GitHub.
    """
    if difficulty is not None and difficulty not in REPOSITORY_DIFFICULTY:
        raise HTTPException(status_code=422, detail=f"invalid difficulty: {difficulty!r}")
    if verification_status is not None and verification_status not in VERIFICATION_STATUS:
        raise HTTPException(
            status_code=422, detail=f"invalid verification_status: {verification_status!r}"
        )
    if license is not None and not license.strip():
        raise HTTPException(status_code=422, detail="license must not be empty")
    query = (q or "").strip()
    if len(query) > REPOSITORIES_MAX_Q_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"q exceeds {REPOSITORIES_MAX_Q_LENGTH} characters",
        )
    effective_limit = REPOSITORIES_DEFAULT_LIMIT
    if limit is not None:
        if not str(limit).isdigit():
            raise HTTPException(status_code=422, detail="limit must be a positive integer")
        value = int(limit)
        if value < 1 or value > REPOSITORIES_MAX_LIMIT:
            raise HTTPException(
                status_code=422,
                detail=f"limit must be between 1 and {REPOSITORIES_MAX_LIMIT}",
            )
        effective_limit = value

    where: list[str] = []
    params: list[object] = []
    if verification_status is not None:
        # Chế độ xem lịch sử: vẫn giữ luật canonical GitHub + loại SAMPLE.
        where.append("verification_status = ?")
        params.append(verification_status)
    else:
        # Default public: VERIFIED + provenance/license không được rỗng.
        where.append("verification_status = 'VERIFIED'")
        where.append("TRIM(COALESCE(provenance, '')) <> ''")
        where.append("TRIM(COALESCE(license, '')) <> ''")
    if query:
        where.append("(name LIKE ? OR COALESCE(purpose, '') LIKE ? OR COALESCE(use_case, '') LIKE ?)")
        needle = f"%{query}%"
        params.extend((needle, needle, needle))
    if difficulty is not None:
        where.append("difficulty = ?")
        params.append(difficulty)
    if license is not None and license.strip():
        where.append("license = ?")
        params.append(license.strip())

    sql = _REPOSITORIES_BASE_SELECT
    if where:
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY name, id LIMIT ?"
    params.append(effective_limit)

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


@app.get("/api/repositories")
def public_repositories(request: Request) -> list[dict]:
    """GET /api/repositories — catalogue repo GitHub public, bounded, chỉ-đọc.

    Chỉ nhận query parameter trong allowlist (tham số lạ -> 422); default
    chỉ trả repo REAL, VERIFIED, có canonical URL GitHub và provenance/
    license không rỗng. Không có cuộc gọi GitHub API.
    """
    filters = dict(request.query_params.multi_items())
    unknown = sorted(key for key in filters if key not in REPOSITORIES_QUERY_PARAMS)
    if unknown:
        raise HTTPException(
            status_code=422, detail=f"unknown query parameters: {', '.join(unknown)}"
        )
    return list_repositories(**filters)
