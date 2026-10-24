"""Daily Radar — tổng hợp tín hiệu THẬT (bài xuất bản + change event) theo cửa sổ.

Hợp đồng (task 015):
- Cửa sổ hợp lệ CHÍNH XÁC: 'today', '7d', '30d', 'all'; giá trị khác -> ValueError
  (route public map thành 422).
- 'today' lấy biên lịch Asia/Ho_Chi_Minh; '7d'/'30d' là biên dưới cuộn (rolling)
  nhận thức UTC; 'all' không có biên dưới.
- Chỉ đọc cột tường minh bằng tham số '?' — không SELECT *, không nối chuỗi vào SQL.
  Chỉ gồm bài article_status='PUBLISHED' không SAMPLE và change_events không SAMPLE;
  KHÔNG bao giờ trả before/after_snapshot, raw_content hay nội dung raw.
- Trạng thái tất định từ mốc bằng chứng mới nhất: không bằng chứng -> SIGNAL_WEAK;
  mốc cũ hơn stale_after_days (> 30 ngày) -> STALE; ngược lại CURRENT.
  Timestamp thiếu/không đọc được KHÔNG BAO GIỜ thành bằng chứng tươi.
- Trả về số lượng + danh sách CÓ CHẶN (bounded) và generated_at; không secret.

An toàn dữ liệu ngoài (AGENTS.md #8): title/url/event text là dữ liệu untrusted —
chỉ được đọc ra và trả nguyên văn làm dữ liệu, không bao giờ thực thi, không bao giờ
nội suy vào SQL hay thành lệnh sửa file.

Timezone: IANA tzdata có thể không có sẵn trên Windows (zoneinfo cần gói 'tzdata').
Việt Nam cố định UTC+7 và KHÔNG có DST kể từ 1975, nên fallback offset cố định +07:00
(tên 'Asia/Ho_Chi_Minh') là chính xác cho mọi mốc trong phạm vi sản phẩm; máy có
tzdata (Linux/CI) vẫn dùng ZoneInfo thật.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

#: Cửa sổ hợp lệ — đúng thứ tự và đúng tên, không có cửa sổ nào khác.
WINDOWS: tuple[str, ...] = ("today", "7d", "30d", "all")
WINDOW_SET: frozenset[str] = frozenset(WINDOWS)

#: Ngưỡng STALE mặc định (ngày): mốc bằng chứng mới nhất cũ HƠN ngưỡng này là STALE.
STALE_AFTER_DAYS: int = 30

#: Item tối đa trả về cho mỗi nguồn bằng chứng (danh sách có chặn).
MAX_ITEMS: int = 50

#: Số dòng tối đa quét cho mỗi nguồn bằng chứng (LIMIT truy vấn — có chặn).
MAX_SCAN_ROWS: int = 500

#: Múi giờ sản phẩm theo hợp đồng.
RADAR_TIMEZONE_NAME: str = "Asia/Ho_Chi_Minh"

#: Asia/Ho_Chi_Minh = UTC+7 quanh năm (Việt Nam không có DST) — offset dự phòng.
_VN_UTC_OFFSET: timedelta = timedelta(hours=7)

#: Giờ chạy Daily Radar theo lịch sản phẩm (07:00 giờ địa phương).
REFRESH_HOUR_LOCAL: int = 7
REFRESH_MINUTE_LOCAL: int = 0

#: Chế độ thực thi mặc định: KHÔNG có job nền — hoãn sang request.
EXECUTION_MODE_DEFERRED: str = "deferred-to-request"

STATUS_CURRENT: str = "CURRENT"
STATUS_STALE: str = "STALE"
STATUS_SIGNAL_WEAK: str = "SIGNAL_WEAK"

# --- Cột tường minh duy nhất trả về từ mỗi nguồn bằng chứng ---------------------
# Không raw snapshot, không content thô, không cột registry nội bộ.
_ARTICLE_SIGNAL_COLUMNS: tuple[str, ...] = (
    "id", "title", "url", "source", "category", "published_at",
)
_EVENT_SIGNAL_COLUMNS: tuple[str, ...] = (
    "id", "event_type", "detected_at",
)

#: SELECT tường minh — tên cột là hằng số module, không bao giờ là dữ liệu ngoài.
#: Mọi giá trị run-time đều qua tham số '?'; 'LIMIT ?' cũng là tham số (có chặn).
_ARTICLE_SQL: str = (
    "SELECT " + ", ".join(_ARTICLE_SIGNAL_COLUMNS)
    + " FROM articles"
    + " WHERE article_status = ? AND (data_origin IS NULL OR data_origin != ?)"
    + " ORDER BY id DESC LIMIT ?"
)
_EVENT_SQL: str = (
    "SELECT " + ", ".join(_EVENT_SIGNAL_COLUMNS)
    + " FROM change_events"
    + " WHERE data_origin IS NULL OR data_origin != ?"
    + " ORDER BY id DESC LIMIT ?"
)


def local_timezone(name: str = RADAR_TIMEZONE_NAME) -> tzinfo:
    """Múi giờ theo tên IANA; thiếu tzdata (Windows) thì dùng offset cố định +07:00.

    Việt Nam không có DST, nên offset cố định mang đúng tên 'Asia/Ho_Chi_Minh' là
    chính xác cho mọi mốc ngày trong phạm vi sản phẩm.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except (ImportError, KeyError):  # ZoneInfoNotFoundError là subclass của KeyError
        return timezone(_VN_UTC_OFFSET, name)


