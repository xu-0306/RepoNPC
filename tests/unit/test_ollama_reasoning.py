"""Generic reasoning discovery and bounded context; no live model calls."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import pytest

from reponpc.admin.onboarding import analysis_generation_policy_identity
from reponpc.providers.contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderMessage,
)
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.openai_compatible import _json_bytes

CAP = ProviderCapabilities(False, True, True, True, True, 32768, 16384)
MESSAGE = (ProviderMessage("user", "synthetic question"),)
SCHEMA = {"type": "object"}


@dataclass
class Transport:
    payload: dict[str, object]
    status: int = 200
    calls: list[tuple[str, dict[str, object], float]] = field(default_factory=list)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        del headers
        assert body is not None
        self.calls.append((url.rsplit("/", 1)[-1], json.loads(body), timeout))
        assert method == "POST"
        if url.endswith("/show"):
            return ProviderHttpResponse(self.status, {}, json.dumps(self.payload).encode())
        return ProviderHttpResponse(
            200,
            {},
            b'{"message":{"content":"{}","thinking":"PRIVATE_THOUGHT_CANARY"},"done_reason":"stop"}',
        )


@pytest.mark.parametrize("model", ["invented/a", "unrelated:b", "arbitrary-family"])
@pytest.mark.parametrize(
    ("metadata", "expected", "supported"),
    [
        ({"thinking": {"values": [False, True], "default": False}}, True, True),
        ({"thinking": {"values": [True], "default": True}}, True, True),
        ({"thinking": {"values": ["economy", "thorough"], "default": "economy"}}, "economy", True),
        ({"capabilities": ["thinking"]}, True, True),
        ({"thinking": {"values": [False], "default": False}}, None, False),
        ({}, None, None),
    ],
)
def test_discovered_control_is_enabled_and_name_independent(
    model: str,
    metadata: dict[str, object],
    expected: object,
    supported: bool | None,
) -> None:
    transport = Transport(metadata)
    provider = OllamaChatProvider("http://127.0.0.1:11434", model, CAP, transport)
    provider.prepare()
    provider.prepare()
    result = provider.generate(MESSAGE, SCHEMA, 16384, 180)
    assert len(transport.calls) == 2
    _, request, timeout = transport.calls[-1]
    assert timeout == 180
    assert request["options"] == {"num_predict": 16384, "num_ctx": 32768}
    assert request.get("think") == expected
    assert ("think" in request) is (expected is not None)
    assert provider.capabilities().reasoning_supported is supported
    assert "PRIVATE_THOUGHT_CANARY" not in repr(result)
    assert "PRIVATE_THOUGHT_CANARY" not in repr(provider)


@pytest.mark.parametrize(
    "metadata",
    [
        {"thinking": "PRIVATE_PATH_CANARY"},
        {"thinking": {"values": []}},
        {"thinking": {"values": [False, True]}},
        {"thinking": {"values": [False, True], "default": 1}},
        {"thinking": {"values": [False, True], "default": "PRIVATE_PATH_CANARY"}},
        {"thinking": {"values": [1], "default": 1}},
        {
            "thinking": {
                "values": ["http://PRIVATE_PATH_CANARY"],
                "default": "http://PRIVATE_PATH_CANARY",
            }
        },
        {"thinking": {"values": ["low"], "default": "unknown"}},
        {"thinking": {"values": ["low"], "default": False}},
        {"thinking": {"values": [True] * 17}},
        {"capabilities": "thinking"},
        {"model_info": {"general.architecture": "../PRIVATE_PATH_CANARY"}},
        {"model_info": {"general.architecture": "fixture", "fixture.context_length": True}},
        {"model_info": {"general.architecture": "fixture", "fixture.context_length": 0}},
    ],
)
def test_malformed_metadata_fails_closed_without_private_diagnostics(
    metadata: dict[str, object],
) -> None:
    transport = Transport(metadata)
    provider = OllamaChatProvider("http://127.0.0.1:11434", "invented", CAP, transport)
    with pytest.raises(ProviderError) as failure:
        provider.prepare()
    assert failure.value.code == ProviderFailureCode.INVALID_RESPONSE
    assert "PRIVATE_PATH_CANARY" not in str(failure.value)
    assert "PRIVATE_PATH_CANARY" not in repr(provider)
    with pytest.raises(ProviderError):
        provider.generate(MESSAGE, SCHEMA, 16384, 180)
    assert len(transport.calls) == 1


@pytest.mark.parametrize("limit", [4096, 16384, 20000, 262144])
def test_native_context_caps_configuration_and_shortage_never_generates(limit: int) -> None:
    transport = Transport(
        {"model_info": {"general.architecture": "fixture", "fixture.context_length": limit}}
    )
    provider = OllamaChatProvider("http://127.0.0.1:11434", "invented", CAP, transport)
    if limit <= 16384:
        with pytest.raises(ProviderError) as failure:
            provider.prepare()
        assert failure.value.code == ProviderFailureCode.CONTEXT_OVERFLOW
        with pytest.raises(ProviderError):
            provider.generate(MESSAGE, SCHEMA, provider.capabilities().max_output_tokens, 180)
        assert len(transport.calls) == 1
    else:
        provider.prepare()
        provider.generate(MESSAGE, SCHEMA, 16384, 180)
        assert transport.calls[-1][1]["options"] == {
            "num_predict": 16384,
            "num_ctx": min(limit, 32768),
        }


@pytest.mark.parametrize("overflow", [0, 1])
def test_complete_serialized_messages_schema_and_output_boundary(overflow: int) -> None:
    messages = (ProviderMessage("system", "政策"), ProviderMessage("user", "x" * 600))
    required = (
        len(
            _json_bytes(
                {
                    "messages": [{"role": item.role, "content": item.content} for item in messages],
                    "format": SCHEMA,
                }
            )
        )
        + 256
        + 16384
    )
    transport = Transport({})
    provider = OllamaChatProvider(
        "http://127.0.0.1:11434",
        "invented",
        replace(CAP, max_context_tokens=required - overflow),
        transport,
    )
    if overflow:
        with pytest.raises(ProviderError) as failure:
            provider.generate(messages, SCHEMA, 16384, 180)
        assert failure.value.code == ProviderFailureCode.CONTEXT_OVERFLOW
        assert transport.calls == []
    else:
        provider.generate(messages, SCHEMA, 16384, 180)
        assert len(transport.calls) == 1


@pytest.mark.parametrize("status", [401, 503, 504])
def test_discovery_failure_has_no_generation_or_hidden_retry(status: int) -> None:
    transport = Transport({}, status)
    provider = OllamaChatProvider("http://127.0.0.1:11434", "invented", CAP, transport)
    with pytest.raises(ProviderError):
        provider.prepare(timeout=2)
    with pytest.raises(ProviderError):
        provider.prepare()
    with pytest.raises(ProviderError):
        provider.generate(MESSAGE, SCHEMA, 16384, 180)
    assert len(transport.calls) == 1
    assert transport.calls[0][2] == 2
    assert not provider.health().ready


@pytest.mark.parametrize("status", [404, 405, 501])
def test_unsupported_discovery_preserves_unknown_model_default(status: int) -> None:
    transport = Transport({}, status)
    provider = OllamaChatProvider("http://127.0.0.1:11434", "invented", CAP, transport)
    provider.prepare()
    provider.generate(MESSAGE, SCHEMA, 16384, 180)
    assert "think" not in transport.calls[-1][1]
    assert provider.capabilities().reasoning_supported is None


def test_cache_identity_changes_with_reasoning_policy_and_explicit_lower_budget() -> None:
    unknown = analysis_generation_policy_identity(16384, CAP)
    enabled = analysis_generation_policy_identity(
        16384, replace(CAP, reasoning_supported=True, reasoning_control=True)
    )
    named = analysis_generation_policy_identity(
        16384, replace(CAP, reasoning_supported=True, reasoning_control="economy")
    )
    lower = analysis_generation_policy_identity(4096, CAP)
    assert len({unknown, enabled, named, lower}) == 4
    assert json.loads(enabled)["output_policy_version"] == "analysis-output-policy-v2-reasoning-on"


@pytest.mark.parametrize("control", [False, 1, "../private", "x" * 33])
def test_capability_cannot_disable_thinking_or_store_unbounded_control(control: object) -> None:
    with pytest.raises(ValueError):
        replace(CAP, reasoning_supported=True, reasoning_control=control)  # type: ignore[arg-type]
