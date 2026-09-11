"""Installed CLI dispatch and real build/publication pipeline integration."""

from __future__ import annotations

import hashlib
import re
import secrets
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

import reponpc.main as runtime_main
from reponpc import cli
from reponpc.admin.auth import AdminSessionService
from reponpc.indexing.pipeline import (
    PENDING_MANIFEST_NAME,
    IndexPipelineError,
    build_index_bundle,
    publish_index_bundle,
    publish_pending_manifest,
)
from reponpc.indexing.sources import ResolvedConfiguration
from tests.integration.test_index_build import (
    FIXTURE_CONFIG,
    DeterministicEmbeddingProvider,
    _fixture_snapshot,
)


class FixtureResolver:
    def resolve(self, *, slug: str, ref: str | None):
        assert slug == "fixture-owner/reponpc-demo"
        assert ref == "a" * 40
        return _fixture_snapshot()


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.asset = b""
        self.stable_content: bytes | None = None

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        self.events.append("release")
        assert tag == name
        return 7

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        self.events.append("upload")
        assert release_id == 7
        assert name.endswith(".tar.zst")
        self.asset = content
        return "https://github.com/fixture-owner/reponpc-demo/releases/download/index/asset.tar.zst"

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        self.events.append("verify")
        assert asset_url.startswith("https://github.com/")
        assert len(self.asset) == size
        assert hashlib.sha256(self.asset).hexdigest() == sha256

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        self.events.append("stable")
        self.stable_content = content


