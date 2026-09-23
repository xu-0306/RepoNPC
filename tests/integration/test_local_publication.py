from __future__ import annotations

import base64
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from reponpc.admin.embedding_reindex import EmbeddingReindexCoordinator
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.local_publication import LocalPortfolioBuilder, LocalPublication
from reponpc.main import create_app
from tests.integration.test_bundle_producer_consumer import _fixture_snapshot
from tests.integration.test_embedding_reindex import _profile, _system
from tests.integration.test_index_build import FIXTURE_CONFIG
from tests.security.test_admin_writeback import ORIGIN, _application_without_github, _login, _sprite


class FixtureResolver:
    def resolve(self, **kwargs):
        assert kwargs["slug"] == _fixture_snapshot().slug
        return _fixture_snapshot()


def test_local_build_reuses_vectors_and_serves_truthful_assertion_citations(tmp_path: Path):
    _database, providers, manager, registry, _, transition = _system(tmp_path)
    provider = providers["a"]
    calls = []
    original = provider.embed_passages

    def count(texts):
        calls.extend(texts)
        return original(texts)

    provider.embed_passages = count
    profile = registry.create(_profile(provider))
    profile = registry.probe(profile.profile_id)
    store = LocalPortfolioStore(tmp_path / "data")
    draft = store.save(
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    builder = LocalPortfolioBuilder(
        draft,
        data_directory=tmp_path / "data",
        resolver=FixtureResolver(),
        max_bundle_bytes=10 * 1024 * 1024,
    )
    coordinator = EmbeddingReindexCoordinator(
        registry=registry, manager=manager, builder=builder, provider_transition=transition
    )
    completed = []
    try:
        coordinator.queue(
            profile.profile_id, force=True, on_finished=lambda b, e: completed.append((b, e))
        )
        activated = coordinator.wait(profile.profile_id, timeout=30)
        assert activated.active and completed[-1][1] is None
        first = manager.status().active_bundle_id
        initial_calls = len(calls)
        changed = store.save(
            content=draft.content.replace("revision: 0", "revision: 1"),
            sprite_base64=None,
            expected_revision=draft.revision,
        )
        assert changed.revision != draft.revision
        updated_builder = LocalPortfolioBuilder(
            changed,
            data_directory=tmp_path / "data",
            resolver=FixtureResolver(),
            max_bundle_bytes=10 * 1024 * 1024,
        )
        coordinator.queue(
            profile.profile_id,
            force=True,
            builder=updated_builder,
            on_finished=lambda b, e: completed.append((b, e)),
        )
        coordinator.wait(profile.profile_id, timeout=30)
        assert len(calls) == initial_calls
        assert manager.status().active_bundle_id != first
        assert manager.status().previous_bundle_id == first
        with manager.acquire() as index:
            rows = [index.evidence(eid) for eid in index.vectors.evidence_ids]
            assertion = next(row for row in rows if row.evidence_class == "OWNER_ASSERTION")
            fact = next(row for row in rows if row.evidence_class == "REPOSITORY_FACT")
        assert assertion.github_permalink.startswith("/api/public/owner-statements/")
        assert fact.github_permalink.startswith("https://github.com/")
        app = create_app(bundle_manager=manager)
        with TestClient(app) as client:
            response = client.get(assertion.github_permalink)
            assert response.status_code == 200
            assert assertion.content in response.text
            assert response.headers["content-type"].startswith("text/plain")
            assert (
                client.get(
                    assertion.github_permalink.replace(assertion.commit_sha, "0" * 40)
                ).status_code
                == 404
            )
        retained = manager.status()

        def broken(*args):
            raise RuntimeError("private upstream body must never appear")

        coordinator.queue(
            profile.profile_id,
            force=True,
            builder=broken,
            on_finished=lambda b, e: completed.append((b, e)),
        )
        coordinator.wait(profile.profile_id, timeout=30)
        assert completed[-1] == (None, "EMBEDDING_REINDEX_FAILED")
        assert manager.status() == retained
        assert registry.get(profile.profile_id).active
    finally:
        coordinator.shutdown()


def test_local_publication_receipt_recovers_interruption(tmp_path: Path):
    _database, _providers, manager, registry, _, transition = _system(tmp_path)
    store = LocalPortfolioStore(tmp_path / "data")
    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=lambda *args: None,
        provider_transition=transition,
    )
    try:
        publication = LocalPublication(
            store=store,
            data_directory=tmp_path / "data",
            coordinator=coordinator,
            registry=registry,
            manager=manager,
            resolver=FixtureResolver(),
            max_bundle_bytes=10 * 1024 * 1024,
            transition_factory=lambda _: transition,
            stop_remote=lambda: None,
        )
        publication.job = {"state": "preparing", "revision": "f" * 64}
        publication._persist()
        recovered = LocalPublication(
            store=store,
            data_directory=tmp_path / "data",
            coordinator=coordinator,
            registry=registry,
            manager=manager,
            resolver=FixtureResolver(),
            max_bundle_bytes=10 * 1024 * 1024,
            transition_factory=lambda _: transition,
            stop_remote=lambda: None,
        )
        assert recovered.status()["error_code"] == "EMBEDDING_REINDEX_INTERRUPTED"
        assert recovered.status()["index_ready"] is False
    finally:
        coordinator.shutdown()


