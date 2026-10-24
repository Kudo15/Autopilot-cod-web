"""Optional OpenAI-compatible editorial enrichment with a safe local fallback.

Environment is read only when a request is made. Model output is untrusted and
is accepted only as bounded editorial data; this module has no persistence or
publication path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import http.client
import json
import os
import socket
import time
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

from backend.app.collectors.registry import _is_unsafe_host
from backend.app.collectors.rss import validate_outbound_url
from backend.app.collectors.runs import bounded_text, redact_secrets
from .rules import classify_rule_based
from .schema import EditorialDraft, EditorialSchemaError

AI_BASE_URL_ENV = "AI_BASE_URL"
AI_API_KEY_ENV = "AI_API_KEY"
AI_MODEL_ENV = "AI_MODEL"
MAX_RESPONSE_BYTES = 200_000
MAX_REQUEST_BYTES = 200_000
MAX_REDIRECTS = 3
MAX_RETRIES = 2
DEFAULT_TIMEOUT_S = 20.0
MAX_REASON_CHARS = 200


class GatewayError(ValueError):
    """Bounded gateway/configuration failure."""


class GatewayTransportError(GatewayError):
    """Transport failure eligible for bounded retry."""


@dataclass(frozen=True, repr=False)
class GatewayConfig:
    base_url: str
    api_key: str
    model: str

    def __repr__(self) -> str:
        return f"GatewayConfig(base_url={self.base_url!r}, api_key='[REDACTED]', model={self.model!r})"

    def safe_dict(self) -> dict[str, str]:
        return {"base_url": self.base_url, "model": self.model, "configured": "true"}


@dataclass(frozen=True)
class GatewayLimits:
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_response_bytes: int = MAX_RESPONSE_BYTES
    max_request_bytes: int = MAX_REQUEST_BYTES
    max_redirects: int = MAX_REDIRECTS
    max_retries: int = MAX_RETRIES
    backoff_s: float = 0.5

    def __post_init__(self) -> None:
        if not 0 < self.timeout_s <= 30:
            raise GatewayError("timeout outside bound")
        if not 1 <= self.max_response_bytes <= 5_000_000:
            raise GatewayError("response bound outside range")
        if not 1 <= self.max_request_bytes <= 5_000_000:
            raise GatewayError("request bound outside range")
        if not 0 <= self.max_redirects <= 10 or not 0 <= self.max_retries <= 5:
            raise GatewayError("retry/redirect bound outside range")
        if not 0 <= self.backoff_s <= 30:
            raise GatewayError("backoff outside bound")


@dataclass(frozen=True)
class GatewayResponse:
    status_code: int
    body: bytes = b""
    location: str | None = None


class GatewayTransport(Protocol):
    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float,
             max_bytes: int) -> GatewayResponse: ...


@dataclass(frozen=True)
class EnrichmentResult:
    draft: EditorialDraft
    source: str
    reason: str | None = None
    gateway_used: bool = False
    freshness: str = field(default="NOT_VERIFIED", init=False)

    def __post_init__(self) -> None:
        if self.source not in {"GATEWAY", "RULE_FALLBACK"}:
            raise GatewayError("invalid enrichment source")
        if self.draft.verification_status != "NEEDS_REVIEW" or self.draft.freshness != "NOT_VERIFIED":
            raise GatewayError("enrichment must remain unverified")
        if self.draft.lifecycle not in {"DRAFT", "PENDING_REVIEW"}:
            raise GatewayError("enrichment cannot publish")
        if self.reason is not None:
            safe = bounded_text(self.reason, "reason", max_chars=MAX_REASON_CHARS, redact=True)
            object.__setattr__(self, "reason", safe)


def _endpoint(base_url: str) -> str:
    checked = validate_outbound_url(base_url)
    parts = urlsplit(checked)
    if parts.query or parts.fragment:
        raise GatewayError("gateway URL must not contain query or fragment")
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        endpoint_path = path
    elif path.endswith("/v1"):
        endpoint_path = path + "/chat/completions"
    elif path:
        endpoint_path = path + "/v1/chat/completions"
    else:
        endpoint_path = "/v1/chat/completions"
    return validate_outbound_url(urlunsplit((parts.scheme, parts.netloc, endpoint_path, "", "")))


def gateway_config_from_env(environ: Mapping[str, str] | None = None) -> GatewayConfig:
    env = os.environ if environ is None else environ
    values = ((AI_BASE_URL_ENV, env.get(AI_BASE_URL_ENV)), (AI_API_KEY_ENV, env.get(AI_API_KEY_ENV)),
              (AI_MODEL_ENV, env.get(AI_MODEL_ENV)))
    missing = [name for name, value in values if not isinstance(value, str) or not value.strip()]
    if missing:
        raise GatewayError("missing gateway configuration: " + ", ".join(missing))
    base_url, api_key, model = (str(value).strip() for _, value in values)
    return GatewayConfig(base_url=_endpoint(base_url), api_key=api_key, model=model[:200])


class HttpChatTransport:
    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout: float,
             max_bytes: int) -> GatewayResponse:
        checked = validate_outbound_url(url)
        parts = urlsplit(checked)
        host = parts.hostname or ""
        try:
            resolved = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
            if any(_is_unsafe_host(row[4][0]) for row in resolved):
                raise GatewayError("gateway resolved host is not public")
        except socket.gaierror as exc:
            raise GatewayTransportError("gateway host could not be resolved") from exc
        cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        connection = cls(host, parts.port, timeout=timeout)
        try:
            path = urlunsplit(("", "", parts.path or "/", parts.query, ""))
            connection.request("POST", path, body=body, headers=dict(headers))
            response = connection.getresponse()
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise GatewayError("gateway response exceeds bound")
            return GatewayResponse(response.status, payload, response.getheader("Location"))
        except GatewayError:
            raise
        except (TimeoutError, socket.timeout, OSError, http.client.HTTPException) as exc:
            raise GatewayTransportError("gateway transport failure") from exc
        finally:
            connection.close()


def _request_body(raw_item: Mapping[str, Any], config: GatewayConfig, limits: GatewayLimits) -> bytes:
    title = str(raw_item.get("title", ""))[:300]
    content = str(raw_item.get("content", raw_item.get("summary", "")))[:20_000]
    payload = {"model": config.model, "temperature": 0, "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": "Return only bounded editorial JSON data."},
                            {"role": "user", "content": json.dumps({"title": title, "content": content}, ensure_ascii=False)}]}
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > limits.max_request_bytes:
        raise GatewayError("gateway request exceeds bound")
    return body


def _post(transport: GatewayTransport, config: GatewayConfig, body: bytes, limits: GatewayLimits,
          sleep: Callable[[float], None]) -> bytes:
    url = config.base_url
    redirects = 0
    retries = 0
    headers = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {config.api_key}"}
    while True:
        try:
            response = transport.post(url, headers=headers, body=body, timeout=limits.timeout_s, max_bytes=limits.max_response_bytes)
        except GatewayTransportError:
            if retries >= limits.max_retries:
                raise GatewayError("gateway request failed after bounded retries")
            sleep(min(limits.backoff_s * (2 ** retries), 30.0))
            retries += 1
            continue
        if 300 <= response.status_code < 400:
            if redirects >= limits.max_redirects or not response.location:
                raise GatewayError("gateway redirect limit exceeded")
            redirects += 1
            url = validate_outbound_url(urljoin(url, response.location))
            continue
        if 500 <= response.status_code <= 599:
            if retries >= limits.max_retries:
                raise GatewayError("gateway request failed after bounded retries")
            sleep(min(limits.backoff_s * (2 ** retries), 30.0))
            retries += 1
            continue
        if response.status_code < 200 or response.status_code >= 300:
            raise GatewayError("gateway returned a non-success status")
        if not isinstance(response.body, (bytes, bytearray)) or len(response.body) > limits.max_response_bytes:
            raise GatewayError("gateway response exceeds bound")
        return bytes(response.body)


def _model_payload(body: bytes) -> Mapping[str, Any]:
    try:
        outer = json.loads(body.decode("utf-8"))
        content = outer["choices"][0]["message"]["content"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise GatewayError("gateway response shape is invalid") from exc
    if not isinstance(content, str):
        raise GatewayError("gateway message content is not text")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise GatewayError("gateway editorial JSON is invalid") from exc
    if not isinstance(value, Mapping):
        raise GatewayError("gateway editorial payload is not an object")
    return value


def _draft_from_model(payload: Mapping[str, Any], raw_item: Mapping[str, Any]) -> EditorialDraft:
    allowed = {"title", "summary_vi", "category", "usefulness", "risk", "recommendation", "lifecycle"}
    if set(payload) - allowed:
        raise GatewayError("gateway output contains untrusted authority fields")
    required = {"title", "summary_vi", "category", "usefulness", "risk", "recommendation"}
    if not required <= set(payload):
        raise GatewayError("gateway output is incomplete")
    lifecycle = payload.get("lifecycle", "PENDING_REVIEW")
    if lifecycle not in {"DRAFT", "PENDING_REVIEW"}:
        raise GatewayError("gateway output lifecycle is not publishable-safe")
    probe = classify_rule_based({"title": payload["title"], "content": payload["summary_vi"]})
    if probe.signals:
        raise GatewayError("gateway output contains instruction-shaped text")
    content_hash = raw_item.get("content_hash") if isinstance(raw_item.get("content_hash"), str) else None
    origin = raw_item.get("data_origin") if raw_item.get("data_origin") in {"REAL", "SAMPLE"} else "UNSPECIFIED"
    try:
        return EditorialDraft(title=payload["title"], summary_vi=payload["summary_vi"], category=payload["category"],
                              usefulness=payload["usefulness"], risk=payload["risk"], recommendation=payload["recommendation"],
                              lifecycle="PENDING_REVIEW" if lifecycle == "PENDING_REVIEW" or payload["risk"] in {"HIGH", "MEDIUM"} else "DRAFT",
                              source_id=str(raw_item.get("source_id", "")), verification_status="NEEDS_REVIEW",
                              freshness="NOT_VERIFIED", ranking=None, content_hash=content_hash, data_origin=origin)
    except (EditorialSchemaError, KeyError, TypeError, ValueError) as exc:
        raise GatewayError("gateway editorial fields are invalid") from exc


def request_draft(raw_item: Mapping[str, Any], config: GatewayConfig, *, transport: GatewayTransport | None = None,
                  sleep: Callable[[float], None] | None = None, limits: GatewayLimits | None = None) -> EditorialDraft:
    limits = limits or GatewayLimits()
    active = transport or HttpChatTransport()
    body = _request_body(raw_item, config, limits)
    response_body = _post(active, config, body, limits, sleep or time.sleep)
    return _draft_from_model(_model_payload(response_body), raw_item)


def enrich_draft(raw_item: Mapping[str, Any], *, transport: GatewayTransport | None = None,
                 environ: Mapping[str, str] | None = None, sleep: Callable[[float], None] | None = None,
                 limits: GatewayLimits | None = None) -> EnrichmentResult:
    if not isinstance(raw_item, Mapping):
        raise ValueError("raw_item must be a mapping")
    try:
        config = gateway_config_from_env(environ)
        draft = request_draft(raw_item, config, transport=transport, sleep=sleep, limits=limits)
        return EnrichmentResult(draft=draft, source="GATEWAY", gateway_used=True)
    except Exception as exc:
        fallback = classify_rule_based(raw_item)
        reason = bounded_text(redact_secrets(type(exc).__name__), "reason", max_chars=MAX_REASON_CHARS, redact=True)
        return EnrichmentResult(draft=fallback, source="RULE_FALLBACK", reason=reason, gateway_used=False)
