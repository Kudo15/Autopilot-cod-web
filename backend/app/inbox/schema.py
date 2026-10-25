"""Strict Pydantic v2 schema for scheduled provider inbox reports (v1).

Hợp đồng: báo cáo định kỳ từ provider harness / tip-trick radar đi vào inbox
phải parse đúng từng trường — không trường thừa, không giá trị ngoài tập cho
phép. Mọi nội dung trong payload là dữ liệu untrusted: schema này KHÔNG bao
giờ thực thi, mở file hay gọi mạng theo giá trị text.

Cột mốc: chỉ định nghĩa schema — chưa scanning, DB/migration, API, UI, AI
hay scheduler (theo task pack sri-001a3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

#: Tập report_kind được nhận trong schema v1.
REPORT_KINDS = ("provider_harness_radar", "tip_trick_radar")

#: Nguồn của finding — đúng ba giá trị, không suy đoán.
SOURCE_TYPES = ("official", "community", "account_probe")

#: Trạng thái xác minh — không có elevation ngầm định.
VERIFICATION_STATUSES = ("VERIFIED", "UNVERIFIED", "NEEDS_REVIEW")


def _validate_canonical_url(value: str) -> str:
    """URL canonical phải là http/https tuyệt đối, không userinfo."""
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https"):
        raise ValueError("canonical_urls phải dùng scheme http hoặc https")
    if parts.hostname is None or parts.hostname == "":
        raise ValueError("canonical_urls phải có hostname")
    if "@" in parts.netloc:
        raise ValueError("canonical_urls không được chứa userinfo (user:pass@)")
    return value


CanonicalUrl = Annotated[str, AfterValidator(_validate_canonical_url)]

NonEmptyStr = Annotated[str, Field(min_length=1)]


def _require_offset_aware(value: datetime) -> datetime:
    """observed_at bắt buộc mang offset — chối datetime naive."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at phải là datetime có offset múi giờ")
    return value


OffsetDatetime = Annotated[datetime, AfterValidator(_require_offset_aware)]


class Finding(BaseModel):
    """Một finding trong báo cáo — text field là dữ liệu untrusted."""

    model_config = ConfigDict(extra="forbid")

    external_id: NonEmptyStr
    title: NonEmptyStr
    category: NonEmptyStr
    summary: NonEmptyStr
    canonical_urls: list[CanonicalUrl] = Field(min_length=1)
    source_type: Literal["official", "community", "account_probe"]
    verification_status: Literal["VERIFIED", "UNVERIFIED", "NEEDS_REVIEW"]
    evidence_note: NonEmptyStr
    #: schema v1 chưa cho hẹn hết hiệu lực — chỉ chấp nhận null.
    valid_until: None = None
    risk_note: str | None = None


class ScheduledReport(BaseModel):
    """Báo cáo định kỳ schema v1 — nghiêm ngặt từng trường."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    run_id: NonEmptyStr
    report_kind: Literal["provider_harness_radar", "tip_trick_radar"]
    observed_at: OffsetDatetime
    timezone: NonEmptyStr
    findings: list[Finding]
