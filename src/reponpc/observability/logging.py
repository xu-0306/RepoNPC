"""Allowlisted structured logging that cannot serialize sensitive request data."""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

MAX_TEXT_LENGTH: Final = 160
MAX_RANKS: Final = 20
_EVENT_RE: Final = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
_SAFE_VERSION_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_SAFE_ROUTE_RE: Final = re.compile(r"^/(?:api(?:/[a-z0-9_./{}-]+)?|healthz|readyz)$")
_SENSITIVE_TEXT_RE: Final = re.compile(
    r"(?i)(api[_ -]?key|authorization|cookie|csrf|password|secret|token|"
    r"prompt|question|answer|upload)"
)
_IP_RE: Final = re.compile(
    r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])|(?:[0-9a-f]{0,4}:){2,}[0-9a-f]{0,4}",
    re.IGNORECASE,
)
_URL_RE: Final = re.compile(r"(?i)https?://")
_WINDOWS_PATH_RE: Final = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\)")
_POSIX_PATH_RE: Final = re.compile(r"(?:^|[\s'\"=:])/(?:[^/\s]+(?:/[^/\s]+)*)")
_ERROR_CATEGORIES: Final = frozenset(
    {
        "authentication",
        "configuration",
        "conflict",
        "context_overflow",
        "internal",
        "invalid_response",
        "not_found",
        "rate_limit",
        "timeout",
        "unavailable",
        "validation",
    }
)
_RATE_OUTCOMES: Final = frozenset(
    {"accepted", "concurrency_limit", "daily_budget_exhausted", "rate_limited", "rejected"}
)
_PROVIDER_ADAPTERS: Final = frozenset(
    {"local_sentence_transformers", "ollama", "openai_compatible"}
)


def _safe_text(value: object, *, limit: int = MAX_TEXT_LENGTH) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return ""
    if (
        _SENSITIVE_TEXT_RE.search(normalized)
        or _IP_RE.search(normalized)
        or _URL_RE.search(normalized)
        or _WINDOWS_PATH_RE.search(normalized)
        or _POSIX_PATH_RE.search(normalized)
    ):
        return "<redacted>"
    return normalized[:limit]


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _safe_ranks(value: object) -> list[int] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    ranks: list[int] = []
    for rank in value[:MAX_RANKS]:
        safe_rank = _safe_int(rank)
        if safe_rank is None:
            return None
        ranks.append(safe_rank)
    return ranks


def _safe_event_name(value: object) -> str:
    if isinstance(value, str) and _EVENT_RE.fullmatch(value):
        return value
    return "invalid_event"


def _sanitize_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the finite allowlisted diagnostics safe for structured logs."""

    safe: dict[str, Any] = {}
    request_id = _safe_text(fields.get("request_id"))
    if request_id is not None:
        safe["request_id"] = request_id
    route = fields.get("route_template")
    if isinstance(route, str) and _SAFE_ROUTE_RE.fullmatch(route):
        safe["route_template"] = route
    status = _safe_int(fields.get("status"))
    if status is not None and status <= 599:
        safe["status"] = status
    latency_ms = _safe_number(fields.get("latency_ms"))
    if latency_ms is not None:
        safe["latency_ms"] = latency_ms
    index_version = fields.get("index_version")
    if isinstance(index_version, str) and _SAFE_VERSION_RE.fullmatch(index_version):
        safe["index_version"] = index_version
    provider_adapter = fields.get("provider_adapter")
    if provider_adapter in _PROVIDER_ADAPTERS:
        safe["provider_adapter"] = provider_adapter
    provider_model = _safe_text(fields.get("provider_model"))
    if provider_model is not None:
        safe["provider_model"] = provider_model
    retrieval_count = _safe_int(fields.get("retrieval_count"))
    if retrieval_count is not None and retrieval_count <= 100:
        safe["retrieval_count"] = retrieval_count
    retrieval_ranks = _safe_ranks(fields.get("retrieval_ranks"))
    if retrieval_ranks is not None:
        safe["retrieval_ranks"] = retrieval_ranks
    for name in ("input_tokens", "output_tokens"):
        token_count = _safe_int(fields.get(name))
        if token_count is not None:
            safe[name] = token_count
    rate_outcome = fields.get("rate_outcome")
    if rate_outcome in _RATE_OUTCOMES:
        safe["rate_outcome"] = rate_outcome
    error_category = fields.get("error_category")
    if error_category in _ERROR_CATEGORIES:
        safe["error_category"] = error_category
    return safe


@dataclass(frozen=True, slots=True)
class SafeLogger:
    """Emit safe JSON events while preserving the application result on failure."""

    _logger: logging.Logger

    def emit(self, severity: int, event: object, /, **fields: Any) -> None:
        """Best-effort structured emission; arbitrary fields and errors are ignored."""

        try:
            payload = {
                "timestamp": datetime.now(UTC).isoformat(),
                "severity": logging.getLevelName(severity),
                "event": _safe_event_name(event),
                **_sanitize_fields(fields),
            }
            serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            self._logger.log(severity, "%s", serialized)
        except Exception:
            # Observability must never change a user-facing success or failure.
            return


def get_safe_logger(name: str = "reponpc") -> SafeLogger:
    """Return a wrapper around the configured Python logger."""

    return SafeLogger(logging.getLogger(name))
