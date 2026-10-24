"""Vũ Học AI Radar — lõi quan sát radar (Phase 8, task 009).

Chỉ chứa logic thuần, bảo thủ: phát hiện thay đổi snapshot (changes) và ghi
quan sát quota append-only (quota). Chưa có route admin/collector trong task này.

Nguyên tắc bất biến:
- Snapshot/source text là dữ liệu KHÔNG tin cậy: chỉ được so sánh/lưu, không
  được thực thi và không được dùng để dựng SQL.
- Thiếu/timeout quan sát = tín hiệu lỗi thu thập, không bao giờ là MODEL_REMOVED.
"""
from __future__ import annotations

from .changes import (
    EVENT_TYPES,
    ChangeEvent,
    CollectionUnavailable,
    detect_offer_changes,
    detect_provider_model_changes,
    evaluate_verification,
)
from .quota import quota_history, record_quota_observation

__version__ = "0.1.0"

__all__ = [
    "EVENT_TYPES",
    "ChangeEvent",
    "CollectionUnavailable",
    "detect_offer_changes",
    "detect_provider_model_changes",
    "evaluate_verification",
    "quota_history",
    "record_quota_observation",
]
