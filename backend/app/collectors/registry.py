"""Strict loader for the server-only source registry (task 012).

Hợp đồng:
- Registry là **tài sản phía server**: file ``source-registry/sources.json`` nằm
  ngoài ``src/``, không bao giờ được import/đóng gói vào frontend bundle. Mọi
  entry chỉ là *dữ liệu*: text trong registry không bao giờ trở thành instruction,
  command hay SQL — không có chỗ nào trong module này thực thi nội dung registry.
- Một entry hợp lệ phải khai báo tường minh ``source_id``, ``name``, ``type``,
  ``url``, ``collection_method``, ``priority``, ``status`` và (tuỳ chọn)
  ``last_checked_at``. Sai hình dạng, ID trùng, type/method/status lạ, URL không
  phải HTTP(S), tên rỗng, priority ngoài khoảng, host private/metadata/nội bộ đều
  bị từ chối ngay tại thời điểm validate.
- ``last_checked_at`` là *bằng chứng quan sát*: chỉ nhận ISO-8601 trong quá khứ
  hoặc NULL. Một entry không có ``last_checked_at`` KHÔNG bao giờ được trình bày
  như đã quan sát thành công (``observation_state == 'NEVER_OBSERVED'``).
- Nguồn không có phương thức thu thập tự động hợp lệ phải được đánh dấu tường minh
  (``collection_method='manual_import'`` + ``status`` 'manual'/'unavailable'/'sample');
  chúng không bao giờ ``automated_collectable``.

Module này KHÔNG thực hiện I/O mạng — chỉ đọc file JSON cục bộ và validate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

#: File registry phía server — resolve từ chính module này (backend/app/collectors/)
#: lên gốc repo, KHÔNG phụ thuộc working directory và KHÔNG nằm trong src/.
REGISTRY_PATH = Path(__file__).resolve().parents[3] / "source-registry" / "sources.json"

#: Loại nguồn được hỗ trợ.
SUPPORTED_SOURCE_TYPES: tuple[str, ...] = ("rss", "atom", "api", "website", "manual")

#: Phương thức có thể thu thập TỰ ĐỘNG (adapter sẽ làm ở task kế tiếp).
AUTOMATED_COLLECTION_METHODS: tuple[str, ...] = ("rss", "atom", "api")

#: Phương thức KHÔNG tự động — chỉ nhập tay hoặc để trạng thái tường minh.
MANUAL_COLLECTION_METHODS: tuple[str, ...] = ("manual_import",)

SUPPORTED_COLLECTION_METHODS: tuple[str, ...] = (
    AUTOMATED_COLLECTION_METHODS + MANUAL_COLLECTION_METHODS
)

#: Trạng thái nguồn. 'sample' = fixture cấu trúc; 'manual' = chỉ nhập tay;
#: 'unavailable' = đã khai báo nhưng không có đường truy cập hợp lệ (login/ToS/...).
SUPPORTED_SOURCE_STATUSES: tuple[str, ...] = (
    "active",
    "paused",
    "sample",
    "manual",
    "unavailable",
)

#: Chỉ trạng thái 'active' + method tự động mới được coi là thu thập tự động.
COLLECTABLE_STATUS = "active"

SUPPORTED_DATA_ORIGINS: tuple[str, ...] = ("REAL", "SAMPLE")

#: Khoảng priority hợp lệ (1 = ưu tiên cao nhất).
MIN_PRIORITY = 1
MAX_PRIORITY = 10

#: Field bắt buộc của một entry.
REQUIRED_ENTRY_FIELDS: tuple[str, ...] = (
    "source_id",
    "name",
    "type",
    "url",
    "collection_method",
    "priority",
    "status",
)

#: Field tuỳ chọn của một entry (ngoài required).
OPTIONAL_ENTRY_FIELDS: tuple[str, ...] = (
    "last_checked_at",
    "data_origin",
    "note",
)

#: Toàn bộ key hợp lệ — khai báo thừa (typo/instruction lạ) bị từ chối để không
#: có field nào bị bỏ qua âm thầm.
ALLOWED_ENTRY_FIELDS: frozenset[str] = frozenset(
    REQUIRED_ENTRY_FIELDS + OPTIONAL_ENTRY_FIELDS
)

#: Key hợp lệ ở cấp file registry.
ALLOWED_TOP_LEVEL_FIELDS: frozenset[str] = frozenset(
    {"version", "description", "$schema", "sources"}
)

#: Hậu tố host không bao giờ được fetch: loopback/mDNS/nội bộ.
UNSAFE_HOST_SUFFIXES: tuple[str, ...] = (
    ".localhost",
    ".local",
    ".localdomain",
    ".internal",
    ".home.arpa",
    ".lan",
    ".intranet",
    ".corp",
    ".private",
)

#: Host đúng tên (không có dấu chấm) bị coi là nội bộ trừ khi là IP công khai.
UNSAFE_HOST_NAMES: frozenset[str] = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "kubernetes.default",
    }
)

#: Shared address space CGNAT (RFC 6598, 100.64.0.0/10) — không phải host công khai.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

#: Trần độ dài note (registry là dữ liệu người viết, giữ chặn để không phình bundle/log).
MAX_NOTE_CHARS = 500
MAX_SOURCE_ID_CHARS = 128
MAX_NAME_CHARS = 200
MAX_URL_CHARS = 2048


class RegistryError(ValueError):
    """Registry hoặc một entry không hợp lệ — không bao giờ được nạp im lặng."""


@dataclass(frozen=True)
class SourceConfig:
    """Một nguồn đã validate. Bất biến (frozen) — không sửa tại chỗ sau khi nạp."""

    source_id: str
    name: str
    type: str
    url: str
    collection_method: str
    priority: int
    status: str
    data_origin: str = "REAL"
    last_checked_at: str | None = None
    note: str | None = None

    # -- hình dạng phái sinh --------------------------------------------------

    def hostname(self) -> str:
        """Host đã được validate là công khai (chỉ trả về, không fetch)."""
        return (urlsplit(self.url).hostname or "").lower()

    @property
    def requires_manual_import(self) -> bool:
        """True khi nguồn này KHÔNG có đường thu thập tự động."""
        return self.collection_method in MANUAL_COLLECTION_METHODS

    @property
    def automated_collectable(self) -> bool:
        """True chỉ khi method tự động VÀ nguồn đang 'active'.

        Fixture ('sample'), nguồn tạm dừng ('paused'), nhập tay ('manual') và
        nguồn không có đường truy cập ('unavailable') đều trả False — registry
        không bao giờ tự ý ám chỉ một nguồn sẽ được thu thập.
        """
        return (
            self.collection_method in AUTOMATED_COLLECTION_METHODS
            and self.status == COLLECTABLE_STATUS
        )

    @property
    def observation_state(self) -> str:
        """'OBSERVED' chỉ khi có mốc quan sát thật; ngược lại 'NEVER_OBSERVED'."""
        return "NEVER_OBSERVED" if self.last_checked_at is None else "OBSERVED"

    def to_row(self) -> dict[str, Any]:
        """Map đúng các cột của bảng ``sources`` (không kèm note nội bộ)."""
        return {
            "source_id": self.source_id,
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "collection_method": self.collection_method,
            "priority": self.priority,
            "status": self.status,
            "last_checked_at": self.last_checked_at,
            "data_origin": self.data_origin,
        }


# --------------------------------------------------------------------- helpers


def _reject(message: str) -> "RegistryError":
    return RegistryError(message)


def _required_text(value: Any, field: str, *, max_chars: int, where: str) -> str:
    if not isinstance(value, str):
        raise _reject(f"{where}: {field} must be a string")
    text = value.strip()
    if not text:
        raise _reject(f"{where}: {field} must not be blank")
    if len(text) > max_chars:
        raise _reject(f"{where}: {field} exceeds {max_chars} characters")
    return text


def _optional_text(value: Any, field: str, *, max_chars: int, where: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field, max_chars=max_chars, where=where)


def _validate_priority(value: Any, where: str) -> int:
    # bool là subclass của int — loại trừ tường minh để True không thành 1.
    if not isinstance(value, int) or isinstance(value, bool):
        raise _reject(f"{where}: priority must be an integer")
    if not MIN_PRIORITY <= value <= MAX_PRIORITY:
        raise _reject(
            f"{where}: priority must be between {MIN_PRIORITY} and {MAX_PRIORITY}"
        )
    return value


def _validate_last_checked_at(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _reject(f"{where}: last_checked_at must be an ISO-8601 string or null")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise _reject(
            f"{where}: last_checked_at must be an ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise _reject(f"{where}: last_checked_at must include a timezone offset")
    # Không bịa freshness: mốc quan sát không được nằm ở tương lai.
    if parsed > datetime.now(timezone.utc):
        raise _reject(
            f"{where}: last_checked_at must not be in the future "
            f"(fabricated freshness is not allowed)"
        )
    return text


def _is_unsafe_host(host: str) -> bool:
    """True nếu host là loopback/private/link-local/metadata/mDNS/nội bộ."""
    candidate = host.strip().strip("[]").rstrip(".").lower()
    if not candidate:
        return True
    if candidate in UNSAFE_HOST_NAMES:
        return True
    if any(candidate.endswith(suffix) for suffix in UNSAFE_HOST_SUFFIXES):
        return True
    # Host một nhãn (không có dấu chấm) là tên nội bộ, không phải FQDN công khai.
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return "." not in candidate
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        or not address.is_global
    ):
        return True
    # IPv6 site-local (fec0::/10) và shared address space CGNAT (100.64.0.0/10)
    # đều bị is_private/is_global loại — chốt lại để chắc trên mọi phiên bản.
    if isinstance(address, ipaddress.IPv6Address) and address.is_site_local:
        return True
    if isinstance(address, ipaddress.IPv4Address) and address in _CGNAT_NETWORK:
        return True
    return False


def _validate_url(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise _reject(f"{where}: url must be an absolute HTTP(S) URL")
    text = value.strip()
    if not text or len(text) > MAX_URL_CHARS:
        raise _reject(f"{where}: url must be a non-empty HTTP(S) URL")
    parts = urlsplit(text)
    if parts.scheme.lower() not in {"http", "https"}:
        raise _reject(
            f"{where}: url must use http or https (got {text!r})"
        )
    if not parts.netloc or not parts.hostname:
        raise _reject(f"{where}: url must include a host (got {text!r})")
    if parts.username is not None or parts.password is not None:
        raise _reject(f"{where}: url user-info is not supported (got {text!r})")
    if _is_unsafe_host(parts.hostname):
        raise _reject(
            f"{where}: unsafe or non-public host {parts.hostname!r} "
            f"in url {text!r} — private/metadata/internal hosts are refused"
        )
    return text


def validate_source(entry: Any, *, where: str = "source") -> SourceConfig:
    """Validate một entry registry thành ``SourceConfig`` bất biến.

    Raises:
        RegistryError: entry sai hình dạng hoặc mang giá trị không được hỗ trợ.
    """
    if not isinstance(entry, Mapping):
        raise _reject(f"{where}: entry must be a JSON object")

    unknown = sorted(str(k) for k in entry if k not in ALLOWED_ENTRY_FIELDS)
    if unknown:
        raise _reject(f"{where}: unknown fields: {', '.join(unknown)}")

    label = f"{where}:{entry.get('source_id')!r}" if isinstance(entry.get("source_id"), str) else where

    source_id = _required_text(
        entry.get("source_id"), "source_id", max_chars=MAX_SOURCE_ID_CHARS, where=label
    )
    label = f"source {source_id!r}"
    name = _required_text(entry.get("name"), "name", max_chars=MAX_NAME_CHARS, where=label)

    source_type = entry.get("type")
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise _reject(
            f"{label}: unsupported type {source_type!r} "
            f"(allowed: {', '.join(SUPPORTED_SOURCE_TYPES)})"
        )

    method = entry.get("collection_method")
    if method not in SUPPORTED_COLLECTION_METHODS:
        raise _reject(
            f"{label}: unsupported collection_method {method!r} "
            f"(allowed: {', '.join(SUPPORTED_COLLECTION_METHODS)})"
        )

    status = entry.get("status")
    if status not in SUPPORTED_SOURCE_STATUSES:
        raise _reject(
            f"{label}: unsupported status {status!r} "
            f"(allowed: {', '.join(SUPPORTED_SOURCE_STATUSES)})"
        )

    url = _validate_url(entry.get("url"), label)
    priority = _validate_priority(entry.get("priority"), label)
    last_checked_at = _validate_last_checked_at(entry.get("last_checked_at"), label)

    data_origin = entry.get("data_origin", "REAL")
    if data_origin not in SUPPORTED_DATA_ORIGINS:
        raise _reject(
            f"{label}: data_origin must be one of {', '.join(SUPPORTED_DATA_ORIGINS)}"
        )

    note = _optional_text(entry.get("note"), "note", max_chars=MAX_NOTE_CHARS, where=label)

    return SourceConfig(
        source_id=source_id,
        name=name,
        type=source_type,
        url=url,
        collection_method=method,
        priority=priority,
        status=status,
        data_origin=data_origin,
        last_checked_at=last_checked_at,
        note=note,
    )


def parse_registry(payload: Any) -> tuple[SourceConfig, ...]:
    """Validate toàn bộ payload registry đã decode thành tuple SourceConfig.

    Payload phải là một JSON object có ``sources`` là list không rỗng; mọi entry
    có thể là dict thô hoặc ``SourceConfig`` đã validate sẵn.
    """
    if not isinstance(payload, Mapping):
        raise _reject("registry must be a JSON object")

    unknown = sorted(str(k) for k in payload if k not in ALLOWED_TOP_LEVEL_FIELDS)
    if unknown:
        raise _reject(f"registry: unknown top-level fields: {', '.join(unknown)}")

    if "sources" not in payload:
        raise _reject("registry: missing required 'sources' list")
    sources = payload["sources"]
    if not isinstance(sources, list):
        raise _reject("registry: 'sources' must be a list")
    return _collect_configs(sources)


def _collect_configs(entries: Iterable[Any]) -> tuple[SourceConfig, ...]:
    if isinstance(entries, (str, bytes)) or not hasattr(entries, "__iter__"):
        raise _reject("registry: 'sources' must be a list of entries")
    materialized = list(entries)
    if not materialized:
        raise _reject("registry: 'sources' must not be empty")

    configs: list[SourceConfig] = []
    seen: set[str] = set()
    for index, entry in enumerate(materialized):
        if isinstance(entry, SourceConfig):
            config = entry
        else:
            config = validate_source(entry, where=f"sources[{index}]")
        if config.source_id in seen:
            raise _reject(
                f"registry: duplicate source_id {config.source_id!r} "
                f"(sources[{index}])"
            )
        seen.add(config.source_id)
        configs.append(config)
    return tuple(configs)


def load_registry(path: Path | str | None = None) -> tuple[SourceConfig, ...]:
    """Nạp và validate registry từ đĩa (mặc định ``source-registry/sources.json``).

    Raises:
        RegistryError: file thiếu, JSON hỏng hoặc có entry không hợp lệ.
    """
    registry_path = Path(path) if path is not None else REGISTRY_PATH
    try:
        text = registry_path.read_text(encoding="utf-8")
    except OSError as error:
        raise _reject(f"cannot read registry file {registry_path}: {error}") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise _reject(f"registry file {registry_path} is not valid JSON: {error}") from error
    try:
        return parse_registry(payload)
    except RegistryError as error:
        raise _reject(f"{registry_path}: {error}") from error


def registry_rows(path: Path | str | None = None) -> Sequence[dict[str, Any]]:
    """Các hàng sẵn sàng INSERT vào bảng ``sources`` (chưa ghi gì — task kế tiếp)."""
    return tuple(config.to_row() for config in load_registry(path))