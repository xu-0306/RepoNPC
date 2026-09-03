"""Frozen-profile reindex, switch rollback, cancellation, and restart recovery."""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileInput,
    EmbeddingProfileRegistry,
)
from reponpc.admin.embedding_reindex import (
    EmbeddingReindexCoordinator,
    ProductionFrozenProfileBuilder,
    ReindexCandidate,
    ReindexTimedOut,
)
from reponpc.bundles.archive import build_bundle, verify_bundle_archive
from reponpc.bundles.manager import ActivationTransition, BundleManager
from reponpc.bundles.manifest import bundle_id_for
from reponpc.config.models import load_public_config
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.sources import EmbeddingIdentity, RepositoryBlob, ResolvedRepository
from reponpc.providers import ProviderHealth
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_bundle_producer_consumer import (
    _configuration_source,
    _fixture_snapshot,
    _public_files,
)
from tests.integration.test_index_build import FIXTURE_CONFIG


class RuntimeFixtureEmbedding:
    def __init__(self, model_id: str, dimension: int = 8) -> None:
        self._identity = EmbeddingIdentity(
            adapter="ollama",
            model_id=model_id,
            dimension=dimension,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_query(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        return self._embed(texts, self._identity.query_prefix)

    def embed_passages(self, texts: list[str]) -> np.ndarray[Any, np.dtype[np.float32]]:
        return self._embed(texts, self._identity.passage_prefix)

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-09-01T00:00:00Z")

    def _embed(self, texts: list[str], prefix: str) -> np.ndarray[Any, np.dtype[np.float32]]:
        result = np.zeros((len(texts), self._identity.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            digest = hashlib.sha256((prefix + text).encode()).digest()
            result[row, int.from_bytes(digest[:2], "big") % self._identity.dimension] = 1.0
        return result


def _profile(provider: RuntimeFixtureEmbedding) -> EmbeddingProfileInput:
    identity = provider.identity()
    return EmbeddingProfileInput(
        provider="ollama",
        model_id=identity.model_id,
        dimension=identity.dimension,
        normalized=True,
        query_prefix=identity.query_prefix,
        passage_prefix=identity.passage_prefix,
        connection_reference="environment",
    )


def _candidate(
    root: Path,
    profile: EmbeddingProfile,
    provider: RuntimeFixtureEmbedding,
    ordinal: int,
) -> ReindexCandidate:
    workspace = root / f"workspace-{ordinal}"
    workspace.mkdir()
    config = load_public_config(FIXTURE_CONFIG)
    identity = provider.identity()
    config = config.model_copy(
        update={
            "retrieval": config.retrieval.model_copy(
                update={
                    "embedding": config.retrieval.embedding.model_copy(
                        update={
                            "adapter": identity.adapter,
                            "model": identity.model_id,
                            "dimension": identity.dimension,
                            "normalized": identity.normalized,
                            "query_prefix": identity.query_prefix,
                            "passage_prefix": identity.passage_prefix,
                        }
                    )
                }
            )
        }
    )
    source = _configuration_source()
    snapshot = _fixture_snapshot()
    result = IndexDatabaseBuilder(provider).build(
        config=config,
        configuration_source=source,
        repositories=(snapshot,),
        output_path=workspace / "index.sqlite",
    )
    built_at = datetime(2026, 9, 1, 0, ordinal, tzinfo=UTC)
    bundle_id = bundle_id_for(
        built_at=built_at,
        configuration_bytes=source.content.encode(),
        repositories=((snapshot.slug, snapshot.commit_sha),),
        embedding=identity,
        parser_chunker_version="p2-02-v1",
    )
    bundle = build_bundle(
        index_result=result,
        configuration_source=source,
        repositories=(snapshot,),
        bundle_id=bundle_id,
        built_at=built_at,
        public_files=_public_files(
            bundle_id=bundle_id,
            built_at=built_at,
            repository_count=result.repository_count,
        ),
        output_path=workspace / f"reponpc-index-{bundle_id}.tar.zst",
    )
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=workspace / "candidate",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=profile.identity,
        max_bundle_bytes=1024 * 1024,
    )
    return ReindexCandidate(verified=verified, workspace=workspace)


def _system(tmp_path: Path):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    providers = {
        "a": RuntimeFixtureEmbedding("a"),
        "b": RuntimeFixtureEmbedding("b"),
        "c": RuntimeFixtureEmbedding("c"),
    }
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=database,
        expected_embedding=providers["a"].identity(),
    )
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda profile: providers.get(profile.model_id),
        activation_compatible=lambda profile: (
            manager.active_embedding_identity() == profile.identity
        ),
    )
    selected: dict[str, RuntimeFixtureEmbedding] = {"provider": providers["a"]}

    def transition(profile: EmbeddingProfile, provider: Any):
        del profile
        previous = selected["provider"]
        selected["provider"] = provider

        def rollback() -> None:
            selected["provider"] = previous

        return rollback

    return database, providers, manager, registry, selected, transition


def test_reindex_switches_profile_bundle_and_provider_and_restart_recovers(
    tmp_path: Path,
) -> None:
    database, providers, manager, registry, selected, transition = _system(tmp_path)
    counter = 0

    def builder(profile, provider, cancel_requested, deadline):
        nonlocal counter
        del cancel_requested, deadline
        counter += 1
        return _candidate(tmp_path, profile, provider, counter)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        queued_a = coordinator.queue(profile_a.profile_id)
        assert queued_a.status == "reindexing"
        active_a = coordinator.wait(profile_a.profile_id, timeout=10)
        bundle_a = manager.status().active_bundle_id
        assert active_a.active and active_a.status == "ready" and bundle_a

        profile_b = registry.create(_profile(providers["b"]))
        coordinator.queue(profile_b.profile_id)
        active_b = coordinator.wait(profile_b.profile_id, timeout=10)
        bundle_b = manager.status().active_bundle_id
        assert active_b.active and active_b.bundle_id == bundle_b
        assert bundle_b != bundle_a
        assert manager.status().previous_bundle_id == bundle_a
        assert selected["provider"] is providers["b"]
        assert not registry.get(profile_a.profile_id).active
        with database.connection() as connection:
            intent_count = connection.execute(
                "SELECT COUNT(*) FROM embedding_switch_intent"
            ).fetchone()[0]
            assert intent_count == 0

        restarted = BundleManager(
            data_directory=tmp_path / "data",
            runtime_database=RuntimeDatabase(tmp_path / "runtime"),
            expected_embedding=providers["a"].identity(),
        )
        registry.reconcile_active_bundle(
            restarted.active_embedding_identity(), restarted.status().active_bundle_id
        )
        assert restarted.status().active_bundle_id == bundle_b
        assert registry.active() is not None
        assert registry.active().profile_id == profile_b.profile_id  # type: ignore[union-attr]
    finally:
        coordinator.shutdown()


def test_activation_persistence_failure_rolls_back_profile_provider_and_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, providers, manager, registry, selected, transition = _system(tmp_path)
    counter = 0

    def builder(profile, provider, cancel_requested, deadline):
        nonlocal counter
        del cancel_requested, deadline
        counter += 1
        return _candidate(tmp_path, profile, provider, counter)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        coordinator.queue(profile_a.profile_id)
        coordinator.wait(profile_a.profile_id, timeout=10)
        prior_bundle = manager.status().active_bundle_id
        profile_b = registry.create(_profile(providers["b"]))
        monkeypatch.setattr(
            database,
            "save_bundle_state",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("CANARY")),
        )
        coordinator.queue(profile_b.profile_id)
        failed = coordinator.wait(profile_b.profile_id, timeout=10)
        assert failed.status == "reindex_required"
        assert failed.last_error_code == "EMBEDDING_ACTIVATION_FAILED"
        assert manager.status().active_bundle_id == prior_bundle
        assert registry.active().profile_id == profile_a.profile_id  # type: ignore[union-attr]
        assert selected["provider"] is providers["a"]
        with database.connection() as connection:
            intent_count = connection.execute(
                "SELECT COUNT(*) FROM embedding_switch_intent"
            ).fetchone()[0]
            assert intent_count == 0
    finally:
        coordinator.shutdown()


