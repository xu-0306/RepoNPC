"""Real P2-01/P2-02/P1 producer integration into schema-v1 SQLite."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from reponpc.bundles.index_reader import ReadOnlyIndex
from reponpc.config.models import load_public_config
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.index_database import (
    INDEX_SCHEMA_VERSION,
    IndexBuildError,
    IndexDatabaseBuilder,
)
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    RepositoryBlob,
    ResolvedConfiguration,
    ResolvedRepository,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_CONFIG = REPOSITORY_ROOT / "tests" / "fixtures" / "phase2" / "reponpc.yml"
FIXTURE_REPOSITORY = REPOSITORY_ROOT / "tests" / "fixtures" / "repos" / "reponpc-demo"
FIXTURE_SHA = "a" * 40


class DeterministicEmbeddingProvider:
    """A non-network, unit-normalized fixture provider with the declared identity."""

    def __init__(self, *, dimension: int = 384, prefix: str = "passage: ") -> None:
        self._identity = EmbeddingIdentity(
            adapter="local_sentence_transformers",
            model_id="intfloat/multilingual-e5-small",
            dimension=dimension,
            normalized=True,
            query_prefix="query: ",
            passage_prefix=prefix,
        )

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        result = np.zeros((len(texts), self._identity.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            result[row, int.from_bytes(digest[:2], "big") % self._identity.dimension] = 1.0
        return result


def _fixture_snapshot(*, extra_blobs: tuple[RepositoryBlob, ...] = ()) -> ResolvedRepository:
    blobs = tuple(
        RepositoryBlob(
            path=path.relative_to(FIXTURE_REPOSITORY).as_posix(),
            entry_kind=SourceEntryKind.REGULAR_FILE,
            size_bytes=path.stat().st_size,
            content=path.read_bytes(),
        )
        for path in sorted(FIXTURE_REPOSITORY.rglob("*"))
        if path.is_file()
    )
    return ResolvedRepository(
        slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        default_branch="main",
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
        blobs=blobs + extra_blobs,
    )


def _configuration_source() -> ResolvedConfiguration:
    return ResolvedConfiguration(
        repository_slug="fixture-owner/reponpc-demo",
        commit_sha=FIXTURE_SHA,
        path="reponpc.yml",
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        github_html_url="https://github.com/fixture-owner/reponpc-demo",
    )


def _build(tmp_path: Path, *, provider: DeterministicEmbeddingProvider | None = None):
    return IndexDatabaseBuilder(provider or DeterministicEmbeddingProvider()).build(
        config=load_public_config(FIXTURE_CONFIG),
        configuration_source=_configuration_source(),
        repositories=(_fixture_snapshot(),),
        output_path=tmp_path / "index.sqlite",
    )


def test_fixture_sources_flow_through_exclusion_chunking_evidence_and_schema(
    tmp_path: Path,
) -> None:
    result = _build(tmp_path)

    assert result.database_path.is_file()
    assert result.repository_count == 1
    assert result.source_count > 1
    assert result.evidence_count > 2
    assert {skip.path for skip in result.skipped_sources} >= {
        ".env.fixture",
        "assets/bundle.min.js",
        "docs/generated/ignored.md",
        "keys/id_rsa",
        "node_modules/fixture-package/index.js",
        "poetry.lock",
    }
    assert all(skip.reason_code != "ELIGIBLE" for skip in result.skipped_sources)

    with sqlite3.connect(result.database_path) as connection:
        source_paths = {
            row[0]
            for row in connection.execute("SELECT path FROM sources WHERE path != 'reponpc.yml'")
        }
        assert "src/retrieval_pipeline.py" in source_paths
        assert "docs/architecture.md" in source_paths
        assert ".env.fixture" not in source_paths
        assert connection.execute(
            "SELECT value FROM bundle_meta WHERE key = 'index_schema_version'"
        ).fetchone() == (str(INDEX_SCHEMA_VERSION),)
        assert connection.execute("SELECT COUNT(*) FROM evidence_fts_terms").fetchone() == (
            result.evidence_count,
        )
        assert connection.execute("SELECT COUNT(*) FROM evidence_fts_trigram").fetchone() == (
            result.evidence_count,
        )
        assert connection.execute("SELECT COUNT(*) FROM embeddings").fetchone() == (
            result.evidence_count,
        )
        assertion = connection.execute(
            "SELECT evidence_class, owner_claim_id, start_line, end_line "
            "FROM evidence WHERE owner_claim_id = 'fixture_retrieval_design'"
        ).fetchone()
        assert assertion is not None
        assert assertion[0] == "OWNER_ASSERTION"
        assert assertion[1] == "fixture_retrieval_design"
        assert assertion[2] <= assertion[3]
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)


def test_high_confidence_secret_blob_is_skipped_without_persisting_its_body(tmp_path: Path) -> None:
    secret_bytes = b"token = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'\n"
    secret_blob = RepositoryBlob(
        path="src/credential_probe.py",
        entry_kind=SourceEntryKind.REGULAR_FILE,
        content=secret_bytes,
        size_bytes=len(secret_bytes),
    )
    builder = IndexDatabaseBuilder(DeterministicEmbeddingProvider())
    result = builder.build(
        config=load_public_config(FIXTURE_CONFIG),
        configuration_source=_configuration_source(),
        repositories=(_fixture_snapshot(extra_blobs=(secret_blob,)),),
        output_path=tmp_path / "index.sqlite",
    )

    assert any(
        skip.path == "src/credential_probe.py" and skip.reason_code == "HIGH_CONFIDENCE_SECRET"
        for skip in result.skipped_sources
    )
    with sqlite3.connect(result.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sources WHERE path = 'src/credential_probe.py'"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence WHERE content LIKE '%ghp_%'"
        ).fetchone() == (0,)


def test_embedding_identity_mismatch_fails_before_writing_an_index(tmp_path: Path) -> None:
    with pytest.raises(IndexBuildError, match="index build failed") as exc_info:
        _build(tmp_path, provider=DeterministicEmbeddingProvider(dimension=383))

    assert exc_info.value.code == "embedding_identity_mismatch"
    assert not (tmp_path / "index.sqlite").exists()


def test_built_database_opens_read_only_and_consumes_both_real_fts_tables(tmp_path: Path) -> None:
    provider = DeterministicEmbeddingProvider()
    result = _build(tmp_path, provider=provider)
    reader = ReadOnlyIndex.open(result.database_path, expected_embedding=provider.identity())
    try:
        candidate_ids = reader.lexical_candidates("hybrid retrieval", limit=8)
        assert candidate_ids
        evidence = reader.evidence(candidate_ids[0])
        assert evidence is not None
        assert evidence.github_permalink.startswith(
            "https://github.com/fixture-owner/reponpc-demo/blob/" + FIXTURE_SHA
        )
        assert not reader.vectors.values.flags.writeable
        with pytest.raises(sqlite3.OperationalError):
            reader._connection.execute("DELETE FROM evidence")
    finally:
        reader.close()
