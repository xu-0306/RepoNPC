"""Measure passage-vector reuse around failed analysis generation and restart."""

from __future__ import annotations

import json
import sqlite3
import tarfile
import threading
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from reponpc.admin.onboarding import GuidedOnboardingError, GuidedOnboardingService
from reponpc.chat.limits import ChatLimits
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.passage_cache import PassageVectorCache
from reponpc.indexing.pipeline import build_index_bundle
from reponpc.indexing.sources import EmbeddingIdentity, RepositoryBlob, ResolvedRepository
from reponpc.main import create_app
from reponpc.providers.contracts import (
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
)
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_index_build import (
    FIXTURE_CONFIG,
    DeterministicEmbeddingProvider,
    _configuration_source,
)


class CountingEmbedding:
    """Deterministic local provider that records real passage work."""

    def __init__(self) -> None:
        self.passage_batches: list[list[str]] = []
        self.query_batches: list[list[str]] = []
        self._identity = EmbeddingIdentity(
            adapter="ollama",
            model_id="fixture-model",
            dimension=3,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        self.passage_batches.append(list(texts))
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def embed_query(self, texts: list[str]) -> np.ndarray:
        self.query_batches.append(list(texts))
        return np.tile(np.asarray([[1.0, 0.0, 0.0]], dtype=np.float32), (len(texts), 1))

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-09-27T00:00:00Z")


class FailingChat:
    """Fail only at generation, after source/index/query work has run."""

    def __init__(self) -> None:
        self.calls = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(False, True, True, True, True, 32768, 8192)

    def generate(self, messages, response_schema, max_output_tokens, timeout):
        del messages, response_schema, max_output_tokens, timeout
        self.calls += 1
        raise ProviderError(ProviderFailureCode.UNAVAILABLE)

    def health(self) -> ProviderHealth:
        return ProviderHealth(True, "2026-09-27T00:00:00Z")


class CountingResolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(
        self,
        *,
        slug: str,
        ref: str | None,
        cancel_requested=None,
        deadline=None,
    ) -> ResolvedRepository:
        del ref, cancel_requested, deadline
        self.calls += 1
        content = b"# Demo\n\nA safe architecture overview.\n"
        return ResolvedRepository(
            slug=slug,
            commit_sha="a" * 40,
            default_branch="main",
            github_html_url=f"https://github.com/{slug}",
            blobs=(
                RepositoryBlob(
                    path="README.md",
                    entry_kind=SourceEntryKind.REGULAR_FILE,
                    size_bytes=len(content),
                    content=content,
                ),
            ),
        )


def _service(
    tmp_path: Path,
    resolver: CountingResolver,
    embedding: CountingEmbedding,
    chat: FailingChat,
    *,
    runtime_name: str,
) -> GuidedOnboardingService:
    database = RuntimeDatabase(tmp_path / runtime_name)
    database.initialize()
    limits = ChatLimits(
        database,
        ip_hash_key=b"fixture-analysis-cache-key",
        requests_per_minute=10,
        daily_budget=10,
        global_concurrency=1,
    )
    providers = ProviderRuntime(
        chat=chat,
        embedding=embedding,
        max_attempts=1,
    )
    return GuidedOnboardingService(
        source_resolver=resolver,  # type: ignore[arg-type]
        providers_supplier=lambda: providers,
        limits_supplier=lambda: limits,
        staging_root=tmp_path / "staging",
        provider_timeout_seconds=45,
    )


def _failed_analysis(service: GuidedOnboardingService) -> None:
    with pytest.raises(GuidedOnboardingError) as error:
        service.analyze_repository(
            session_hash="session-a",
            slug="octocat/demo",
            ref=None,
            include=(),
            exclude=(),
            cancel_requested=threading.Event(),
        )
    assert error.value.code == "MODEL_UNAVAILABLE"


def _passage_work(provider: CountingEmbedding) -> int:
    return sum(len(batch) for batch in provider.passage_batches)


def _passage_cache_files(tmp_path: Path) -> list[Path]:
    return sorted((tmp_path / "passage-cache").glob("*.json"))


def test_failed_analysis_reuses_passage_vectors_after_retry_and_restart(
    tmp_path: Path,
) -> None:
    """Measure cache reuse without claiming that the transient index is reused."""

    resolver = CountingResolver()
    first_embedding = CountingEmbedding()
    first_chat = FailingChat()
    service = _service(
        tmp_path,
        resolver,
        first_embedding,
        first_chat,
        runtime_name="runtime-first",
    )

    _failed_analysis(service)
    cold_passage_work = _passage_work(first_embedding)
    assert cold_passage_work > 0
    assert len(first_embedding.passage_batches) > 0
    assert len(first_embedding.query_batches) == 1
    assert first_chat.calls == 1
    assert resolver.calls == 1

    _failed_analysis(service)
    assert _passage_work(first_embedding) == cold_passage_work
    assert len(first_embedding.passage_batches) == 1
    assert len(first_embedding.query_batches) == 2
    assert first_chat.calls == 2
    assert resolver.calls == 2

    restarted_embedding = CountingEmbedding()
    restarted_chat = FailingChat()
    restarted = _service(
        tmp_path,
        resolver,
        restarted_embedding,
        restarted_chat,
        runtime_name="runtime-restarted",
    )

    _failed_analysis(restarted)
    assert _passage_work(restarted_embedding) == 0
    assert restarted_embedding.passage_batches == []
    assert len(restarted_embedding.query_batches) == 1
    assert restarted_chat.calls == 1
    assert resolver.calls == 3


def test_corrupted_passage_entry_is_reembedded_after_restart(tmp_path: Path) -> None:
    resolver = CountingResolver()
    cold_embedding = CountingEmbedding()
    cold = _service(
        tmp_path,
        resolver,
        cold_embedding,
        FailingChat(),
        runtime_name="runtime-cold",
    )

    _failed_analysis(cold)
    cache_files = _passage_cache_files(tmp_path)
    assert len(cache_files) == _passage_work(cold_embedding) == 4

    corrupted = cache_files[0]
    payload = json.loads(corrupted.read_text(encoding="utf-8"))
    original_checksum = payload["payload_sha256"]
    payload["payload_sha256"] = ("0" if original_checksum[0] != "0" else "1") + original_checksum[
        1:
    ]
    corrupted.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    restarted_embedding = CountingEmbedding()
    restarted = _service(
        tmp_path,
        resolver,
        restarted_embedding,
        FailingChat(),
        runtime_name="runtime-restarted",
    )

    _failed_analysis(restarted)
    assert len(restarted_embedding.passage_batches) == 1
    assert _passage_work(restarted_embedding) == 1
    assert len(_passage_cache_files(tmp_path)) == len(cache_files)
    assert resolver.calls == 2


def test_passage_cache_is_unreachable_from_public_routes(tmp_path: Path) -> None:
    resolver = CountingResolver()
    embedding = CountingEmbedding()
    service = _service(
        tmp_path,
        resolver,
        embedding,
        FailingChat(),
        runtime_name="runtime-routes",
    )
    _failed_analysis(service)
    cache_file = _passage_cache_files(tmp_path)[0]

    web_dist = tmp_path / "web"
    web_dist.mkdir()
    (web_dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    app = create_app(
        web_dist=web_dist,
        runtime_database=RuntimeDatabase(tmp_path / "runtime-routes"),
    )
    with TestClient(app) as client:
        for route in (
            f"/passage-cache/{cache_file.name}",
            f"/api/public/passage-cache/{cache_file.name}",
            f"/public/passage-cache/{cache_file.name}",
        ):
            response = client.get(route)
            assert response.status_code == 404
            assert cache_file.read_text(encoding="utf-8") not in response.text


def test_passage_cache_is_excluded_from_bundle_export(tmp_path: Path) -> None:
    cache_root = tmp_path / "passage-cache"
    resolver = CountingResolver()
    embedding = CountingEmbedding()
    service = _service(
        tmp_path,
        resolver,
        embedding,
        FailingChat(),
        runtime_name="runtime-export",
    )
    _failed_analysis(service)
    cache_file = _passage_cache_files(tmp_path)[0]

    bundle = build_index_bundle(
        FIXTURE_CONFIG,
        tmp_path / "export",
        resolver=resolver,
        embedding_provider=DeterministicEmbeddingProvider(),
        configuration_source=_configuration_source(),
        passage_cache=PassageVectorCache(cache_root),
    )
    with tarfile.open(bundle.archive_path, "r:zst") as archive:
        names = archive.getnames()
    assert all("passage-cache" not in name for name in names)
    assert cache_file.name not in names
    assert "index.sqlite" in names
    assert "public/profile.json" in names


def test_passage_cache_is_excluded_from_runtime_sqlite_backup(tmp_path: Path) -> None:
    resolver = CountingResolver()
    embedding = CountingEmbedding()
    service = _service(
        tmp_path,
        resolver,
        embedding,
        FailingChat(),
        runtime_name="runtime-backup",
    )
    _failed_analysis(service)
    cache_files = _passage_cache_files(tmp_path)
    assert cache_files

    database = RuntimeDatabase(tmp_path / "runtime-backup")
    destination = tmp_path / "backups" / "runtime.sqlite"
    destination.parent.mkdir()
    database.backup_to(destination)

    assert destination.is_file()
    assert destination.parent.joinpath("passage-cache").exists() is False
    with sqlite3.connect(destination) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    backup_bytes = destination.read_bytes()
    assert all(cache_file.name.encode() not in backup_bytes for cache_file in cache_files)
