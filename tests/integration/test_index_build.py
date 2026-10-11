"""Real P2-01/P2-02/P1 producer integration into schema-v1 SQLite."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

import numpy as np
import pytest

from reponpc.bundles.index_reader import ReadOnlyIndex
from reponpc.chat.answers import validate_v2_answer
from reponpc.config.models import load_public_config
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.index_database import (
    INDEX_SCHEMA_VERSION,
    IndexBuildError,
    IndexDatabaseBuilder,
    _embedding_batch_size,
)
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    ParticipationCommit,
    RepositoryBlob,
    RepositoryParticipation,
    ResolvedConfiguration,
    ResolvedRepository,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
FIXTURE_CONFIG = REPOSITORY_ROOT / "tests" / "fixtures" / "phase2" / "reponpc.yml"
FIXTURE_REPOSITORY = REPOSITORY_ROOT / "tests" / "fixtures" / "repos" / "reponpc-demo"
FIXTURE_SHA = "a" * 40


class DeterministicEmbeddingProvider:
    """A non-network, unit-normalized fixture provider with the declared identity."""

    def __init__(self, *, dimension: int | None = None, prefix: str | None = None) -> None:
        configured = load_public_config(FIXTURE_CONFIG).retrieval.embedding
        self._identity = EmbeddingIdentity(
            adapter=configured.adapter,
            model_id=configured.model,
            dimension=configured.dimension if dimension is None else dimension,
            normalized=configured.normalized,
            query_prefix=configured.query_prefix,
            passage_prefix=configured.passage_prefix if prefix is None else prefix,
        )
        self.raw_passages: list[str] = []
        self.passage_batches: list[int] = []

    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        self.passage_batches.append(len(texts))
        self.raw_passages.extend(texts)
        result = np.zeros((len(texts), self._identity.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            prefixed = self._identity.passage_prefix + text
            digest = hashlib.sha256(prefixed.encode("utf-8")).digest()
            result[row, int.from_bytes(digest[:2], "big") % self._identity.dimension] = 1.0
        return result

    def embed_query(self, texts: list[str]) -> np.ndarray:
        return self.embed_passages(texts)


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
        assert "pyproject.toml" in source_paths
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
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence WHERE evidence_class = 'PARTICIPATION'"
        ).fetchone() == (0,)


def test_participation_facts_keep_unavailable_distinct_and_link_to_immutable_commits(
    tmp_path: Path,
) -> None:
    provider = DeterministicEmbeddingProvider()
    participation = RepositoryParticipation(
        is_repository_owner=True,
        has_visible_commits=True,
        first_commit=ParticipationCommit("b" * 40, "2024-02"),
        last_commit=ParticipationCommit("c" * 40, "2026-08"),
        other_contributors_visible=None,
    )
    result = IndexDatabaseBuilder(provider).build(
        config=load_public_config(FIXTURE_CONFIG),
        configuration_source=_configuration_source(),
        repositories=(replace(_fixture_snapshot(), participation=participation),),
        output_path=tmp_path / "index.sqlite",
    )
    with sqlite3.connect(result.database_path) as connection:
        assert (
            connection.execute(
                "SELECT value FROM bundle_meta WHERE key LIKE 'participation:%'"
            ).fetchone()
            is None
        )
        stored = json.loads(
            connection.execute(
                "SELECT metadata_json FROM evidence WHERE evidence_class = 'PARTICIPATION' LIMIT 1"
            ).fetchone()[0]
        )
        assert stored["other_contributors_visible"] is None
        rows = connection.execute(
            "SELECT evidence_id, content FROM evidence WHERE evidence_class = 'PARTICIPATION' "
            "ORDER BY start_line"
        ).fetchall()
    assert len(rows) == 3
    assert all("count" not in content.lower() for _, content in rows)
    assert all("role" not in content.lower() for _, content in rows)
    reader = ReadOnlyIndex.open(result.database_path, expected_embedding=provider.identity())
    try:
        assert reader.owner_aliases == ("fixture-owner",)
        participation_records = [reader.evidence(evidence_id) for evidence_id, _ in rows]
        assert all(record is not None for record in participation_records)
        assert [
            record.github_permalink for record in participation_records if record is not None
        ] == [
            "https://github.com/fixture-owner/reponpc-demo/tree/" + FIXTURE_SHA,
            "https://github.com/fixture-owner/reponpc-demo/commit/" + "b" * 40,
            "https://github.com/fixture-owner/reponpc-demo/commit/" + "c" * 40,
        ]
        with sqlite3.connect(result.database_path) as connection:
            project_id = connection.execute(
                "SELECT evidence_id FROM evidence JOIN sources USING(source_id) "
                "WHERE sources.path = 'pyproject.toml' LIMIT 1"
            ).fetchone()[0]
        first = reader.evidence(rows[1][0])
        project = reader.evidence(project_id)
        assert first is not None and project is not None
        for locale, activity, project_text in (
            (
                "en",
                "{{owner}} had a visible GitHub commit in 2024-02.",
                "The repository includes project configuration.",
            ),
            ("zh-TW", "{{owner}} 在 2024-02 有可見的 GitHub 提交。", "這個專案包含設定檔。"),
        ):
            answer = validate_v2_answer(
                {
                    "segments": [
                        {"kind": "participation", "text": activity, "source_ids": ["S1"]},
                        {"kind": "project", "text": project_text, "source_ids": ["S2"]},
                    ],
                    "insufficient_evidence": False,
                },
                {"S1": first, "S2": project},
                cast(Literal["zh-TW", "en"], locale),
                owner_name="Fixture Developer",
                owner_aliases=reader.owner_aliases,
            )
            assert answer.insufficient_evidence is False
            assert "2024-02" in answer.answer_markdown
            assert {citation.evidence_class for citation in answer.citations} == {
                "PARTICIPATION",
                "REPOSITORY_FACT",
            }
    finally:
        reader.close()


def test_root_manifest_is_line_addressable_and_provider_receives_stored_plaintext(
    tmp_path: Path,
) -> None:
    provider = DeterministicEmbeddingProvider()
    result = _build(tmp_path, provider=provider)

    with sqlite3.connect(result.database_path) as connection:
        rows = connection.execute(
            "SELECT sources.source_type, evidence.evidence_class, evidence.start_line, "
            "evidence.end_line, evidence.metadata_json "
            "FROM sources JOIN evidence USING(source_id) WHERE sources.path = 'pyproject.toml'"
        ).fetchall()
        stored_passages = [row[0] for row in connection.execute("SELECT content FROM evidence")]

    assert rows
    assert all(row[0] == "repository_metadata" for row in rows)
    assert all(row[1] == "REPOSITORY_FACT" for row in rows)
    assert all(1 <= row[2] <= row[3] for row in rows)
    assert all(json.loads(row[4])["source_type"] == "repository_metadata" for row in rows)
    assert provider.raw_passages
    assert sorted(provider.raw_passages) == sorted(stored_passages)
    assert provider.identity().passage_prefix == ""


def test_index_builder_splits_embeddings_below_transport_response_limit(
    tmp_path: Path,
) -> None:
    provider = DeterministicEmbeddingProvider()
    extra_blobs: list[RepositoryBlob] = []
    for index in range(20):
        content = (
            f"def batch_fixture_{index}():\n"
            f'    """Return deterministic fixture number {index}."""\n'
            f"    return {index}\n"
        ).encode()
        extra_blobs.append(
            RepositoryBlob(
                path=f"src/batch_fixture_{index}.py",
                entry_kind=SourceEntryKind.REGULAR_FILE,
                content=content,
                size_bytes=len(content),
            )
        )
    result = IndexDatabaseBuilder(provider).build(
        config=load_public_config(FIXTURE_CONFIG),
        configuration_source=_configuration_source(),
        repositories=(_fixture_snapshot(extra_blobs=tuple(extra_blobs)),),
        output_path=tmp_path / "index.sqlite",
    )

    assert len(provider.passage_batches) > 1
    assert max(provider.passage_batches) <= 16
    assert sum(provider.passage_batches) == result.evidence_count


def test_embedding_batch_size_accounts_for_high_dimension_json() -> None:
    assert _embedding_batch_size(4096) == 15


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
        dimension = load_public_config(FIXTURE_CONFIG).retrieval.embedding.dimension
        _build(tmp_path, provider=DeterministicEmbeddingProvider(dimension=dimension - 1))

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


def test_onboarding_placeholder_does_not_create_participation(tmp_path: Path) -> None:
    from reponpc.admin.onboarding import _analysis_config

    provider = DeterministicEmbeddingProvider()
    config, content = _analysis_config(
        slug="fixture-owner/reponpc-demo",
        ref=FIXTURE_SHA,
        include=(),
        exclude=(),
        identity=provider.identity(),
    )
    assert config.profile.github_login == "reponpc-onboarding"
    result = IndexDatabaseBuilder(provider).build(
        config=config,
        configuration_source=replace(_configuration_source(), content=content),
        repositories=(_fixture_snapshot(),),
        output_path=tmp_path / "index.sqlite",
    )
    with sqlite3.connect(result.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence WHERE evidence_class = 'PARTICIPATION'"
        ).fetchone() == (0,)
