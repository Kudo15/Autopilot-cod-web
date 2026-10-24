"""Deterministic change detection + freshness evaluation (Phase 8, task 009).

Hợp đồng (contract t_39e86174):
- So sánh cặp snapshot before/after (provider-model hoặc offer) và CHỈ trả về
  chín loại sự kiện được phép trong schema `change_events`.
- Bản ghi trước/sau là dữ liệu KHÔNG tin cậy: chỉ được so sánh, KHÔNG bao giờ
  được thực thi và KHÔNG bao giờ dùng để dựng SQL.
- Quan sát thiếu/timeout/không lấy được -> tín hiệu lỗi thu thập
  (`CollectionUnavailable`), TUYỆT ĐỐI không được báo MODEL_REMOVED.
- Kết quả tất định: snapshot không đổi thì không sinh sự kiện nào.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

#: Chín loại sự kiện hợp lệ — khớp CHECK constraint của bảng change_events.
_ALLOWED_EVENT_TYPES: tuple[str, ...] = (
    "NEW_PROVIDER",
    "NEW_MODEL",
    "MODEL_REMOVED",
    "FREE_TO_PAID",
    "PAID_TO_FREE",
    "QUOTA_CHANGED",
    "OFFER_STARTED",
    "OFFER_EXPIRED",
    "TERMS_CHANGED",
)
EVENT_TYPES: frozenset[str] = frozenset(_ALLOWED_EVENT_TYPES)

#: Thứ tự chuẩn hoá để kết quả tất định (không phụ thuộc thứ tự đầu vào).
_EVENT_ORDER: dict[str, int] = {name: index for index, name in enumerate(_ALLOWED_EVENT_TYPES)}

#: Tập giá trị free theo MISSION; PAID là giá trị trả phí duy nhất.
_FREE_VALUES: frozenset[str] = frozenset(
    {"FREE_API", "FREE_CREDIT", "FREE_TRIAL", "FREE_WEB_ONLY", "PROMO"}
)
_PAID_VALUES: frozenset[str] = frozenset({"PAID"})


class CollectionUnavailable(RuntimeError):
    """Tín hiệu lỗi thu thập (thiếu bản ghi / timeout / không lấy được).

    Được ném ra thay vì sinh MODEL_REMOVED để một lần timeout không bao giờ
    bị hiểu nhầm thành model bị xóa. Caller phải map nó sang trạng thái
    STALE/collection-failure ở tầng gọi (ngoài phạm vi task này).
    """


@dataclass(frozen=True)
class ChangeEvent:
    """Một thay đổi phát hiện được giữa hai quan sát.

    `key` định danh bản ghi đã đổi, `before`/`after` là snapshot tương ứng
    (None nghĩa là chưa từng có / không còn quan sát được).
    """

    event_type: str
    key: tuple[Any, ...]
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None


def _require_available(rows: Any, label: str) -> list[Mapping[str, Any]]:
    """Materialize một quan sát; rỗng/None = lỗi thu thập, không phải xóa hàng loạt."""
    if rows is None:
        raise CollectionUnavailable(f"{label} observation is missing")
    if isinstance(rows, Mapping):
        status = rows.get("status")
        if status is not None and str(status).upper() in {"TIMEOUT", "ERROR", "UNAVAILABLE", "FAILED"}:
            raise CollectionUnavailable(f"{label} observation failed: {status}")
        raise ValueError(f"{label} observation must be a sequence of snapshots, not a single mapping")
    materialized = list(rows)
    if not materialized:
        raise CollectionUnavailable(f"{label} observation is empty/unavailable")
    return materialized


def _index(
    rows: Iterable[Mapping[str, Any]] | None, key_fn, label: str
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Lập chỉ mục snapshot theo định danh; định danh trùng -> ValueError (tất định)."""
    if rows is None:
        rows = []
    index: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} snapshot rows must be mappings")
        identity = key_fn(row)
        if identity in index:
            raise ValueError(f"duplicate identity in {label} observation: {identity!r}")
        index[identity] = dict(row)
    return index


