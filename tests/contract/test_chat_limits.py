"""Raised chat caps reach configured profiles while context and other budgets remain independent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reponpc.admin.chat_profiles import ChatProfileInput, ChatProfileRegistry
from reponpc.chat.service import GroundedChatService
from reponpc.config.environment import load_environment
from reponpc.main import _chat_provider_from_connection
from reponpc.providers import ProviderError, ProviderFailureCode, ProviderMessage
from reponpc.providers.http_transport import ProviderHttpResponse, UrllibProviderHttpTransport
from reponpc.providers.runtime import ProviderRuntime
from tests.contract.test_environment import deployment_environment
from tests.integration.test_chat_grounding_security import Bundles, Embedding, Limits
from tests.unit.test_chat_profiles import _connection_input, _registries


def test_chat_limits_default_without_raising_context_or_analysis(tmp_path: Path) -> None:
    settings = load_environment(deployment_environment(), secret_roots=(tmp_path,))
    assert settings.chat_timeout_seconds == 300
    assert settings.chat_max_output_tokens == 16384
    assert settings.chat_max_context_tokens == 32768
    assert settings.analysis_max_output_tokens == 16384


@pytest.mark.parametrize("provider_name", ["ollama", "openai_compatible", "vllm", "responses"])
@pytest.mark.parametrize("context", [32768, 65536])
def test_chat_profile_probe_admits_32768_only_with_room_for_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider_name: str, context: int
) -> None:
    settings = load_environment(
        deployment_environment(
            REPONPC_CHAT_MAX_OUTPUT_TOKENS="32768", REPONPC_CHAT_MAX_CONTEXT_TOKENS=str(context)
        ),
        secret_roots=(tmp_path,),
    )
    requests = []

    def fake_request(_transport, method, url, **kwargs):
        assert method == "POST"
        requests.append((url, json.loads(kwargs["body"])))
        if url.endswith("/api/show"):
            return ProviderHttpResponse(200, {}, b"{}")
        content = '{"ok":true}'
        if provider_name == "ollama":
            payload = {"message": {"content": content}, "done_reason": "stop"}
        elif provider_name == "responses":
            payload = {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": content}],
                    }
                ],
            }
        else:
            payload = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        return ProviderHttpResponse(200, {}, json.dumps(payload).encode())

    monkeypatch.setattr(UrllibProviderHttpTransport, "request", fake_request)
    connections, original_profiles = _registries(tmp_path)
    connection = connections.create(_connection_input())
    profiles = ChatProfileRegistry(
        original_profiles._database,
        connections,
        lambda profile: _chat_provider_from_connection(
            settings,
            "openai_compatible" if provider_name == "responses" else provider_name,
            profile.model_id,
            "https://model.example.test/v1",
            None,
            chat_api="responses" if provider_name == "responses" else "chat_completions",
        ),
    )
    profile = profiles.create(ChatProfileInput(connection.connection_id, "arbitrary-model"))
    result = profiles.probe(profile.profile_id)
    if context == 32768:
        assert result.status == "probe_failed"
        assert result.last_error_code == "PROVIDER_CONTEXT_OVERFLOW"
        assert requests == []
    else:
        assert result.status == "ready"
        generation = requests[-1][1]
        assert (
            generation["options"]["num_predict"]
            if provider_name == "ollama"
            else generation["max_output_tokens"]
            if provider_name == "responses"
            else generation["max_tokens"]
        ) == 32768


@pytest.mark.parametrize("output", [32768, 32769])
def test_chat_output_at_or_above_context_fails_before_any_provider_call(output: int) -> None:
    from reponpc.providers import ProviderCapabilities

    class Chat:
        calls = 0

        def capabilities(self):
            return ProviderCapabilities(False, True, True, True, True, 32768, 32768)

        def generate(self, *_args, **_kwargs):
            self.calls += 1
            pytest.fail("No generation is allowed without input room")

    chat = Chat()
    embedding = Embedding()
    service = GroundedChatService(
        bundles=Bundles(),
        providers=ProviderRuntime(chat=chat, embedding=embedding),  # type: ignore[arg-type]
        limits=Limits(),  # type: ignore[arg-type]
        max_output_tokens=output,
        timeout_seconds=300,
    )
    with pytest.raises(ProviderError) as raised:
        service.answer(message="What is implemented?", locale="en", history=(), client_ip=None)
    assert raised.value.code is ProviderFailureCode.CONTEXT_OVERFLOW
    assert chat.calls == 0
    assert embedding.calls == 0


@pytest.mark.parametrize("provider_name", ["ollama", "openai_compatible", "vllm", "responses"])
def test_chat_adapter_rejects_output_context_equality_without_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider_name: str
) -> None:
    settings = load_environment(
        deployment_environment(REPONPC_CHAT_MAX_OUTPUT_TOKENS="32768"), secret_roots=(tmp_path,)
    )
    requests = []

    def forbidden_request(*args, **kwargs):
        requests.append((args, kwargs))
        pytest.fail("Unsafe output/context configuration must not reach any provider endpoint")

    monkeypatch.setattr(UrllibProviderHttpTransport, "request", forbidden_request)
    provider = _chat_provider_from_connection(
        settings,
        "openai_compatible" if provider_name == "responses" else provider_name,
        "arbitrary-model",
        "https://model.example.test/v1",
        None,
        chat_api="responses" if provider_name == "responses" else "chat_completions",
    )
    with pytest.raises(ProviderError) as raised:
        provider.generate((ProviderMessage("user", "Fixture"),), {}, 32768, 300)
    assert raised.value.code is ProviderFailureCode.CONTEXT_OVERFLOW
    assert requests == []
