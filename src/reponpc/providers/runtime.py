"""Single-owner runtime provider health and bounded retry orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import TypeVar

import numpy as np
from numpy.typing import NDArray

from reponpc.indexing.sources import EmbeddingIdentity, EmbeddingProvider
from reponpc.providers.contracts import (
    ChatProvider,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
    ResponseSchema,
    RuntimeEmbeddingProvider,
)

_TRANSIENT_FAILURES = frozenset(
    {
        ProviderFailureCode.RATE_LIMIT,
        ProviderFailureCode.TIMEOUT,
        ProviderFailureCode.UNAVAILABLE,
    }
)
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RuntimeProviderStatus:
    """One safe atomic health snapshot for the explicitly selected providers."""

    ready: bool
    checked_at: str
    failure_code: ProviderFailureCode | None = None


class ProviderRuntime:
    """Own selected providers, health state, and retry policy without fallback."""

    def __init__(
        self,
        *,
        chat: ChatProvider,
        embedding: RuntimeEmbeddingProvider,
        max_attempts: int = 2,
        retry_base_seconds: float = 0.05,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 2:
            raise ValueError("runtime provider attempts must be one or two")
        if retry_base_seconds < 0:
            raise ValueError("retry delay must be non-negative")
        self.chat = chat
        self.embedding = embedding
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._sleep = sleep
        self._monotonic = monotonic
        self._lock = RLock()
        self._status = RuntimeProviderStatus(
            ready=False,
            checked_at="1970-01-01T00:00:00Z",
            failure_code=ProviderFailureCode.UNAVAILABLE,
        )

    def status(self) -> RuntimeProviderStatus:
        with self._lock:
            return self._status

    def poll_health(self) -> RuntimeProviderStatus:
        """Poll both selected providers once and publish one safe snapshot."""

        try:
            chat_health = self.chat.health()
        except Exception:
            chat_health = ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        try:
            embedding_health = self.embedding.health()
        except Exception:
            embedding_health = ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        ready = chat_health.ready and embedding_health.ready
        failure = None
        if not ready:
            failure = chat_health.failure_code or embedding_health.failure_code
            if failure is None:
                failure = ProviderFailureCode.UNAVAILABLE
        checked_at = max(chat_health.checked_at, embedding_health.checked_at)
        result = RuntimeProviderStatus(ready, checked_at, failure)
        with self._lock:
            self._status = result
        return result

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        """Generate within one deadline and retry only the same selected adapter."""

        return self._within_deadline(
            timeout,
            lambda remaining: self.chat.generate(
                messages, response_schema, max_output_tokens, remaining
            ),
        )

    def generate_once(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        """Call only the configured chat adapter once within the supplied sub-deadline."""

        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        return self.chat.generate(messages, response_schema, max_output_tokens, float(timeout))

    def embed_query(self, texts: list[str], *, timeout: float) -> NDArray[np.float32]:
        """Embed a query batch with bounded same-adapter transient retries."""

        return self._within_deadline(timeout, lambda _remaining: self.embedding.embed_query(texts))

    def embed_query_once(self, texts: list[str], *, timeout: float) -> NDArray[np.float32]:
        """Call only the configured embedding adapter once for explicit no-retry flows."""

        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        return self.embedding.embed_query(texts)

    def _within_deadline(self, timeout: float, operation: Callable[[float], T]) -> T:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        deadline = self._monotonic() + float(timeout)
        for attempt in range(self._max_attempts):
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                raise ProviderError(ProviderFailureCode.TIMEOUT)
            try:
                return operation(remaining)
            except ProviderError as exc:
                if exc.code not in _TRANSIENT_FAILURES or attempt + 1 >= self._max_attempts:
                    raise
                delay = min(self._retry_base_seconds * (2**attempt), remaining)
                if delay > 0:
                    self._sleep(delay)
        raise ProviderError(ProviderFailureCode.TIMEOUT)


class LocalRuntimeEmbeddingProvider(RuntimeEmbeddingProvider):
    """Add safe runtime health to the Phase 2 local embedding implementation."""

    def __init__(self, delegate: EmbeddingProvider) -> None:
        self._delegate = delegate

    def identity(self) -> EmbeddingIdentity:
        return self._delegate.identity()

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        return self._delegate.embed_query(texts)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        return self._delegate.embed_passages(texts)

    def health(self) -> ProviderHealth:
        try:
            output = self._delegate.embed_query(["health"])
            if output.shape != (1, self.identity().dimension):
                raise ValueError
        except Exception:
            return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        return ProviderHealth(True, _checked_at())


def _checked_at() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