def _provider_model_key(snapshot: Mapping[str, Any]) -> tuple[Any, ...]:
    provider_id = snapshot.get("provider_id")
    model_id = snapshot.get("model_id")
    if provider_id is None or model_id is None:
        raise ValueError("provider-model snapshot requires both provider_id and model_id")
    return (provider_id, model_id)


def _offer_key(snapshot: Mapping[str, Any]) -> tuple[Any, ...]:
    offer_id = snapshot.get("offer_id")
    if offer_id is not None:
        return ("offer", offer_id)
    provider_model_id = snapshot.get("provider_model_id")
    title = snapshot.get("title")
    if provider_model_id is None or title is None:
        raise ValueError("offer snapshot requires offer_id, or provider_model_id and title")
    return ("offer", provider_model_id, title)


def _free_transition(before_value: Any, after_value: Any) -> str | None:
    """FREE_TO_PAID / PAID_TO_FREE — chỉ khi cả hai phía đều rõ ràng."""
    before_free, before_paid = before_value in _FREE_VALUES, before_value in _PAID_VALUES
    after_free, after_paid = after_value in _FREE_VALUES, after_value in _PAID_VALUES
    if before_free and after_paid:
        return "FREE_TO_PAID"
    if before_paid and after_free:
        return "PAID_TO_FREE"
    # UNKNOWN/None: không đủ bằng chứng để khẳng định chuyển hướng.
    return None


