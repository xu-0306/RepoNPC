"""Shared contract tests for concrete Phase 3 chat adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from reponpc.providers import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderMessage,
)
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider

CAPABILITIES = ProviderCapabilities(
    streaming=False,
    system_role=True,
    structured_output=True,
    usage_reporting=True,
    health_check=True,
    max_context_tokens=8_192,
    max_output_tokens=1_000,
)
MESSAGES = (ProviderMessage("system", "policy"), ProviderMessage("user", "question"))
SCHEMA = {"type": "object", "properties": {"answer_markdown": {"type": "string"}}}
SCENARIO_FIXTURE = Path(__file__).parents[1] / "fixtures" / "providers" / "chat_scenarios.json"


@dataclass(slots=True)
class RecordedRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None
    timeout: float


@dataclass(slots=True)
class RecordingTransport:
    responses: list[ProviderHttpResponse]
    requests: list[RecordedRequest] = field(default_factory=list)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        self.requests.append(RecordedRequest(method, url, dict(headers), body, timeout))
        return self.responses.pop(0)


def response(status: int, payload: object) -> ProviderHttpResponse:
    return ProviderHttpResponse(status, {}, json.dumps(payload).encode())


def fixture_scenarios() -> dict[str, dict[str, Any]]:
    payload = json.loads(SCENARIO_FIXTURE.read_text(encoding="utf-8"))
    return {scenario["id"]: scenario for scenario in payload["scenarios"]}


def fixture_response(scenario: dict[str, Any]) -> ProviderHttpResponse:
    body = scenario["body"]
    encoded = (
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if scenario["body_type"] == "json"
        else body.encode()
    )
    return ProviderHttpResponse(scenario["status"], {}, encoded)


def test_openai_adapter_buffers_structured_output_and_usage_without_streaming() -> None:
    transport = RecordingTransport(
        [
            response(
                200,
                {
                    "id": "request-1",
                    "choices": [
                        {
                            "message": {"content": {"answer_markdown": "ok [S1]"}},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 4},
                },
            )
        ]
    )
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1", "fixture-chat", CAPABILITIES, "fake-key", transport
    )

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    request = transport.requests[0]
    assert request.body is not None
    body = json.loads(request.body.decode())
    assert request.url == "https://models.example.test/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer fake-key"
    assert body["stream"] is False
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert result.content == {"answer_markdown": "ok [S1]"}
    assert result.usage is not None and result.usage.output_tokens == 4


def test_ollama_adapter_uses_only_private_origin_and_supported_fields() -> None:
    transport = RecordingTransport(
        [
            response(
                200,
                {
                    "message": {"content": "ok [S1]"},
                    "done_reason": "stop",
                    "prompt_eval_count": 6,
                    "eval_count": 2,
                },
            )
        ]
    )
    provider = OllamaChatProvider("http://ollama:11434", "fixture-chat", CAPABILITIES, transport)

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    request = transport.requests[0]
    assert request.body is not None
    body = json.loads(request.body.decode())
    assert request.url == "http://ollama:11434/api/chat"
    assert body == {
        "format": SCHEMA,
        "messages": [
            {"content": "policy", "role": "system"},
            {"content": "question", "role": "user"},
        ],
        "model": "fixture-chat",
        "options": {"num_predict": 100},
        "stream": False,
    }
    assert result.usage is not None and result.usage.input_tokens == 6


@pytest.mark.parametrize("status", [401, 429, 504, 503, 418])
def test_both_adapters_map_failures_without_reflecting_private_body(status: int) -> None:
    private = "http://private-provider.internal/secret"
    for provider in (
        OpenAICompatibleChatProvider(
            "https://models.example.test/v1",
            "fixture",
            CAPABILITIES,
            transport=RecordingTransport([response(status, {"error": private})]),
        ),
        OllamaChatProvider(
            "http://ollama:11434",
            "fixture",
            CAPABILITIES,
            RecordingTransport([response(status, {"error": private})]),
        ),
    ):
        with pytest.raises(ProviderError) as raised:
            provider.generate(MESSAGES, SCHEMA, 100, 3.0)
        assert private not in str(raised.value)


@pytest.mark.parametrize("status", [400, 413, 422])
def test_validation_statuses_are_not_assumed_to_be_context_overflow(status: int) -> None:
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1",
        "fixture",
        CAPABILITIES,
        transport=RecordingTransport(
            [response(status, {"error": {"code": "unsupported_parameter"}})]
        ),
    )

    with pytest.raises(ProviderError) as raised:
        provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert raised.value.code is ProviderFailureCode.INVALID_RESPONSE


def test_allowlisted_structured_error_code_maps_to_context_overflow() -> None:
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1",
        "fixture",
        CAPABILITIES,
        transport=RecordingTransport(
            [response(400, {"error": {"code": "context_length_exceeded"}})]
        ),
    )

    with pytest.raises(ProviderError) as raised:
        provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert raised.value.code is ProviderFailureCode.CONTEXT_OVERFLOW


def test_capabilities_prevent_unsupported_system_and_structured_parameters() -> None:
    limited = ProviderCapabilities(False, False, False, False, True, 4_096, 256)
    transport = RecordingTransport([])
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1", "fixture", limited, transport=transport
    )

    with pytest.raises(ProviderError) as raised:
        provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert raised.value.code is ProviderFailureCode.INVALID_RESPONSE
    assert transport.requests == []


def test_openai_compatible_omits_structured_output_when_capability_is_disabled() -> None:
    limited = ProviderCapabilities(False, True, False, False, True, 4_096, 256)
    transport = RecordingTransport(
        [
            response(
                200,
                {
                    "choices": [
                        {
                            "message": {"content": '{"answer_markdown":"ok [S1]"}'},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"vendor_tokens": "not-standard"},
                },
            )
        ]
    )
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1", "fixture", limited, transport=transport
    )

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert transport.requests[0].body is not None
    body = json.loads(transport.requests[0].body.decode())
    assert "response_format" not in body
    assert result.usage is None


def test_ollama_ignores_usage_fields_when_reporting_capability_is_disabled() -> None:
    limited = ProviderCapabilities(False, True, True, False, True, 4_096, 256)
    provider = OllamaChatProvider(
        "http://ollama:11434",
        "fixture",
        limited,
        RecordingTransport(
            [
                response(
                    200,
                    {
                        "message": {"content": "ok [S1]"},
                        "done_reason": "stop",
                        "prompt_eval_count": "not-standard",
                    },
                )
            ]
        ),
    )

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert result.usage is None


def test_health_is_safe_and_does_not_return_provider_url() -> None:
    openai = OpenAICompatibleChatProvider(
        "https://models.example.test/v1",
        "fixture",
        CAPABILITIES,
        transport=RecordingTransport([response(200, {"data": [{"id": "fixture"}]})]),
    )
    ollama = OllamaChatProvider(
        "http://ollama:11434",
        "fixture",
        CAPABILITIES,
        RecordingTransport([response(503, {"error": "private"})]),
    )

    assert openai.health().ready is True
    health = ollama.health()
    assert health.ready is False
    assert health.failure_code is ProviderFailureCode.UNAVAILABLE
    assert "ollama" not in repr(health).casefold()


@pytest.mark.parametrize(
    "provider",
    [
        OpenAICompatibleChatProvider(
            "https://models.example.test/v1",
            "selected-model",
            CAPABILITIES,
            transport=RecordingTransport([response(200, {"data": [{"id": "other-model"}]})]),
        ),
        OllamaChatProvider(
            "http://ollama:11434",
            "selected-model",
            CAPABILITIES,
            RecordingTransport([response(200, {"models": [{"name": "other-model"}]})]),
        ),
    ],
)
def test_health_requires_the_explicitly_selected_model(provider: object) -> None:
    health = provider.health()  # type: ignore[attr-defined]

    assert health.ready is False
    assert health.failure_code is ProviderFailureCode.UNAVAILABLE


def test_ollama_health_accepts_the_default_latest_tag_for_selected_model() -> None:
    provider = OllamaChatProvider(
        "http://ollama:11434",
        "selected-model",
        CAPABILITIES,
        RecordingTransport([response(200, {"models": [{"name": "selected-model:latest"}]})]),
    )

    assert provider.health().ready is True


def test_insecure_public_openai_and_public_ollama_urls_are_rejected() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleChatProvider("http://models.example.test/v1", "fixture", CAPABILITIES)
    with pytest.raises(ValueError):
        OllamaChatProvider("http://public.example.test", "fixture", CAPABILITIES)


def test_private_chat_origins_are_not_exposed_by_provider_representations() -> None:
    vllm_url = "http://127.0.0.1:8000/v1"
    ollama_url = "http://ollama:11434"
    vllm = OpenAICompatibleChatProvider(
        vllm_url,
        "fixture",
        CAPABILITIES,
        api_key="private-key",
        allow_private_http=True,
    )
    ollama = OllamaChatProvider(ollama_url, "fixture", CAPABILITIES)

    rendered = repr(vllm) + repr(ollama)
    assert vllm_url not in rendered
    assert ollama_url not in rendered
    assert "private-key" not in rendered


@pytest.mark.parametrize(
    "scenario_id,expected_usage",
    [
        ("openai_success_structured_usage", (11, 7)),
        ("openai_success_null_usage", None),
    ],
)
def test_openai_adapter_consumes_the_frozen_success_fixtures(
    scenario_id: str,
    expected_usage: tuple[int, int] | None,
) -> None:
    scenario = fixture_scenarios()[scenario_id]
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1",
        "fixture",
        CAPABILITIES,
        transport=RecordingTransport([fixture_response(scenario)]),
    )

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert isinstance(result.content, dict)
    if expected_usage is None:
        assert result.usage is None
    else:
        assert result.usage is not None
        assert (result.usage.input_tokens, result.usage.output_tokens) == expected_usage


def test_ollama_adapter_consumes_the_frozen_success_fixture() -> None:
    scenario = fixture_scenarios()["ollama_success"]
    provider = OllamaChatProvider(
        "http://ollama:11434",
        "fixture",
        CAPABILITIES,
        RecordingTransport([fixture_response(scenario)]),
    )

    result = provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert result.content == "Fixture Ollama answer [E1]"
    assert result.usage is not None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (9, 5)


@pytest.mark.parametrize(
    "scenario_id,expected_code",
    [
        ("authentication_401", ProviderFailureCode.AUTHENTICATION),
        ("rate_limit_429", ProviderFailureCode.RATE_LIMIT),
        ("timeout_504", ProviderFailureCode.TIMEOUT),
        ("unavailable_503", ProviderFailureCode.UNAVAILABLE),
        ("malformed_json_body", ProviderFailureCode.INVALID_RESPONSE),
        ("context_overflow_422", ProviderFailureCode.CONTEXT_OVERFLOW),
    ],
)
def test_openai_adapter_consumes_frozen_failure_fixtures_without_reflection(
    scenario_id: str,
    expected_code: ProviderFailureCode,
) -> None:
    scenario = fixture_scenarios()[scenario_id]
    provider = OpenAICompatibleChatProvider(
        "https://models.example.test/v1",
        "fixture",
        CAPABILITIES,
        transport=RecordingTransport([fixture_response(scenario)]),
    )

    with pytest.raises(ProviderError) as raised:
        provider.generate(MESSAGES, SCHEMA, 100, 3.0)

    assert raised.value.code is expected_code
    assert str(scenario["body"]) not in str(raised.value)
