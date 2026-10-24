"""Editorial engine — schema + deterministic rule-based fallback (task 010).

Chỉ-server, chỉ-localhost, không gateway:

- ``schema.py``        — hợp đồng bản nháp biên tập ``EditorialDraft``: enum tường
  minh + text có trần; rỗng/sai enum/key lạ đều bị từ chối; bất biến (frozen).
- ``rules.py``         — ``classify_rule_based(raw_item)`` tất định, thuần tuý:
  coi toàn bộ title/content là dữ liệu không tin cậy, không chạy lệnh, không ghi
  tệp, không gọi mạng, không đọc secret, không publish. Đầu ra chỉ ``DRAFT`` hoặc
  ``PENDING_REVIEW``.

Không có gateway/biến môi trường/route production nào thuộc phạm vi task này.
Task 011 (gateway) sẽ định nghĩa luồng AI; module này chỉ là phương án dự phòng.
"""

from .rules import classify_rule_based  # noqa: F401
from .schema import (  # noqa: F401
    CATEGORIES,
    CATEGORY_VALUES,
    DATA_ORIGIN_VALUES,
    EditorialDraft,
    EditorialSchemaError,
    FRESHNESS_VALUES,
    LIFECYCLE_VALUES,
    MAX_CONTENT_CHARS,
    MAX_RANKING_EVIDENCE_CHARS,
    MAX_SIGNAL_CHARS,
    MAX_SIGNALS,
    MAX_SOURCE_ID_CHARS,
    MAX_SUMMARY_CHARS,
    MAX_TITLE_CHARS,
    RANKING_VALUES,
    RECOMMENDATION_VALUES,
    RISK_VALUES,
    UNKNOWN_CATEGORY,
    USEFULNESS_VALUES,
    VERIFICATION_VALUES,
    draft_from_mapping,
)

__all__ = [
    "classify_rule_based",
    "EditorialDraft",
    "EditorialSchemaError",
    "draft_from_mapping",
    "CATEGORIES",
    "CATEGORY_VALUES",
    "UNKNOWN_CATEGORY",
    "USEFULNESS_VALUES",
    "RISK_VALUES",
    "RECOMMENDATION_VALUES",
    "RANKING_VALUES",
    "LIFECYCLE_VALUES",
    "VERIFICATION_VALUES",
    "FRESHNESS_VALUES",
    "DATA_ORIGIN_VALUES",
    "MAX_SOURCE_ID_CHARS",
    "MAX_TITLE_CHARS",
    "MAX_SUMMARY_CHARS",
    "MAX_RANKING_EVIDENCE_CHARS",
    "MAX_CONTENT_CHARS",
    "MAX_SIGNAL_CHARS",
    "MAX_SIGNALS",
]