def _write_public_assets(directory: Path) -> Path:
    public = directory / "public"
    public.mkdir()
    (public / "character.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    for theme in ("light", "dark"):
        for locale in ("zh-TW", "en"):
            (public / f"card-{theme}-{locale}.svg").write_bytes(
                b"<svg xmlns='http://www.w3.org/2000/svg'/>"
            )
            (public / f"card-{theme}-{locale}.gif").write_bytes(b"GIF89a")
            (public / f"card-{theme}-{locale}.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    return public


def test_real_pipeline_builds_verifies_then_splits_pending_pointer_publication(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "reponpc.yml"
    config_content = FIXTURE_CONFIG.read_text(encoding="utf-8")
    config_path.write_text(config_content, encoding="utf-8")
    public_directory = _write_public_assets(tmp_path)
    output = tmp_path / "dist"
    built_at = datetime(2026, 8, 12, 1, 2, 3, tzinfo=UTC)
    configuration_source = ResolvedConfiguration(
        repository_slug="fixture-owner/reponpc-demo",
        commit_sha="a" * 40,
        path="reponpc.yml",
        content=config_content,
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
    )

    bundle = build_index_bundle(
        config_path,
        output,
        resolver=FixtureResolver(),
        embedding_provider=DeterministicEmbeddingProvider(),
        configuration_source=configuration_source,
        built_at=built_at,
        public_directory=public_directory,
    )

    assert bundle.archive_path.is_file()
    assert (output / "index.sqlite").is_file()
    assert (output / "bundle-build.json").is_file()
    publisher = RecordingPublisher()
    pending_path = publish_index_bundle(output, publisher=publisher, now=built_at)
    assert pending_path == output / PENDING_MANIFEST_NAME
    assert pending_path.is_file()
    assert publisher.events == ["release", "upload", "verify"]
    assert publisher.stable_content is None

    publish_pending_manifest(output, publisher=publisher)

    assert publisher.events == ["release", "upload", "verify", "verify", "stable"]
    assert publisher.stable_content == pending_path.read_bytes()


def test_entrypoint_mapping_and_no_argument_serve_dispatch(monkeypatch) -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["reponpc"] == "reponpc.cli:run"
    calls: list[str] = []
    monkeypatch.setattr(cli, "run_server", lambda: calls.append("serve"))

    assert cli.main([]) == 0
    assert cli.main(["serve"]) == 0

    assert calls == ["serve", "serve"]


def test_config_and_index_commands_do_not_start_server(tmp_path: Path, monkeypatch, capsys) -> None:
    server_calls: list[str] = []
    command_calls: list[tuple[str, Path]] = []
    monkeypatch.setattr(cli, "run_server", lambda: server_calls.append("serve"))
    monkeypatch.setattr(
        cli,
        "build_index_bundle",
        lambda config, output: (
            command_calls.append(("build", Path(output)))
            or SimpleNamespace(manifest=SimpleNamespace(bundle_id="fixture-bundle"))
        ),
    )
    monkeypatch.setattr(
        cli,
        "publish_index_bundle",
        lambda directory: (
            command_calls.append(("publish", Path(directory)))
            or Path(directory) / PENDING_MANIFEST_NAME
        ),
    )
    monkeypatch.setattr(
        cli,
        "publish_pending_manifest",
        lambda directory: command_calls.append(("publish-manifest", Path(directory))),
    )

    assert cli.main(["config", "validate", str(FIXTURE_CONFIG)]) == 0
    assert (
        cli.main(["index", "build", "--config", str(FIXTURE_CONFIG), "--output", str(tmp_path)])
        == 0
    )
    assert cli.main(["index", "publish", "--bundle-dir", str(tmp_path)]) == 0
    assert cli.main(["index", "publish-manifest", "--bundle-dir", str(tmp_path)]) == 0

    assert server_calls == []
    assert [item[0] for item in command_calls] == ["build", "publish", "publish-manifest"]
    assert "fixture-bundle" in capsys.readouterr().out


def test_admin_hash_password_reads_twice_and_emits_only_argon2id_hash(monkeypatch, capsys) -> None:
    prompts: list[str] = []

    def password_input(prompt: str) -> str:
        prompts.append(prompt)
        return "correct horse battery staple"

    monkeypatch.setattr(cli, "getpass", password_input)

    assert cli.main(["admin", "hash-password"]) == 0
    output = capsys.readouterr().out.strip()
    assert prompts == ["Password: ", "Confirm password: "]
    assert re.fullmatch(r"\$argon2id\$.*", output)
    assert "correct horse battery staple" not in output


def test_admin_setup_code_uses_runtime_database_and_emits_raw_code_once(
    tmp_path: Path, capsys
) -> None:
    data_dir = tmp_path / "runtime"

    assert cli.main(["admin", "setup-code", "--data-dir", str(data_dir)]) == 0
    first = capsys.readouterr().out.strip()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", first)

    database = cli.RuntimeDatabase(data_dir)
    with database.connection() as connection:
        first_hash = connection.execute("SELECT code_hash FROM admin_setup").fetchone()[0]
    assert first_hash == hashlib.sha256(first.encode()).hexdigest()
    assert first != first_hash

    assert cli.main(["admin", "setup-code", "--data-dir", str(data_dir)]) == 0
    second = capsys.readouterr().out.strip()
    with database.connection() as connection:
        second_hash = connection.execute("SELECT code_hash FROM admin_setup").fetchone()[0]
    assert second != first
    assert second_hash == hashlib.sha256(second.encode()).hexdigest()
    assert second_hash != first_hash


def test_admin_launch_token_emits_one_fragment_url_and_replaces_prior_grant(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    data_dir = tmp_path / "runtime"
    settings = SimpleNamespace(
        data_dir=data_dir,
        deployment_profile="loopback_evaluation",
        public_base_url="http://localhost:8090",
    )
    monkeypatch.setattr(cli, "load_environment", lambda: settings)

    assert cli.main(["admin", "launch-token"]) == 0
    first_lines = capsys.readouterr().out.splitlines()
    assert len(first_lines) == 1
    first = urlsplit(first_lines[0])
    assert first.scheme == "http"
    assert first.netloc == "localhost:8090"
    assert first.path == "/admin"
    assert first.query == ""
    assert set(parse_qs(first.fragment)) == {"local-launch"}
    first_grant = parse_qs(first.fragment)["local-launch"][0]

    assert cli.main(["admin", "launch-token", "--data-dir", str(data_dir)]) == 0
    second_lines = capsys.readouterr().out.splitlines()
    assert len(second_lines) == 1
    second = urlsplit(second_lines[0])
    second_grant = parse_qs(second.fragment)["local-launch"][0]
    assert second_grant != first_grant

    database = cli.RuntimeDatabase(data_dir)
    with database.connection() as connection:
        stored = connection.execute(
            "SELECT grant_hash FROM admin_local_launch_grants WHERE state_key = 'current'"
        ).fetchone()[0]
    assert stored == hashlib.sha256(second_grant.encode()).hexdigest()
    assert first_grant not in stored
    assert second_grant not in stored


@pytest.mark.parametrize(
    ("profile", "proxy_headers"),
    [("loopback_evaluation", False), ("production", True)],
)
def test_server_proxy_header_trust_tracks_deployment_profile(
    tmp_path: Path, monkeypatch, profile: str, proxy_headers: bool
) -> None:
    settings = SimpleNamespace(
        data_dir=tmp_path / profile,
        sqlite_busy_timeout_ms=1_000,
        host="127.0.0.1",
        port=8090,
        deployment_profile=profile,
    )
    database = SimpleNamespace(initialize=lambda: None)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(runtime_main, "load_environment", lambda: settings)
    monkeypatch.setattr(runtime_main, "RuntimeDatabase", lambda *_args, **_kwargs: database)
    monkeypatch.setattr(runtime_main, "_configure_admin", lambda *_args: None)
    monkeypatch.setattr(runtime_main, "_configure_bundle_lifecycle", lambda *_args: None)
    monkeypatch.setattr(runtime_main.uvicorn, "run", lambda *_args, **kwargs: calls.append(kwargs))
    runtime_main.app.state.analysis_batch_service = None

    runtime_main.run()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8090,
            "factory": False,
            "proxy_headers": proxy_headers,
        }
    ]


def test_admin_setup_code_uses_data_dir_environment(tmp_path: Path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "configured-runtime"
    monkeypatch.setenv("REPONPC_DATA_DIR", str(data_dir))

    assert cli.main(["admin", "setup-code"]) == 0

    output = capsys.readouterr().out.strip()
    assert output
    assert (data_dir / "runtime.sqlite").is_file()


def test_admin_setup_code_fails_safely_after_owner_exists(tmp_path: Path, capsys) -> None:
    data_dir = tmp_path / "runtime"
    database = cli.RuntimeDatabase(data_dir)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        deployment_profile="production",
    )
    setup_code = secrets.token_urlsafe(32)
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_setup VALUES ('current', ?, '2026-08-13T00:00:00Z', "
            "'2099-08-13T00:15:00Z')",
            (hashlib.sha256(setup_code.encode()).hexdigest(),),
        )
    service.setup_owner(
        setup_code=setup_code,
        username="owner",
        password="correct horse battery staple",
        password_confirmation="correct horse battery staple",
    )

    assert cli.main(["admin", "setup-code", "--data-dir", str(data_dir)]) == 1

    captured = capsys.readouterr()
    assert "setup_already_complete" in captured.err
    assert setup_code not in captured.err


def test_set_password_uses_optional_owner_selector_and_preserves_username(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    data_dir = tmp_path / "runtime"
    database = cli.RuntimeDatabase(data_dir)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        deployment_profile="production",
    )
    setup_code = secrets.token_urlsafe(32)
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_setup VALUES ('current', ?, '2026-08-13T00:00:00Z', "
            "'2099-08-13T00:15:00Z')",
            (hashlib.sha256(setup_code.encode()).hexdigest(),),
        )
    service.setup_owner(
        setup_code=setup_code,
        username="owner",
        password="correct horse battery staple",
        password_confirmation="correct horse battery staple",
    )
    replacement = "安全密碼" * 4
    prompts = iter((replacement, replacement))
    monkeypatch.setattr(cli, "getpass", lambda _prompt: next(prompts))
    monkeypatch.setenv("REPONPC_DEPLOYMENT_PROFILE", "production")

    assert cli.main(["admin", "set-password", "--data-dir", str(data_dir)]) == 0
    assert "completed" in capsys.readouterr().out
    restarted = AdminSessionService(
        database=database,
        identity_hmac_key=b"k" * 32,
        deployment_profile="production",
    )
    restarted.login(username="owner", password=replacement, remote_identity="host")


def test_runtime_check_and_online_backup_are_verified_and_non_overwriting(
    tmp_path: Path, capsys
) -> None:
    data_dir = tmp_path / "runtime"
    database = cli.RuntimeDatabase(data_dir)
    database.initialize()
    destination = tmp_path / "backups" / "runtime.sqlite"
    destination.parent.mkdir()

    assert cli.main(["runtime", "check", "--data-dir", str(data_dir)]) == 0
    assert "integrity ok" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "runtime",
                "backup",
                str(destination),
                "--data-dir",
                str(data_dir),
            ]
        )
        == 0
    )
    assert destination.is_file()
    copied = cli.RuntimeDatabase(destination.parent)
    copied.check_integrity()

    assert (
        cli.main(
            [
                "runtime",
                "backup",
                str(destination),
                "--data-dir",
                str(data_dir),
            ]
        )
        == 1
    )
    assert "runtime_backup_target_invalid" in capsys.readouterr().err


