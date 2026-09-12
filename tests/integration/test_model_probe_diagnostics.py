"""Real adapters -> probe registry -> authenticated API; no external model calls."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.chat_profiles import ChatProfileInput, ChatProfileRegistry
from reponpc.admin.embedding_profiles import EmbeddingProfileInput, EmbeddingProfileRegistry
from reponpc.admin.model_connections import (
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.admin.operations import AdminOperations
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.main import create_app
from reponpc.providers.contracts import ProviderCapabilities, ProviderError, ProviderFailureCode
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.ollama_embeddings import OllamaEmbeddingProvider
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider
from reponpc.providers.openai_embeddings import OpenAICompatibleEmbeddingProvider
from reponpc.runtime.database import RuntimeDatabase

ORIGIN = "https://portfolio.example.com"
CANARY = "SYNTHETIC_SECRET_CANARY https://private.example.test/private"
CAPABILITIES = ProviderCapabilities(False, True, True, False, True, 4096, 256)


class Transport:
    def __init__(self, failure: int | str, key: str | None = None) -> None:
        self.failure: int | str | None = failure
        self.key = key

    def request(self, *_args: object, **_kwargs: object) -> ProviderHttpResponse:
        if isinstance(self.failure, int):
            return ProviderHttpResponse(
                self.failure,
                {},
                json.dumps(
                    {
                        "error": {
                            "message": "Original upstream issue Ω-7: https://service.example.test"
                            + (f" {self.key}" if self.key else "")
                        },
                        "metadata": CANARY,
                    }
                ).encode(),
            )
        if self.failure == "timeout":
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        if self.failure == "unknown":
            raise RuntimeError(CANARY)
        if self.failure == "malformed":
            return ProviderHttpResponse(200, {}, CANARY.encode())
        payload = {
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "message": {"content": '{"ok":true}'},
            "data": [{"index": 0, "embedding": [0.6, 0.8]}],
            "embeddings": [[0.6, 0.8]],
        }
        return ProviderHttpResponse(200, {}, json.dumps(payload).encode())


@pytest.mark.parametrize("adapter", ["openai_compatible", "ollama"])
@pytest.mark.parametrize("role", ["chat", "embedding"])
@pytest.mark.parametrize(
    "failure", [401, 402, 403, 404, 429, 503, 504, "timeout", "unknown", "malformed"]
)
def test_probe_diagnostics_survive_reload_and_clear_after_success(
    tmp_path: Path, adapter: str, role: str, failure: int | str
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database, ProtectedModelSecretStore(tmp_path / "secrets" / "model.key")
    )
    connection = connections.create(
        ModelConnectionInput("Fixture service", adapter, "https://service.example.test", None)
    )
    key = "SYNTHETIC_SECRET_CANARY" if adapter == "openai_compatible" else None
    transport = Transport(failure, key)
    credentials = {"api_key": key} if key else {}
    identity = EmbeddingIdentity(adapter, "fixture-model", 2, True, "", "")
    chat_class = OllamaChatProvider if adapter == "ollama" else OpenAICompatibleChatProvider
    embed_class = (
        OllamaEmbeddingProvider if adapter == "ollama" else OpenAICompatibleEmbeddingProvider
    )
    chat = chat_class(
        "https://service.example.test",
        "fixture-model",
        CAPABILITIES,
        transport=transport,
        **credentials,
    )
    embedding = embed_class(
        "https://service.example.test", "fixture-model", identity, transport, **credentials
    )
    chats = ChatProfileRegistry(database, connections, lambda _: chat)
    embeddings = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _: embedding,
        activation_compatible=lambda _: True,
    )
    if role == "chat":
        profile = chats.create(ChatProfileInput(connection.connection_id, "fixture-model"))
    else:
        profile = embeddings.create(
            EmbeddingProfileInput(
                adapter, "fixture-model", 2, True, "", "", connection.connection_id
            )
        )
    auth = AdminSessionService(
        database=database,
        username="admin",
        password_hash=PasswordHasher().hash("fixture password for model diagnostics"),
        identity_hmac_key=b"d" * 32,
    )
    app = create_app(
        admin_session_service=auth,
        admin_origins=(ORIGIN,),
        admin_operations=AdminOperations(
            github=None,
            database=database,
            public_base_url=ORIGIN,
            model_connections=connections,
            chat_profiles=chats,
            embedding_profiles=embeddings,
        ),
    )
    endpoint = f"/api/admin/{role}-profiles"
    expected = (
        f"PROVIDER_HTTP_{failure}"
        if isinstance(failure, int)
        else "PROVIDER_TIMEOUT"
        if failure == "timeout"
        else "PROVIDER_INVALID_RESPONSE"
        if failure == "malformed"
        else "PROVIDER_UNAVAILABLE"
        if role == "embedding"
        else f"{role.upper()}_PROBE_FAILED"
    )
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get(endpoint, headers={"Origin": ORIGIN}).status_code == 401
        login = client.post(
            "/api/admin/session",
            headers={"Origin": ORIGIN},
            json={
                "username": "admin",
                "password": "fixture password for model diagnostics",
            },
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        failed = client.post(f"{endpoint}/{profile.profile_id}/probe", headers=headers)
        assert failed.status_code == 200
        assert failed.json()["last_error_code"] == expected
        expected_message = (
            "Original upstream issue Ω-7: [redacted]" if isinstance(failure, int) else None
        )
        if failure == "malformed" and role == "chat":
            expected_message = (
                "RepoNPC response check: HTTP 200; response body is not a JSON object."
            )
        if isinstance(failure, int) and key:
            expected_message += " [redacted]"
        assert failed.json()["last_error_message"] == expected_message
        assert failed.json()["status"] == "probe_failed"
        assert failed.json()["active"] is False
        reloaded = client.get(endpoint, headers=headers)
        assert reloaded.json()["profiles"][0]["last_error_code"] == expected
        assert reloaded.json()["profiles"][0]["last_error_message"] == expected_message
        assert CANARY not in failed.text + reloaded.text
        if key:
            assert key not in failed.text + reloaded.text
        assert "private.example.test" not in failed.text + reloaded.text
        transport.failure = None
        passed = client.post(f"{endpoint}/{profile.profile_id}/probe", headers=headers)
        assert passed.json()["status"] == "ready"
        assert passed.json()["last_error_code"] is None
        assert passed.json()["last_error_message"] is None
        assert (
            client.get(endpoint, headers=headers).json()["profiles"][0]["last_error_code"] is None
        )
        activated = client.post(f"{endpoint}/{profile.profile_id}/activate", headers=headers)
        assert activated.status_code == 200
        transport.failure = failure
        failed_active = client.post(f"{endpoint}/{profile.profile_id}/probe", headers=headers)
        assert failed_active.json()["active"] is True
        assert failed_active.json()["status"] == "last_known_good"
        assert failed_active.json()["last_error_code"] == expected
        assert failed_active.json()["last_error_message"] == expected_message


@pytest.mark.parametrize("status", [True, 99, 600, "402", 402.0])
def test_provider_error_rejects_non_http_metadata(status: object) -> None:
    with pytest.raises(ValueError):
        ProviderError(ProviderFailureCode.UNAVAILABLE, upstream_status=status)  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["chat", "embedding"])
def test_provider_resolution_failure_is_saved_without_exception_text(
    tmp_path: Path, role: str
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database, ProtectedModelSecretStore(tmp_path / "secrets" / "model.key")
    )
    connection = connections.create(
        ModelConnectionInput("Fixture", "ollama", "https://service.example.test", None)
    )

    def unavailable(_: object) -> None:
        raise ProviderError(ProviderFailureCode.UNAVAILABLE)

    registry: ChatProfileRegistry | EmbeddingProfileRegistry
    if role == "chat":
        registry = ChatProfileRegistry(database, connections, unavailable)
        profile = registry.create(ChatProfileInput(connection.connection_id, "fixture-model"))
    else:
        registry = EmbeddingProfileRegistry(
            database=database, provider_resolver=unavailable, activation_compatible=lambda _: True
        )
        profile = registry.create(
            EmbeddingProfileInput(
                "ollama", "fixture-model", 2, True, "", "", connection.connection_id
            )
        )
    result = registry.probe(profile.profile_id)
    assert result.last_error_code == "PROVIDER_UNAVAILABLE"
    assert registry.get(profile.profile_id).last_error_code == "PROVIDER_UNAVAILABLE"
