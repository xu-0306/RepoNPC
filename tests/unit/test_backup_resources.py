"""Disposable same-host restore resources; no provider or owner runtime access."""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml
from cryptography.fernet import Fernet
from PIL import Image

from reponpc.admin import backup_resources as resources
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.model_connections import ModelConnectionSecret, ProtectedModelSecretStore
from reponpc.bundles.archive import verify_bundle_archive
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase
from reponpc.scene.images import validate_scene_image
from tests.integration import test_bundle_producer_consumer as bundle_fixtures
from tests.integration import test_index_build as index_fixtures
from tests.integration.test_index_build import DeterministicEmbeddingProvider

STAMP = "2026-10-03T00:00:00Z"
OTHER_ID = "20261003T000000Z-123456789abc"


@dataclass
class Fixture:
    data: Path
    current: RuntimeDatabase
    candidate: RuntimeDatabase

    def check(self) -> None:
        resources.validate_restore_resources(self.candidate.database_path, self.current, self.data)


@pytest.fixture
def state(tmp_path: Path) -> Fixture:
    data = tmp_path / "data"
    current = RuntimeDatabase(data)
    candidate = RuntimeDatabase(tmp_path / "normalized")
    for database in (current, candidate):
        database.initialize()
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO admin_owner VALUES ('current','synthetic-owner',?,?)",
                ("$argon2id$synthetic-owner-hash", STAMP),
            )
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.execute("PRAGMA journal_mode=DELETE")
    return Fixture(data, current, candidate)


