"""Installed CLI dispatch and real build/publication pipeline integration."""

from __future__ import annotations

import hashlib
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from reponpc import cli
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
