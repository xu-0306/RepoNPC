from __future__ import annotations

import os
import stat
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

import reponpc.config.environment as environment
import reponpc.main as main
from reponpc.admin.embedding_profiles import EmbeddingProfileInput
from reponpc.admin.model_connections import (
    ModelConnectionInput,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.config.environment import (
    EnvironmentIssue,
    EnvironmentValidationError,
    SecretValue,
    load_environment,
)
from reponpc.runtime.database import RuntimeDatabase


def deployment_environment(**overrides: str) -> dict[str, str]:
    values = {
        "REPONPC_PUBLIC_BASE_URL": "https://portfolio.example.com",
        "REPONPC_CONFIG_REPOSITORY": "example/portfolio",
        "REPONPC_INDEX_MANIFEST_URL": "https://raw.githubusercontent.com/example/portfolio/main/stable-manifest.json",
        "REPONPC_CHAT_MODEL": "test-model",
        "REPONPC_CHAT_BASE_URL": "http://ollama:11434",
        "REPONPC_EMBEDDING_MODEL": "intfloat/multilingual-e5-small",
        "REPONPC_EMBEDDING_BASE_URL": "http://ollama:11434",
    }
    values.update(overrides)
    return values


def issue_codes(exc: EnvironmentValidationError) -> set[str]:
    return {issue.code for issue in exc.issues}


def test_load_environment_uses_typed_defaults_and_redacts_direct_secrets(tmp_path: Path) -> None:
    canary = "DIRECT_SECRET_CANARY_NEVER_RENDER"
    settings = load_environment(
        deployment_environment(
            REPONPC_PORT="8123",
            REPONPC_GITHUB_TOKEN=canary,
            REPONPC_IP_HASH_KEY="ip-hmac-canary",
        ),
        secret_roots=(tmp_path,),
    )

    assert settings.port == 8123
    assert settings.data_dir == Path("/var/lib/reponpc")
    assert settings.secrets["github_token"].reveal() == canary
    assert repr(settings.secrets["github_token"]) == "SecretValue(<redacted>)"
    assert canary not in repr(settings)
    assert canary not in str(settings.secrets["github_token"])


@pytest.mark.parametrize(
    ("host", "public_base_url"),
    [
        ("127.0.0.1", "http://localhost:8000"),
        ("::1", "http://[::1]:8000"),
        ("LOCALHOST", "http://LOCALHOST:8000"),
    ],
)
def test_deployment_profile_is_explicit_and_accepts_only_loopback_endpoints(
    tmp_path: Path,
    host: str,
    public_base_url: str,
) -> None:
    production = load_environment(deployment_environment(), secret_roots=(tmp_path,))
    assert production.deployment_profile == "production"

    loopback = load_environment(
        deployment_environment(
            REPONPC_DEPLOYMENT_PROFILE="loopback_evaluation",
            REPONPC_HOST=host,
            REPONPC_PUBLIC_BASE_URL=public_base_url,
        ),
        secret_roots=(tmp_path,),
    )
    assert loopback.deployment_profile == "loopback_evaluation"


@pytest.mark.parametrize(
    ("host", "public_base_url"),
    [
        ("0.0.0.0", "http://localhost:8000"),
        ("::", "http://[::1]:8000"),
        ("192.168.1.10", "http://localhost:8000"),
        ("localhost.evil.example", "http://localhost:8000"),
        ("127.0.0.1", "http://127.0.0.1.evil.example:8000"),
        ("127.0.0.1", "http://2130706433:8000"),
    ],
)
def test_loopback_profile_rejects_exposed_or_rebinding_shaped_endpoints(
    tmp_path: Path,
    host: str,
    public_base_url: str,
) -> None:
    with pytest.raises(EnvironmentValidationError) as exposed:
        load_environment(
            deployment_environment(
                REPONPC_DEPLOYMENT_PROFILE="loopback_evaluation",
                REPONPC_HOST=host,
                REPONPC_PUBLIC_BASE_URL=public_base_url,
            ),
            secret_roots=(tmp_path,),
        )
    assert "loopback_profile_exposed" in issue_codes(exposed.value)


@pytest.mark.parametrize("trusted_proxy_cidrs", ["127.0.0.1/32", "::1/128"])
def test_loopback_profile_rejects_all_trusted_proxy_interpretation(
    tmp_path: Path,
    trusted_proxy_cidrs: str,
) -> None:
    with pytest.raises(EnvironmentValidationError) as exposed:
        load_environment(
            deployment_environment(
                REPONPC_DEPLOYMENT_PROFILE="loopback_evaluation",
                REPONPC_HOST="127.0.0.1",
                REPONPC_PUBLIC_BASE_URL="http://localhost:8000",
                REPONPC_TRUSTED_PROXY_CIDRS=trusted_proxy_cidrs,
            ),
            secret_roots=(tmp_path,),
        )

    assert "loopback_profile_exposed" in issue_codes(exposed.value)


def test_production_preserves_trusted_proxy_configuration(tmp_path: Path) -> None:
    settings = load_environment(
        deployment_environment(REPONPC_TRUSTED_PROXY_CIDRS="127.0.0.1/32"),
        secret_roots=(tmp_path,),
    )

    assert settings.trusted_proxy_cidrs == ("127.0.0.1/32",)


def test_legacy_recovery_command_and_local_production_embedding_are_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(EnvironmentValidationError) as legacy:
        load_environment(
            deployment_environment(
                REPONPC_GITHUB_OWNER_RECOVERY_COMMAND="unsafe free-form command"
            ),
            secret_roots=(tmp_path,),
        )
    assert "unknown_variable" in issue_codes(legacy.value)

    with pytest.raises(EnvironmentValidationError) as local_embedding:
        load_environment(
            deployment_environment(REPONPC_EMBEDDING_PROVIDER="local_sentence_transformers"),
            secret_roots=(tmp_path,),
        )
    assert "invalid_choice" in issue_codes(local_embedding.value)


def test_vllm_is_an_explicit_openai_compatible_provider_preset(tmp_path: Path) -> None:
    private_chat_url = "http://127.0.0.1:8000/v1"
    private_embedding_url = "http://127.0.0.1:8001/v1"
    settings = load_environment(
        deployment_environment(
            REPONPC_CHAT_PROVIDER="vllm",
            REPONPC_CHAT_BASE_URL=private_chat_url,
            REPONPC_EMBEDDING_PROVIDER="vllm",
            REPONPC_EMBEDDING_BASE_URL=private_embedding_url,
        ),
        secret_roots=(tmp_path,),
    )

    assert settings.chat_provider == "vllm"
    assert settings.embedding_provider == "vllm"
    assert private_chat_url not in repr(settings)
    assert private_embedding_url not in repr(settings)


def test_first_owner_mode_needs_no_default_username_or_github_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = deployment_environment(REPONPC_IP_HASH_KEY="ip-hmac-canary")
    settings = load_environment(values, secret_roots=(tmp_path,))
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()

    monkeypatch.setattr(
        main.app.state, "admin_session_service", main.app.state.admin_session_service
    )
    monkeypatch.setattr(main.app.state, "admin_operations", main.app.state.admin_operations)
    monkeypatch.setattr(main.app.state, "admin_origins", main.app.state.admin_origins)
    monkeypatch.setattr(main.app.state, "github_rate_limiter", main.app.state.github_rate_limiter)
    main._configure_admin(settings, database)

    assert settings.admin_username == ""
    assert settings.admin_password_hash is None
    assert main.app.state.admin_session_service is not None
    assert main.app.state.admin_session_service.setup_status().setup_required is True
    assert main.app.state.admin_operations is not None
    assert main.app.state.admin_operations.github is None
    assert main.app.state.github_rate_limiter is not None
    assert (
        main.app.state.admin_operations.onboarding._source_resolver.rate_limiter
        is main.app.state.github_rate_limiter
    )


def test_admin_startup_honors_disabled_environment_embedding_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    settings = load_environment(
        deployment_environment(
            REPONPC_DATA_DIR=str(data_dir),
            REPONPC_EMBEDDING_PROVIDER="ollama",
            REPONPC_IP_HASH_KEY="ip-hmac-canary",
        ),
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(data_dir)
    database.initialize()
    registry = ModelConnectionRegistry(
        database,
        ProtectedModelSecretStore(data_dir / "model-secrets" / "master.key"),
    )
    connection = registry.ensure_host_managed(
        "environment-embedding",
        display_name="Environment embedding",
        provider=settings.embedding_provider,
        base_url=settings.embedding_base_url or "",
        api_key=None,
    )
    assert connection is not None
    registry.delete(connection.connection_id)

    monkeypatch.setattr(
        main.app.state, "admin_session_service", main.app.state.admin_session_service
    )
    monkeypatch.setattr(main.app.state, "admin_operations", main.app.state.admin_operations)
    monkeypatch.setattr(main.app.state, "admin_origins", main.app.state.admin_origins)
    monkeypatch.setattr(main.app.state, "github_rate_limiter", main.app.state.github_rate_limiter)
    main._configure_admin(settings, database)

    operations = main.app.state.admin_operations
    assert operations is not None and operations.model_connections is not None
    assert operations.embedding_profiles is not None
    assert all(
        item.connection_id != "environment-embedding"
        for item in operations.model_connections.list()
    )
    assert all(item.profile_id != "environment" for item in operations.embedding_profiles.list())


def test_admin_restart_preserves_owner_managed_environment_embedding_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    settings = load_environment(
        deployment_environment(
            REPONPC_DATA_DIR=str(data_dir),
            REPONPC_EMBEDDING_PROVIDER="ollama",
            REPONPC_EMBEDDING_MODEL="environment-default-model",
            REPONPC_EMBEDDING_DIMENSION="1024",
            REPONPC_IP_HASH_KEY="ip-hmac-canary",
        ),
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(data_dir)
    database.initialize()
    for attribute in (
        "admin_session_service",
        "admin_operations",
        "admin_origins",
        "github_rate_limiter",
    ):
        monkeypatch.setattr(main.app.state, attribute, getattr(main.app.state, attribute))
    main._configure_admin(settings, database)

    operations = main.app.state.admin_operations
    assert operations is not None
    connections = operations.model_connections
    profiles = operations.embedding_profiles
    assert connections is not None and profiles is not None
    connection = connections.get("environment-embedding")
    replaced = connections.update(
        connection.connection_id,
        ModelConnectionInput(
            display_name="Owner Ollama",
            provider="ollama",
            base_url="http://127.0.0.1:22434",
            credential_action="retain",
        ),
    )
    profiles.update(
        "environment",
        EmbeddingProfileInput(
            provider="ollama",
            model_id="owner-selected-model",
            dimension=4096,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
            connection_reference=replaced.connection_id,
            connection_revision=replaced.revision,
        ),
    )

    main._configure_admin(settings, database)

    restarted = main.app.state.admin_operations
    assert restarted is not None
    persisted_connection = restarted.model_connections.get("environment-embedding")
    persisted_profile = restarted.embedding_profiles.get("environment")
    assert persisted_connection.source == "managed"
    assert persisted_connection.revision == replaced.revision
    assert persisted_profile.model_id == "owner-selected-model"
    assert persisted_profile.dimension == 4096
    assert persisted_profile.connection_revision == replaced.revision


def test_retired_github_public_read_settings_warn_and_are_never_loaded(tmp_path: Path) -> None:
    client_secret = "oauth-client-secret-canary"
    encryption_key = "credential-encryption-key-canary-material"
    missing_secret = tmp_path / "must-not-be-read"

    with pytest.warns(DeprecationWarning, match="ignored"):
        settings = load_environment(
            deployment_environment(
                REPONPC_GITHUB_OAUTH_CLIENT_ID="oauth-client-id",
                REPONPC_GITHUB_OAUTH_CLIENT_SECRET=client_secret,
                REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE=str(missing_secret),
                REPONPC_GITHUB_OAUTH_CALLBACK_URL=(
                    "https://portfolio.example.com/api/admin/github/callback"
                ),
                REPONPC_CREDENTIAL_ENCRYPTION_KEY=encryption_key,
                REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE=str(missing_secret),
            ),
            secret_roots=(tmp_path,),
        )

    assert not hasattr(settings, "github_oauth_client_id")
    assert not hasattr(settings, "github_oauth_callback_url")
    assert "github_oauth_client_secret" not in settings.secrets
    assert "credential_encryption_key" not in settings.secrets
    assert client_secret not in repr(settings)
    assert encryption_key not in repr(settings)


def test_admin_service_remains_unavailable_without_identity_hmac_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    values = deployment_environment()
    settings = load_environment(values, secret_roots=(tmp_path,))
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()

    monkeypatch.setattr(
        main.app.state, "admin_session_service", main.app.state.admin_session_service
    )
    monkeypatch.setattr(main.app.state, "admin_operations", main.app.state.admin_operations)
    monkeypatch.setattr(main.app.state, "admin_origins", main.app.state.admin_origins)
    monkeypatch.setattr(main.app.state, "github_rate_limiter", main.app.state.github_rate_limiter)
    main._configure_admin(settings, database)

    assert main.app.state.admin_session_service is None
    assert main.app.state.admin_operations is None
    assert main.app.state.github_rate_limiter is None


@pytest.mark.parametrize(
    "override",
    [
        {"REPONPC_ADMIN_USERNAME": "owner", "REPONPC_ADMIN_PASSWORD_HASH": ""},
        {"REPONPC_ADMIN_USERNAME": "", "REPONPC_ADMIN_PASSWORD_HASH": "$argon2id$hash"},
    ],
)
def test_preprovisioned_admin_credentials_require_an_explicit_pair(
    tmp_path: Path, override: dict[str, str]
) -> None:
    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(**override),
            secret_roots=(tmp_path,),
        )

    assert "admin_credential_pair_required" in issue_codes(raised.value)


def test_direct_and_file_secret_collision_is_safe(tmp_path: Path) -> None:
    secret_file = tmp_path / "github-token"
    secret_file.write_text("FILE_SECRET_CANARY", encoding="utf-8")

    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(
                REPONPC_GITHUB_TOKEN="DIRECT_SECRET_CANARY",
                REPONPC_GITHUB_TOKEN_FILE=str(secret_file),
            ),
            secret_roots=(tmp_path,),
        )

    rendered = repr(raised.value) + str(raised.value) + repr(raised.value.issues)
    assert "secret_source_collision" in issue_codes(raised.value)
    assert "DIRECT_SECRET_CANARY" not in rendered
    assert "FILE_SECRET_CANARY" not in rendered
    assert str(secret_file) not in rendered


def test_secret_file_must_be_bounded_regular_utf8_file_inside_allowed_root(tmp_path: Path) -> None:
    secret_root = tmp_path / "secrets"
    secret_root.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("OUTSIDE_SECRET", encoding="utf-8")
    oversized = secret_root / "oversized"
    oversized.write_bytes(b"x" * 33)
    empty = secret_root / "empty"
    empty.write_text("\n\t", encoding="utf-8")
    malformed = secret_root / "malformed"
    malformed.write_bytes(b"\xff")
    directory = secret_root / "directory"
    directory.mkdir()

    cases = [
        (outside, "secret_file_outside_root"),
        (oversized, "secret_file_too_large"),
        (empty, "empty_secret_file"),
        (malformed, "invalid_secret_encoding"),
        (directory, "unsafe_secret_file"),
    ]
    for candidate, expected_code in cases:
        with pytest.raises(EnvironmentValidationError) as raised:
            load_environment(
                deployment_environment(REPONPC_GITHUB_TOKEN_FILE=str(candidate)),
                secret_roots=(secret_root,),
                max_secret_bytes=32,
            )
        assert expected_code in issue_codes(raised.value)
        assert str(candidate) not in repr(raised.value.issues)


def test_secret_file_respects_a_custom_limit_above_the_default_read_bound(tmp_path: Path) -> None:
    secret_file = tmp_path / "github-token"
    canary = "x" * (environment.SECRET_MAX_BYTES + 2)
    secret_file.write_text(canary, encoding="utf-8")

    settings = load_environment(
        deployment_environment(REPONPC_GITHUB_TOKEN_FILE=str(secret_file)),
        secret_roots=(tmp_path,),
        max_secret_bytes=len(canary),
    )

    assert settings.secrets["github_token"].reveal() == canary


def test_symlinked_secret_file_is_rejected_without_disclosing_target(tmp_path: Path) -> None:
    secret_root = tmp_path / "secrets"
    secret_root.mkdir()
    target = secret_root / "target"
    target.write_text("SYMLINK_TARGET_SECRET", encoding="utf-8")
    link = secret_root / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable in this test environment")

    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(REPONPC_GITHUB_TOKEN_FILE=str(link)),
            secret_roots=(secret_root,),
        )

    assert "unsafe_secret_file" in issue_codes(raised.value)
    assert "SYMLINK_TARGET_SECRET" not in repr(raised.value.issues)


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits are not exposed on Windows")
def test_group_or_world_readable_secret_file_is_rejected(tmp_path: Path) -> None:
    secret_file = tmp_path / "github-token"
    secret_file.write_text("POSIX_SECRET", encoding="utf-8")
    secret_file.chmod(stat.S_IRUSR | stat.S_IRGRP)

    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(REPONPC_GITHUB_TOKEN_FILE=str(secret_file)),
            secret_roots=(tmp_path,),
        )

    assert "unsafe_secret_permissions" in issue_codes(raised.value)


