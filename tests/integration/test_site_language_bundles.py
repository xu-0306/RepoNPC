from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

from reponpc import cli
from reponpc.api.public import SetupState
from reponpc.bundles.archive import BundleError, verify_bundle_archive
from reponpc.bundles.manager import BundleManager
from reponpc.i18n.languages import language_tags
from reponpc.i18n.plan import ANALYSIS_LOCALES, LocaleNotEnabledError
from reponpc.indexing.pipeline import build_index_bundle
from reponpc.indexing.public_profile import (
    localized_public_profile_bytes,
    parse_public_profile_bytes,
)
from reponpc.indexing.sources import ResolvedConfiguration
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase
from reponpc.sharing.export import build_site_files, build_visitor_site_export
from reponpc.sharing.manifest import MANIFEST_NAME, canonical_json_bytes
from reponpc.sharing.pages import PagesSharingService
from reponpc.sharing.readme import render_profile_readme
from tests.fixtures.bundles.site_languages import site_data
from tests.integration.test_index_build import DeterministicEmbeddingProvider, _fixture_snapshot
from tests.security.test_a5_sharing_review import _visitor_build

TAGS = language_tags()
SITE_SETS = [ANALYSIS_LOCALES, ("en",), ("es",), ("zh-CN", "en"), TAGS, TAGS[1:] + TAGS[:1]]
ANCHOR = Path(__file__).parents[1] / "fixtures" / "bundles" / "v1-zh-TW-en"


def _legacy_bundle(stage: Path):
    spec = importlib.util.spec_from_file_location("legacy_bundle", ANCHOR / "loader.py")
    assert spec is not None and spec.loader is not None
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    return loader.load_bundle(stage)


def _configuration(root: Path, tags: tuple[str, ...]) -> tuple[Path, ResolvedConfiguration]:
    root.mkdir(parents=True, exist_ok=True)
    data = site_data(tags, default=tags[-1])
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path = root / "reponpc.yml"
    path.write_text(content, encoding="utf-8")
    return path, ResolvedConfiguration(
        repository_slug="fixture-owner/reponpc-demo",
        commit_sha="a" * 40,
        path="reponpc.yml",
        content=content,
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
    )


class _Resolver:
    def resolve(self, *, slug: str, ref: str | None):
        return _fixture_snapshot()


def _build(root: Path, tags: tuple[str, ...]):
    path, source = _configuration(root, tags)
    return build_index_bundle(
        path,
        root / "dist",
        resolver=_Resolver(),
        embedding_provider=DeterministicEmbeddingProvider(),
        configuration_source=source,
        built_at=datetime(2026, 11, 3, tzinfo=UTC),
    )


def _verify(path: Path, stage: Path, digest: str | None = None):
    return verify_bundle_archive(
        archive_path=path,
        staging_directory=stage,
        expected_outer_sha256=digest or hashlib.sha256(path.read_bytes()).hexdigest(),
        expected_embedding=DeterministicEmbeddingProvider().identity(),
        max_bundle_bytes=1024 * 1024,
    )


def _manager(root: Path):
    runtime = RuntimeDatabase(root / "runtime")
    runtime.initialize()
    return BundleManager(
        data_directory=root / "data",
        runtime_database=runtime,
        expected_embedding=DeterministicEmbeddingProvider().identity(),
    ), runtime


@pytest.mark.parametrize("tags", SITE_SETS)
def test_build_verify_activate_and_serve_stored_summaries(
    tmp_path: Path, tags: tuple[str, ...]
) -> None:
    bundle = _build(tmp_path / "build", tags)
    verified = _verify(bundle.archive_path, tmp_path / "stage")
    manager, _ = _manager(tmp_path)
    manager.activate(verified)
    with manager.acquire_snapshot() as (index, bundle_id, public):
        document = parse_public_profile_bytes((public / "profile.json").read_bytes())
        assert (
            document.schema_version
            == bundle.manifest.index_schema_version
            == index.index_schema_version
            == 2
        )
        assert tuple(document.locales) == index.locales.supported == tags
        assert index.locales.default == tags[-1]
        assert bundle_id == bundle.manifest.bundle_id
        for tag in tags:
            assert index.repository_summaries(tag) == {
                repository.slug: repository.summary
                for repository in document.locales[tag].repositories
            }
            assert json.loads(localized_public_profile_bytes(document, tag))["locale"] == tag
        for tag in set(TAGS) - set(tags):
            with pytest.raises(LocaleNotEnabledError):
                index.repository_summaries(tag)
        with sqlite3.connect(
            f"file:{(public.parent / 'index.sqlite').as_posix()}?mode=ro", uri=True
        ) as connection:
            columns = connection.execute("PRAGMA table_info(repository_summaries)").fetchall()
            assert [(row[1], row[5]) for row in columns if row[5]] == [
                ("repository_id", 1),
                ("locale", 2),
            ]
            assert connection.execute("SELECT COUNT(*) FROM repository_summaries").fetchone() == (
                len(tags),
            )
    assert set(bundle.manifest.as_dict()) == set(_legacy_manifest())
    assert manager.verify(bundle.manifest.bundle_id).bundle_id == bundle.manifest.bundle_id


