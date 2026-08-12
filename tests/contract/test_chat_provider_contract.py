"""Frozen Phase 3 chat and runtime embedding provider contracts."""

from __future__ import annotations

import numpy as np

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers import (
    ChatProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
    ProviderUsage,
    ResponseSchema,
    RuntimeEmbeddingProvider,
)


class _ConformingChatProvider:
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=False,
            system_role=True,
            structured_output=True,
            usage_reporting=True,
            health_check=True,
            max_context_tokens=8_192,
            max_output_tokens=1_000,
        )

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: ResponseSchema,
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        del messages, response_schema, max_output_tokens, timeout
        return ProviderResult(
            content={"answer_markdown": "Supported [S1]"},
            finish_reason="stop",
            usage=ProviderUsage(input_tokens=5, output_tokens=3),
            provider_request_id="fixture-request",
            duration_ms=12.5,
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(ready=True, checked_at="2026-08-12T12:00:00Z")


class _ConformingRuntimeEmbeddingProvider:
    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity(
            adapter="local_sentence_transformers",
            model_id="fixture/model",
            dimension=3,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), 3), dtype=np.float32)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), 3), dtype=np.float32)

    def health(self) -> ProviderHealth:
        return ProviderHealth(ready=True, checked_at="2026-08-12T12:00:00Z")


def test_conforming_chat_provider_exposes_the_complete_runtime_boundary() -> None:
    provider = _ConformingChatProvider()

    assert isinstance(provider, ChatProvider)
    assert provider.capabilities().structured_output is True
    assert provider.generate((), {}, 100, 1.0).usage == ProviderUsage(5, 3)


def test_runtime_embedding_provider_reuses_phase2_semantics_and_adds_health() -> None:
    provider = _ConformingRuntimeEmbeddingProvider()

    assert isinstance(provider, RuntimeEmbeddingProvider)
    assert provider.identity().query_prefix == "query: "
    assert provider.health().ready is True


def test_provider_errors_are_bounded_and_do_not_reflect_upstream_text() -> None:
    error = ProviderError(ProviderFailureCode.UNAVAILABLE)

    assert error.code is ProviderFailureCode.UNAVAILABLE
    assert str(error) == "model provider failed"
    assert "http://private-provider.internal" not in str(error)


def test_provider_contract_values_reject_impossible_or_unsafe_states() -> None:
    for value in (0, -1, True):
        try:
            ProviderCapabilities(False, False, False, False, False, 8_192, value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid token limit was accepted")

    try:
        ProviderHealth(ready=False, checked_at="2026-08-12T12:00:00Z")
    except ValueError:
        pass
    else:
        raise AssertionError("unavailable health without a stable code was accepted")
