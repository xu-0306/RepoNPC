"""Concrete network embedding adapters obey the frozen runtime contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
import pytest

from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers import ProviderError, ProviderFailureCode
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.ollama_embeddings import OllamaEmbeddingProvider, OllamaPullCancelled
from reponpc.providers.openai_embeddings import OpenAICompatibleEmbeddingProvider


@dataclass
class Request:
    method: str
    url: str
    body: bytes | None


@dataclass
class Transport:
    responses: list[ProviderHttpResponse]
    requests: list[Request] = field(default_factory=list)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        del headers, timeout
        self.requests.append(Request(method, url, body))
        return self.responses.pop(0)


@dataclass
class StreamingTransport(Transport):
    lines: list[bytes] = field(default_factory=list)

    def stream_lines(self, method: str, url: str, **values: object) -> int:
        body = values["body"]
        assert isinstance(body, bytes)
        self.requests.append(Request(method, url, body))
        cancelled = values["cancelled"]
        on_line = values["on_line"]
        assert callable(cancelled) and callable(on_line)
        for line in self.lines:
            if cancelled():
                raise InterruptedError
            on_line(line)
        return 200


def response(status: int, payload: object) -> ProviderHttpResponse:
    return ProviderHttpResponse(status, {}, json.dumps(payload).encode())


def identity(adapter: str) -> EmbeddingIdentity:
    return EmbeddingIdentity(adapter, "fixture", 2, True, "query: ", "passage: ")


def test_openai_success_preserves_order_prefixes_once_and_float32() -> None:
    transport = Transport(
        [
            response(
                200,
                {
                    "data": [
                        {"index": 0, "embedding": [1, 0]},
                        {"index": 1, "embedding": [0, 1]},
                    ]
                },
            )
        ]
    )
    provider = OpenAICompatibleEmbeddingProvider(
        "https://models.example.test/v1", "fixture", identity("openai_compatible"), transport
    )

    output = provider.embed_query(["question", "query: existing"])

    assert output.dtype == np.float32
    assert output.shape == (2, 2)
    assert transport.requests[0].body is not None
    payload = json.loads(transport.requests[0].body.decode())
    assert payload["input"] == ["query: question", "query: existing"]
    assert payload["encoding_format"] == "float"


def test_ollama_success_and_empty_input_do_not_leak_or_call_twice() -> None:
    transport = Transport([response(200, {"embeddings": [[1.0, 0.0]]})])
    provider = OllamaEmbeddingProvider(
        "http://ollama:11434", "fixture", identity("ollama"), transport
    )

    empty = provider.embed_query([])
    output = provider.embed_passages(["document"])

    assert empty.shape == (0, 2) and empty.dtype == np.float32
    assert output.shape == (1, 2)
    assert len(transport.requests) == 1
    assert "ollama:11434" not in repr(provider)


def test_ollama_model_lifecycle_uses_only_provider_owned_fixed_endpoints() -> None:
    transport = Transport([response(200, {"status": "success"}), response(200, {})])
    provider = OllamaEmbeddingProvider(
        "http://ollama:11434", "fixture", identity("ollama"), transport
    )

    provider.pull_model()
    provider.delete_model()

    assert [(request.method, request.url) for request in transport.requests] == [
        ("POST", "http://ollama:11434/api/pull"),
        ("DELETE", "http://ollama:11434/api/delete"),
    ]
    assert json.loads(transport.requests[0].body or b"{}") == {
        "model": "fixture",
        "stream": False,
    }
    assert json.loads(transport.requests[1].body or b"{}") == {"model": "fixture"}


def test_ollama_pull_stream_reports_bounded_progress_and_honors_cancel() -> None:
    transport = StreamingTransport(
        [],
        lines=[
            b'{"status":"pulling","completed":2,"total":10}\n',
            b'{"status":"pulling","completed":10,"total":10}\n',
        ],
    )
    provider = OllamaEmbeddingProvider(
        "http://ollama:11434", "fixture", identity("ollama"), transport
    )
    progress: list[tuple[int | None, int | None]] = []

    provider.pull_model(
        cancelled=lambda: False, on_progress=lambda done, total: progress.append((done, total))
    )

    assert progress == [(2, 10), (10, 10)]
    assert json.loads(transport.requests[0].body or b"{}") == {
        "model": "fixture",
        "stream": True,
    }
    with pytest.raises(OllamaPullCancelled):
        provider.pull_model(cancelled=lambda: True)


def test_ollama_installed_models_returns_only_validated_ids() -> None:
    transport = Transport(
        [
            response(
                200,
                {
                    "models": [
                        {"name": "qwen3-embedding:0.6b"},
                        {"model": "bge-m3:latest"},
                    ]
                },
            )
        ]
    )
    provider = OllamaEmbeddingProvider(
        "http://ollama:11434", "fixture", identity("ollama"), transport
    )

    assert provider.installed_models() == (
        "bge-m3:latest",
        "qwen3-embedding:0.6b",
    )
    assert transport.requests[0].url == "http://ollama:11434/api/tags"


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 1, "embedding": [1, 0]}]},
        {"data": [{"index": 0, "embedding": [True, 0]}]},
        {"data": [{"index": 0, "embedding": [2, 0]}]},
        {"data": [{"index": 0, "embedding": [float("nan"), 0]}]},
    ],
)
def test_openai_rejects_bad_order_values_and_normalization(payload: object) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        "https://models.example.test/v1",
        "fixture",
        identity("openai_compatible"),
        Transport([response(200, payload)]),
    )

    with pytest.raises(ProviderError) as raised:
        provider.embed_query(["question"])
    assert raised.value.code is ProviderFailureCode.INVALID_RESPONSE


def test_status_mapping_and_safe_repr_do_not_reflect_secret_or_url() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        "https://private.example.test/v1",
        "fixture",
        identity("openai_compatible"),
        Transport([response(429, {"error": "private"})]),
        api_key="fixture-secret-key",
    )

    with pytest.raises(ProviderError) as raised:
        provider.embed_query(["question"])
    assert raised.value.code is ProviderFailureCode.RATE_LIMIT
    assert "fixture-secret-key" not in repr(provider)
    assert "private.example.test" not in repr(provider)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("unsupported_parameter", ProviderFailureCode.INVALID_RESPONSE),
        ("context_length_exceeded", ProviderFailureCode.CONTEXT_OVERFLOW),
    ],
)
def test_openai_embedding_maps_only_allowlisted_context_errors(
    code: str, expected: ProviderFailureCode
) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        "https://models.example.test/v1",
        "fixture",
        identity("openai_compatible"),
        Transport([response(400, {"error": {"code": code}})]),
    )

    with pytest.raises(ProviderError) as raised:
        provider.embed_query(["question"])

    assert raised.value.code is expected


def test_health_and_origin_policy_are_safe() -> None:
    provider = OllamaEmbeddingProvider(
        "http://ollama:11434",
        "fixture",
        identity("ollama"),
        Transport([response(503, {"error": "private"})]),
    )

    health = provider.health()

    assert health.ready is False
    assert health.failure_code is ProviderFailureCode.UNAVAILABLE
    assert "ollama" not in repr(health).casefold()
    with pytest.raises(ValueError):
        OllamaEmbeddingProvider("http://public.example.test", "fixture", identity("ollama"))


@pytest.mark.parametrize(
    "provider",
    [
        OpenAICompatibleEmbeddingProvider(
            "https://models.example.test/v1",
            "fixture",
            identity("openai_compatible"),
            Transport([response(200, {"data": [{"id": "other-model"}]})]),
        ),
        OllamaEmbeddingProvider(
            "http://ollama:11434",
            "fixture",
            identity("ollama"),
            Transport([response(200, {"models": [{"name": "other-model"}]})]),
        ),
    ],
)
def test_embedding_health_requires_the_explicitly_selected_model(provider: object) -> None:
    health = provider.health()  # type: ignore[attr-defined]

    assert health.ready is False
    assert health.failure_code is ProviderFailureCode.UNAVAILABLE


@pytest.mark.parametrize(
    "provider",
    [
        OpenAICompatibleEmbeddingProvider(
            "https://models.example.test/v1",
            "fixture",
            identity("openai_compatible"),
            Transport([response(200, {"data": [{"id": "fixture"}]})]),
        ),
        OllamaEmbeddingProvider(
            "http://ollama:11434",
            "fixture",
            identity("ollama"),
            Transport([response(200, {"models": [{"model": "fixture:latest"}]})]),
        ),
    ],
)
def test_embedding_health_accepts_the_selected_model(provider: object) -> None:
    assert provider.health().ready is True  # type: ignore[attr-defined]