def _legacy_manifest():
    with tarfile.open(ANCHOR / "bundle.tar.zst", "r:zst") as archive:
        return json.load(archive.extractfile("manifest.json"))


def test_frozen_v1_fixture_verifies_activates_and_serves_without_rewriting(tmp_path: Path) -> None:
    verified = _legacy_bundle(tmp_path / "stage")
    before = {
        path.relative_to(verified.directory): path.read_bytes()
        for path in verified.directory.rglob("*")
        if path.is_file()
    }
    manager, _ = _manager(tmp_path)
    manager.activate(verified)
    with manager.acquire_snapshot() as (index, bundle_id, public):
        assert index.index_schema_version == 1
        document = parse_public_profile_bytes((public / "profile.json").read_bytes())
        assert document.schema_version == 1
        assert tuple(document.locales) == ANALYSIS_LOCALES
        for tag, localized in document.locales.items():
            assert index.repository_summaries(tag) == {
                repository.slug: repository.summary for repository in localized.repositories
            }
        assert {
            path.relative_to(public.parent): path.read_bytes()
            for path in public.parent.rglob("*")
            if path.is_file()
        } == before
        app = create_app(
            setup_state=SetupState(
                index_ready=True, index_version=bundle_id, public_directory=public
            )
        )
        with TestClient(app) as client:
            for tag in document.locales:
                response = client.get("/api/public/profile", params={"locale": tag})
                assert response.status_code == 200
                assert response.content == localized_public_profile_bytes(document, tag)
    assert manager.verify(bundle_id).index_schema_version == 1


def _rewrite_bundle(source: Path, target: Path, mutation: str) -> None:
    with tarfile.open(source, "r:zst") as archive:
        files = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
    document = json.loads(files["public/profile.json"])
    tags = tuple(document["locales"])
    if mutation == "missing_locale":
        del document["locales"][tags[-1]]
        for theme in ("light", "dark"):
            for extension in ("svg", "gif", "png"):
                del files[f"public/card-{theme}-{tags[-1]}.{extension}"]
    elif mutation == "extra_locale":
        extra = next(tag for tag in TAGS if tag not in tags)
        document["locales"][extra] = document["locales"][tags[0]]
        for theme in ("light", "dark"):
            for extension in ("svg", "gif", "png"):
                files[f"public/card-{theme}-{extra}.{extension}"] = files[
                    f"public/card-{theme}-{tags[0]}.{extension}"
                ]
    elif mutation == "v1_third_locale":
        document["schema_version"] = 1
    elif mutation == "missing_card":
        del files[f"public/card-dark-{tags[-1]}.png"]
    elif mutation == "extra_card":
        extra = next(tag for tag in TAGS if tag not in tags)
        files[f"public/card-light-{extra}.svg"] = files[f"public/card-light-{tags[0]}.svg"]
    elif mutation == "missing_summary":
        database_path = target.parent / "tampered.sqlite"
        database_path.write_bytes(files["index.sqlite"])
        with sqlite3.connect(database_path) as connection:
            connection.execute("DELETE FROM repository_summaries WHERE locale = ?", (tags[-1],))
        files["index.sqlite"] = database_path.read_bytes()
    else:
        files["public/character.png"] += b"tampered"
    files["public/profile.json"] = json.dumps(
        document, ensure_ascii=False, separators=(",", ":")
    ).encode()
    if mutation != "checksum":
        manifest = json.loads(files["manifest.json"])
        manifest["files"] = [
            {"path": path, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for path, content in sorted(files.items())
            if path not in {"manifest.json", "checksums.sha256"}
        ]
        files["manifest.json"] = canonical_json_bytes(manifest)
        files["checksums.sha256"] = "".join(
            f"{hashlib.sha256(content).hexdigest()}  {path}\n"
            for path, content in sorted(files.items())
            if path != "checksums.sha256"
        ).encode()
    with tarfile.open(target, "w:zst") as archive:
        for path, content in sorted(files.items()):
            member = tarfile.TarInfo(path)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_locale",
        "extra_locale",
        "missing_card",
        "extra_card",
        "v1_third_locale",
        "missing_summary",
        "checksum",
    ],
)
def test_every_invalid_candidate_retains_last_known_good(tmp_path: Path, mutation: str) -> None:
    manager, _ = _manager(tmp_path)
    manager.activate(_legacy_bundle(tmp_path / "old-stage"))
    active = manager.status().active_bundle_id
    tags = (
        (*ANALYSIS_LOCALES, next(tag for tag in TAGS if tag not in ANALYSIS_LOCALES))
        if mutation == "v1_third_locale"
        else TAGS[:-1]
    )
    bundle = _build(tmp_path / "build", tags)
    candidate = tmp_path / "tampered.tar.zst"
    _rewrite_bundle(bundle.archive_path, candidate, mutation)
    with pytest.raises(BundleError) as error:
        manager.activate(_verify(candidate, tmp_path / "invalid-stage"))
    assert (
        error.value.code
        == {
            "missing_locale": "bundle_profile_invalid",
            "extra_locale": "bundle_profile_invalid",
            "missing_card": "bundle_layout_invalid",
            "extra_card": "bundle_layout_invalid",
            "v1_third_locale": "bundle_layout_invalid",
            "missing_summary": "bundle_index_invalid",
            "checksum": "bundle_payload_checksum_invalid",
        }[mutation]
    )
    assert manager.status().active_bundle_id == active
    assert not (tmp_path / "invalid-stage").exists()
    assert manager.verify(active).bundle_id == active


