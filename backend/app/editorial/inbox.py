"""Source-grounded inbox editorial draft adapter (sri-002).

Chuyển một finding đã validate (``ScheduledFinding``) thành một bản nháp bài
viết tiếng Việt ngắn, bám nguồn, luôn ở vòng đời ``DRAFT``.

Hợp đồng an toàn:
- Input bounded, data-only: chỉ đọc các trường allowlist của finding
  (title, summary, category, canonical_urls, verification_status) +
  ``observed_at`` do caller (scanner) cấp. Không trường nào được chọn lệnh,
  đường dẫn, request option hay trạng thái publish.
- Tái dụng đúng đường validate gateway hiện có (``enrich_draft``): gateway
  vốn chỉ có thể trả draft ``NEEDS_REVIEW``/``NOT_VERIFIED`` và
  ``DRAFT``/``PENDING_REVIEW``; mọi lỗi (thiếu cấu hình, timeout, 5xx, JSON
  hỏng, key lạ, lifecycle publish, injection, category/risk ngoài tập) đều
  rơi về deterministic rules.
- Sau MỌI đường dẫn: ``lifecycle`` chốt ``DRAFT``; ``verification_status``
  là trạng thái nguồn (bảo thủ) hoặc chặt hơn — gateway không bao giờ sinh
  ``VERIFIED``.
- Summary giữ link nguồn chính thức (+ thời điểm quan sát khi được cấp) cho
  attribution an toàn với người đọc; provenance riêng (run_id, evidence_note
  ...) do scanner giữ trong DB.
- Không bịa quota/giá/hết hiệu lực/trạng thái free: text chỉ là khung tiếng
  Việt + nội dung quan sát được của chính nguồn + link nguồn.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Callable, Mapping

from ..inbox.schema import Finding as ScheduledFinding
from .gateway import (
    GatewayLimits,
    GatewayTransport,
    enrich_draft,
)
from .schema import (
    MAX_SUMMARY_CHARS,
    MAX_TITLE_CHARS,
    UNKNOWN_CATEGORY,
    EditorialDraft,
)

#: Allowlist mapping ``finding.category`` (text tự do của report) → editorial
#: category. Thứ tự trong tuple là thứ tự ưu tiên; không khớp → UNKNOWN.
_CATEGORY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("POLICY_QUOTA", ("quota", "hạn mức", "chính sách", "policy", "rate limit")),
    ("FREE_MODEL_EXPLORER", ("free model", "free tier", "free api", "model miễn phí", "miễn phí")),
    ("AI_DEALS", ("deal", "offer", "khuyến mãi", "ưu đãi", "promo", "voucher")),
    ("PROVIDER_COMPARISON", ("comparison", "so sánh", "benchmark", "provider")),
    ("ADMIN_RADAR", ("admin", "nội bộ", "quản trị")),
    ("TIP_TRICK", ("tip", "trick", "mẹo", "thủ thuật", "tutorial", "hướng dẫn")),
    ("AI_MODEL", ("model", "ai", "mô hình", "llm")),
)

#: Khung mở đầu tiếng Việt theo trạng thái xác minh ĐÃ LƯU (bảo thủ).
_STATUS_LEAD: dict[str, str] = {
    "UNVERIFIED": "Chưa xác minh",
    "NEEDS_REVIEW": "Cần kiểm tra lại",
    "VERIFIED": "Đã xác minh theo nguồn",
}

#: Source row cố định của inbox — trùng service.SOURCE_ID, không lấy từ artifact.
_SOURCE_ID = "scheduled_inbox"


def _bounded(value: str, limit: int) -> str:
    """NFC + collapse whitespace + cắt trần — text ra luôn là dữ liệu thuần."""
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFC", value).split())[:limit]


def _map_category(raw_category: str) -> str:
    """Mapping bounded; text lạ → UNKNOWN (không bao giờ ném lỗi)."""
    text = _bounded(raw_category, 120).casefold()
    for category, terms in _CATEGORY_TERMS:
        if any(term in text for term in terms):
            return category
    return UNKNOWN_CATEGORY


def _source_line(source_url: str, observed_at: datetime | None) -> str:
    """Dòng attribution an toàn với người đọc: link nguồn + thời điểm quan sát."""
    line = f"Nguồn: {source_url}"
    if observed_at is not None:
        line += f", quan sát {observed_at.isoformat()}"
    return line + "."


def _compose_summary(lead: str, analysis: str, source_line: str) -> str:
    """Khung tiếng Việt + analysis bounded + dòng nguồn; luôn ≤ 600 ký tự.

    Link nguồn luôn sống sót; analysis bị cắt trước. Trường hợp bệnh lý
    (URL dài quá trần), chỉ giữ khung + dòng nguồn bị cắt — URL đầy đủ vẫn
    nằm ở cột url của article và provenance.
    """
    prefix = f"[{lead}] "
    tail = " " + source_line
    budget = MAX_SUMMARY_CHARS - len(prefix) - len(tail)
    if budget <= 0:
        return (prefix + tail)[:MAX_SUMMARY_CHARS]
    analysis = _bounded(analysis, budget)
    if not analysis:
        return prefix.rstrip() + tail
    return f"{prefix}{analysis}{tail}"[:MAX_SUMMARY_CHARS]


def create_inbox_article_draft(
    finding: ScheduledFinding,
    *,
    observed_at: datetime | None = None,
    transport: GatewayTransport | None = None,
    environ: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] | None = None,
    limits: GatewayLimits | None = None,
) -> EditorialDraft:
    """Tạo draft tiếng Việt ngắn, source-grounded, luôn ``DRAFT``.

    ``finding`` phải là ``ScheduledFinding`` đã validate; mọi text field đều
    là dữ liệu untrusted. Gateway (nếu được cấu hình qua ``environ``/env) chỉ
    được dùng qua đường validate hiện có; mọi thất bại → deterministic rules.
    Hàm này không I/O ngoài call gateway được cấp; không bao giờ publish hay
    nâng trạng thái xác minh.
    """
    if not isinstance(finding, ScheduledFinding):
        raise ValueError("finding must be a ScheduledFinding")
    if observed_at is not None and (
        observed_at.tzinfo is None or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at must be offset-aware")
    if not finding.canonical_urls:
        raise ValueError("finding must carry at least one canonical URL")

    source_url = finding.canonical_urls[0]
    # Bounded data-only raw item cho đường gateway/rules hiện có.
    raw_item = {
        "title": _bounded(finding.title, 300),
        "content": _bounded(finding.summary, 20_000),
        "source_id": _SOURCE_ID,
        "data_origin": "REAL",
    }
    result = enrich_draft(
        raw_item, transport=transport, environ=environ, sleep=sleep, limits=limits
    )
    base = result.draft

    if result.source == "GATEWAY":
        # Output đã qua validate: bounded, injection-probed, NEEDS_REVIEW,
        # NOT_VERIFIED, lifecycle DRAFT/PENDING_REVIEW.
        title = base.title
        analysis = base.summary_vi
        category = base.category
    else:
        # Deterministic: echo data nguồn (không bịa), category qua allowlist.
        title = _bounded(finding.title, MAX_TITLE_CHARS)
        analysis = _bounded(finding.summary, 20_000)
        category = _map_category(finding.category)
    # Mọi đường dẫn đều chốt NEEDS_REVIEW: không inbox output nào xác minh
    # được. Claim VERIFIED/UNVERIFIED/NEEDS_REVIEW của report chỉ là dữ liệu —
    # vẫn nằm trong provenance riêng tư và trong nhãn tiếng Việt bên dưới
    # (bảo thủ hơn hoặc bằng trạng thái nguồn).
    verification = "NEEDS_REVIEW"

    return EditorialDraft(
        title=title,
        # Nhãn mở đầu theo claim của chính nguồn (bám nguồn, không bịa).
        summary_vi=_compose_summary(_STATUS_LEAD[finding.verification_status], analysis, _source_line(source_url, observed_at)),
        category=category,
        usefulness=base.usefulness,
        risk=base.risk,
        recommendation=base.recommendation,
        lifecycle="DRAFT",  # chốt cứng: không đường nào publish được
        source_id=base.source_id or _SOURCE_ID,
        verification_status=verification,
        freshness="NOT_VERIFIED",
        signals=base.signals,
        content_hash=base.content_hash,
        data_origin="REAL",
    )
