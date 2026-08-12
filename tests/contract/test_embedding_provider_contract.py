"""Frozen common embedding-provider contract for Phase 2 and later consumers."""

from __future__ import annotations

import numpy as np

from reponpc.indexing.sources import (
    EmbeddingIdentity,
    EmbeddingProvider,
    EmbeddingProviderError,
)


class _ConformingProvider:
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


def test_common_embedding_provider_requires_query_and_passage_methods() -> None:
    assert isinstance(_ConformingProvider(), EmbeddingProvider)


def test_embedding_provider_error_exposes_only_a_stable_code() -> None:
    error = EmbeddingProviderError("model_load_failed")

    assert error.code == "model_load_failed"
    assert str(error) == "embedding provider failed"