def _scene_service(manager):
    def snapshot(bundle_id, public_directory):
        document = parse_public_profile_bytes((public_directory / "profile.json").read_bytes())
        sprite = (public_directory / "character.png").read_bytes()
        return SimpleNamespace(
            document=document,
            bundle_id=bundle_id,
            sprite_content=sprite,
            sprite_sha256=hashlib.sha256(sprite).hexdigest(),
            character_revision=document.character.revision,
            appearance_revision=None,
            issued_revision=document.character.revision,
            background_content=None,
            settings={},
        )

    return SimpleNamespace(manager=manager, _snapshot_from_lease=snapshot)


class _Faq:
    def __init__(self, manager, database, *, failing_locale=None):
        self.bundles = manager
        self.database = database
        self.calls = []
        self.failing_locale = failing_locale

    def public_payload_for_bundle(self, locale, bundle_id, connection):
        assert connection.in_transaction
        self.calls.append(locale)
        if locale == self.failing_locale:
            raise ValueError("fixture language has no FAQ")
        return {
            "bundle_id": bundle_id,
            "locale": locale,
            "entries": [
                {
                    "question": f"{locale}: question",
                    "answer_markdown": f"{locale}: answer",
                    "citations": [],
                }
            ],
        }


@pytest.mark.parametrize("tag", TAGS)
def test_readme_rejects_every_disabled_registry_language(tmp_path: Path, tag: str) -> None:
    enabled = next(other for other in TAGS if other != tag)
    bundle = _build(tmp_path / "build", (enabled,))
    manager, runtime = _manager(tmp_path)
    manager.activate(_verify(bundle.archive_path, tmp_path / "stage"))
    service = PagesSharingService(
        database=runtime,
        faq=_Faq(manager, runtime),
        scene_service=_scene_service(manager),
        gateway_supplier=lambda: None,
    )
    with pytest.raises(LocaleNotEnabledError):
        service.readme(web_dist=tmp_path / "unused", locale=tag)