def parse_timestamp(value: Any) -> datetime | None:
    """Chỉ chấp nhận timestamp ISO-8601 rõ ràng; mọi thứ khác -> None (chưa biết).

    'Z' -> '+00:00'; naive được coi là UTC (quy ước của radar/changes.py) để phép so
    sánh với biên cửa sổ aware luôn hợp lệ và tất định.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_utc(moment: datetime | str | None, field: str = "now") -> datetime:
    """Chuẩn hoá một mốc thời gian về aware UTC; hình dạng khác -> ValueError."""
    if moment is None:
        return datetime.now(timezone.utc)
    if isinstance(moment, str):
        parsed = parse_timestamp(moment)
        if parsed is None:
            raise ValueError(f"{field} must be an ISO-8601 timestamp")
        return parsed.astimezone(timezone.utc)
    if isinstance(moment, datetime):
        if moment.tzinfo is None:
            return moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc)
    raise ValueError(f"{field} must be a datetime, an ISO-8601 string or None")


def validate_window(window: str) -> str:
    """Cửa sổ hợp lệ duy nhất là today/7d/30d/all; khác -> ValueError (route -> 422)."""
    if window not in WINDOW_SET:
        raise ValueError(f"invalid window: {window!r} (allowed: {', '.join(WINDOWS)})")
    return window


def window_bounds(
    window: str,
    *,
    now: datetime,
    tz: tzinfo,
) -> tuple[datetime | None, datetime | None]:
    """(biên_dưới_utc, biên_trên_utc) cho một cửa sổ; None = không có biên.

    - 'today': [nửa đêm hôm nay .. nửa đêm mai) theo lịch Asia/Ho_Chi_Minh.
    - '7d'/'30d': [now - N ngày .. None) — rolling nhận thức UTC (now đã aware UTC).
    - 'all': (None, None) — không có biên dưới.
    """
    validate_window(window)
    now_utc = now.astimezone(timezone.utc)
    if window == "all":
        return None, None
    if window == "today":
        local = now_utc.astimezone(tz)
        start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    days = 7 if window == "7d" else 30
    return now_utc - timedelta(days=days), None


@dataclass
class RadarSchedule:
    """Mốc lịch chạy Daily Radar 07:00 Asia/Ho_Chi_Minh — CHỈ trong bộ nhớ.

    Không thread nền, không sleep, không dependency, không gọi mạng, không
    publish/verify. Việc tính lại được HOÃN sang request ('deferred-to-request'):
    GET /api/radar chỉ đọc; POST /api/admin/radar/refresh là nơi đóng dấu mốc.
    """

    refresh_hour_local: int = REFRESH_HOUR_LOCAL
    refresh_minute_local: int = REFRESH_MINUTE_LOCAL
    timezone_name: str = RADAR_TIMEZONE_NAME
    execution_mode: str = EXECUTION_MODE_DEFERRED
    last_marker_at: str | None = None

    def local_timezone(self) -> tzinfo:
        return local_timezone(self.timezone_name)

    def scheduled_time_local(self, moment: datetime | str | None) -> datetime:
        """07:00 giờ địa phương của NGÀY chứa `moment` (aware local)."""
        now_local = _as_utc(moment).astimezone(self.local_timezone())
        return now_local.replace(
            hour=self.refresh_hour_local,
            minute=self.refresh_minute_local,
            second=0,
            microsecond=0,
        )

    def is_due(self, moment: datetime | str | None = None) -> bool:
        """Đã qua 07:00 hôm nay (giờ địa phương) mà chưa có mốc nào cho hôm nay chưa?"""
        now_utc = _as_utc(moment)
        now_local = now_utc.astimezone(self.local_timezone())
        scheduled = self.scheduled_time_local(now_utc)
        if now_local < scheduled:
            return False
        marker = parse_timestamp(self.last_marker_at)
        if marker is None:
            return True
        return marker.astimezone(self.local_timezone()) < scheduled

    def mark(self, moment: datetime | str | None = None) -> str:
        """Đóng dấu mốc "đã chạy" bằng thời điểm hiện tại; trả về chuỗi ISO lưu giữ."""
        marker = _as_utc(moment).isoformat()
        self.last_marker_at = marker
        return marker

    def snapshot(self, moment: datetime | str | None = None) -> dict:
        """Trạng thái marker để test/doc — không có secret, không có instruction."""
        now_utc = _as_utc(moment)
        local_now = now_utc.astimezone(self.local_timezone())
        scheduled = self.scheduled_time_local(local_now)
        if local_now >= scheduled:
            scheduled = scheduled + timedelta(days=1)
        return {
            "refresh_local_time": f"{self.refresh_hour_local:02d}:{self.refresh_minute_local:02d}",
            "timezone": self.timezone_name,
            "execution_mode": self.execution_mode,
            "deferred_to_request": True,
            "last_marker_at": self.last_marker_at,
            "due": self.is_due(now_utc),
            "next_local_run": scheduled.astimezone(self.local_timezone()).isoformat(),
        }


def _collect(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[object, ...],
    lower: datetime | None,
    upper: datetime | None,
    timestamp_column: str,
    window: str,
    limit: int,
) -> dict:
    """Quét (có chặn) một nguồn bằng chứng rồi lọc theo cửa sổ bằng code thuần.

    Trả về dict: items (đã cắt theo `limit`), newest (mốc hợp lệ mới nhất hoặc None),
    selected (số dòng hợp lệ trong phạm vi scan — để báo counts trung thực),
    bounded (scan chạm MAX_SCAN_ROWS). Timestamp không đọc được (NULL/lạ) chỉ được
    coi là item hợp lệ cho cửa sổ 'all' (không có biên dưới); CHÚNG KHÔNG BAO GIỜ
    thành bằng chứng 'newest' — không bịa freshness.
    """
    scan_limit = MAX_SCAN_ROWS
    rows = conn.execute(sql, [*params, scan_limit]).fetchall()
    bounded = len(rows) >= scan_limit

    qualified: list[tuple[datetime | None, dict]] = []
    for row in rows:
        record = dict(row)
        stamp = parse_timestamp(record.get(timestamp_column))
        if stamp is None:
            # Undated: chỉ được liệt kê (không làm bằng chứng) khi không có biên dưới.
            if window == "all":
                qualified.append((None, record))
            continue
        if lower is not None and stamp < lower:
            continue
        if upper is not None and stamp >= upper:
            continue
        qualified.append((stamp, record))

    # Sắp xếp tất định: có mốc mới nhất trước, undated sau cùng (theo id giảm dần).
    def _sort_key(pair: tuple[datetime | None, dict]) -> tuple[object, ...]:
        stamp, record = pair
        if stamp is None:
            return (1, 0.0, -int(record["id"]))
        return (0, -stamp.timestamp(), -int(record["id"]))

    qualified.sort(key=_sort_key)

    newest = max((stamp for stamp, _ in qualified if stamp is not None), default=None)
    return {
        "items": [record for _, record in qualified[:limit]],
        "newest": newest,
        "selected": len(qualified),
        "bounded": bounded,
    }


def daily_radar(
    conn: sqlite3.Connection,
    window: str = "today",
    *,
    now: datetime | str | None = None,
    tz: tzinfo | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
    limit: int = MAX_ITEMS,
) -> dict:
    """Tổng hợp Daily Radar trong một cửa sổ — tất định, có chặn, không chạm mạng.

    window không hợp lệ / stale_after_days / limit sai / now ko parse được -> ValueError
    (route public map thành 422). Trạng thái CHỈ do bằng chứng tươi quyết định.
    """
    validate_window(window)
    if isinstance(stale_after_days, bool) or not isinstance(stale_after_days, int) or stale_after_days <= 0:
        raise ValueError("stale_after_days must be a positive int")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive int")
    moment = _as_utc(now)
    zone = tz if tz is not None else local_timezone()
    lower, upper = window_bounds(window, now=moment, tz=zone)

    article_scan = _collect(
        conn, _ARTICLE_SQL, ("PUBLISHED", "SAMPLE"),
        lower, upper, "published_at", window, limit,
    )
    event_scan = _collect(
        conn, _EVENT_SQL, ("SAMPLE",),
        lower, upper, "detected_at", window, limit,
    )

    newest = None
    for candidate in (article_scan["newest"], event_scan["newest"]):
        if candidate is not None and (newest is None or candidate > newest):
            newest = candidate

    if newest is None:
        status = STATUS_SIGNAL_WEAK
    elif moment - newest > timedelta(days=stale_after_days):
        status = STATUS_STALE
    else:
        status = STATUS_CURRENT

    articles, events = article_scan["items"], event_scan["items"]
    truncated = article_scan["selected"] > len(articles) or event_scan["selected"] > len(events)
    return {
        "window": window,
        "timezone": RADAR_TIMEZONE_NAME,
        "generated_at": moment.isoformat(),
        "window_start": lower.isoformat() if lower is not None else None,
        "window_end": upper.isoformat() if upper is not None else None,
        "stale_after_days": stale_after_days,
        "status": status,
        "is_stale": status == STATUS_STALE,
        "newest_evidence_at": newest.isoformat() if newest is not None else None,
        "counts": {
            "articles": article_scan["selected"],
            "change_events": event_scan["selected"],
        },
        "articles": articles,
        "change_events": events,
        "truncated": truncated,
        "scan_bounded": article_scan["bounded"] or event_scan["bounded"],
    }
