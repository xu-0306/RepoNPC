"""Private Ollama runtime embedding provider."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers.contracts import (
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    RuntimeEmbeddingProvider,
)
from reponpc.providers.http_transport import (
    ProviderHttpTransport,
    ProviderOrigin,
    UrllibProviderHttpTransport,
    failure_for_status,
)
from reponpc.providers.model_catalog import ollama_model_available, ollama_model_ids
from reponpc.providers.openai_embeddings import (
    _checked_at,
    _json_bytes,
    _json_object,
    _prefix_once,
    _validate_normalization,
    _validated_row,
)

_REQUEST_TIMEOUT_SECONDS = 30.0


class OllamaPullCancelled(RuntimeError):
    """Internal cooperative-cancellation signal without provider detail."""


class OllamaEmbeddingProvider(RuntimeEmbeddingProvider):
    """Adapt one explicitly configured Ollama embedding model.

    Ollama is intentionally allowed to use private HTTP origins.  The origin
    and endpoint are still checked by :class:`ProviderOrigin`, redirects are
    rejected by the injectable transport, and no cloud fallback is attempted.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        identity: EmbeddingIdentity,
        transport: ProviderHttpTransport | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url:
            raise ValueError("embedding base URL must be non-empty")
        if not isinstance(model, str) or not model:
            raise ValueError("embedding model must be non-empty")
        if not isinstance(identity, EmbeddingIdentity):
            raise TypeError("embedding identity is required")
        if identity.adapter != "ollama":
            raise ValueError("embedding identity adapter does not match Ollama provider")
        if identity.model_id != model:
            raise ValueError("embedding identity model does not match configured model")
        if identity.normalized is not True:
            raise ValueError("normalized embeddings are required")

        self._model = model
        self._identity = identity
        self._transport = transport or UrllibProviderHttpTransport()
        self._origin = ProviderOrigin(base_url, allow_private_http=True)

    def __repr__(self) -> str:
        # Do not include base_url: Ollama's URL is often a private network
        # location and must not enter diagnostics or snapshots.
        return f"{type(self).__name__}(model={self._model!r}, identity={self._identity!r})"

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        return self._embed(texts, self._identity.query_prefix)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        return self._embed(texts, self._identity.passage_prefix)

    def health(self) -> ProviderHealth:
        try:
            response = self._transport.request(
                "GET",
                self._origin.endpoint("api/tags"),
                headers={"Accept": "application/json", "User-Agent": "RepoNPC-provider"},
                body=None,
                timeout=5.0,
            )
        except ProviderError as exc:
            return ProviderHealth(False, _checked_at(), exc.code)
        except Exception:
            return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        if response.status != 200:
            return ProviderHealth(False, _checked_at(), failure_for_status(response.status))
        try:
            payload = _json_object(response.body)
            if not ollama_model_available(payload, self._model):
                return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            return ProviderHealth(
                False,
                _checked_at(),
                ProviderFailureCode.INVALID_RESPONSE,
            )
        return ProviderHealth(True, _checked_at())

    def pull_model(
        self,
        *,
        cancelled: Callable[[], bool] | None = None,
        on_progress: Callable[[int | None, int | None], None] | None = None,
    ) -> None:
        """Use Ollama's provider-owned model lifecycle for the configured model."""

        is_cancelled = cancelled or (lambda: False)
        progress = on_progress or (lambda _completed, _total: None)
        stream_lines = getattr(self._transport, "stream_lines", None)
        if callable(stream_lines):
            if is_cancelled():
                raise OllamaPullCancelled

            def consume(line: bytes) -> None:
                if is_cancelled():
                    raise OllamaPullCancelled
                try:
                    payload = _json_object(line)
                    completed = payload.get("completed")
                    total = payload.get("total")
                    if completed is not None and (
                        isinstance(completed, bool) or not isinstance(completed, int)
                    ):
                        raise ValueError
                    if total is not None and (
                        isinstance(total, bool) or not isinstance(total, int)
                    ):
                        raise ValueError
                    progress(completed, total)
                except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
                    raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None

            try:
                status = stream_lines(
                    "POST",
                    self._origin.endpoint("api/pull"),
                    headers={
                        "Accept": "application/x-ndjson",
                        "Content-Type": "application/json",
                        "User-Agent": "RepoNPC-provider",
                    },
                    body=_json_bytes({"model": self._model, "stream": True}),
                    timeout=300.0,
                    cancelled=is_cancelled,
                    on_line=consume,
                )
            except InterruptedError:
                raise OllamaPullCancelled from None
            if status != 200:
                raise ProviderError(failure_for_status(status))
            return

        progress(None, None)
        self._model_action(
            "POST",
            "api/pull",
            {"model": self._model, "stream": False},
            timeout=300.0,
        )
        if is_cancelled():
            raise OllamaPullCancelled

    def installed_models(self) -> tuple[str, ...]:
        """Return validated provider model IDs without exposing the provider origin."""

        try:
            response = self._transport.request(
                "GET",
                self._origin.endpoint("api/tags"),
                headers={"Accept": "application/json", "User-Agent": "RepoNPC-provider"},
                body=None,
                timeout=5.0,
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        if response.status != 200:
            raise ProviderError(failure_for_status(response.status))
        try:
            return ollama_model_ids(_json_object(response.body))
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None

    def delete_model(self) -> None:
        """Delete only the explicitly configured Ollama model."""

        self._model_action(
            "DELETE",
            "api/delete",
            {"model": self._model},
            timeout=30.0,
        )

    def _model_action(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, object],
        *,
        timeout: float,
    ) -> None:
        try:
            response = self._transport.request(
                method,
                self._origin.endpoint(endpoint),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "RepoNPC-provider",
                },
                body=_json_bytes(payload),
                timeout=timeout,
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        if response.status != 200:
            raise ProviderError(failure_for_status(response.status))

    def _embed(self, texts: list[str], prefix: str) -> NDArray[np.float32]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        if not texts:
            return np.empty((0, self._identity.dimension), dtype=np.float32)

        request = {
            "input": [_prefix_once(text, prefix) for text in texts],
            "model": self._model,
        }
        try:
            response = self._transport.request(
                "POST",
                self._origin.endpoint("api/embed"),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "RepoNPC-provider",
                },
                body=_json_bytes(request),
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        if response.status != 200:
            raise ProviderError(failure_for_status(response.status))
        try:
            payload = _json_object(response.body)
            raw_vectors = payload["embeddings"]
            if not isinstance(raw_vectors, list) or len(raw_vectors) != len(texts):
                raise ValueError
            matrix = _parse_vectors(raw_vectors, len(texts), self._identity.dimension)
        except ProviderError:
            raise
        except (KeyError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        return matrix


def _parse_vectors(values: list[Any], count: int, dimension: int) -> NDArray[np.float32]:
    if len(values) != count:
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    rows = [_validated_row(value, dimension) for value in values]
    matrix = np.asarray(rows, dtype=np.float32)
    _validate_normalization(matrix)
    return matrix