@pytest.mark.parametrize("tags", [(tag,) for tag in TAGS] + [TAGS, TAGS[1:] + TAGS[:1]])
def test_export_uses_every_site_language_and_exact_public_profile_bytes(
    tmp_path: Path, tags: tuple[str, ...]
) -> None:
    bundle = _build(tmp_path / "build", tags)
    manager, runtime = _manager(tmp_path)
    manager.activate(_verify(bundle.archive_path, tmp_path / "stage"))
    faq = _Faq(manager, runtime)
    arguments = dict(
        faq=faq,
        scene_service=_scene_service(manager),
        web_dist=_visitor_build(tmp_path),
        pages_url="https://fixture.github.io/portfolio/",
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    files, manifest = build_site_files(**arguments)
    assert faq.calls == list(tags)
    assert {path for path in files if path.startswith("profile-")} == {
        f"profile-{tag}.json" for tag in tags
    }
    assert {path for path in files if path.startswith("faq-")} == {
        f"faq-{tag}.json" for tag in tags
    }
    assert {path for path in files if path.startswith("card-")} == {
        f"card-{theme}-{tag}.{extension}"
        for tag in tags
        for theme in ("light", "dark")
        for extension in ("svg", "png", "gif")
    }
    for path, payload in files.items():
        if path.endswith(".html"):
            assert f'<html lang="{tags[-1]}"'.encode() in payload
    with manager.acquire_snapshot() as (_, bundle_id, public):
        document = parse_public_profile_bytes((public / "profile.json").read_bytes())
        for tag in tags:
            assert files[f"profile-{tag}.json"] == localized_public_profile_bytes(document, tag)
            assert json.loads(files[f"faq-{tag}.json"]) == {
                "bundle_id": bundle_id,
                "locale": tag,
                "entries": [
                    {
                        "question": f"{tag}: question",
                        "answer_markdown": f"{tag}: answer",
                        "citations": [],
                    }
                ],
            }
            assert f"card-light-{tag}.gif".encode() in render_profile_readme(
                document.locales[tag],
                pages_url="https://fixture.github.io/portfolio/",
                locale=tag,
            )
    artifact = build_visitor_site_export(**arguments)
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            assert (
                archive.read("profile-" + tags[0] + ".json")
                == files["profile-" + tags[0] + ".json"]
            )
            assert json.loads(archive.read(MANIFEST_NAME)) == manifest
    finally:
        artifact.cleanup()


@pytest.mark.parametrize("tag", TAGS)
def test_export_writes_empty_public_faq_shape_when_service_raises(tmp_path: Path, tag: str) -> None:
    bundle = _build(tmp_path / "build", (tag,))
    manager, runtime = _manager(tmp_path)
    manager.activate(_verify(bundle.archive_path, tmp_path / "stage"))
    files, _ = build_site_files(
        faq=_Faq(manager, runtime, failing_locale=tag),
        scene_service=_scene_service(manager),
        web_dist=_visitor_build(tmp_path),
        pages_url="https://fixture.github.io/portfolio/",
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    assert json.loads(files[f"faq-{tag}.json"]) == {
        "bundle_id": bundle.manifest.bundle_id,
        "locale": tag,
        "entries": [],
    }


def test_serving_and_export_never_invoke_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import reponpc.i18n.convert as conversion

    def forbidden(*args, **kwargs):
        pytest.fail("serving/export must use stored text without conversion")

    original = conversion.convert
    for name, module in tuple(sys.modules.items()):
        if name.startswith("reponpc.") and module is not None:
            for attribute, value in tuple(vars(module).items()):
                if value is original:
                    monkeypatch.setattr(module, attribute, forbidden)
    bundle = _build(tmp_path / "build", TAGS)
    manager, runtime = _manager(tmp_path)
    manager.activate(_verify(bundle.archive_path, tmp_path / "stage"))
    with manager.acquire_snapshot() as (index, _, public):
        document = parse_public_profile_bytes((public / "profile.json").read_bytes())
        for tag in TAGS:
            assert index.repository_summaries(tag)
            assert localized_public_profile_bytes(document, tag)
        app = create_app(
            setup_state=SetupState(
                index_ready=True,
                index_version=bundle.manifest.bundle_id,
                public_directory=public,
            )
        )
        with TestClient(app) as client:
            for tag in ANALYSIS_LOCALES:
                assert client.get("/api/public/profile", params={"locale": tag}).status_code == 200
                assert client.get("/api/public/card.png", params={"locale": tag}).status_code == 200
    files, _ = build_site_files(
        faq=_Faq(manager, runtime),
        scene_service=_scene_service(manager),
        web_dist=_visitor_build(tmp_path),
        pages_url="https://fixture.github.io/portfolio/",
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    assert all(f"profile-{tag}.json" in files for tag in TAGS)


@pytest.mark.parametrize("tags", [ANALYSIS_LOCALES, TAGS])
def test_cli_index_build_runs_real_v2_pipeline_for_legacy_and_full_set(
    tmp_path: Path, tags: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    path, source = _configuration(tmp_path, tags)

    def build(config, output, **kwargs):
        return build_index_bundle(
            config,
            output,
            resolver=_Resolver(),
            embedding_provider=DeterministicEmbeddingProvider(),
            configuration_source=source,
            built_at=datetime(2026, 11, 3, tzinfo=UTC),
        )

    monkeypatch.setattr(cli, "build_index_bundle", build)
    assert (
        cli.main(["index", "build", "--config", str(path), "--output", str(tmp_path / "dist")]) == 0
    )
    archive = next((tmp_path / "dist").glob("*.tar.zst"))
    verified = _verify(archive, tmp_path / "stage")
    try:
        assert verified.manifest.index_schema_version == 2
        assert verified.index.locales.supported == tags
    finally:
        verified.close()
