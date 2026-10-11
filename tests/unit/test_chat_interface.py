"""Explicit interface survives revisioning, old ciphertext, migration and backup."""

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from reponpc.admin.model_connections import (
    ModelConnectionError,
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.config.environment import load_environment
from reponpc.main import _chat_provider_from_connection
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider
from reponpc.providers.openai_responses import OpenAIResponsesChatProvider
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase
from tests.contract.test_environment import deployment_environment


def test_migration_legacy_ciphertext_and_revision_protocol_are_preserved(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize(migrations=MIGRATIONS[:-1])
    database.initialize()
    store = ProtectedModelSecretStore(tmp_path / "model.key")
    old = Fernet(store.current_key()).encrypt(
        json.dumps(
            {"base_url": "https://api.example.test/v1", "api_key": "TEST_KEY_CANARY"}
        ).encode()
    )
    assert store.decrypt(old).chat_api == "chat_completions"
    registry = ModelConnectionRegistry(database, store)
    first = registry.create(
        ModelConnectionInput("API", "openai_compatible", "https://api.example.test/v1")
    )
    second = registry.update(
        first.connection_id,
        ModelConnectionInput(
            "API", "openai_compatible", None, endpoint_action="retain", chat_api="responses"
        ),
    )
    assert second.revision == 2 and second.safe_dict()["chat_api"] == "responses"
    assert registry.revision_for(first.connection_id, 1).secret.chat_api == "chat_completions"
    assert registry.revision_for(first.connection_id, 2).secret.chat_api == "responses"
    retained = registry.update(
        first.connection_id,
        ModelConnectionInput("Renamed", "openai_compatible", None, endpoint_action="retain"),
    )
    assert retained.revision == 2 and retained.chat_api == "responses"
    registry.rotate_key()
    assert registry.secret_for(first.connection_id, 2).chat_api == "responses"
    backup = database.backup_to(tmp_path / "backup.sqlite")
    assert backup.is_file()
    database.check_integrity()


def test_explicit_factory_does_not_switch_legacy_or_other_provider() -> None:
    settings = load_environment(deployment_environment())
    legacy = _chat_provider_from_connection(
        settings, "openai_compatible", "owner-chosen", "https://api.example.test/v1", None
    )
    summary = _chat_provider_from_connection(
        settings,
        "openai_compatible",
        "owner-chosen",
        "https://api.example.test/v1",
        None,
        chat_api="responses",
    )
    assert type(legacy) is OpenAICompatibleChatProvider
    assert type(summary) is OpenAIResponsesChatProvider
    with pytest.raises(ValueError):
        _chat_provider_from_connection(
            settings, "vllm", "owner-chosen", "http://localhost:8000/v1", None, chat_api="responses"
        )


@pytest.mark.parametrize("provider", ["ollama", "vllm"])
def test_native_connections_reject_responses(provider: str) -> None:
    with pytest.raises(ModelConnectionError):
        ModelConnectionInput(
            "Native", provider, "http://localhost:8000", chat_api="responses"
        ).validate()
