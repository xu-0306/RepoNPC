"""Runtime activation/rollback with real staged bundles and SQLite state."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.bundles.archive import verify_bundle_archive
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.runtime.database import RuntimeDatabase


def _verified(tmp_path: Path, label: str, minute: int):
    bundle, provider = _bundle_at(tmp_path / label, minute)
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=tmp_path / f"stage-{label}",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    return verified, provider


def _bundle_at(tmp_path: Path, minute: int):
    # _bundle's ID is determined by the passed clock after replacing the small
    # helper's timestamp through a local wrapper used only in this test suite.
    from reponpc.bundles.archive import build_bundle
    from reponpc.bundles.manifest import bundle_id_for
    from tests.integration.test_bundle_producer_consumer import (
        _configuration_source,
        _fixture_snapshot,
        _public_files,
    )
    from tests.integration.test_index_build import DeterministicEmbeddingProvider, _build

    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
    configuration = _configuration_source()
    repository = _fixture_snapshot()
    built_at = datetime(2026, 8, 10, 12, minute, tzinfo=UTC)
    bundle_id = bundle_id_for(
        built_at=built_at,
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    return (
        build_bundle(
            index_result=index_result,
            configuration_source=configuration,
            repositories=(repository,),
            bundle_id=bundle_id,
            built_at=built_at,
            public_files=_public_files(
                bundle_id=bundle_id,
                built_at=built_at,
                repository_count=index_result.repository_count,
            ),
            output_path=tmp_path / f"reponpc-index-{bundle_id}.tar.zst",
        ),
        provider,
    )


def test_atomic_activation_retains_inflight_handle_and_rolls_back_on_pre_swap_fault(
    tmp_path: Path,
) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    active_a = manager.status().active_bundle_id
    assert active_a is not None

    candidate_b, _ = _verified(tmp_path, "b", 1)
    with manager.acquire() as inflight_a:
        manager.activate(candidate_b)
        assert inflight_a.lexical_candidates("hybrid retrieval", limit=1)
        assert manager.status().active_bundle_id != active_a
        assert manager.status().previous_bundle_id == active_a
        with manager.acquire() as new_b:
            assert new_b is not inflight_a
            assert new_b.lexical_candidates("hybrid retrieval", limit=1)

    candidate_c, _ = _verified(tmp_path, "c", 2)
    with pytest.raises(BundleActivationError) as error:
        manager.activate(
            candidate_c, before_pointer_swap=lambda: (_ for _ in ()).throw(RuntimeError())
        )
    assert error.value.code == "bundle_pointer_swap_failed"
    assert manager.status().active_bundle_id != candidate_c.manifest.bundle_id
    assert runtime.bundle_state().active_bundle_id == manager.status().active_bundle_id

    verified_manifest = manager.verify(active_a)
    assert verified_manifest.bundle_id == active_a

    manager.pin(active_a)
    assert manager.status().active_bundle_id == active_a
    assert manager.status().pinned_bundle_id == active_a
    manager.unpin()
    assert manager.status().pinned_bundle_id is None


def test_manager_reopens_persisted_active_and_previous_bundles_after_restart(
    tmp_path: Path,
) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    active_a = manager.status().active_bundle_id
    assert active_a is not None

    candidate_b, _ = _verified(tmp_path, "b", 1)
    manager.activate(candidate_b)
    active_b = manager.status().active_bundle_id
    assert active_b is not None
    assert manager.status().previous_bundle_id == active_a

    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id == active_b
    assert restarted.status().previous_bundle_id == active_a
    with restarted.acquire() as active_index:
        assert active_index.lexical_candidates("hybrid retrieval", limit=1)


def test_activation_persistence_failure_restores_active_pointer_and_restart_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    prior = manager.status()
    candidate_b, _ = _verified(tmp_path, "b", 1)

    def fail_persist(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(runtime, "save_bundle_state", fail_persist)
    with pytest.raises(BundleActivationError):
        manager.activate(candidate_b)

    assert manager.status() == prior
    assert runtime.bundle_state().active_bundle_id == prior.active_bundle_id
    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id == prior.active_bundle_id


def test_switched_pin_persistence_failure_restores_prior_active_and_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    candidate_b, _ = _verified(tmp_path, "b", 1)
    manager.activate(candidate_b)
    prior = manager.status()

    monkeypatch.setattr(
        runtime, "save_bundle_state", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError())
    )
    with pytest.raises(BundleActivationError):
        manager.pin(candidate_a.manifest.bundle_id)

    assert manager.status() == prior
    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id == prior.active_bundle_id


def test_first_activation_persistence_failure_leaves_no_restartable_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, provider = _verified(tmp_path, "first", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    monkeypatch.setattr(
        runtime,
        "save_bundle_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("CANARY")),
    )

    with pytest.raises(BundleActivationError) as error:
        manager.activate(candidate)

    assert error.value.code == "bundle_pointer_swap_failed"
    assert "CANARY" not in str(error.value)
    assert manager.status().active_bundle_id is None
    assert runtime.bundle_state().active_bundle_id is None
    assert not (tmp_path / "data" / "bundles" / "active.json").exists()
    assert not (tmp_path / "data" / "bundles" / "validated" / candidate.manifest.bundle_id).exists()
    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id is None


def test_already_active_pin_and_unpin_persistence_failures_preserve_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, provider = _verified(tmp_path, "active", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate)
    active_id = candidate.manifest.bundle_id
    manager.pin(active_id)
    pinned = manager.status()
    monkeypatch.setattr(
        runtime,
        "save_bundle_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("CANARY")),
    )

    with pytest.raises(BundleActivationError):
        manager.pin(active_id)
    assert manager.status() == pinned
    assert runtime.bundle_state().pinned_bundle_id == active_id
    with manager.acquire() as index:
        assert index.lexical_candidates("hybrid retrieval", limit=1)
    with pytest.raises(BundleActivationError):
        manager.unpin()
    assert manager.status() == pinned
    assert runtime.bundle_state().pinned_bundle_id == active_id
    with manager.acquire() as index:
        assert index.lexical_candidates("hybrid retrieval", limit=1)


def test_failed_retained_verification_keeps_last_known_good_on_restart(tmp_path: Path) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    candidate_b, _ = _verified(tmp_path, "b", 1)
    manager.activate(candidate_b)
    prior = manager.status()
    bad_asset = (
        tmp_path
        / "data"
        / "bundles"
        / "validated"
        / candidate_a.manifest.bundle_id
        / "public"
        / "profile.json"
    )
    bad_asset.write_text("{}", encoding="utf-8")

    with pytest.raises(BundleActivationError):
        manager.pin(candidate_a.manifest.bundle_id)

    assert manager.status() == prior
    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id == prior.active_bundle_id


def test_failed_pointer_restore_cannot_leave_candidate_restartable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_a, provider = _verified(tmp_path, "a", 0)
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    manager.activate(candidate_a)
    candidate_b, _ = _verified(tmp_path, "b", 1)
    monkeypatch.setattr(
        runtime,
        "save_bundle_state",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("CANARY")),
    )
    monkeypatch.setattr(
        manager, "_restore_pointer", lambda _: (_ for _ in ()).throw(OSError("CANARY"))
    )

    with pytest.raises(BundleActivationError):
        manager.activate(candidate_b)

    assert not (
        tmp_path / "data" / "bundles" / "validated" / candidate_b.manifest.bundle_id
    ).exists()
    restarted = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=RuntimeDatabase(tmp_path / "runtime"),
        expected_embedding=provider.identity(),
    )
    assert restarted.status().active_bundle_id == candidate_a.manifest.bundle_id