def _normalized_quota(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.lstrip("+-").isdigit():
            return int(candidate)
    return value


def _quota_changed(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    """Chỉ báo đổi quota khi cả hai phía đều biết giá trị và chúng khác nhau."""
    before_quota, after_quota = before.get("daily_quota"), after.get("daily_quota")
    if before_quota is not None and after_quota is not None:
        if _normalized_quota(before_quota) != _normalized_quota(after_quota):
            return True
    before_rate, after_rate = before.get("rate_limit"), after.get("rate_limit")
    if before_rate is not None and after_rate is not None and before_rate != after_rate:
        return True
    return False


def _sort_events(events: list[ChangeEvent]) -> list[ChangeEvent]:
    return sorted(events, key=lambda event: (_EVENT_ORDER.get(event.event_type, len(_EVENT_ORDER)), event.key))


def detect_provider_model_changes(
    before: Iterable[Mapping[str, Any]] | None,
    after: Iterable[Mapping[str, Any]] | None,
) -> list[ChangeEvent]:
    """So sánh hai quan sát provider-model và trả về danh sách sự kiện thay đổi.

    - `after` rỗng/None -> CollectionUnavailable (KHÔNG phải MODEL_REMOVED).
    - Khi `after` có ít nhất một model khác chứng minh buổi thu thập thành công,
      model vắng mặt trong `after` được báo MODEL_REMOVED.
    """
    after_rows = _require_available(after, "after")
    before_index = _index(before, _provider_model_key, "before")
    after_index = _index(after_rows, _provider_model_key, "after")

    events: list[ChangeEvent] = []

    known_providers = {identity[0] for identity in before_index}
    for provider_id in sorted(
        {identity[0] for identity in after_index} - known_providers, key=str
    ):
        observed_models = sorted(
            (identity[1] for identity in after_index if identity[0] == provider_id), key=str
        )
        events.append(
            ChangeEvent(
                "NEW_PROVIDER",
                (provider_id,),
                None,
                {"provider_id": provider_id, "model_ids": observed_models},
            )
        )

    for identity in sorted(after_index.keys() - before_index.keys()):
        events.append(ChangeEvent("NEW_MODEL", identity, None, after_index[identity]))

    for identity in sorted(before_index.keys() - after_index.keys()):
        events.append(ChangeEvent("MODEL_REMOVED", identity, before_index[identity], None))

    for identity in sorted(before_index.keys() & after_index.keys()):
        previous, current = before_index[identity], after_index[identity]
        transition = _free_transition(previous.get("free_status"), current.get("free_status"))
        if transition is not None:
            events.append(ChangeEvent(transition, identity, previous, current))
        if _quota_changed(previous, current):
            events.append(ChangeEvent("QUOTA_CHANGED", identity, previous, current))

    return _sort_events(events)


def detect_offer_changes(
    before: Iterable[Mapping[str, Any]] | None,
    after: Iterable[Mapping[str, Any]] | None,
) -> list[ChangeEvent]:
    """So sánh hai quan sát offer: OFFER_STARTED / OFFER_EXPIRED / TERMS_CHANGED.

    Cùng luật an toàn: `after` rỗng/None -> CollectionUnavailable, không bao giờ
    báo OFFER_EXPIRED cho một lần thu thập thất bại.
    """
    after_rows = _require_available(after, "after")
    before_index = _index(before, _offer_key, "before")
    after_index = _index(after_rows, _offer_key, "after")

    events: list[ChangeEvent] = []

    for identity in sorted(after_index.keys() - before_index.keys()):
        events.append(ChangeEvent("OFFER_STARTED", identity, None, after_index[identity]))

    for identity in sorted(before_index.keys() - after_index.keys()):
        events.append(ChangeEvent("OFFER_EXPIRED", identity, before_index[identity], None))

    for identity in sorted(before_index.keys() & after_index.keys()):
        previous, current = before_index[identity], after_index[identity]
        transition = _free_transition(previous.get("offer_type"), current.get("offer_type"))
        if transition is not None:
            events.append(ChangeEvent(transition, identity, previous, current))
        previous_terms, current_terms = previous.get("terms"), current.get("terms")
        if (
            previous_terms is not None
            and current_terms is not None
            and previous_terms != current_terms
        ):
            events.append(ChangeEvent("TERMS_CHANGED", identity, previous, current))

    return _sort_events(events)


def _parse_timestamp(value: Any) -> datetime | None:
    """Chỉ chấp nhận timestamp ISO-8601 rõ ràng; mọi thứ khác coi như chưa biết."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_verification(
    last_verified: str | None,
    valid_until: str | None,
    *,
    now: str | None = None,
    stale_after_days: int = 30,
    review_lead_days: int = 7,
) -> str:
    """Trạng thái xác minh chỉ từ timestamp/validity rõ ràng.

    Thứ tự quyết định (tất định, dừng ở điều kiện đầu tiên đúng):
    1. Thiếu last_verified (NULL/rỗng/không đọc được)   -> UNVERIFIED
    2. valid_until đã qua                               -> EXPIRED
    3. valid_until trong hạn review_lead_days           -> NEEDS_REVIEW
    4. last_verified cũ hơn stale_after_days            -> STALE
    5. last_verified sắp cũ (chạm ngưỡng review)        -> NEEDS_REVIEW
    6. còn lại                                          -> VERIFIED

    NULL/không rõ KHÔNG bao giờ được suy đoán thành VERIFIED.
    """
    if not isinstance(stale_after_days, int) or isinstance(stale_after_days, bool) or stale_after_days <= 0:
        raise ValueError("stale_after_days must be a positive int")
    if not isinstance(review_lead_days, int) or isinstance(review_lead_days, bool) or review_lead_days < 0:
        raise ValueError("review_lead_days must be a non-negative int")

    now_dt = _parse_timestamp(now) if now is not None else datetime.now(timezone.utc)
    if now_dt is None:
        raise ValueError("now must be an ISO-8601 timestamp or None")

    verified_dt = _parse_timestamp(last_verified)
    if verified_dt is None:
        return "UNVERIFIED"

    expiry_dt = _parse_timestamp(valid_until)
    if expiry_dt is not None and expiry_dt < now_dt:
        return "EXPIRED"
    if expiry_dt is not None and expiry_dt <= now_dt + timedelta(days=review_lead_days):
        return "NEEDS_REVIEW"

    age = now_dt - verified_dt
    if age > timedelta(days=stale_after_days):
        return "STALE"
    if age >= timedelta(days=stale_after_days - review_lead_days):
        return "NEEDS_REVIEW"
    return "VERIFIED"
