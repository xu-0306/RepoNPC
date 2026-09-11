from __future__ import annotations

import socket
from pathlib import Path

import pytest

from reponpc.admin.model_connections import (
    ModelConnectionError,
    ModelConnectionInput,
    ModelConnectionRegistry,
    ModelConnectionSecret,
    ModelSecretStoreError,
    ProtectedModelSecretStore,
    validate_provider_base_url,
    validate_resolved_provider_addresses,
)
from reponpc.providers.contracts import ProviderError, ProviderFailureCode
from reponpc.providers.http_transport import UrllibProviderHttpTransport
from reponpc.runtime.database import RuntimeDatabase

CANARY_KEY = "MODEL_KEY_CANARY_7f35"
CANARY_URL = "https://gateway.example.test/v1"


def _registry(tmp_path: Path) -> tuple[ModelConnectionRegistry, RuntimeDatabase]:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = ProtectedModelSecretStore(tmp_path / "secrets" / "model.key")
    return ModelConnectionRegistry(database, store), database


def _values(
    *,
    url: str = CANARY_URL,
    key: str | None = CANARY_KEY,
    action: str = "replace",
) -> ModelConnectionInput:
    return ModelConnectionInput(
        display_name="Primary gateway",
        provider="openai_compatible",
        base_url=url,
        api_key=key,
        credential_action=action,
    )


def test_create_update_and_remove_are_revisioned_and_write_only(tmp_path: Path) -> None:
    registry, database = _registry(tmp_path)

    created = registry.create(_values())
    assert created.revision == 1
    assert created.key_configured is True
    assert CANARY_KEY not in repr(created)
    assert CANARY_KEY not in str(created.safe_dict())
    assert CANARY_URL not in str(created.safe_dict())
    assert registry.secret_for(created.connection_id).api_key == CANARY_KEY

    with pytest.raises(ModelConnectionError) as changed_destination:
        registry.update(
            created.connection_id,
            _values(url="https://other.example.test/v1", key=None, action="retain"),
        )
    assert changed_destination.value.code == "CREDENTIAL_REPLACE_REQUIRED"

    updated = registry.update(
        created.connection_id,
        _values(url="https://other.example.test/v1", key="NEW_KEY_CANARY"),
    )
    assert updated.revision == 2
    assert registry.secret_for(updated.connection_id, 1).api_key == CANARY_KEY
    assert registry.secret_for(updated.connection_id, 2).api_key == "NEW_KEY_CANARY"

    removed = registry.update(
        updated.connection_id,
        _values(url="https://other.example.test/v1", key=None, action="remove"),
    )
    assert removed.revision == 3
    assert removed.key_configured is False
    assert registry.secret_for(removed.connection_id).api_key is None

    with database.connection() as connection:
        ciphertext = connection.execute(
            "SELECT ciphertext FROM model_connection_secrets WHERE connection_id = ?",
            (created.connection_id,),
        ).fetchall()
    assert all(CANARY_KEY.encode() not in bytes(row[0]) for row in ciphertext)


def test_corrupt_secret_fails_closed_and_rotation_preserves_all_revisions(tmp_path: Path) -> None:
    registry, database = _registry(tmp_path)
    connection = registry.create(_values())
    registry.update(
        connection.connection_id,
        _values(url=CANARY_URL, key="SECOND_KEY_CANARY"),
    )
    store_key = tmp_path / "secrets" / "model.key"
    before_rotation = store_key.read_bytes()
    registry.rotate_key()
    assert store_key.read_bytes() != before_rotation
    assert registry.secret_for(connection.connection_id, 1).api_key == CANARY_KEY
    assert registry.secret_for(connection.connection_id, 2).api_key == "SECOND_KEY_CANARY"

    with database.connection() as db_connection:
        db_connection.execute(
            "UPDATE model_connection_secrets SET ciphertext = ? "
            "WHERE connection_id = ? AND revision = 1",
            (b"corrupt", connection.connection_id),
        )
    key_before_failed_rotation = store_key.read_bytes()
    with pytest.raises(ModelConnectionError) as raised:
        registry.rotate_key()
    assert raised.value.code == "MODEL_SECRET_STORAGE_UNAVAILABLE"
    assert store_key.read_bytes() == key_before_failed_rotation


def test_missing_master_key_does_not_create_a_replacement_during_decryption(
    tmp_path: Path,
) -> None:
    key_path = tmp_path / "secrets" / "model.key"
    store = ProtectedModelSecretStore(key_path)
    ciphertext = store.encrypt(ModelConnectionSecret(CANARY_URL, CANARY_KEY))
    original_key = key_path.read_bytes()
    key_path.unlink()

    with pytest.raises(ModelSecretStoreError) as raised:
        store.decrypt(ciphertext)

    assert raised.value.code == "MODEL_SECRET_STORAGE_UNAVAILABLE"
    assert not key_path.exists()
    store.install_key(original_key)
    assert store.decrypt(ciphertext).api_key == CANARY_KEY


