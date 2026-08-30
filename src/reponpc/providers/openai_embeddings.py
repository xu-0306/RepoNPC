"""OpenAI-compatible runtime embedding provider.

The adapter deliberately owns only the wire-format translation.  Provider
selection, retries, and fallback policy remain with the runtime orchestrator;
an error from this module is always mapped to the stable ``ProviderError``
contract and never contains upstream response text.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
from reponpc.providers.model_catalog import openai_model_available
from reponpc.providers.openai_compatible import _failure_for_response

_NORMALIZATION_ATOL = 1e-5
_NORMALIZATION_RTOL = 1e-4
_REQUEST_TIMEOUT_SECONDS = 30.0


class OpenAICompatibleEmbeddingProvider(RuntimeEmbeddingProvider):
    """Adapt one explicitly selected OpenAI-compatible embedding model.

    ``identity`` is the bundle-declared contract.  It is retained unchanged
    and every successful response is checked against it before being exposed to
    retrieval.  This adapter never chooses a different model or provider after
    a failure.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        identity: EmbeddingIdentity,
        transport: ProviderHttpTransport | None = None,
        *,
        api_key: str | None = None,
        allow_private_http: bool = False,
    ) -> None:
        if not isinstance(base_url, str) or not base_url:
            raise ValueError("embedding base URL must be non-empty")
        if not isinstance(model, str) or not model:
            raise ValueError("embedding model must be non-empty")
        if not isinstance(identity, EmbeddingIdentity):
            raise TypeError("embedding identity is required")
        if identity.adapter != "openai_compatible":
            raise ValueError("embedding identity adapter does not match OpenAI-compatible provider")
        if identity.model_id != model:
            raise ValueError("embedding identity model does not match configured model")
        if identity.normalized is not True:
            raise ValueError("normalized embeddings are required")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("embedding API key must be text")
        if not isinstance(allow_private_http, bool):
            raise ValueError("private HTTP policy must be boolean")

        self._model = model
        self._identity = identity
        self._transport = transport or UrllibProviderHttpTransport()
        self._api_key = api_key
        self._origin = ProviderOrigin(base_url, allow_private_http)

    def __repr__(self) -> str:
        # Keep the credential out of diagnostics while retaining useful model
        # and policy context.  ProviderError/ProviderHealth are even safer and
        # contain no URL or response body at all.
        return f"{type(self).__name__}(identity={self._identity!r})"

    def identity(self) -> EmbeddingIdentity:
        """Return the exact configured, immutable embedding identity."""

        return self._identity

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed raw query text with the configured query prefix exactly once."""

        return self._embed(texts, self._identity.query_prefix)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed raw passage text with the configured passage prefix exactly once."""

        return self._embed(texts, self._identity.passage_prefix)

    def health(self) -> ProviderHealth:
        """Check the selected service through its safe model-list endpoint."""

        try:
            response = self._transport.request(
                "GET",
                self._origin.endpoint("models"),
                headers=self._headers(),
                body=None,
                timeout=5.0,
            )
        except ProviderError as exc:
            return ProviderHealth(False, _checked_at(), exc.code)
        except Exception:
            return ProviderHealth(
                False,
                _checked_at(),
                ProviderFailureCode.UNAVAILABLE,
            )
        if response.status != 200:
            return ProviderHealth(
                False,
                _checked_at(),
                failure_for_status(response.status),
            )
        try:
            payload = _json_object(response.body)
            if not openai_model_available(payload, self._model):
                return ProviderHealth(False, _checked_at(), ProviderFailureCode.UNAVAILABLE)
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            return ProviderHealth(
                False,
                _checked_at(),
                ProviderFailureCode.INVALID_RESPONSE,
            )
        return ProviderHealth(True, _checked_at())

    def _embed(self, texts: list[str], prefix: str) -> NDArray[np.float32]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        if not texts:
            return np.empty((0, self._identity.dimension), dtype=np.float32)

        request = {
            "encoding_format": "float",
            "input": [_prefix_once(text, prefix) for text in texts],
            "model": self._model,
        }
        try:
            response = self._transport.request(
                "POST",
                self._origin.endpoint("embeddings"),
                headers=self._headers({"Content-Type": "application/json"}),
                body=_json_bytes(request),
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
        if response.status != 200:
            raise ProviderError(_failure_for_response(response.status, response.body))
        try:
            payload = _json_object(response.body)
            records = payload["data"]
            if not isinstance(records, list) or len(records) != len(texts):
                raise ValueError
            matrix = _parse_records(records, len(texts), self._identity.dimension)
        except ProviderError:
            raise
        except (KeyError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        return matrix

    def _headers(self, additional: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "RepoNPC-provider"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if additional:
            headers.update(additional)
        return headers


def _parse_records(records: list[Any], count: int, dimension: int) -> NDArray[np.float32]:
    """Validate OpenAI records, including optional response indexes."""

    has_index = [isinstance(record, dict) and "index" in record for record in records]
    if any(has_index):
        if not all(has_index):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        indexes = [record["index"] for record in records]
        if any(isinstance(index, bool) or not isinstance(index, int) for index in indexes):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        if indexes != list(range(count)):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)

    rows: list[list[float]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        raw_vector = record.get("embedding")
        rows.append(_validated_row(raw_vector, dimension))
    matrix = np.asarray(rows, dtype=np.float32)
    _validate_normalization(matrix)
    return matrix


def _validated_row(raw_vector: object, dimension: int) -> list[float]:
    if not isinstance(raw_vector, list) or len(raw_vector) != dimension:
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    row: list[float] = []
    for value in raw_vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        try:
            converted = np.float32(value)
        except (OverflowError, TypeError, ValueError):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE) from None
        if not np.isfinite(converted):
            raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
        row.append(float(converted))
    return row


def _validate_normalization(matrix: NDArray[np.float32]) -> None:
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
    norms = np.linalg.norm(matrix, axis=1)
    if (
        np.any(norms == 0)
        or not np.all(np.isfinite(norms))
        or not np.allclose(
            norms,
            1.0,
            rtol=_NORMALIZATION_RTOL,
            atol=_NORMALIZATION_ATOL,
        )
    ):
        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)


def _json_object(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError from exc
    if not isinstance(payload, dict):
        raise ValueError
    return payload


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _checked_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _prefix_once(text: str, prefix: str) -> str:
    return text if text.startswith(prefix) else prefix + text
