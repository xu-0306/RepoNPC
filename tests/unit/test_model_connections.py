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


def test_same_provider_origin_path_change_retains_protected_key(tmp_path: Path) -> None:
    registry, _database = _registry(tmp_path)
    created = registry.create(_values(url="https://gateway.example.test"))

    updated = registry.update(
        created.connection_id,
        _values(
            url="https://GATEWAY.example.test:443/v1",
            key=None,
            action="retain",
        ),
    )

    assert updated.revision == 2
    secret = registry.secret_for(updated.connection_id)
    assert secret.base_url == "https://GATEWAY.example.test:443/v1"
    assert secret.api_key == CANARY_KEY


@pytest.mark.parametrize(
    "provider,url",
    (
        ("vllm", "https://gateway.example.test/v1"),
        ("openai_compatible", "https://gateway.example.test:8443/v1"),
        ("openai_compatible", "https://other.example.test/v1"),
    ),
)
def test_provider_or_origin_change_cannot_retain_protected_key(
    tmp_path: Path, provider: str, url: str
) -> None:
    registry, _database = _registry(tmp_path)
    created = registry.create(_values(url="https://gateway.example.test"))

    with pytest.raises(ModelConnectionError) as raised:
        registry.update(
            created.connection_id,
            ModelConnectionInput(
                display_name="Primary gateway",
                provider=provider,
                base_url=url,
                credential_action="retain",
            ),
        )

    assert raised.value.code == "CREDENTIAL_REPLACE_REQUIRED"
    assert registry.get(created.connection_id) == created


def test_effective_update_rebinds_only_safe_candidates_and_invalidates_selection(
    tmp_path: Path,
) -> None:
    registry, database = _registry(tmp_path)
    model_connection = registry.create(_values())
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_profiles(
              profile_id, connection_id, connection_revision, model_id, status, active,
              observed_model_id, last_error_code, last_error_message, created_at,
              updated_at, last_probed_at
            ) VALUES
              ('chat-candidate', ?, 1, 'chat-model', 'probe_failed', 0,
               'old-chat', 'PROVIDER_TIMEOUT', 'old error', 'now', 'now', 'now'),
              ('chat-active', ?, 1, 'active-chat', 'ready', 1,
               'active-chat', NULL, NULL, 'now', 'now', 'now'),
              ('chat-previous', ?, 1, 'previous-chat', 'last_known_good', 0,
               'previous-chat', NULL, NULL, 'now', 'now', 'now')
            """,
            (model_connection.connection_id,) * 3,
        )
        connection.execute(
            """
            INSERT INTO embedding_profiles(
              profile_id, provider, model_id, dimension, normalized, query_prefix,
              passage_prefix, connection_reference, connection_revision, status, active,
              observed_adapter, observed_model_id, observed_dimension, last_error_code,
              last_error_message, created_at, updated_at, last_probed_at
            ) VALUES
              ('embedding-candidate', 'openai_compatible', 'embed-model', 1536, 1, '', '',
               ?, 1, 'probe_failed', 0, 'openai_compatible', 'embed-model', 1536,
               'PROVIDER_TIMEOUT', 'old error', 'now', 'now', 'now'),
              ('embedding-active', 'openai_compatible', 'active-embed', 1536, 1, '', '',
               ?, 1, 'ready', 1, 'openai_compatible', 'active-embed', 1536,
               NULL, NULL, 'now', 'now', 'now'),
              ('embedding-reindexing', 'openai_compatible', 'building-embed', 1536, 1, '', '',
               ?, 1, 'reindexing', 0, 'openai_compatible', 'building-embed', 1536,
               NULL, NULL, 'now', 'now', 'now'),
              ('embedding-previous', 'openai_compatible', 'previous-embed', 1536, 1, '', '',
               ?, 1, 'last_known_good', 0, 'openai_compatible', 'previous-embed', 1536,
               NULL, NULL, 'now', 'now', 'now')
            """,
            (model_connection.connection_id,) * 4,
        )
        connection.execute(
            """
            UPDATE analysis_model_selection SET
              chat_profile_id = 'chat-candidate', chat_connection_revision = 1,
              embedding_profile_id = 'embedding-candidate',
              embedding_connection_revision = 1, selection_generation = 7,
              updated_at = 'now'
            WHERE selection_key = 'current'
            """
        )

    updated = registry.update(
        model_connection.connection_id,
        ModelConnectionInput(
            display_name="Local Ollama",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            credential_action="remove",
        ),
    )

    assert updated.revision == 2
    assert registry.revision_for(updated.connection_id, 1).provider == "openai_compatible"
    assert registry.revision_for(updated.connection_id, 2).provider == "ollama"
    with database.connection() as connection:
        chat_rows = {
            row["profile_id"]: row
            for row in connection.execute("SELECT * FROM chat_profiles").fetchall()
        }
        embedding_rows = {
            row["profile_id"]: row
            for row in connection.execute("SELECT * FROM embedding_profiles").fetchall()
        }
        selection = connection.execute(
            "SELECT * FROM analysis_model_selection WHERE selection_key = 'current'"
        ).fetchone()

    candidate = chat_rows["chat-candidate"]
    assert (candidate["connection_revision"], candidate["status"]) == (2, "probe")
    assert candidate["observed_model_id"] is None
    assert candidate["last_error_code"] is None
    assert candidate["last_error_message"] is None
    assert candidate["last_probed_at"] is None
    assert chat_rows["chat-active"]["connection_revision"] == 1
    assert chat_rows["chat-previous"]["connection_revision"] == 1

    embedding_candidate = embedding_rows["embedding-candidate"]
    assert (
        embedding_candidate["provider"],
        embedding_candidate["connection_revision"],
        embedding_candidate["status"],
    ) == ("ollama", 2, "reindex_required")
    assert embedding_candidate["observed_adapter"] is None
    assert embedding_candidate["observed_model_id"] is None
    assert embedding_candidate["observed_dimension"] is None
    assert embedding_candidate["last_error_code"] is None
    assert embedding_candidate["last_error_message"] is None
    assert embedding_candidate["last_probed_at"] is None
    assert embedding_rows["embedding-active"]["connection_revision"] == 1
    assert embedding_rows["embedding-reindexing"]["connection_revision"] == 1
    assert embedding_rows["embedding-previous"]["connection_revision"] == 1

    assert selection is not None
    assert selection["selection_generation"] == 8
    assert selection["chat_connection_revision"] == 1
    assert selection["embedding_connection_revision"] == 1


def test_host_managed_refresh_rebinds_a_safe_environment_candidate(tmp_path: Path) -> None:
    registry, database = _registry(tmp_path)
    model_connection = registry.ensure_host_managed(
        "environment-embedding",
        display_name="Environment embedding",
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
    )
    assert model_connection is not None
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO embedding_profiles(
              profile_id, provider, model_id, dimension, normalized, query_prefix,
              passage_prefix, connection_reference, connection_revision, status, active,
              created_at, updated_at
            ) VALUES (
              'environment', 'ollama', 'qwen3-embedding:8b', NULL, 1, '', '',
              'environment-embedding', 1, 'probe_failed', 0, 'now', 'now'
            )
            """
        )

    refreshed = registry.ensure_host_managed(
        "environment-embedding",
        display_name="Environment embedding",
        provider="ollama",
        base_url="http://127.0.0.1:22434",
        api_key=None,
    )

    assert refreshed is not None and refreshed.revision == 2
    with database.connection() as connection:
        profile = connection.execute(
            "SELECT * FROM embedding_profiles WHERE profile_id = 'environment'"
        ).fetchone()
    assert profile is not None
    assert profile["connection_revision"] == 2
    assert profile["status"] == "reindex_required"
    assert profile["last_probed_at"] is None


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


