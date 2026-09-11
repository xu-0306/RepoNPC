from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from reponpc.admin.chat_profiles import (
    ChatProfile,
    ChatProfileError,
    ChatProfileInput,
    ChatProfileRegistry,
)
from reponpc.admin.model_connections import (
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.providers.contracts import ProviderResult
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class _ProbeProvider:
    def generate(self, *_args: object, **_kwargs: object) -> ProviderResult:
        return ProviderResult('{"ok":true}', "stop", None, None, 1.0)


def _registries(tmp_path: Path) -> tuple[ModelConnectionRegistry, ChatProfileRegistry]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(tmp_path / "secrets" / "model.key"),
    )
    profiles = ChatProfileRegistry(database, connections, lambda _profile: _ProbeProvider())
    return connections, profiles


def _connection_input(*, api_key: str = "chat-key-canary") -> ModelConnectionInput:
    return ModelConnectionInput(
        display_name="Chat gateway",
        provider="openai_compatible",
        base_url="https://chat.example.test/v1",
        api_key=api_key,
        credential_action="replace",
    )


def test_chat_profiles_require_probe_and_freeze_the_connection_revision(tmp_path: Path) -> None:
    connections, profiles = _registries(tmp_path)
    connection = connections.create(_connection_input())
    profile = profiles.create(ChatProfileInput(connection.connection_id, "chat-model"))

    with pytest.raises(ChatProfileError) as required:
        profiles.activate(profile.profile_id)
    assert required.value.code == "CHAT_PROBE_REQUIRED"

    probed = profiles.probe(profile.profile_id)
    assert probed.status == "ready"
    assert probed.observed_model_id == "chat-model"

    active = profiles.activate(profile.profile_id)
    assert active.active is True
    assert active.connection_revision == 1

    replacement = profiles.create(ChatProfileInput(connection.connection_id, "replacement"))
    profiles.probe(replacement.profile_id)
    connections.update(
        connection.connection_id,
        _connection_input(api_key="rotated-chat-key-canary"),
    )
    with pytest.raises(ChatProfileError) as stale:
        profiles.activate(replacement.profile_id)
    assert stale.value.code == "CHAT_PROFILE_STALE"
    assert profiles.active().profile_id == profile.profile_id  # type: ignore[union-attr]


def test_failed_runtime_switch_rolls_back_database_and_restores_previous_runtime(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(tmp_path / "secrets" / "model.key"),
    )
    active_models: list[str] = []

    def switch_runtime(profile: ChatProfile, _provider: object) -> None:
        model_id = profile.model_id
        active_models.append(model_id)
        if model_id == "replacement":
            raise RuntimeError("synthetic runtime failure")

    profiles = ChatProfileRegistry(
        database,
        connections,
        lambda _profile: _ProbeProvider(),
        on_activated=switch_runtime,
    )
    connection = connections.create(_connection_input())
    original = profiles.create(ChatProfileInput(connection.connection_id, "original"))
    replacement = profiles.create(ChatProfileInput(connection.connection_id, "replacement"))
    profiles.probe(original.profile_id)
    profiles.activate(original.profile_id)
    profiles.probe(replacement.profile_id)

    with pytest.raises(ChatProfileError) as raised:
        profiles.activate(replacement.profile_id)

    assert raised.value.code == "CHAT_RUNTIME_SWITCH_FAILED"
    assert profiles.active().profile_id == original.profile_id  # type: ignore[union-attr]
    assert active_models == ["original", "replacement", "original"]


def test_database_commit_failure_restores_previous_runtime_and_active_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    connections = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(tmp_path / "secrets" / "model.key"),
    )
    active_models: list[str] = []

    def switch_runtime(profile: ChatProfile, _provider: object) -> None:
        active_models.append(profile.model_id)

    profiles = ChatProfileRegistry(
        database,
        connections,
        lambda _profile: _ProbeProvider(),
        on_activated=switch_runtime,
    )
    connection = connections.create(_connection_input())
    original = profiles.create(ChatProfileInput(connection.connection_id, "original"))
    replacement = profiles.create(ChatProfileInput(connection.connection_id, "replacement"))
    profiles.probe(original.profile_id)
    profiles.activate(original.profile_id)
    profiles.probe(replacement.profile_id)
    open_connection = database.connection

    class FailingCommitConnection:
        def __init__(self, delegate: sqlite3.Connection) -> None:
            self.delegate = delegate

        @property
        def in_transaction(self) -> bool:
            return self.delegate.in_transaction

        def execute(
            self, statement: str, parameters: tuple[object, ...] = ()
        ) -> sqlite3.Cursor:
            if statement == "COMMIT":
                raise sqlite3.OperationalError("synthetic commit failure")
            return self.delegate.execute(statement, parameters)

    @contextmanager
    def failing_connection() -> Iterator[FailingCommitConnection]:
        with open_connection() as delegate:
            yield FailingCommitConnection(delegate)

    monkeypatch.setattr(database, "connection", failing_connection)

    with pytest.raises(RuntimeDatabaseError) as raised:
        profiles.activate(replacement.profile_id)

    monkeypatch.undo()
    assert raised.value.code == "runtime_chat_profile_failed"
    assert profiles.active().profile_id == original.profile_id  # type: ignore[union-attr]
    assert active_models == ["original", "replacement", "original"]

    clean_database = RuntimeDatabase(tmp_path / "clean-runtime")
    clean_database.initialize()
    clean_connections = ModelConnectionRegistry(
        clean_database,
        ProtectedModelSecretStore(tmp_path / "clean-secrets" / "model.key"),
    )
    runtime_model = ["bootstrap"]

    def switch_first_runtime(
        profile: ChatProfile, _provider: object
    ) -> Callable[[], None]:
        prior = runtime_model[0]
        runtime_model[0] = profile.model_id
        return lambda: runtime_model.__setitem__(0, prior)

    clean_profiles = ChatProfileRegistry(
        clean_database,
        clean_connections,
        lambda _profile: _ProbeProvider(),
        on_activated=switch_first_runtime,
    )
    clean_connection = clean_connections.create(_connection_input())
    first = clean_profiles.create(ChatProfileInput(clean_connection.connection_id, "first"))
    clean_profiles.probe(first.profile_id)
    clean_open_connection = clean_database.connection

    @contextmanager
    def clean_failing_connection() -> Iterator[FailingCommitConnection]:
        with clean_open_connection() as delegate:
            yield FailingCommitConnection(delegate)

    monkeypatch.setattr(clean_database, "connection", clean_failing_connection)

    with pytest.raises(RuntimeDatabaseError):
        clean_profiles.activate(first.profile_id)

    monkeypatch.undo()
    assert clean_profiles.active() is None
    assert runtime_model == ["bootstrap"]
