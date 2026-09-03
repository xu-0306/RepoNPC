"""Runtime provider owner health and retry contract tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
)
from reponpc.providers.runtime import ProviderRuntime

IDENTITY = EmbeddingIdentity(
    adapter="ollama",
    model_id="fixture-embedding",
    dimension=2,
    normalized=True,
    query_prefix="query: ",
    passage_prefix="passage: ",
)


@dataclass
class FixtureChat:
    health_result: ProviderHealth
    failures: list[ProviderFailureCode] = field(default_factory=list)
    calls: list[float] = field(default_factory=list)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 1000, 100)

    def health(self) -> ProviderHealth:
        return self.health_result

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: dict[str, Any],
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        del messages, response_schema, max_output_tokens
        self.calls.append(timeout)
        if self.failures:
            raise ProviderError(self.failures.pop(0))
        return ProviderResult("ok", "stop", None, None, 1.0)


@dataclass
class FixtureEmbedding:
    health_result: ProviderHealth
    failures: list[ProviderFailureCode] = field(default_factory=list)
    calls: int = 0

    def identity(self) -> EmbeddingIdentity:
        return IDENTITY

    def health(self) -> ProviderHealth:
        return self.health_result

    def embed_query(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        self.calls += 1
        if self.failures:
            raise ProviderError(self.failures.pop(0))
        return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def embed_passages(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        return self.embed_query(texts)


READY = ProviderHealth(True, "2026-08-12T00:00:00Z")
DOWN = ProviderHealth(False, "2026-08-12T00:00:01Z", ProviderFailureCode.UNAVAILABLE)


def test_health_requires_both_selected_providers_without_fallback() -> None:
    runtime = ProviderRuntime(
        chat=FixtureChat(READY),  # type: ignore[arg-type]
        embedding=FixtureEmbedding(DOWN),  # type: ignore[arg-type]
    )

    status = runtime.poll_health()

    assert status.ready is False
    assert status.failure_code is ProviderFailureCode.UNAVAILABLE
    assert status.checked_at == "2026-08-12T00:00:01Z"


def test_transient_chat_failure_retries_same_provider_once_within_deadline() -> None:
    clock_values = iter([0.0, 0.0, 0.1])
    chat = FixtureChat(READY, [ProviderFailureCode.TIMEOUT])
    runtime = ProviderRuntime(
        chat=chat,  # type: ignore[arg-type]
        embedding=FixtureEmbedding(READY),  # type: ignore[arg-type]
        retry_base_seconds=0,
        monotonic=lambda: next(clock_values),
    )

    result = runtime.generate((ProviderMessage("user", "question"),), {}, 10, 1.0)

    assert result.content == "ok"
    assert chat.calls == [1.0, 0.9]


def test_nontransient_failure_never_retries() -> None:
    embedding = FixtureEmbedding(READY, [ProviderFailureCode.AUTHENTICATION])
    runtime = ProviderRuntime(
        chat=FixtureChat(READY),  # type: ignore[arg-type]
        embedding=embedding,  # type: ignore[arg-type]
        retry_base_seconds=0,
    )

    with pytest.raises(ProviderError) as raised:
        runtime.embed_query(["question"], timeout=1.0)

    assert raised.value.code is ProviderFailureCode.AUTHENTICATION
    assert embedding.calls == 1


def test_invalid_or_expired_deadline_does_not_call_provider() -> None:
    chat = FixtureChat(READY)
    runtime = ProviderRuntime(
        chat=chat,  # type: ignore[arg-type]
        embedding=FixtureEmbedding(READY),  # type: ignore[arg-type]
    )

    with pytest.raises(ProviderError) as raised:
        runtime.generate((ProviderMessage("user", "question"),), {}, 10, 0)

    assert raised.value.code is ProviderFailureCode.TIMEOUT
    assert chat.calls == []


def test_replaced_embedding_keeps_old_identity_for_inflight_index_lease() -> None:
    old = FixtureEmbedding(READY)
    replacement_identity = EmbeddingIdentity(
        adapter="ollama",
        model_id="replacement",
        dimension=2,
        normalized=True,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )

    class ReplacementEmbedding(FixtureEmbedding):
        def identity(self) -> EmbeddingIdentity:
            return replacement_identity

        def embed_query(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
            self.calls += 1
            return np.tile(np.array([[0.0, 1.0]], dtype=np.float32), (len(texts), 1))

    replacement = ReplacementEmbedding(READY)
    runtime = ProviderRuntime(
        chat=FixtureChat(READY),  # type: ignore[arg-type]
        embedding=old,  # type: ignore[arg-type]
        max_attempts=1,
    )

    previous = runtime.replace_embedding(replacement)  # type: ignore[arg-type]
    old_result = runtime.embed_query_for(IDENTITY, ["old"], timeout=1.0)
    new_result = runtime.embed_query_for(replacement_identity, ["new"], timeout=1.0)

    assert previous is old
    assert old_result.tolist() == [[1.0, 0.0]]
    assert new_result.tolist() == [[0.0, 1.0]]
    assert old.calls == 1
    assert replacement.calls == 1