def test_missing_master_key_blocks_credential_replacement_without_new_revision(
    tmp_path: Path,
) -> None:
    registry, _database = _registry(tmp_path)
    connection = registry.create(_values())
    key_path = tmp_path / "secrets" / "model.key"
    original_key = key_path.read_bytes()
    key_path.unlink()

    with pytest.raises(ModelConnectionError) as raised:
        registry.update(
            connection.connection_id,
            _values(key="replacement-key-canary"),
        )

    assert raised.value.code == "MODEL_SECRET_STORAGE_UNAVAILABLE"
    assert not key_path.exists()
    assert registry.get(connection.connection_id).revision == 1
    ProtectedModelSecretStore(key_path).install_key(original_key)
    assert registry.secret_for(connection.connection_id, 1).api_key == CANARY_KEY


def test_connection_delete_rejects_any_profile_reference(tmp_path: Path) -> None:
    registry, database = _registry(tmp_path)
    connection = registry.create(_values())
    with database.connection() as db_connection:
        db_connection.execute(
            "INSERT INTO chat_profiles("
            "profile_id, connection_id, connection_revision, model_id, status, active, "
            "created_at, updated_at"
            ") VALUES ('chat-1', ?, 1, 'chat-model', 'probe', 0, 'now', 'now')",
            (connection.connection_id,),
        )

    with pytest.raises(ModelConnectionError) as raised:
        registry.delete(connection.connection_id)
    assert raised.value.code == "MODEL_CONNECTION_IN_USE"
    assert registry.get(connection.connection_id).connection_id == connection.connection_id


@pytest.mark.parametrize(
    "url",
    (
        "ftp://gateway.example.test",
        "https://user:password@gateway.example.test",
        "https://gateway.example.test?token=canary",
        "https://gateway.example.test/../admin",
        "https://gateway.example.test/%2e%2e/admin",
        "https://gateway.example.test/model name",
        "http://gateway.example.test",
    ),
)
def test_provider_url_policy_rejects_unsafe_or_public_http(url: str) -> None:
    with pytest.raises(ModelConnectionError):
        validate_provider_base_url(url, provider="openai_compatible")


def test_provider_url_policy_allows_explicit_private_http() -> None:
    validate_provider_base_url("http://127.0.0.1:11434/api", provider="ollama")


def test_resolved_provider_addresses_reject_forbidden_classes() -> None:
    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    with pytest.raises(ModelConnectionError) as raised:
        validate_resolved_provider_addresses("gateway.example.test", resolver=resolver)
    assert raised.value.code == "PROVIDER_NETWORK_BLOCKED"

    def mapped_metadata(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("::ffff:169.254.169.254", 443, 0, 0),
            )
        ]

    with pytest.raises(ModelConnectionError):
        validate_resolved_provider_addresses("gateway.example.test", resolver=mapped_metadata)


def test_resolved_provider_addresses_returns_normalized_addresses() -> None:
    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        ]

    assert validate_resolved_provider_addresses("gateway.example.test", resolver=resolver) == (
        "2001:db8::1",
        "8.8.8.8",
    )


@pytest.mark.parametrize(
    ("hostname", "address"),
    (
        ("169.254.169.254", "169.254.169.254"),
        ("gateway.example.test", "127.0.0.1"),
        ("gateway.example.test", "::ffff:169.254.169.254"),
    ),
)
def test_provider_transport_blocks_forbidden_destinations_before_socket_connect(
    hostname: str,
    address: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr: tuple[object, ...] = (
        (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
    )

    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]

    reached_socket = False

    def forbidden_socket(*_args: object, **_kwargs: object) -> object:
        nonlocal reached_socket
        reached_socket = True
        raise AssertionError("forbidden destination reached socket construction")

    monkeypatch.setattr("reponpc.providers.http_transport.socket.socket", forbidden_socket)
    transport = UrllibProviderHttpTransport(resolver=resolver)

    with pytest.raises(ProviderError) as raised:
        transport.request(
            "POST",
            f"https://{hostname}/v1/chat/completions",
            headers={},
            body=b"{}",
            timeout=1,
        )

    assert raised.value.code == ProviderFailureCode.UNAVAILABLE
    assert reached_socket is False


def test_provider_stream_blocks_forbidden_destination_before_socket_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolver(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    reached_socket = False

    def forbidden_socket(*_args: object, **_kwargs: object) -> object:
        nonlocal reached_socket
        reached_socket = True
        raise AssertionError("forbidden destination reached socket construction")

    monkeypatch.setattr("reponpc.providers.http_transport.socket.socket", forbidden_socket)

    with pytest.raises(ProviderError):
        UrllibProviderHttpTransport(resolver=resolver).stream_lines(
            "POST",
            "https://169.254.169.254/api/chat",
            headers={},
            body=b"{}",
            timeout=1,
            cancelled=lambda: False,
            on_line=lambda _line: None,
        )

    assert reached_socket is False


def test_secret_repr_is_redacted() -> None:
    secret = ModelConnectionSecret(CANARY_URL, CANARY_KEY)
    assert repr(secret) == "ModelConnectionSecret(<redacted>)"
    assert CANARY_KEY not in repr(secret)