def test_cancelled_reindex_cleans_staging_and_preserves_last_known_good(
    tmp_path: Path,
) -> None:
    _database, providers, manager, registry, selected, transition = _system(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def first_builder(profile, provider, cancel_requested, deadline):
        del cancel_requested, deadline
        return _candidate(tmp_path, profile, provider, 1)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=first_builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        coordinator.queue(profile_a.profile_id)
        coordinator.wait(profile_a.profile_id, timeout=10)
        prior_bundle = manager.status().active_bundle_id

        def blocking_builder(profile, provider, cancel_requested, deadline):
            entered.set()
            assert release.wait(timeout=5)
            if cancel_requested():
                from reponpc.admin.embedding_reindex import ReindexCancelled

                raise ReindexCancelled
            return _candidate(tmp_path, profile, provider, 2)

        coordinator._builder = blocking_builder
        profile_b = registry.create(_profile(providers["b"]))
        coordinator.queue(profile_b.profile_id)
        assert entered.wait(timeout=5)
        assert coordinator.cancel(profile_b.profile_id)
        release.set()
        cancelled = coordinator.wait(profile_b.profile_id, timeout=10)
        assert cancelled.status == "reindex_required"
        assert cancelled.last_error_code == "EMBEDDING_REINDEX_CANCELLED"
        assert manager.status().active_bundle_id == prior_bundle
        assert registry.active().profile_id == profile_a.profile_id  # type: ignore[union-attr]
        assert selected["provider"] is providers["a"]
    finally:
        release.set()
        coordinator.shutdown()


def test_timed_out_reindex_preserves_last_known_good(tmp_path: Path) -> None:
    _database, providers, manager, registry, selected, transition = _system(tmp_path)

    def first_builder(profile, provider, cancel_requested, deadline):
        del cancel_requested, deadline
        return _candidate(tmp_path, profile, provider, 1)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=first_builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        coordinator.queue(profile_a.profile_id)
        coordinator.wait(profile_a.profile_id, timeout=10)
        prior_bundle = manager.status().active_bundle_id

        def timeout_builder(profile, provider, cancel_requested, deadline):
            del profile, provider, cancel_requested, deadline
            raise ReindexTimedOut

        coordinator._builder = timeout_builder
        profile_b = registry.create(_profile(providers["b"]))
        coordinator.queue(profile_b.profile_id)
        timed_out = coordinator.wait(profile_b.profile_id, timeout=10)
        assert timed_out.status == "reindex_required"
        assert timed_out.last_error_code == "EMBEDDING_REINDEX_TIMEOUT"
        assert manager.status().active_bundle_id == prior_bundle
        assert registry.active().profile_id == profile_a.profile_id  # type: ignore[union-attr]
        assert selected["provider"] is providers["a"]
    finally:
        coordinator.shutdown()


def test_restart_repairs_crash_before_pointer_swap_from_durable_intent(tmp_path: Path) -> None:
    database, providers, manager, registry, _selected, transition = _system(tmp_path)

    def builder(profile, provider, cancel_requested, deadline):
        del cancel_requested, deadline
        return _candidate(tmp_path, profile, provider, 1)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        coordinator.queue(profile_a.profile_id)
        coordinator.wait(profile_a.profile_id, timeout=10)
        bundle_a = manager.status().active_bundle_id
        assert bundle_a is not None

        profile_b = registry.create(_profile(providers["b"]))
        registry.probe(profile_b.profile_id)
        frozen_b = registry.begin_reindex(profile_b.profile_id)
        uncommitted_bundle_b = "20260901T000200Z-000000000000"
        registry.activate_reindexed(
            frozen_b.profile_id,
            frozen_b.reindex_generation,
            uncommitted_bundle_b,
        )

        restarted = BundleManager(
            data_directory=tmp_path / "data",
            runtime_database=RuntimeDatabase(tmp_path / "runtime"),
            expected_embedding=providers["b"].identity(),
        )
        registry.reconcile_active_bundle(
            restarted.active_embedding_identity(), restarted.status().active_bundle_id
        )

        assert restarted.status().active_bundle_id == bundle_a
        assert registry.active().profile_id == profile_a.profile_id  # type: ignore[union-attr]
        with database.connection() as connection:
            intent_count = connection.execute(
                "SELECT COUNT(*) FROM embedding_switch_intent"
            ).fetchone()[0]
            assert intent_count == 0
    finally:
        coordinator.shutdown()


def test_restart_completes_crash_after_pointer_and_bundle_state(tmp_path: Path) -> None:
    database, providers, manager, registry, _selected, transition = _system(tmp_path)

    def builder(profile, provider, cancel_requested, deadline):
        del cancel_requested, deadline
        return _candidate(tmp_path, profile, provider, 1)

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=builder,
        provider_transition=transition,
    )
    try:
        profile_a = registry.create(_profile(providers["a"]))
        coordinator.queue(profile_a.profile_id)
        coordinator.wait(profile_a.profile_id, timeout=10)

        profile_b = registry.create(_profile(providers["b"]))
        registry.probe(profile_b.profile_id)
        frozen_b = registry.begin_reindex(profile_b.profile_id)
        candidate_b = _candidate(tmp_path, frozen_b, providers["b"], 2)
        bundle_b = candidate_b.verified.manifest.bundle_id

        def crash_transition() -> ActivationTransition:
            profile_transition = registry.activate_reindexed(
                frozen_b.profile_id,
                frozen_b.reindex_generation,
                bundle_b,
            )

            def crash() -> None:
                raise SystemExit("injected crash")

            return ActivationTransition(rollback=profile_transition.rollback, commit=crash)

        with pytest.raises(SystemExit, match="injected crash"):
            manager.activate(
                candidate_b.verified,
                expected_embedding=frozen_b.identity,
                state_transition=crash_transition,
            )

        restarted = BundleManager(
            data_directory=tmp_path / "data",
            runtime_database=RuntimeDatabase(tmp_path / "runtime"),
            expected_embedding=providers["a"].identity(),
        )
        registry.reconcile_active_bundle(
            restarted.active_embedding_identity(), restarted.status().active_bundle_id
        )

        assert restarted.status().active_bundle_id == bundle_b
        assert registry.active().profile_id == profile_b.profile_id  # type: ignore[union-attr]
        with database.connection() as connection:
            intent_count = connection.execute(
                "SELECT COUNT(*) FROM embedding_switch_intent"
            ).fetchone()[0]
            assert intent_count == 0
    finally:
        coordinator.shutdown()


