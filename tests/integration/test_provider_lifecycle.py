"""The real FastAPI lifespan owns provider health and publishes safe readiness."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from reponpc.admin.embedding_profiles import EmbeddingProfileInput, EmbeddingProfileRegistry
from reponpc.api.public import SetupState
from reponpc.config.environment import load_environment
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.main import (
    _configure_provider_lifecycle,
    _environment_embedding_provider,
    create_app,
)
from reponpc.providers import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    ProviderCapabilities,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
)
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase


@dataclass
class LifecycleChat:
    health_result: ProviderHealth
    health_calls: int = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 1000, 100)

    def health(self) -> ProviderHealth:
        self.health_calls += 1
        return self.health_result

    def generate(
        self,
        messages: tuple[ProviderMessage, ...],
        response_schema: dict[str, Any],
        max_output_tokens: int,
        timeout: float,
    ) -> ProviderResult:
        del messages, response_schema, max_output_tokens, timeout
        return ProviderResult("ok", "stop", None, None, 1.0)


@dataclass
class LifecycleEmbedding:
    health_result: ProviderHealth
    health_calls: int = 0

    def identity(self) -> EmbeddingIdentity:
        return EmbeddingIdentity("ollama", "fixture", 2, True, "query: ", "passage: ")

    def health(self) -> ProviderHealth:
        self.health_calls += 1
        return self.health_result

    def embed_query(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def embed_passages(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        return self.embed_query(texts)


def test_real_lifespan_polls_selected_providers_before_serving_and_degrades_safely() -> None:
    chat = LifecycleChat(ProviderHealth(True, "2026-08-12T00:00:00Z"))
    embedding = LifecycleEmbedding(
        ProviderHealth(False, "2026-08-12T00:00:01Z", ProviderFailureCode.UNAVAILABLE)
    )
    runtime = ProviderRuntime(
        chat=chat,  # type: ignore[arg-type]
        embedding=embedding,  # type: ignore[arg-type]
    )
    application = create_app(
        setup_state=SetupState(index_ready=True, index_version="fixture-index"),
        provider_runtime=runtime,
        provider_adapter="ollama",
        provider_health_seconds=3600,
    )

    with TestClient(application) as client:
        status = client.get("/api/public/status")
        readiness = client.get("/readyz")

        assert status.status_code == 200
        assert status.json()["model"] == {
            "ready": False,
            "provider": "ollama",
            "last_checked_at": "2026-08-12T00:00:01Z",
        }
        assert status.json()["chat_available"] is False
        assert readiness.status_code == 503
        assert chat.health_calls == 1
        assert embedding.health_calls == 1
    assert chat.health_calls == 1
    assert embedding.health_calls == 1


def test_real_lifespan_marks_ready_only_when_index_storage_and_both_providers_are_ready() -> None:
    ready = ProviderHealth(True, "2026-08-12T00:00:00Z")
    runtime = ProviderRuntime(
        chat=LifecycleChat(ready),  # type: ignore[arg-type]
        embedding=LifecycleEmbedding(ready),  # type: ignore[arg-type]
    )
    application = create_app(
        setup_state=SetupState(index_ready=True, index_version="fixture-index"),
        provider_runtime=runtime,
        provider_adapter="openai_compatible",
    )

    with TestClient(application) as client:
        assert client.get("/readyz").status_code == 200
        status = client.get("/api/public/status").json()
        assert status["status"] == "ready"
        assert status["model"]["provider"] == "openai_compatible"


def test_production_assembly_wires_only_selected_ollama_adapters_and_configured_limits(
    tmp_path: Path, monkeypatch: object
) -> None:
    settings = load_environment(
        {
            "REPONPC_DATA_DIR": str(tmp_path),
            "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
            "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
            "REPONPC_INDEX_MANIFEST_URL": "https://raw.githubusercontent.com/example/portfolio/main/stable-manifest.json",
            "REPONPC_CHAT_PROVIDER": "ollama",
            "REPONPC_CHAT_MODEL": "fixture-chat",
            "REPONPC_CHAT_BASE_URL": "http://127.0.0.1:11434",
            "REPONPC_EMBEDDING_PROVIDER": "ollama",
            "REPONPC_EMBEDDING_MODEL": "fixture-embed",
            "REPONPC_EMBEDDING_BASE_URL": "http://127.0.0.1:11434",
            "REPONPC_EMBEDDING_DIMENSION": "2",
            "REPONPC_MAX_MESSAGE_CHARACTERS": "8",
            "REPONPC_MAX_HISTORY_MESSAGES": "2",
            "REPONPC_MAX_HISTORY_CHARACTERS": "12",
        },
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(settings.data_dir)
    database.initialize()
    application = create_app(runtime_database=database)
    cloud_calls: list[str] = []

    def cloud_chat(*_args: object, **_kwargs: object) -> object:
        cloud_calls.append("chat")
        raise AssertionError("cloud chat must not be constructed")

    def cloud_embedding(*_args: object, **_kwargs: object) -> object:
        cloud_calls.append("embedding")
        raise AssertionError("cloud embedding must not be constructed")

    monkeypatch.setattr("reponpc.main.app", application)  # type: ignore[attr-defined]
    monkeypatch.setattr("reponpc.main.OpenAICompatibleChatProvider", cloud_chat)  # type: ignore[attr-defined]
    monkeypatch.setattr("reponpc.main.OpenAICompatibleEmbeddingProvider", cloud_embedding)  # type: ignore[attr-defined]

    _configure_provider_lifecycle(settings, database)

    assert cloud_calls == []
    assert application.state.provider_adapter == "ollama"
    assert application.state.provider_runtime.chat.__class__.__name__ == "OllamaChatProvider"
    assert (
        application.state.provider_runtime.embedding.__class__.__name__ == "OllamaEmbeddingProvider"
    )
    assert application.state.chat_service is None
    assert application.state.max_message_characters == 8
    assert application.state.max_history_messages == 2
    assert application.state.max_history_characters == 12


def test_production_assembly_maps_vllm_to_private_openai_compatible_transport(
    tmp_path: Path, monkeypatch: object
) -> None:
    settings = load_environment(
        {
            "REPONPC_DATA_DIR": str(tmp_path),
            "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
            "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
            "REPONPC_INDEX_MANIFEST_URL": "https://raw.githubusercontent.com/example/portfolio/main/stable-manifest.json",
            "REPONPC_CHAT_PROVIDER": "vllm",
            "REPONPC_CHAT_MODEL": "fixture-chat",
            "REPONPC_CHAT_BASE_URL": "http://127.0.0.1:8000/v1",
            "REPONPC_CHAT_API_KEY": "VLLM_CHAT_KEY_CANARY",
            "REPONPC_EMBEDDING_PROVIDER": "vllm",
            "REPONPC_EMBEDDING_MODEL": "fixture-embed",
            "REPONPC_EMBEDDING_BASE_URL": "http://127.0.0.1:8001/v1",
            "REPONPC_EMBEDDING_API_KEY": "VLLM_EMBEDDING_KEY_CANARY",
            "REPONPC_EMBEDDING_DIMENSION": "2",
        },
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(settings.data_dir)
    database.initialize()
    application = create_app(runtime_database=database)

    def forbidden_ollama(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("vLLM must not construct an Ollama adapter")

    monkeypatch.setattr("reponpc.main.app", application)  # type: ignore[attr-defined]
    monkeypatch.setattr("reponpc.main.OllamaChatProvider", forbidden_ollama)  # type: ignore[attr-defined]
    monkeypatch.setattr("reponpc.main.OllamaEmbeddingProvider", forbidden_ollama)  # type: ignore[attr-defined]
    _configure_provider_lifecycle(settings, database)

    assert application.state.provider_adapter == "openai_compatible"
    assert isinstance(application.state.provider_runtime.chat, OpenAICompatibleChatProvider)
    assert isinstance(
        application.state.provider_runtime.embedding,
        OpenAICompatibleEmbeddingProvider,
    )
    assert application.state.provider_runtime.chat._origin.allow_private_http is True
    assert application.state.provider_runtime.embedding.identity().adapter == "openai_compatible"
    assert (
        application.state.provider_runtime.chat._origin.endpoint("chat/completions")
        == "http://127.0.0.1:8000/v1/chat/completions"
    )
    assert (
        application.state.provider_runtime.embedding._origin.endpoint("embeddings")
        == "http://127.0.0.1:8001/v1/embeddings"
    )
    rendered = repr(settings) + repr(application.state.provider_runtime.chat)
    assert "VLLM_CHAT_KEY_CANARY" not in rendered
    assert "VLLM_EMBEDDING_KEY_CANARY" not in rendered


def test_environment_connection_resolves_changed_model_from_frozen_profile(
    tmp_path: Path,
) -> None:
    settings = load_environment(
        {
            "REPONPC_DATA_DIR": str(tmp_path / "data"),
            "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
            "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
            "REPONPC_INDEX_MANIFEST_URL": "https://raw.githubusercontent.com/example/portfolio/main/stable-manifest.json",
            "REPONPC_CHAT_PROVIDER": "ollama",
            "REPONPC_CHAT_MODEL": "fixture-chat",
            "REPONPC_CHAT_BASE_URL": "http://127.0.0.1:11434",
            "REPONPC_EMBEDDING_PROVIDER": "ollama",
            "REPONPC_EMBEDDING_MODEL": "initial-model",
            "REPONPC_EMBEDDING_BASE_URL": "http://127.0.0.1:11434",
            "REPONPC_EMBEDDING_DIMENSION": "2",
        },
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: None,
        activation_compatible=lambda _profile: False,
    )
    profile = registry.create(
        EmbeddingProfileInput(
            provider="ollama",
            model_id="replacement-model",
            dimension=2,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
            connection_reference="environment",
        )
    )

    provider = _environment_embedding_provider(settings, profile)

    assert provider is not None
    assert provider.identity() == profile.identity
    assert provider.__class__.__name__ == "OllamaEmbeddingProvider"