def test_status_does_not_call_a_rolled_back_draft_applied(tmp_path: Path):
    from types import SimpleNamespace

    store = LocalPortfolioStore(tmp_path)
    draft = store.save(
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    active = ["current"]
    publication = LocalPublication(
        store=store,
        data_directory=tmp_path,
        coordinator=None,
        registry=None,
        manager=SimpleNamespace(status=lambda: SimpleNamespace(active_bundle_id=active[0])),
        resolver=None,
        max_bundle_bytes=1024,
        transition_factory=lambda _: None,
        stop_remote=lambda: None,
    )
    publication.job = {"state": "ready", "revision": draft.revision, "bundle_id": "current"}
    assert publication.status()["draft_changed"] is False
    active[0] = "previous"
    assert publication.status()["index_ready"] is True
    assert publication.status()["draft_changed"] is True
    active[0] = None
    assert publication.status()["draft_changed"] is True


def test_protected_local_save_character_preview_and_conflict_without_github(tmp_path: Path):
    app = _application_without_github(tmp_path)
    app.state.admin_operations = replace(
        app.state.admin_operations, local_portfolio=LocalPortfolioStore(tmp_path)
    )
    body = {"content": FIXTURE_CONFIG.read_text(encoding="utf-8"), "expected_revision": None}
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/api/admin/portfolio", headers={"Origin": ORIGIN}).status_code == 401
        token = _login(client)
        headers = {"Origin": ORIGIN, "X-CSRF-Token": token}
        assert (
            client.put("/api/admin/portfolio", headers={"Origin": ORIGIN}, json=body).status_code
            == 403
        )
        assert (
            client.put(
                "/api/admin/portfolio",
                headers={**headers, "Origin": "https://evil.example"},
                json=body,
            ).status_code
            == 403
        )
        saved = client.put("/api/admin/portfolio", headers=headers, json=body)
        assert saved.status_code == 200
        revision = saved.json()["revision"]
        assert client.put("/api/admin/portfolio", headers=headers, json=body).status_code == 409
        assert client.get("/api/admin/portfolio", headers=headers).json()["revision"] == revision
        applied = client.post(
            "/api/admin/portfolio/character",
            headers=headers,
            json={**body, "sprite_base64": base64.b64encode(_sprite()).decode("ascii")},
        )
        assert applied.status_code == 200
        content = applied.json()["content"]
        assert "mode: custom" in content
        preview = client.post(
            "/api/admin/portfolio/preview",
            headers=headers,
            json={"content": content, "sprite_base64": applied.json()["sprite_base64"]},
        )
        assert preview.status_code == 200
        assert preview.json()["character"]["mode"] == "custom"
        assert preview.json()["cards"]["light-zh-TW"]["gif_base64"]
        assert preview.headers["cache-control"] == "no-store"
        assert client.get("/api/admin/portfolio", headers=headers).json()["revision"] == revision


def test_local_archive_resolver_pins_snapshot_and_stops_before_fetch():
    import time
    from types import SimpleNamespace

    import pytest

    from reponpc.admin.batch_resolver import (
        BatchCapacity,
        BatchResolverError,
        MetadataResolution,
        ResolutionBlocker,
    )
    from reponpc.admin.batches import BatchStageGates
    from reponpc.admin.embedding_reindex import ReindexCancelled
    from reponpc.admin.local_publication import LocalArchiveResolver

    calls = []
    repository = _fixture_snapshot()

    class Metadata:
        result = MetadataResolution((repository,), ())

        def resolve_all(self, *, selections):
            calls.append(selections[0])
            return self.result

    def fetch(**kwargs):
        assert kwargs["repository"].commit_sha == repository.commit_sha
        assert not kwargs["cancel_requested"]()
        return repository

    metadata = Metadata()
    resolver = LocalArchiveResolver(
        metadata, SimpleNamespace(fetch=fetch), BatchStageGates(BatchCapacity(1, 1, 1, 1, 1))
    )
    assert (
        resolver.resolve(slug=repository.slug, ref="release", deadline=time.monotonic() + 10)
        is repository
    )
    assert calls[0].ref == "release"
    with pytest.raises(ReindexCancelled):
        resolver.resolve(slug=repository.slug, ref=None, cancel_requested=lambda: True)
    assert len(calls) == 1
    metadata.result = MetadataResolution(
        (), (ResolutionBlocker(repository.slug, "GITHUB_RATE_LIMITED"),)
    )
    with pytest.raises(BatchResolverError) as error:
        resolver.resolve(slug=repository.slug, ref=None)
    assert error.value.code == "GITHUB_RATE_LIMITED"


def test_local_embedding_cancellation_checks_after_inflight_batch():
    import time

    import pytest

    from reponpc.admin.embedding_reindex import ReindexCancelled, ReindexTimedOut
    from reponpc.admin.local_publication import _BoundedEmbeddingProvider
    from tests.integration.test_index_build import DeterministicEmbeddingProvider

    provider = DeterministicEmbeddingProvider()
    cancelled = [False]
    original = provider.embed_passages

    def finish_then_cancel(texts):
        result = original(texts)
        cancelled[0] = True
        return result

    provider.embed_passages = finish_then_cancel
    bounded = _BoundedEmbeddingProvider(provider, lambda: cancelled[0], time.monotonic() + 20)
    with pytest.raises(ReindexCancelled):
        bounded.embed_passages(["public passage"])
    with pytest.raises(ReindexTimedOut):
        _BoundedEmbeddingProvider(provider, lambda: False, time.monotonic() - 1).embed_query(
            ["question"]
        )


def test_local_bundle_does_not_require_fixture_topic_and_restores(tmp_path):
    import re
    import time

    from reponpc.bundles.archive import verify_retained_bundle_directory
    from tests.integration.test_embedding_reindex import RuntimeFixtureEmbedding

    provider = RuntimeFixtureEmbedding("catalog")
    snapshot = _fixture_snapshot()

    def replace_word(text):
        return re.sub("retrieval", "catalogue", text, flags=re.IGNORECASE)

    snapshot = replace(
        snapshot,
        blobs=tuple(
            replace(
                blob,
                path=replace_word(blob.path),
                content=(
                    re.sub(b"retrieval", b"catalogue", blob.content, flags=re.IGNORECASE)
                    if blob.content
                    else blob.content
                ),
            )
            for blob in snapshot.blobs
        ),
    )

    class Resolver:
        def resolve(self, **kwargs):
            return snapshot

    draft = LocalPortfolioStore(tmp_path).save(
        content=replace_word(FIXTURE_CONFIG.read_text(encoding="utf-8")).replace(
            "\ncatalogue:", "\nretrieval:"
        ),
        sprite_base64=None,
        expected_revision=None,
    )

    class Profile:
        identity = provider.identity()
        dimension = provider.identity().dimension

    candidate = LocalPortfolioBuilder(
        draft, data_directory=tmp_path, resolver=Resolver(), max_bundle_bytes=10 * 1024 * 1024
    )(Profile(), provider, lambda: False, time.monotonic() + 30)
    directory = candidate.verified.directory
    assert candidate.verified.index.lexical_candidates("retrieval", limit=1) == []
    assert candidate.verified.index.lexical_smoke_test()
    candidate.verified.close()
    restored = verify_retained_bundle_directory(
        directory=directory, expected_embedding=provider.identity()
    )
    assert restored.index.lexical_smoke_test()
    restored.close()
