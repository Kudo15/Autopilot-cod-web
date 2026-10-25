"""Scheduled provider inbox — hợp đồng JSON nghiêm ngặt (schema v1) +
scanner an toàn (sri-001c).

- ``schema``: Pydantic v2 v1, extra='forbid'; mọi trường text là dữ liệu
  untrusted, không được thực thi.
- ``service``: quét artifact ``*.json`` cuối cùng trong thư mục inbox và
  persistence quyết định vào SQLite (sources / raw_items / articles /
  scheduled_inbox_runs) — không mạng, không lệnh, không AI enrichment.
"""
from .schema import (
    Finding,
    REPORT_KINDS,
    SOURCE_TYPES,
    ScheduledReport,
    VERIFICATION_STATUSES,
)
from .service import InboxScanResult, list_inbox_runs, scan_inbox

__all__ = [
    "Finding",
    "InboxScanResult",
    "REPORT_KINDS",
    "SOURCE_TYPES",
    "ScheduledReport",
    "VERIFICATION_STATUSES",
    "list_inbox_runs",
    "scan_inbox",
]