class FixtureEmbeddingProvider(DeterministicEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__()
        self._identity = replace(
            self._identity, adapter="ollama", model_id="invented-fixture-model"
        )


@pytest.fixture
def bundle(
    state: Fixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, EmbeddingIdentity]:
    monkeypatch.setattr(bundle_fixtures, "DeterministicEmbeddingProvider", FixtureEmbeddingProvider)
    fixture_config = tmp_path / "fixture-config.yml"
    raw = yaml.safe_load(index_fixtures.FIXTURE_CONFIG.read_text(encoding="utf-8"))
    raw["retrieval"]["embedding"].update(adapter="ollama", model="invented-fixture-model")
    fixture_config.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(bundle_fixtures, "FIXTURE_CONFIG", fixture_config)
    monkeypatch.setattr(index_fixtures, "FIXTURE_CONFIG", fixture_config)
    built, provider = bundle_fixtures._bundle(tmp_path / "build")
    verified = verify_bundle_archive(
        archive_path=built.archive_path,
        staging_directory=state.data / "bundles" / "validated" / built.manifest.bundle_id,
        expected_outer_sha256=built.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    verified.close()
    return built.manifest.bundle_id, provider.identity()


def _profile(state: Fixture, identity: EmbeddingIdentity, bundle_id: str | None = None) -> None:
    with state.candidate.connection() as connection:
        connection.execute(
            "INSERT INTO embedding_profiles(profile_id,provider,model_id,dimension,normalized,"
            "query_prefix,passage_prefix,connection_reference,status,active,created_at,updated_at,"
            "connection_revision,bundle_id) VALUES ('fixture',?,?,?,?,?,?,'environment',"
            "'last_known_good',1,?,?,0,?)",
            (
                identity.adapter,
                identity.model_id,
                identity.dimension,
                int(identity.normalized),
                identity.query_prefix,
                identity.passage_prefix,
                STAMP,
                STAMP,
                bundle_id,
            ),
        )


def _pointer(state: Fixture, column: str, bundle_id: str) -> None:
    assert column in {"active_bundle_id", "previous_bundle_id", "pinned_bundle_id"}
    with state.candidate.connection() as connection:
        connection.execute(
            f"INSERT INTO bundle_state(state_key,{column}) VALUES ('current',?)", (bundle_id,)
        )


def _scene(state: Fixture, bundle_id: str, *, background: bytes | None = None) -> None:
    sprite = state.data / "bundles" / "validated" / bundle_id / "public" / "character.png"
    digest = hashlib.sha256(background).hexdigest() if background else None
    if background:
        assets = state.data / "scene-appearance" / "assets"
        assets.mkdir(parents=True)
        (assets / f"{digest}.png").write_bytes(background)
    with state.candidate.connection() as connection:
        connection.execute(
            "UPDATE scene_appearance_state SET issued_revision=1,source_bundle_id=?,"
            "sprite_sha256=?,character_revision=0,appearance_revision=1,scene_json='{}',"
            "background_sha256=?,background_extension=?",
            (
                bundle_id,
                hashlib.sha256(sprite.read_bytes()).hexdigest(),
                digest,
                "png" if background else None,
            ),
        )


def _faq(state: Fixture, bundle_id: str, review_state: str = "approved") -> None:
    with state.candidate.connection() as connection:
        connection.execute(
            "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,topic,"
            "claim_kind,answer_markdown,coverage_status,review_state,revision) "
            "VALUES ('fixture','question',?,'en','Question','repo_summary','context',"
            "'Answer','answered',?,1)",
            (bundle_id, review_state),
        )


def _secrets(state: Fixture) -> Path:
    key_path = state.data / "model-secrets" / "master.key"
    store = ProtectedModelSecretStore(key_path)
    with state.candidate.connection() as connection:
        connection.execute(
            "INSERT INTO model_connections(connection_id,display_name,provider,source,revision,"
            "secret_ref,endpoint_configured,key_configured,status,created_at,updated_at) "
            "VALUES ('fixture','Synthetic','ollama','managed',2,"
            "'secret-2',1,0,'available',?,?)",
            (STAMP, STAMP),
        )
        for revision in (1, 2):
            cipher = store.encrypt(ModelConnectionSecret("http://127.0.0.1:11434", None))
            connection.execute(
                "INSERT INTO model_connection_secrets VALUES (?,?,?,?,?,?)",
                (f"secret-{revision}", "fixture", revision, cipher, STAMP, "ollama"),
            )
    return key_path


def _fails(state: Fixture, code: str) -> None:
    with pytest.raises(resources.BackupResourceError) as caught:
        state.check()
    assert caught.value.code == code
    assert str(caught.value) == "backup resources unavailable"
    assert caught.value.__cause__ is None


def test_empty_resources_need_no_key_and_never_mutate_databases(state: Fixture) -> None:
    before = [database.database_path.read_bytes() for database in (state.current, state.candidate)]
    state.check()
    assert before == [
        database.database_path.read_bytes() for database in (state.current, state.candidate)
    ]
    assert not (state.data / "model-secrets").exists()


def test_owner_hash_and_username_may_be_old_but_created_identity_must_match(state: Fixture) -> None:
    with state.candidate.connection() as connection:
        connection.execute(
            "UPDATE admin_owner SET username='old-owner',password_hash='$argon2id$old-hash'"
        )
    state.check()
    with state.candidate.connection() as connection:
        connection.execute("UPDATE admin_owner SET created_at='2026-10-02T00:00:00Z'")
    _fails(state, "RESTORE_OWNER_MISMATCH")


def test_missing_owner_is_different_owner(state: Fixture) -> None:
    with state.candidate.connection() as connection:
        connection.execute("DELETE FROM admin_owner")
    _fails(state, "RESTORE_OWNER_MISMATCH")


def test_existing_key_decrypts_every_historical_revision(state: Fixture) -> None:
    key = _secrets(state)
    before = key.read_bytes()
    state.check()
    assert key.read_bytes() == before
    with state.candidate.connection() as connection:
        connection.execute(
            "UPDATE model_connection_secrets SET ciphertext=? WHERE revision=1", (b"bad",)
        )
    _fails(state, "RESTORE_SECRET_UNAVAILABLE")


@pytest.mark.parametrize("failure", ["missing", "wrong", "malformed", "oversize"])
def test_key_failure_is_safe_and_never_creates_replacement(state: Fixture, failure: str) -> None:
    key = _secrets(state)
    if failure == "missing":
        key.unlink()
    else:
        key.write_bytes(
            Fernet.generate_key()
            if failure == "wrong"
            else b"x" * (65 if failure == "oversize" else 44)
        )
    before = key.read_bytes() if key.exists() else None
    _fails(state, "RESTORE_SECRET_UNAVAILABLE")
    assert (key.read_bytes() if key.exists() else None) == before


@pytest.mark.parametrize("column", ["active_bundle_id", "previous_bundle_id", "pinned_bundle_id"])
def test_real_retained_bundle_pointers(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], column: str
) -> None:
    bundle_id, identity = bundle
    _pointer(state, column, bundle_id)
    if column != "previous_bundle_id":
        _profile(state, identity)
    state.check()


@pytest.mark.parametrize(
    "reference", ["active_bundle_id", "previous_bundle_id", "pinned_bundle_id", "profile", "faq"]
)
def test_every_retained_reference_must_exist(state: Fixture, reference: str) -> None:
    if reference == "profile":
        _profile(state, EmbeddingIdentity("ollama", "invented", 2, True, "", ""), OTHER_ID)
    elif reference == "faq":
        _faq(state, OTHER_ID)
    else:
        _pointer(state, reference, OTHER_ID)
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")


@pytest.mark.parametrize(
    "bundle_id", ["../outside", "a/b", "C:\\outside", "x" * 10000, "20261003T000000Z-123456789abg"]
)
def test_bundle_reference_cannot_select_arbitrary_path(state: Fixture, bundle_id: str) -> None:
    _pointer(state, "previous_bundle_id", bundle_id)
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")


def test_profile_only_bundle_and_approved_faq_are_verified(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    bundle_id, identity = bundle
    _profile(state, identity, bundle_id)
    _faq(state, bundle_id)
    state.check()


def test_pending_faq_and_inactive_historical_profile_need_no_retained_bundle(
    state: Fixture,
) -> None:
    _faq(state, OTHER_ID, "pending")
    _profile(state, EmbeddingIdentity("ollama", "invented", 2, True, "", ""), OTHER_ID)
    with state.candidate.connection() as connection:
        connection.execute("UPDATE embedding_profiles SET active=0,status='probe_failed'")
    state.check()


@pytest.mark.parametrize(
    "change", ["missing", "model", "dimension", "prefix", "adapter", "normalized"]
)
def test_active_and_pin_embedding_identity_fail_closed(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], change: str
) -> None:
    bundle_id, identity = bundle
    _pointer(state, "pinned_bundle_id", bundle_id)
    if change != "missing":
        _profile(state, identity)
        mutations = {
            "model": "model_id='different'",
            "dimension": "dimension=2",
            "prefix": "query_prefix='different'",
            "adapter": "provider='vllm'",
            "normalized": "normalized=0",
        }
        with state.candidate.connection() as connection:
            connection.execute("UPDATE embedding_profiles SET " + mutations[change])
    _fails(state, "RESTORE_EMBEDDING_INCOMPATIBLE")


@pytest.mark.parametrize(
    "file", ["index.sqlite", "public/character.png", "manifest.json", "checksums.sha256"]
)
def test_tampered_retained_bytes_fail_verifier(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], file: str
) -> None:
    bundle_id, _ = bundle
    _pointer(state, "previous_bundle_id", bundle_id)
    path = state.data / "bundles" / "validated" / bundle_id / file
    path.write_bytes(path.read_bytes() + b"tampered")
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")