def test_host_managed_connection_can_be_replaced_and_disabled_across_restart(
    tmp_path: Path,
) -> None:
    registry, database = _registry(tmp_path)
    created = registry.ensure_host_managed(
        "environment-chat",
        display_name="Environment chat",
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
    )
    assert created is not None and created.source == "host-managed"

    replaced = registry.update(
        created.connection_id,
        ModelConnectionInput(
            display_name="My Ollama",
            provider="ollama",
            base_url="http://127.0.0.1:22434",
            credential_action="retain",
        ),
    )
    assert replaced.source == "managed"
    assert replaced.revision == 2
    assert registry.secret_for(replaced.connection_id).base_url == "http://127.0.0.1:22434"
    assert (
        registry.ensure_host_managed(
            "environment-chat",
            display_name="Environment chat",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            api_key=None,
        )
        == replaced
    )

    registry.delete(replaced.connection_id)
    assert (
        registry.ensure_host_managed(
            "environment-chat",
            display_name="Environment chat",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            api_key=None,
        )
        is None
    )

    direct = registry.ensure_host_managed(
        "environment-embedding",
        display_name="Environment embedding",
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
    )
    assert direct is not None and direct.source == "host-managed"
    registry.delete(direct.connection_id)
    assert (
        registry.ensure_host_managed(
            "environment-embedding",
            display_name="Environment embedding",
            provider="ollama",
            base_url="http://127.0.0.1:11434",
            api_key=None,
        )
        is None
    )
    assert registry.list() == ()
    with database.connection() as connection:
        states = connection.execute(
            "SELECT connection_id, state FROM host_managed_connection_overrides "
            "ORDER BY connection_id"
        ).fetchall()
    assert [(row["connection_id"], row["state"]) for row in states] == [
        ("environment-chat", "disabled"),
        ("environment-embedding", "disabled"),
    ]


def test_host_managed_connection_requires_explicit_replacement_url(tmp_path: Path) -> None:
    registry, _database = _registry(tmp_path)
    created = registry.ensure_host_managed(
        "environment-chat",
        display_name="Environment chat",
        provider="ollama",
        base_url="http://127.0.0.1:11434",
        api_key=None,
    )
    assert created is not None

    with pytest.raises(ModelConnectionError) as raised:
        registry.update(
            created.connection_id,
            ModelConnectionInput(
                display_name="Renamed",
                provider="ollama",
                base_url=None,
                endpoint_action="retain",
                credential_action="retain",
            ),
        )

    assert raised.value.code == "HOST_CONNECTION_REPLACEMENT_REQUIRED"
    assert registry.get(created.connection_id) == created


def test_managed_no_key_destination_change_still_requires_explicit_intent(
    tmp_path: Path,
) -> None:
    registry, _database = _registry(tmp_path)
    created = registry.create(_values(key=None, action="retain"))

    with pytest.raises(ModelConnectionError) as raised:
        registry.update(
            created.connection_id,
            _values(url="https://other.example.test/v1", key=None, action="retain"),
        )

    assert raised.value.code == "CREDENTIAL_REPLACE_REQUIRED"
    assert registry.get(created.connection_id) == created


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
