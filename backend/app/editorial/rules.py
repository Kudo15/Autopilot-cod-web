"""Pure deterministic editorial fallback.

Only a small allowlist of raw fields is read. Their contents remain text data;
no field can select a command, file operation, network request, or publication
state.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import re
import unicodedata
from typing import Any

from .schema import EditorialDraft, UNKNOWN_CATEGORY

_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ADMIN_RADAR", ("admin radar", "quản trị", "nội bộ")),
    ("AI_DEALS", ("khuyến mãi", "ưu đãi", "promo", "voucher", "coupon", "free credit", "trial")),
    ("FREE_MODEL_EXPLORER", ("free model", "model miễn phí", "free tier", "free api", "miễn phí")),
    ("PROVIDER_COMPARISON", ("so sánh", "comparison", "benchmark", "versus", "provider", "nhà cung cấp")),
    ("POLICY_QUOTA", ("quota", "hạn mức", "chính sách", "policy", "rate limit", "điều khoản", "terms", "giới hạn")),
    ("AI_MODEL", ("mô hình", "model", "llm", "gpt", "gemini", "claude", "llama", "qwen", "deepseek", "mistral", "trí tuệ nhân tạo", "vision")),
    ("TIP_TRICK", ("tip", "trick", "thủ thuật", "mẹo", "hướng dẫn", "tutorial", "prompt", "workflow")),
)
_INJECTION: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("INSTRUCTION_OVERRIDE", ("ignore previous instructions", "bỏ qua hướng dẫn", "disregard", "system prompt", "developer mode", "jailbreak")),
    ("COMMAND_SHAPED", ("rm -rf", "powershell", "cmd.exe", "subprocess", "os.system", "eval(", "exec(", "curl ", "wget ", "chmod ")),
    ("FILE_WRITE_SHAPED", ("write to file", "ghi vào file", "tạo file", "save to", ">>")),
    ("SECRET_SHAPED", ("api key", "api_key", "secret", "bearer ", "token=", "password")),
    ("MARKUP_SHAPED", ("<script", "javascript:", "{{", "```")),
)
_RISK_TERMS = {
    "HIGH": ("rm -rf", "powershell", "cmd.exe", "subprocess", "os.system", "eval(", "exec("),
    "MEDIUM": ("credit card", "thẻ thanh toán", "tự động gia hạn", "subscription", "api key", "api_key", "password", "token="),
}
_UNVERIFIED_CLAIM = ("free forever", "miễn phí trọn đời", "verified quota", "quota verified", "guaranteed", "đảm bảo")


def _normalize(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFC", value).split())[:limit]


def _matches(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def _signals(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for label, terms in _INJECTION:
        if _matches(text, terms):
            found.append(label)
    return tuple(found)


def _category(text: str) -> str:
    for category, terms in _CATEGORIES:
        if _matches(text, terms):
            return category
    return UNKNOWN_CATEGORY


def _risk(text: str, signals: tuple[str, ...]) -> str:
    if "COMMAND_SHAPED" in signals or _matches(text, _RISK_TERMS["HIGH"]):
        return "HIGH"
    if "SECRET_SHAPED" in signals or _matches(text, _RISK_TERMS["MEDIUM"]):
        return "MEDIUM"
    return "LOW" if text else "UNKNOWN"


def classify_rule_based(raw_item: Mapping[str, Any]) -> EditorialDraft:
    """Classify a normalized raw item without I/O or external configuration."""
    if not isinstance(raw_item, Mapping):
        raise ValueError("raw_item must be a mapping")
    title = _normalize(raw_item.get("title"), 300)
    content = _normalize(raw_item.get("content", raw_item.get("summary", "")), 20_000)
    if not title:
        raise ValueError("raw_item.title must not be empty")
    combined = f"{title} {content}".strip()
    signals = _signals(combined)
    category = _category(combined)
    risk = _risk(combined, signals)
    usefulness = "MEDIUM" if content else "UNKNOWN"
    unverified = _matches(combined, _UNVERIFIED_CLAIM)
    recommendation = "INFO_ONLY" if risk == "HIGH" else ("CAUTION" if risk in {"MEDIUM", "UNKNOWN"} or unverified else "SAFE_TO_TRY")
    lifecycle = "PENDING_REVIEW" if category == UNKNOWN_CATEGORY or signals or risk in {"HIGH", "MEDIUM"} or unverified else "DRAFT"
    summary = content[:600] if content else title[:600]
    content_hash = raw_item.get("content_hash") if isinstance(raw_item.get("content_hash"), str) else None
    if content_hash is None and content:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    source_id = _normalize(raw_item.get("source_id"), 128)
    origin = raw_item.get("data_origin") if raw_item.get("data_origin") in {"REAL", "SAMPLE"} else "UNSPECIFIED"
    return EditorialDraft(
        title=title,
        summary_vi=summary,
        category=category,
        usefulness=usefulness,
        risk=risk,
        recommendation=recommendation,
        lifecycle=lifecycle,
        source_id=source_id,
        ranking=None,
        ranking_evidence=None,
        verification_status="NEEDS_REVIEW",
        freshness="NOT_VERIFIED",
        signals=signals,
        content_hash=content_hash,
        data_origin=origin,
    )
