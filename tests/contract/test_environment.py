from __future__ import annotations

import os
import stat
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest

import reponpc.config.environment as environment
import reponpc.main as main
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
    main._configure_admin(settings, database)

    assert settings.admin_username == ""
    assert settings.admin_password_hash is None
    assert main.app.state.admin_session_service is not None
    assert main.app.state.admin_session_service.setup_status().setup_required is True
    assert main.app.state.admin_operations is not None
    assert main.app.state.admin_operations.github is None


def test_github_oauth_requires_complete_same_origin_encrypted_configuration(tmp_path: Path) -> None:
    credential_key = "credential-encryption-key-canary-material"
    client_secret = "oauth-client-secret-canary"
    settings = load_environment(
        deployment_environment(
            REPONPC_GITHUB_OAUTH_CLIENT_ID="oauth-client-id",
            REPONPC_GITHUB_OAUTH_CLIENT_SECRET=client_secret,
            REPONPC_GITHUB_OAUTH_CALLBACK_URL=(
                "https://portfolio.example.com/api/admin/github/callback"
            ),
            REPONPC_CREDENTIAL_ENCRYPTION_KEY=credential_key,
            REPONPC_GITHUB_OWNER_RECOVERY_COMMAND="reponpc admin set-password",
        ),
        secret_roots=(tmp_path,),
    )

    assert settings.github_oauth_client_id == "oauth-client-id"
    assert settings.github_oauth_callback_url.endswith("/api/admin/github/callback")
    assert client_secret not in repr(settings)
    assert credential_key not in repr(settings)

    with pytest.raises(EnvironmentValidationError) as incomplete:
        load_environment(
            deployment_environment(REPONPC_GITHUB_OAUTH_CLIENT_ID="oauth-client-id"),
            secret_roots=(tmp_path,),
        )
    assert "oauth_configuration_incomplete" in issue_codes(incomplete.value)

    with pytest.raises(EnvironmentValidationError) as invalid_callback:
        load_environment(
            deployment_environment(
                REPONPC_GITHUB_OAUTH_CLIENT_ID="oauth-client-id",
                REPONPC_GITHUB_OAUTH_CLIENT_SECRET=client_secret,
                REPONPC_GITHUB_OAUTH_CALLBACK_URL=(
                    "https://portfolio.example.com/api/admin/session/github/callback"
                ),
                REPONPC_CREDENTIAL_ENCRYPTION_KEY=credential_key,
            ),
            secret_roots=(tmp_path,),
        )
    assert "invalid_oauth_callback" in issue_codes(invalid_callback.value)

    with pytest.raises(EnvironmentValidationError) as malformed_callback:
        load_environment(
            deployment_environment(
                REPONPC_GITHUB_OAUTH_CLIENT_ID="oauth-client-id",
                REPONPC_GITHUB_OAUTH_CLIENT_SECRET=client_secret,
                REPONPC_GITHUB_OAUTH_CALLBACK_URL=("https://[malformed/api/admin/github/callback"),
                REPONPC_CREDENTIAL_ENCRYPTION_KEY=credential_key,
            ),
            secret_roots=(tmp_path,),
        )
    assert "invalid_oauth_callback" in issue_codes(malformed_callback.value)


def test_credential_encryption_key_allows_pat_only_without_oauth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = load_environment(
        deployment_environment(
            REPONPC_CREDENTIAL_ENCRYPTION_KEY="credential-encryption-key-canary-material",
            REPONPC_IP_HASH_KEY="ip-hmac-canary",
        ),
        secret_roots=(tmp_path,),
    )
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()

    monkeypatch.setattr(
        main.app.state, "github_identity_service", main.app.state.github_identity_service
    )
    main._configure_admin(settings, database)

    assert settings.secrets["credential_encryption_key"] is not None
    assert settings.github_oauth_client_id == ""
    assert settings.github_oauth_callback_url == ""
    assert main.app.state.github_identity_service is not None
    assert main.app.state.github_identity_service.oauth_available is False


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
    main._configure_admin(settings, database)

    assert main.app.state.admin_session_service is None
    assert main.app.state.admin_operations is None


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
            data_dir=tmp_path / "runtime-data",
            sqlite_busy_timeout_ms=5_000,
        ),
    )
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs))

    main.run()

    assert calls == [{"host": "127.0.0.2", "port": 8123, "factory": False}]


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