def test_production_builder_uses_frozen_profile_over_public_yaml_embedding(
    tmp_path: Path,
) -> None:
    provider = RuntimeFixtureEmbedding("external-model")
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    registry = EmbeddingProfileRegistry(
        database=database,
        provider_resolver=lambda _profile: provider,
        activation_compatible=lambda _profile: False,
    )
    profile = registry.create(_profile(provider))
    profile = registry.probe(profile.profile_id)
    config_bytes = FIXTURE_CONFIG.read_bytes()
    config_snapshot = ResolvedRepository(
        slug="config-owner/profile",
        commit_sha="b" * 40,
        default_branch="main",
        github_html_url="https://github.com/config-owner/profile",
        blobs=(
            RepositoryBlob(
                path="reponpc.yml",
                entry_kind=SourceEntryKind.REGULAR_FILE,
                size_bytes=len(config_bytes),
                content=config_bytes,
            ),
        ),
    )
    repository_snapshot = _fixture_snapshot()

    class Resolver:
        def resolve(
            self,
            *,
            slug: str,
            ref: str | None,
            cancel_requested=None,
            deadline=None,
        ) -> ResolvedRepository:
            del ref, cancel_requested, deadline
            if slug == config_snapshot.slug:
                return config_snapshot
            assert slug == repository_snapshot.slug
            return repository_snapshot

    builder = ProductionFrozenProfileBuilder(
        data_directory=tmp_path / "data",
        config_repository=config_snapshot.slug,
        config_branch="main",
        github_api_url="https://api.github.com",
        max_bundle_bytes=8 * 1024 * 1024,
        source_resolver=Resolver(),  # type: ignore[arg-type]
    )

    candidate = builder(profile, provider, lambda: False, float("inf"))
    try:
        assert candidate.verified.manifest.embedding == profile.identity
        assert candidate.verified.manifest.config_sha256 == hashlib.sha256(config_bytes).hexdigest()
        assert candidate.verified.index.embedding == profile.identity
    finally:
        candidate.verified.close()
