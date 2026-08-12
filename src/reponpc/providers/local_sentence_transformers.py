"""Local sentence-transformers embeddings used by the build-time indexer."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import numpy as np
from numpy.typing import NDArray

from reponpc.indexing.sources import EmbeddingIdentity, EmbeddingProviderError

_NORMALIZATION_ATOL = 1e-5
_NORMALIZATION_RTOL = 1e-4


class LocalSentenceTransformersEmbeddingProvider:
    """Fail-closed adapter for one explicitly configured local model."""

    def __init__(
        self,
        *,
        model_id: str,
        dimension: int,
        normalized: bool,
        query_prefix: str,
        passage_prefix: str,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        if not isinstance(model_id, str) or not model_id:
            raise ValueError("model_id must be non-empty")
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
            raise ValueError("dimension must be a positive integer")
        if normalized is not True:
            raise ValueError("normalized must be true")
        if not isinstance(query_prefix, str) or not query_prefix:
            raise ValueError("query_prefix must be non-empty")
        if not isinstance(passage_prefix, str) or not passage_prefix:
            raise ValueError("passage_prefix must be non-empty")
        if not isinstance(device, str) or not device:
            raise ValueError("device must be non-empty")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        self._identity = EmbeddingIdentity(
            adapter="local_sentence_transformers",
            model_id=model_id,
            dimension=dimension,
            normalized=normalized,
            query_prefix=query_prefix,
            passage_prefix=passage_prefix,
        )
        self._device = device
        self._batch_size = batch_size
        self._model: Any | None = None

    def identity(self) -> EmbeddingIdentity:
        """Return the exact immutable embedding contract."""

        return self._identity

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed raw queries with exactly the configured query prefix."""

        return self._embed(texts, self._identity.query_prefix)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed raw passages with exactly the configured passage prefix."""

        return self._embed(texts, self._identity.passage_prefix)

    def _embed(self, texts: list[str], prefix: str) -> NDArray[np.float32]:
        if not texts:
            return np.empty((0, self._identity.dimension), dtype=np.float32)

        prefixed_texts = [prefix + text for text in texts]
        model = self._load_model()
        try:
            output = model.encode(
                prefixed_texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception:
            raise EmbeddingProviderError("embedding_encode_failed") from None
        return self._validated_output(output, len(texts))

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            sentence_transformers = import_module("sentence_transformers")
        except Exception:
            raise EmbeddingProviderError("embedding_dependency_unavailable") from None
        try:
            model = sentence_transformers.SentenceTransformer(
                self._identity.model_id,
                device=self._device,
                trust_remote_code=False,
            )
        except Exception:
            raise EmbeddingProviderError("embedding_model_load_failed") from None
        self._model = model
        return model

    def _validated_output(self, output: object, count: int) -> NDArray[np.float32]:
        if not isinstance(output, np.ndarray) or output.dtype != np.float32:
            raise EmbeddingProviderError("embedding_output_invalid")
        if output.shape != (count, self._identity.dimension):
            raise EmbeddingProviderError("embedding_output_invalid")
        if not np.all(np.isfinite(output)):
            raise EmbeddingProviderError("embedding_output_invalid")
        norms = np.linalg.norm(output, axis=1)
        if np.any(norms == 0) or not np.allclose(
            norms,
            1.0,
            rtol=_NORMALIZATION_RTOL,
            atol=_NORMALIZATION_ATOL,
        ):
            raise EmbeddingProviderError("embedding_output_invalid")
        return output
