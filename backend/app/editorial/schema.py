"""Strict, immutable schema for editorial drafts.

The values in a draft are editorial metadata only. They are never instructions,
commands, verification evidence, quota data, or a publication decision.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping

UNKNOWN_CATEGORY = "UNKNOWN"
CATEGORIES = (
    "TIP_TRICK", "AI_MODEL", "POLICY_QUOTA", "FREE_MODEL_EXPLORER",
    "AI_DEALS", "PROVIDER_COMPARISON", "ADMIN_RADAR", UNKNOWN_CATEGORY,
)
CATEGORY_VALUES = frozenset(CATEGORIES)
USEFULNESS_VALUES = frozenset({"HIGH", "MEDIUM", "LOW", "UNKNOWN"})
RISK_VALUES = frozenset({"NONE", "LOW", "MEDIUM", "HIGH", "UNKNOWN"})
RECOMMENDATION_VALUES = frozenset({"SAFE_TO_TRY", "CAUTION", "INFO_ONLY"})
RANKING_VALUES = frozenset({"S", "A", "B", "C", "D"})
LIFECYCLE_VALUES = frozenset({"DRAFT", "PENDING_REVIEW"})
VERIFICATION_VALUES = frozenset({"VERIFIED", "UNVERIFIED", "STALE", "EXPIRED", "NEEDS_REVIEW"})
FRESHNESS_VALUES = frozenset({"NOT_VERIFIED", "UNKNOWN"})
DATA_ORIGIN_VALUES = frozenset({"REAL", "SAMPLE", "UNSPECIFIED"})

MAX_SOURCE_ID_CHARS = 128
MAX_TITLE_CHARS = 300
MAX_SUMMARY_CHARS = 600
MAX_RANKING_EVIDENCE_CHARS = 600
MAX_CONTENT_CHARS = 20_000
MAX_SIGNAL_CHARS = 80
MAX_SIGNALS = 16
_HASH = re.compile(r"^[0-9a-f]{64}$")


class EditorialSchemaError(ValueError):
    """A draft contains invalid, empty, unknown, or unbounded data."""


def _text(value: Any, name: str, limit: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise EditorialSchemaError(f"{name} must be text")
    value = " ".join(value.split()).strip()
    if required and not value:
        raise EditorialSchemaError(f"{name} must not be empty")
    if len(value) > limit:
        raise EditorialSchemaError(f"{name} exceeds {limit} characters")
    return value


@dataclass(frozen=True, slots=True)
class EditorialDraft:
    title: str
    summary_vi: str
    category: str
    usefulness: str
    risk: str
    recommendation: str
    lifecycle: str
    source_id: str = ""
    ranking: str | None = None
    ranking_evidence: str | None = None
    verification_status: str = "NEEDS_REVIEW"
    freshness: str = "NOT_VERIFIED"
    signals: tuple[str, ...] = ()
    content_hash: str | None = None
    data_origin: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _text(self.title, "title", MAX_TITLE_CHARS))
        object.__setattr__(self, "summary_vi", _text(self.summary_vi, "summary_vi", MAX_SUMMARY_CHARS))
        source = _text(self.source_id, "source_id", MAX_SOURCE_ID_CHARS, required=False)
        object.__setattr__(self, "source_id", source)
        for field_name, allowed in (
            ("category", CATEGORY_VALUES),
            ("usefulness", USEFULNESS_VALUES),
            ("risk", RISK_VALUES),
            ("recommendation", RECOMMENDATION_VALUES),
            ("lifecycle", LIFECYCLE_VALUES),
            ("verification_status", VERIFICATION_VALUES),
            ("freshness", FRESHNESS_VALUES),
            ("data_origin", DATA_ORIGIN_VALUES),
        ):
            value = getattr(self, field_name)
            if value not in allowed:
                raise EditorialSchemaError(f"invalid {field_name}")
        if self.ranking is not None and self.ranking not in RANKING_VALUES:
            raise EditorialSchemaError("invalid ranking")
        if self.ranking is None and self.ranking_evidence is not None:
            raise EditorialSchemaError("ranking_evidence requires ranking")
        if self.ranking is not None and not isinstance(self.ranking_evidence, str):
            raise EditorialSchemaError("ranking requires bounded evidence")
        if self.ranking_evidence is not None:
            object.__setattr__(self, "ranking_evidence", _text(self.ranking_evidence, "ranking_evidence", MAX_RANKING_EVIDENCE_CHARS))
        if self.content_hash is not None and (not isinstance(self.content_hash, str) or not _HASH.fullmatch(self.content_hash)):
            raise EditorialSchemaError("content_hash must be a lowercase SHA-256 value or None")
        if not isinstance(self.signals, tuple):
            raise EditorialSchemaError("signals must be a tuple")
        if len(self.signals) > MAX_SIGNALS:
            raise EditorialSchemaError("too many signals")
        normalized_signals = tuple(_text(signal, "signal", MAX_SIGNAL_CHARS) for signal in self.signals)
        object.__setattr__(self, "signals", normalized_signals)

    @property
    def evidence(self) -> dict[str, Any]:
        """Return bounded plain data; no text is interpreted as an instruction."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "content_hash": self.content_hash,
            "signals": self.signals,
        }

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["signals"] = list(self.signals)
        return result


def draft_from_mapping(payload: Mapping[str, Any]) -> EditorialDraft:
    if not isinstance(payload, Mapping):
        raise EditorialSchemaError("draft must be a mapping")
    allowed = set(EditorialDraft.__dataclass_fields__)
    unknown = sorted(str(key) for key in payload if key not in allowed)
    if unknown:
        raise EditorialSchemaError(f"unknown draft fields: {', '.join(unknown)}")
    return EditorialDraft(**dict(payload))
