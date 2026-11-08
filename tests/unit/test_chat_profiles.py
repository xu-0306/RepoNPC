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
from reponpc.providers.contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderResult,
)
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class _ProbeProvider:
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 8192, 1024)

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


@pytest.mark.parametrize(
    "preparation,completion",
    [(5.0, 5.0), (5.0, 25.0), (5.0, 59.0), (5.0, 60.0), (5.0, 65.0), (61.0, 61.0)],
)
def test_probe_preparation_consumes_original_sixty_second_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preparation: float,
    completion: float,
) -> None:
    connections, profiles = _registries(tmp_path)
    connection = connections.create(_connection_input())
    profile = profiles.create(ChatProfileInput(connection.connection_id, "arbitrary-model"))
    budgets: list[float] = []

    class PreparedProbe(_ProbeProvider):
        def generate(self, *_args: object, **kwargs: object) -> ProviderResult:
            budgets.append(float(kwargs["timeout"]))  # type: ignore[arg-type]
            return super().generate()

    profiles._provider_resolver = lambda _profile: PreparedProbe()
    ticks = iter([0.0, preparation, completion])
    monkeypatch.setattr("reponpc.admin.chat_profiles.time.monotonic", lambda: next(ticks))
    result = profiles.probe(profile.profile_id)
    if completion < 60:
        assert result.status == "ready"
        assert budgets == [55.0]
    else:
        assert result.status == "probe_failed"
        assert result.last_error_code == "PROVIDER_TIMEOUT"
        assert budgets == ([] if preparation >= 60 else [55.0])


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
    rebound = profiles.get(replacement.profile_id)
    assert rebound.connection_revision == 2
    assert rebound.status == "probe"
    assert rebound.observed_model_id is None

    with pytest.raises(ChatProfileError) as stale:
        profiles.activate(replacement.profile_id)
    assert stale.value.code == "CHAT_PROBE_REQUIRED"
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

        def execute(self, statement: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
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

    def switch_first_runtime(profile: ChatProfile, _provider: object) -> Callable[[], None]:
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


def test_probe_wall_clock_can_exceed_budget_outside_provider_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connections, profiles = _registries(tmp_path)
    connection = connections.create(_connection_input())
    profile = profiles.create(ChatProfileInput(connection.connection_id, "fixture-model"))
    elapsed = 0.0
    budgets: list[float] = []
    original_get = profiles.get

    def delayed_lookup(profile_id: str) -> ChatProfile:
        nonlocal elapsed
        elapsed += 7.0 if elapsed == 0.0 else 8.0
        return original_get(profile_id)

    class TimedProbe(_ProbeProvider):
        def generate(self, *_args: object, **kwargs: object) -> ProviderResult:
            nonlocal elapsed
            budgets.append(float(kwargs["timeout"]))  # type: ignore[arg-type]
            elapsed += 55.0
            return super().generate()

    monkeypatch.setattr(profiles, "get", delayed_lookup)
    monkeypatch.setattr(profiles, "_provider_resolver", lambda _profile: TimedProbe())
    monkeypatch.setattr("reponpc.admin.chat_profiles.time.monotonic", lambda: elapsed)

    result = profiles.probe(profile.profile_id)

    assert result.status == "ready"
    assert result.last_error_code is None
    assert budgets == [60.0]
    assert elapsed == 70.0


class _Interfaces:
    """Resolver double: each named interface either answers or fails the way a service would."""

    def __init__(self, outcomes: dict[str, ProviderError | None]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def __call__(self, _profile: ChatProfile, interface: str) -> object:
        self.calls.append(interface)
        outcome = self.outcomes[interface]

        class Provider(_ProbeProvider):
            def generate(self, *_args: object, **_kwargs: object) -> ProviderResult:
                if outcome is not None:
                    raise outcome
                return super().generate()

        return Provider()


def _detecting(
    tmp_path: Path, outcomes: dict[str, ProviderError | None]
) -> tuple[ModelConnectionRegistry, ChatProfileRegistry, _Interfaces, ChatProfile]:
    connections, profiles = _registries(tmp_path)
    interfaces = _Interfaces(outcomes)
    profiles._interface_resolver = interfaces  # type: ignore[assignment]
    connection = connections.create(_connection_input())
    profile = profiles.create(ChatProfileInput(connection.connection_id, "arbitrary-model"))
    return connections, profiles, interfaces, profile


def test_probe_detects_responses_and_saves_it_on_the_connection(tmp_path: Path) -> None:
    connections, profiles, interfaces, profile = _detecting(
        tmp_path, {"responses": None, "chat_completions": None}
    )
    result = profiles.probe(profile.profile_id)
    assert result.status == "ready" and result.last_error_code is None
    assert interfaces.calls == ["responses"]
    connection = connections.get(profile.connection_id)
    assert connection.chat_api == "responses"
    # The new revision carries the profile, so the passed test stays usable.
    assert result.connection_revision == connection.revision == 2
    assert connections.secret_for(connection.connection_id).chat_api == "responses"


def test_probe_uses_chat_completions_when_the_service_refuses_responses(tmp_path: Path) -> None:
    connections, profiles, interfaces, profile = _detecting(
        tmp_path,
        {
            "responses": ProviderError(ProviderFailureCode.INVALID_RESPONSE),
            "chat_completions": None,
        },
    )
    result = profiles.probe(profile.profile_id)
    assert result.status == "ready"
    assert interfaces.calls == ["responses", "chat_completions"]
    connection = connections.get(profile.connection_id)
    assert connection.chat_api == "chat_completions" and connection.revision == 1


@pytest.mark.parametrize(
    "failure",
    [
        ProviderFailureCode.AUTHENTICATION,
        ProviderFailureCode.RATE_LIMIT,
        ProviderFailureCode.TIMEOUT,
        ProviderFailureCode.UNAVAILABLE,
    ],
)
def test_probe_does_not_switch_interface_after_a_failure_that_is_not_about_the_interface(
    tmp_path: Path, failure: ProviderFailureCode
) -> None:
    connections, profiles, interfaces, profile = _detecting(
        tmp_path, {"responses": ProviderError(failure), "chat_completions": None}
    )
    result = profiles.probe(profile.profile_id)
    assert result.status == "probe_failed" and result.last_error_code
    assert interfaces.calls == ["responses"]
    assert connections.get(profile.connection_id).chat_api == "chat_completions"


def test_probe_reports_the_last_failure_when_neither_interface_works(tmp_path: Path) -> None:
    connections, profiles, interfaces, profile = _detecting(
        tmp_path,
        {
            "responses": ProviderError(ProviderFailureCode.INVALID_RESPONSE),
            "chat_completions": ProviderError(ProviderFailureCode.AUTHENTICATION),
        },
    )
    result = profiles.probe(profile.profile_id)
    assert result.status == "probe_failed"
    assert interfaces.calls == ["responses", "chat_completions"]
    assert connections.get(profile.connection_id).revision == 1


def test_probe_keeps_the_interface_of_an_active_profile(tmp_path: Path) -> None:
    connections, profiles, interfaces, profile = _detecting(
        tmp_path, {"responses": None, "chat_completions": None}
    )
    with profiles._database.connection() as database:
        database.execute(
            "UPDATE chat_profiles SET active = 1, status = 'ready' WHERE profile_id = ?",
            (profile.profile_id,),
        )
    result = profiles.probe(profile.profile_id)
    assert result.status == "ready"
    assert interfaces.calls == []
    assert connections.get(profile.connection_id).chat_api == "chat_completions"


def test_probe_does_not_detect_for_services_without_two_interfaces(tmp_path: Path) -> None:
    connections, profiles = _registries(tmp_path)
    interfaces = _Interfaces({"responses": None, "chat_completions": None})
    profiles._interface_resolver = interfaces  # type: ignore[assignment]
    connection = connections.create(
        ModelConnectionInput(
            display_name="Local",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
        )
    )
    profile = profiles.create(ChatProfileInput(connection.connection_id, "arbitrary-model"))
    assert profiles.probe(profile.profile_id).status == "ready"
    assert interfaces.calls == []