def test_unknown_or_unsupported_environment_values_fail_before_startup(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(
                REPONPC_UNKNOWN_SETTING="not-supported",
                REPONPC_ALLOWED_ORIGINS="*",
                REPONPC_PERSIST_CONVERSATIONS="true",
            ),
            secret_roots=(tmp_path,),
        )

    assert {"unknown_variable", "wildcard_origin_forbidden", "unsupported_value"} <= issue_codes(
        raised.value
    )


def test_secret_value_cannot_be_constructed_with_a_leaking_representation() -> None:
    secret = SecretValue("REPR_SECRET_CANARY")

    assert "REPR_SECRET_CANARY" not in repr(secret)
    assert "REPR_SECRET_CANARY" not in str(secret)
    with pytest.raises(TypeError):
        asdict(secret)


@pytest.mark.skipif(os.name != "posix", reason="descriptor no-follow semantics require POSIX")
def test_secret_file_replacement_by_a_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_root = tmp_path / "secrets"
    secret_root.mkdir()
    secret_file = secret_root / "github-token"
    secret_file.write_text("ORIGINAL_SECRET", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.write_text("OUTSIDE_SECRET", encoding="utf-8")
    original_open = environment.os.open

    def replace_final_component(
        path: str | bytes | os.PathLike[str],
        *args: object,
        **kwargs: object,
    ) -> int:
        if path == secret_file.name and kwargs.get("dir_fd") is not None:
            secret_file.unlink()
            secret_file.symlink_to(outside)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(environment.os, "open", replace_final_component)

    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            deployment_environment(REPONPC_GITHUB_TOKEN_FILE=str(secret_file)),
            secret_roots=(secret_root,),
        )

    assert "unsafe_secret_file" in issue_codes(raised.value)
    assert "OUTSIDE_SECRET" not in repr(raised.value.issues)


def test_production_entrypoint_uses_validated_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        main,
        "load_environment",
        lambda: SimpleNamespace(
            host="127.0.0.2",
            port=8123,
            deployment_profile="production",
            data_dir=tmp_path / "runtime-data",
            sqlite_busy_timeout_ms=5_000,
        ),
    )
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    main.run()

    assert calls == [
        {
            "host": "127.0.0.2",
            "port": 8123,
            "factory": False,
            "proxy_headers": True,
        }
    ]


def test_production_entrypoint_reports_environment_failure_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary = "STARTUP_SECRET_CANARY"
    failure = EnvironmentValidationError(
        [
            EnvironmentIssue(
                name="REPONPC_GITHUB_TOKEN",
                code="secret_source_collision",
                message=canary,
            )
        ]
    )
    monkeypatch.setattr(main, "load_environment", lambda: (_ for _ in ()).throw(failure))

    with pytest.raises(SystemExit) as raised:
        main.run()

    assert str(raised.value) == "deployment environment is invalid"
    assert canary not in str(raised.value)