def test_cli_help_exposes_bounded_bundle_and_runtime_groups(capsys) -> None:
    with pytest.raises(SystemExit) as stopped:
        cli.main(["--help"])
    assert stopped.value.code == 0
    help_text = capsys.readouterr().out
    assert "bundle" in help_text
    assert "runtime" in help_text


def test_bundle_commands_dispatch_explicit_ids_and_persisted_actions(monkeypatch, capsys) -> None:
    calls: list[tuple[str, str | None]] = []

    class Manager:
        def status(self):
            calls.append(("status", None))
            return SimpleNamespace(
                active_bundle_id="bundle-active",
                previous_bundle_id="bundle-previous",
                pinned_bundle_id=None,
            )

        def verify(self, bundle_id: str) -> None:
            calls.append(("verify", bundle_id))

        def pin(self, bundle_id: str) -> None:
            calls.append(("pin", bundle_id))

        def unpin(self) -> None:
            calls.append(("unpin", None))

    monkeypatch.setattr(cli, "_bundle_manager", lambda _data_dir: Manager())

    assert cli.main(["bundle", "status"]) == 0
    assert '"active_bundle_id": "bundle-active"' in capsys.readouterr().out
    assert cli.main(["bundle", "verify", "bundle-1"]) == 0
    assert cli.main(["bundle", "pin", "bundle-1"]) == 0
    assert cli.main(["bundle", "unpin"]) == 0
    assert calls == [
        ("status", None),
        ("verify", "bundle-1"),
        ("pin", "bundle-1"),
        ("unpin", None),
    ]

    with pytest.raises(SystemExit) as missing_id:
        cli.main(["bundle", "verify"])
    assert missing_id.value.code == 2


def test_cli_failure_is_nonzero_safe_and_does_not_echo_internal_text(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    canary = "CANARY-UPSTREAM-BODY"

    def fail(*args: object, **kwargs: object) -> None:
        try:
            raise RuntimeError(canary)
        except RuntimeError as exc:
            raise IndexPipelineError("index_build_failed") from exc

    monkeypatch.setattr(cli, "build_index_bundle", fail)

    exit_code = cli.main(
        ["index", "build", "--config", str(FIXTURE_CONFIG), "--output", str(tmp_path)]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "index_build_failed" in captured.err
    assert canary not in captured.err
