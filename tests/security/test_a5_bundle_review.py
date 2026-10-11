"""Main verifies semantic asset safety even when all bundle hashes match."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import threading
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.scene import AdminSceneService, SceneServiceError
from reponpc.bundles.archive import BundleError, verify_retained_bundle_directory
from reponpc.bundles.manager import BundleActivationError
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.scene.images import validate_scene_image
from reponpc.scene.registry import SceneRegistry
from reponpc.scene.resolve import _average_edge_color
from tests.browser.a5_server import build_application


@pytest.fixture
def scene_runtime(tmp_path: Path):
    runtime = tmp_path / "host"
    application = build_application(runtime, tmp_path / "web", "http://testserver")
    with TestClient(application):
        yield application, runtime


@pytest.fixture
def published_bundle(scene_runtime, tmp_path: Path):
    application, _runtime = scene_runtime
    manager = application.application.state.bundle_manager
    target = tmp_path / "review-copy"
    with manager.acquire_snapshot() as (_index, _bundle_id, public_directory):
        shutil.copytree(public_directory.parent, target)
    yield target, manager.active_embedding_identity()


def _rehash(directory: Path) -> None:
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    hashes = {}
    for item in manifest["files"]:
        content = (directory / item["path"]).read_bytes()
        item["size"] = len(content)
        item["sha256"] = hashlib.sha256(content).hexdigest()
        hashes[item["path"]] = item["sha256"]
    manifest_path.write_bytes(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    hashes["manifest.json"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (directory / "checksums.sha256").write_bytes(
        "".join(f"{digest}  {path}\n" for path, digest in sorted(hashes.items())).encode("ascii")
    )


def test_review_copy_is_a_real_valid_bundle(
    published_bundle: tuple[Path, EmbeddingIdentity],
) -> None:
    directory, embedding = published_bundle
    verified = verify_retained_bundle_directory(directory=directory, expected_embedding=embedding)
    verified.close()


def test_verified_bundle_background_survives_public_snapshot_without_runtime_database(
    published_bundle: tuple[Path, EmbeddingIdentity], scene_runtime
) -> None:
    directory, embedding = published_bundle
    encoded = io.BytesIO()
    Image.new("RGBA", (640, 360), (21, 37, 53, 255)).save(encoded, "PNG")
    image = validate_scene_image(encoded.getvalue(), filename="fixture.png")
    relative = f"public/scene/{image.sha256}.png"
    image_path = directory / relative
    image_path.parent.mkdir()
    image_path.write_bytes(image.content)
    profile_path = directory / "public/profile.json"
    profile = json.loads(profile_path.read_bytes())
    next_id = "20260929T095100Z-" + image.sha256[:12]
    profile["index"]["version"] = next_id
    revision = profile["character"]["revision"]
    profile["character"]["scene"]["background_url"] = f"/api/public/scene-background?rev={revision}"
    profile["character"]["scene"]["background_dim"] = "high"
    profile_path.write_bytes(json.dumps(profile).encode())
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["bundle_id"] = next_id
    manifest["files"].append({"path": relative, "size": len(image.content), "sha256": image.sha256})
    manifest["files"].sort(key=lambda item: item["path"])
    manifest_path.write_bytes(json.dumps(manifest).encode())
    _rehash(directory)
    verified = verify_retained_bundle_directory(directory=directory, expected_embedding=embedding)
    application, runtime = scene_runtime
    manager = application.application.state.bundle_manager
    manager.activate(verified)
    service = AdminSceneService(manager=manager, database=None, data_directory=runtime / "data")
    with service.published_profile() as snapshot:
        assert snapshot.background_content == image.content
        assert snapshot.document.character.scene.background_url.endswith(f"rev={revision}")
        assert snapshot.settings is None  # External bundles have no private settings receipt.


def test_rehashed_sprite_stage_cannot_hide_a_failing_edge_contrast(
    published_bundle: tuple[Path, EmbeddingIdentity],
) -> None:
    directory, embedding = published_bundle
    with Image.open(directory / "public/character.png") as sprite:
        edge = _average_edge_color(sprite.convert("RGBA"))
    path = directory / "public/profile.json"
    profile = json.loads(path.read_bytes())
    for variant in ("light", "dark"):
        profile["character"]["scene"]["themes"][variant]["stage"] = edge
    path.write_bytes(json.dumps(profile, ensure_ascii=False).encode("utf-8"))
    _rehash(directory)
    with pytest.raises(BundleError):
        verify_retained_bundle_directory(directory=directory, expected_embedding=embedding)


def test_rehashed_character_cannot_publish_private_metadata(
    published_bundle: tuple[Path, EmbeddingIdentity],
) -> None:
    directory, embedding = published_bundle
    path = directory / "public/character.png"
    with Image.open(path) as source:
        image = source.convert("RGBA")
    encoded = io.BytesIO()
    image.save(encoded, "PNG", icc_profile=b"A5_PRIVATE_PUBLISHED_ICC_CANARY")
    path.write_bytes(encoded.getvalue())
    _rehash(directory)
    with pytest.raises(BundleError):
        verified = verify_retained_bundle_directory(
            directory=directory, expected_embedding=embedding
        )
        verified.close()


def test_two_appearance_applies_with_no_saved_draft_have_one_winner(
    scene_runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    application, runtime = scene_runtime
    service = AdminSceneService(
        manager=application.application.state.bundle_manager,
        database=application.application.state.runtime_database,
        data_directory=runtime / "data",
        portfolio=None,
    )
    state = service.scene_state()
    expected = {
        key: state[key]
        for key in (
            "source_bundle_id",
            "source_character_revision",
            "sprite_sha256",
            "character_revision",
            "appearance_revision",
            "draft_revision",
        )
    }
    assert expected["draft_revision"] is None
    captured = threading.Event()
    resume = threading.Event()
    read_snapshot = service._snapshot_from_lease

    def paused_snapshot(*args, **kwargs):
        result = read_snapshot(*args, **kwargs)
        if threading.current_thread().name == "a5-review-first":
            captured.set()
            assert resume.wait(5)
        return result

    monkeypatch.setattr(service, "_snapshot_from_lease", paused_snapshot)
    successes: list[dict[str, object]] = []
    failures: list[BaseException] = []

    def apply(mode: str) -> None:
        try:
            successes.append(
                service.apply(
                    session_hash="a" * 64,
                    proposal={"color_mode": mode, "background": "none"},
                    expected=expected,
                )
            )
        except BaseException as exc:
            failures.append(exc)

    first = threading.Thread(target=apply, args=("dark",), name="a5-review-first")
    second = threading.Thread(target=apply, args=("light",))
    first.start()
    try:
        assert captured.wait(5)
        second.start()
        second.join(0.25)
    finally:
        resume.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert len(successes) == len(failures) == 1
    assert isinstance(failures[0], SceneServiceError) and failures[0].code == "SCENE_CONFLICT"
    with service.published_profile() as snapshot:
        assert snapshot.document.character.scene.model_dump(mode="json") == successes[0]["scene"]
    assert application.chat.calls == 2  # Only fixture initialization used the synthetic model.


@pytest.mark.parametrize("change", ["new-registry-version", "retired-alias"])
def test_published_appearance_keeps_resolved_tokens_across_registry_compatibility(
    scene_runtime, change: str
) -> None:
    application, runtime = scene_runtime
    service = AdminSceneService(
        manager=application.application.state.bundle_manager,
        database=application.application.state.runtime_database,
        data_directory=runtime / "data",
    )
    state = service.scene_state()
    expected = {
        key: state[key]
        for key in (
            "source_bundle_id",
            "source_character_revision",
            "sprite_sha256",
            "character_revision",
            "appearance_revision",
            "draft_revision",
        )
    }
    scheme_id = state["settings"]["color_scheme"]
    registry = service.registry
    proposed_id = scheme_id
    if change == "retired-alias":
        proposed_id = "retired-review-scheme"
        service.registry = SceneRegistry(
            registry.schemes,
            MappingProxyType({**registry.aliases, proposed_id: scheme_id}),
            registry.source_sha256,
        )
    applied = service.apply(
        session_hash="a" * 64,
        proposal={"color_scheme": proposed_id, "background": "none"},
        expected=expected,
    )
    if change == "new-registry-version":
        schemes = dict(registry.schemes)
        schemes[scheme_id] = replace(schemes[scheme_id], version=schemes[scheme_id].version + 1)
        service.registry = SceneRegistry(
            MappingProxyType(schemes), registry.aliases, registry.source_sha256
        )
    with service.published_profile() as snapshot:
        assert snapshot.document.character.scene.model_dump(mode="json") == applied["scene"]
        assert snapshot.settings["color_scheme"] == scheme_id


def test_retired_scheme_alias_keeps_published_scene_tokens_and_settings_receipts(
    scene_runtime,
) -> None:
    application, runtime = scene_runtime
    manager = application.application.state.bundle_manager
    database = application.application.state.runtime_database
    service = AdminSceneService(
        manager=manager,
        database=database,
        data_directory=runtime / "data",
    )
    state = service.scene_state()
    old_id = state["scene"]["scheme"]["id"]
    registry = service.registry
    old_scheme = registry.schemes[old_id]
    replacement_id = next(
        scheme_id
        for scheme_id, scheme in registry.schemes.items()
        if scheme_id != old_id
        and scheme.version == old_scheme.version
        and (scheme.light != old_scheme.light or scheme.dark != old_scheme.dark)
    )
    replacement = registry.schemes[replacement_id]
    assert replacement.version == state["scene"]["scheme"]["version"]
    assert replacement.light != old_scheme.light or replacement.dark != old_scheme.dark
    schemes = dict(registry.schemes)
    del schemes[old_id]
    aliases = dict(registry.aliases)
    aliases[old_id] = replacement_id
    retired_registry = SceneRegistry(
        MappingProxyType(schemes), MappingProxyType(aliases), registry.source_sha256
    )

    receipt_service = AdminSceneService(
        manager=manager,
        database=database,
        data_directory=runtime / "data",
        registry=retired_registry,
    )
    with receipt_service.published_profile() as receipt_snapshot:
        assert receipt_snapshot.document.character.scene.model_dump(mode="json") == state["scene"]
        assert receipt_snapshot.settings is not None
        assert receipt_snapshot.settings["color_scheme"] == replacement_id

    unaliased_registry = SceneRegistry(
        MappingProxyType(schemes), registry.aliases, registry.source_sha256
    )
    unknown_receipt_service = AdminSceneService(
        manager=manager,
        database=database,
        data_directory=runtime / "data",
        registry=unaliased_registry,
    )
    with unknown_receipt_service.published_profile() as unknown_receipt_snapshot:
        assert unknown_receipt_snapshot.settings is None

    applied = service.apply(
        session_hash="b" * 64,
        proposal={"color_scheme": old_id, "background": "none"},
        expected={
            key: state[key]
            for key in (
                "source_bundle_id",
                "source_character_revision",
                "sprite_sha256",
                "character_revision",
                "appearance_revision",
                "draft_revision",
            )
        },
    )
    service.registry = retired_registry
    with service.published_profile() as appearance_snapshot:
        assert (
            appearance_snapshot.document.character.scene.model_dump(mode="json") == applied["scene"]
        )
        assert appearance_snapshot.settings is not None
        assert appearance_snapshot.settings["color_scheme"] == replacement_id

    service.registry = unaliased_registry
    with pytest.raises(SceneServiceError) as failure, service.published_profile():
        pytest.fail("an unknown published scheme was served")
    assert failure.value.code == "PUBLIC_SCENE_UNAVAILABLE"


def test_runtime_pointer_cannot_publish_mismatched_character_and_scene_revisions(
    scene_runtime,
) -> None:
    application, runtime = scene_runtime
    service = AdminSceneService(
        manager=application.application.state.bundle_manager,
        database=application.application.state.runtime_database,
        data_directory=runtime / "data",
    )
    state = service.scene_state()
    service.apply(
        session_hash="a" * 64,
        proposal={"background": "none"},
        expected={
            key: state[key]
            for key in (
                "source_bundle_id",
                "source_character_revision",
                "sprite_sha256",
                "character_revision",
                "appearance_revision",
                "draft_revision",
            )
        },
    )
    with service.database.connection() as connection:
        value = json.loads(
            connection.execute(
                "SELECT scene_json FROM scene_appearance_state WHERE singleton=1"
            ).fetchone()[0]
        )
        value["public"]["revision"] += 1
        connection.execute(
            "UPDATE scene_appearance_state SET scene_json=? WHERE singleton=1",
            (json.dumps(value),),
        )
    with pytest.raises(SceneServiceError) as failure, service.published_profile():
        pytest.fail("the mismatched public revisions were served")
    assert failure.value.code == "PUBLIC_SCENE_UNAVAILABLE"


def test_active_bundle_guard_defers_real_activation_until_coordinated_commit(
    scene_runtime, tmp_path: Path
) -> None:
    application, _runtime = scene_runtime
    manager = application.application.state.bundle_manager
    with manager.acquire_snapshot() as (_index, original_id, public_directory):
        candidate_directory = tmp_path / "candidate"
        shutil.copytree(public_directory.parent, candidate_directory)
    next_id = "20260929T092100Z-" + hashlib.sha256(original_id.encode()).hexdigest()[:12]
    manifest_path = candidate_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["bundle_id"] = next_id
    manifest_path.write_bytes(json.dumps(manifest).encode())
    profile_path = candidate_directory / "public/profile.json"
    profile = json.loads(profile_path.read_bytes())
    profile["index"]["version"] = next_id
    profile_path.write_bytes(json.dumps(profile).encode())
    _rehash(candidate_directory)
    candidate = verify_retained_bundle_directory(
        directory=candidate_directory, expected_embedding=manager.active_embedding_identity()
    )
    entered = threading.Event()
    completed = threading.Event()
    failures: list[BaseException] = []

    def activate() -> None:
        entered.set()
        try:
            manager.activate(candidate)
        except BaseException as exc:
            failures.append(exc)
        finally:
            completed.set()

    transition = threading.Thread(target=activate)
    with manager.guard_active_bundle(original_id):
        transition.start()
        assert entered.wait(5)
        assert not completed.wait(0.25)
        assert manager.status().active_bundle_id == original_id
    transition.join(5)
    assert completed.is_set() and not failures
    assert manager.status().active_bundle_id == next_id
    with pytest.raises(BundleActivationError) as failure, manager.guard_active_bundle(original_id):
        pytest.fail("stale source entered its commit boundary")
    assert failure.value.code == "bundle_snapshot_stale"