def test_verifier_handle_is_closed(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, _ = bundle
    _pointer(state, "previous_bundle_id", bundle_id)
    original = resources.verify_retained_bundle_directory
    close = Mock()

    def track(**kwargs: object) -> object:
        result = original(**kwargs)  # type: ignore[arg-type]

        def close_both() -> None:
            result.close()
            close()

        return SimpleNamespace(manifest=result.manifest, close=close_both)

    monkeypatch.setattr(resources, "verify_retained_bundle_directory", track)
    state.check()
    close.assert_called_once_with()


def test_scene_sprite_and_canonical_background_resources(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    image = io.BytesIO()
    Image.new("RGBA", (640, 360), (20, 30, 40, 255)).save(image, format="PNG")
    canonical = validate_scene_image(image.getvalue(), filename="background.png")
    _scene(state, bundle[0], background=canonical.content)
    state.check()
    background = state.data / "scene-appearance" / "assets" / f"{canonical.sha256}.png"
    background.unlink()
    _fails(state, "RESTORE_APPEARANCE_UNAVAILABLE")


def test_scene_sprite_binding_cannot_change(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    _scene(state, bundle[0])
    with state.candidate.connection() as connection:
        connection.execute("UPDATE scene_appearance_state SET sprite_sha256=?", ("f" * 64,))
    _fails(state, "RESTORE_APPEARANCE_UNAVAILABLE")


def test_background_noncanonical_even_with_matching_raw_hash_is_rejected(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    image = io.BytesIO()
    Image.new("RGBA", (640, 360)).save(image, format="PNG", compress_level=0)
    _scene(state, bundle[0], background=image.getvalue())
    _fails(state, "RESTORE_APPEARANCE_UNAVAILABLE")


@pytest.mark.parametrize("batch_state", ["queued", "running", "paused", "cancelling"])
def test_unfinished_batches_are_never_recovered(state: Fixture, batch_state: str) -> None:
    with state.candidate.connection() as connection:
        connection.execute(
            "INSERT INTO analysis_batches(batch_id,plan_id,selection_hash,idempotency_key_hash,"
            "state,maximum_generation_attempts,created_at,updated_at) VALUES ('fixture','plan',"
            "?,?,?,3,?,?)",
            ("1" * 64, "2" * 64, batch_state, STAMP, STAMP),
        )
    _fails(state, "RESTORE_WORK_PENDING")


@pytest.mark.parametrize("kind", ["journal", "switch"])
def test_other_pending_work_is_not_replayed(state: Fixture, kind: str) -> None:
    with state.candidate.connection() as connection:
        if kind == "journal":
            connection.execute("UPDATE scene_appearance_state SET journal_json='{}'")
        else:
            _profile(state, EmbeddingIdentity("ollama", "invented", 2, True, "", ""))
            connection.execute(
                "INSERT INTO embedding_switch_intent VALUES ('current',1,NULL,NULL,'fixture',?,?)",
                (OTHER_ID, STAMP),
            )
    _fails(state, "RESTORE_WORK_PENDING")


def test_local_source_marker_requires_valid_existing_draft(state: Fixture) -> None:
    root = state.data / "local-portfolio"
    root.mkdir()
    (root / "source-local").write_bytes(b"fixture")
    _fails(state, "RESTORE_PORTFOLIO_UNAVAILABLE")
    content = (Path(__file__).parents[1] / "fixtures/phase2/reponpc.yml").read_text(
        encoding="utf-8"
    )
    LocalPortfolioStore(state.data).save(
        content=content, sprite_base64=None, expected_revision=None
    )
    before = (root / "draft.json").read_bytes()
    state.check()
    assert (root / "draft.json").read_bytes() == before
    (root / "draft.json").write_bytes(b"{broken")
    _fails(state, "RESTORE_PORTFOLIO_UNAVAILABLE")


@pytest.mark.parametrize("linked", ["master.key", "manifest.json", "index.sqlite"])
def test_hardlinked_host_resource_is_rejected(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], tmp_path: Path, linked: str
) -> None:
    if linked == "master.key":
        path, code = _secrets(state), "RESTORE_SECRET_UNAVAILABLE"
    else:
        _pointer(state, "previous_bundle_id", bundle[0])
        path = state.data / "bundles" / "validated" / bundle[0] / linked
        code = "RESTORE_BUNDLE_UNAVAILABLE"
    os.link(path, tmp_path / "alias")
    _fails(state, code)


def test_symlink_bundle_directory_rejected(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity], tmp_path: Path
) -> None:
    _pointer(state, "previous_bundle_id", bundle[0])
    path = state.data / "bundles" / "validated" / bundle[0]
    target = tmp_path / "external"
    path.rename(target)
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("host does not permit disposable symlink creation")
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")


def test_reparse_attribute_is_rejected_without_following(
    state: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.lstat

    def lstat(path: Path) -> object:
        info = original(path)
        if path == state.data:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    _fails(state, "RESTORE_RESOURCE_INVALID")


def test_permission_failure_has_no_path_or_exception_details(
    state: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("private path and key material")

    monkeypatch.setattr(resources, "_connection", denied)
    _fails(state, "RESTORE_RESOURCE_INVALID")


def test_current_owner_reads_live_wal_snapshot(state: Fixture) -> None:
    with state.current.connection() as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("UPDATE admin_owner SET created_at='2026-10-02T00:00:00Z'")
        _fails(state, "RESTORE_OWNER_MISMATCH")


def test_missing_current_file_is_never_created(state: Fixture) -> None:
    state.current.database_path.unlink()
    _fails(state, "RESTORE_RESOURCE_INVALID")
    assert not state.current.database_path.exists()


@pytest.mark.parametrize("database", ["candidate", "current"])
def test_database_hardlink_cannot_be_opened(state: Fixture, tmp_path: Path, database: str) -> None:
    target = state.candidate if database == "candidate" else state.current
    os.link(target.database_path, tmp_path / "alias.sqlite")
    _fails(state, "RESTORE_RESOURCE_INVALID")


def test_bundle_directory_name_must_match_manifest_identity(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    root = state.data / "bundles" / "validated"
    (root / bundle[0]).rename(root / OTHER_ID)
    _pointer(state, "previous_bundle_id", OTHER_ID)
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")


def test_background_hash_checks_canonical_bytes_not_only_valid_image(
    state: Fixture, bundle: tuple[str, EmbeddingIdentity]
) -> None:
    def content(color: tuple[int, int, int, int]) -> bytes:
        stream = io.BytesIO()
        Image.new("RGBA", (640, 360), color).save(stream, format="PNG")
        return validate_scene_image(stream.getvalue(), filename="background.png").content

    original = content((255, 0, 0, 255))
    _scene(state, bundle[0], background=original)
    path = (
        state.data / "scene-appearance" / "assets" / f"{hashlib.sha256(original).hexdigest()}.png"
    )
    path.write_bytes(content((0, 255, 0, 255)))
    _fails(state, "RESTORE_APPEARANCE_UNAVAILABLE")


def test_linked_unused_directory_inside_bundle_is_rejected_before_verifier(
    state: Fixture,
    bundle: tuple[str, EmbeddingIdentity],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pointer(state, "previous_bundle_id", bundle[0])
    target = tmp_path / "outside"
    target.mkdir()
    link = state.data / "bundles" / "validated" / bundle[0] / "unused"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("host does not permit disposable symlink creation")
    verifier = Mock()
    monkeypatch.setattr(resources, "verify_retained_bundle_directory", verifier)
    _fails(state, "RESTORE_BUNDLE_UNAVAILABLE")
    verifier.assert_not_called()
