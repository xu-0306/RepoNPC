"""RepoNPC-owned runtime provider contracts.

Concrete network adapters consume these strict transport-neutral values.  The
contracts deliberately contain no endpoint, credential, fallback, or logging
policy; those remain server-owned orchestration concerns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from reponpc.indexing.sources import EmbeddingProvider
from reponpc.providers.error_messages import MAX_ERROR_MESSAGE_CHARS


class ProviderFailureCode(StrEnum):
    """Stable internal provider failures from Technical Specification 13.1."""

    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    CONTEXT_OVERFLOW = "context_overflow"


class ProviderError(RuntimeError):
    """Safe exception text with optional bounded admin-only provider diagnostics."""

    def __init__(
        self,
        code: ProviderFailureCode,
        *,
        upstream_status: int | None = None,
        upstream_message: str | None = None,
    ) -> None:
        if not isinstance(code, ProviderFailureCode):
            raise TypeError("code must be a ProviderFailureCode")
        if upstream_status is not None and (
            type(upstream_status) is not int or not 100 <= upstream_status <= 599
        ):
            raise ValueError("upstream_status must be an HTTP status integer")
        self.code = code
        self.upstream_status = upstream_status
        if upstream_message is not None and (
            not isinstance(upstream_message, str) or len(upstream_message) > MAX_ERROR_MESSAGE_CHARS
        ):
            raise ValueError("upstream_message must be bounded redacted text")
        self.upstream_message = upstream_message
        super().__init__("model provider failed")


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Capabilities an adapter may truthfully expose to orchestration."""

    streaming: bool
    system_role: bool
    structured_output: bool
    usage_reporting: bool
    health_check: bool
    max_context_tokens: int
    max_output_tokens: int

    def __post_init__(self) -> None:
        for value in (self.max_context_tokens, self.max_output_tokens):
            if isinstance(value, bool) or value <= 0:
                raise ValueError("provider token limits must be positive integers")
        if self.max_output_tokens > self.max_context_tokens:
            raise ValueError("provider output limit must not exceed context limit")


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    """One already-policy-checked message sent to a provider adapter."""

    role: Literal["system", "user", "assistant"]
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError("provider message role is invalid")
        if not self.content:
            raise ValueError("provider message content must be non-empty")


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    """Nullable provider-reported token accounting."""

    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError("provider usage must contain non-negative integers")


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Complete buffered provider output before RepoNPC validates it."""

    content: str | dict[str, Any]
    finish_reason: str
    usage: ProviderUsage | None
    provider_request_id: str | None
    duration_ms: float

    def __post_init__(self) -> None:
        if not isinstance(self.content, (str, dict)):
            raise TypeError("provider content must be text or an object")
        if isinstance(self.content, str) and not self.content:
            raise ValueError("provider text content must be non-empty")
        if not self.finish_reason:
            raise ValueError("provider finish_reason must be non-empty")
        if not math.isfinite(self.duration_ms) or self.duration_ms < 0:
            raise ValueError("provider duration must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    """Safe health observation without a URL or upstream diagnostic body."""

    ready: bool
    checked_at: str
    failure_code: ProviderFailureCode | None = None

    def __post_init__(self) -> None:
        if not self.checked_at:
            raise ValueError("provider health requires a checked_at value")
        if self.ready and self.failure_code is not None:
            raise ValueError("a ready provider must not expose a failure code")
        if not self.ready and self.failure_code is None:
            raise ValueError("an unavailable provider requires a stable failure code")


ResponseSchema = dict[str, Any]


@runtime_checkable
class ChatProvider(Protocol):
    """Common complete-output chat boundary for every concrete adapter."""

    def capabilities(self) -> ProviderCapabilities:
        """Return only capabilities supported by the selected adapter/model."""

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        """Return one complete buffered result or raise :class:`ProviderError`."""

    def health(self) -> ProviderHealth:
        """Return the selected provider's safe health state."""


@runtime_checkable
class RuntimeEmbeddingProvider(EmbeddingProvider, Protocol):
    """Phase 2 embedding semantics plus Phase 3 runtime health ownership."""

    def health(self) -> ProviderHealth:
        """Return safe readiness for the exact configured embedding identity."""
