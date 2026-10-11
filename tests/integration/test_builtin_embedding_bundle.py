"""Built-in inference crosses the real bundle producer/consumer boundaries.

The tokenizer is a saved local synthetic fixture and the ONNX session is an
explicit test double. These tests establish contracts, not model quality.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from reponpc.bundles.archive import BuiltBundle, BundleError, verify_bundle_archive
from reponpc.bundles.index_reader import IndexReadError, ReadOnlyIndex
from reponpc.config.models import EmbeddingConfig, load_public_config
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.pipeline import BUILD_RECEIPT_NAME, build_index_bundle
from reponpc.providers import BuiltinOnnxEmbeddingProvider, ProviderError, ProviderFailureCode
from reponpc.providers.builtin_artifacts import BuiltinArtifactError, builtin_embedding_identity
from tests.integration.test_cli import FixtureResolver, _write_public_assets
from tests.integration.test_index_build import (
    FIXTURE_CONFIG,
    _configuration_source,
    _fixture_snapshot,
)
from tests.unit.test_builtin_onnx import Session, tokenizer


def _config_path(tmp_path: Path) -> Path:
    identity = builtin_embedding_identity()
    embedding = EmbeddingConfig(
        adapter="builtin_onnx",
        model=identity.model_id,
        dimension=identity.dimension,
        normalized=True,
        query_prefix=identity.query_prefix,
        passage_prefix=identity.passage_prefix,
    )
    raw = yaml.safe_load(FIXTURE_CONFIG.read_text(encoding="utf-8"))
    raw["retrieval"]["embedding"] = embedding.model_dump(mode="json")
    path = tmp_path / "reponpc.yml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert load_public_config(path).retrieval.embedding == embedding
    return path


def _provider(
    tmp_path: Path,
    session_factory: Callable[[Path], Any],
    verify_artifacts: Callable[[Path], Path],
) -> BuiltinOnnxEmbeddingProvider:
    model = tmp_path / "synthetic-model"
    model.mkdir()
    tokenizer().save(str(model / "tokenizer.json"))
    return BuiltinOnnxEmbeddingProvider(
        model, verify_artifacts=verify_artifacts, session_factory=session_factory
    )


def _build(tmp_path: Path, provider: BuiltinOnnxEmbeddingProvider) -> BuiltBundle:
    config_path = _config_path(tmp_path)
    return build_index_bundle(
        config_path,
        tmp_path / "dist",
        resolver=FixtureResolver(),
        embedding_provider=provider,
        configuration_source=replace(
            _configuration_source(), content=config_path.read_text(encoding="utf-8")
        ),
        built_at=datetime(2026, 10, 3, tzinfo=UTC),
        public_directory=_write_public_assets(tmp_path),
    )


@pytest.fixture
def built_bundle(tmp_path: Path) -> tuple[BuiltBundle, BuiltinOnnxEmbeddingProvider, Session]:
    session = Session()
    provider = _provider(tmp_path, lambda _: session, lambda root: root)
    return _build(tmp_path, provider), provider, session


def test_builtin_bundle_is_verified_and_consumed_with_same_query_provider(
    tmp_path: Path,
    built_bundle: tuple[BuiltBundle, BuiltinOnnxEmbeddingProvider, Session],
) -> None:
    bundle, provider, session = built_bundle
    expected = builtin_embedding_identity()
    assert bundle.manifest.embedding == provider.identity() == expected
    assert expected.adapter == "builtin_onnx"
    assert expected.model_id == "BAAI/bge-m3:5617a9f61b028005a4858fdac845db406aefb181"
    assert expected.dimension == 1024
    assert expected.normalized and expected.query_prefix == expected.passage_prefix == ""
    assert session.calls  # Production builder called the real provider passage method.
    passage_call_count = len(session.calls)
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=tmp_path / "verified",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=expected,
        max_bundle_bytes=10 * 1024 * 1024,
    )
    try:
        reader = verified.index
        assert isinstance(reader, ReadOnlyIndex)
        assert reader.embedding == expected
        assert reader.vectors.values.dtype == np.float32
        assert reader.vectors.values.shape[1] == 1024
        assert not reader.vectors.values.flags.writeable
        np.testing.assert_allclose(np.linalg.norm(reader.vectors.values, axis=1), 1, rtol=1e-5)
        query = provider.embed_query(["hybrid retrieval"])
        assert len(session.calls) == passage_call_count + 1
        assert query.dtype == np.float32 and query.shape == (1, 1024)
        np.testing.assert_array_equal(query, provider.embed_passages(["hybrid retrieval"]))
        candidates = reader.hybrid_candidates("hybrid retrieval", query_vector=query[0])
        assert candidates
        assert set(candidates) <= set(reader.vectors.evidence_ids)
        assert all(reader.evidence(evidence_id) is not None for evidence_id in candidates)
        with sqlite3.connect(tmp_path / "dist" / "index.sqlite") as database:
            assert database.execute(
                "SELECT DISTINCT model_id, dimension, normalized, length(vector_f32_le) "
                "FROM embeddings"
            ).fetchall() == [(expected.model_id, 1024, 1, 4096)]
    finally:
        verified.close()


def test_revision_mismatch_is_rejected_by_archive_and_read_only_index(
    tmp_path: Path,
    built_bundle: tuple[BuiltBundle, BuiltinOnnxEmbeddingProvider, Session],
) -> None:
    bundle, provider, _ = built_bundle
    incompatible = replace(provider.identity(), model_id="BAAI/bge-m3:" + "0" * 40)
    with pytest.raises(IndexReadError) as index_error:
        ReadOnlyIndex.open(tmp_path / "dist" / "index.sqlite", expected_embedding=incompatible)
    assert index_error.value.code == "embedding_identity_mismatch"
    staging = tmp_path / "incompatible"
    with pytest.raises(BundleError) as archive_error:
        verify_bundle_archive(
            archive_path=bundle.archive_path,
            staging_directory=staging,
            expected_outer_sha256=bundle.archive_sha256,
            expected_embedding=incompatible,
            max_bundle_bytes=10 * 1024 * 1024,
        )
    assert archive_error.value.code == "bundle_embedding_incompatible"
    assert not staging.exists()


def test_artifact_failure_stops_before_session_and_bundle_output(tmp_path: Path) -> None:
    events: list[str] = []

    def reject(_: Path) -> Path:
        events.append("verify")
        raise BuiltinArtifactError("builtin_artifact_invalid")

    def forbidden_session(_: Path) -> Session:
        pytest.fail("session factory ran before successful artifact verification")

    provider = _provider(tmp_path, forbidden_session, reject)
    with pytest.raises(ProviderError) as error:
        _build(tmp_path, provider)
    assert error.value.code is ProviderFailureCode.UNAVAILABLE
    assert str(error.value) == "model provider failed"
    assert events == ["verify"]
    output = tmp_path / "dist"
    assert not (output / "index.sqlite").exists()
    assert not (output / BUILD_RECEIPT_NAME).exists()
    assert not list(output.glob("*.tar.zst"))
    assert not list(output.glob(".index-*.sqlite.tmp"))


def test_failed_builtin_rebuild_preserves_last_known_good_index_and_cleans_temporary(
    tmp_path: Path,
    built_bundle: tuple[BuiltBundle, BuiltinOnnxEmbeddingProvider, Session],
) -> None:
    bundle, _, _ = built_bundle
    output = tmp_path / "dist"
    index_path = output / "index.sqlite"
    last_good = index_path.read_bytes()
    archive_bytes = bundle.archive_path.read_bytes()
    attempt = tmp_path / "failed-rebuild"
    attempt.mkdir()
    events: list[str] = []

    def reject(_: Path) -> Path:
        events.append("verify")
        raise BuiltinArtifactError("builtin_artifact_invalid")

    def forbidden_session(_: Path) -> Session:
        pytest.fail("failed artifact verification allowed session creation")

    provider = _provider(attempt, forbidden_session, reject)
    config_path = _config_path(attempt)
    with pytest.raises(ProviderError) as error:
        IndexDatabaseBuilder(provider).build(
            config=load_public_config(config_path),
            configuration_source=replace(
                _configuration_source(), content=config_path.read_text(encoding="utf-8")
            ),
            repositories=(_fixture_snapshot(),),
            output_path=index_path,
        )
    assert error.value.code is ProviderFailureCode.UNAVAILABLE
    assert str(error.value) == "model provider failed"
    assert error.value.upstream_message is None
    assert error.value.upstream_status is None
    assert error.value.__cause__ is None
    assert events == ["verify"]
    assert index_path.read_bytes() == last_good
    assert bundle.archive_path.read_bytes() == archive_bytes
    assert not list(output.glob(".index-*.sqlite.tmp"))
