"""Deterministic schema-v1 immutable index creation.

The builder is the first real consumer of the P2 exclusion/parser primitives.
It accepts only already-resolved repository snapshots, writes a fresh SQLite
file, runs integrity checks, and never touches mutable ``runtime.sqlite``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from reponpc.config.models import PublicConfig
from reponpc.domain.evidence import EvidenceClass, EvidenceRecord, normalize_content
from reponpc.indexing.exclusions import (
    ExclusionPolicy,
    SourceMetadata,
    classify_source,
)
from reponpc.indexing.parsing import ChunkCandidate, chunk_source
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    PassageEmbeddingProvider,
    RepositoryBlob,
    ResolvedConfiguration,
    ResolvedRepository,
)
from reponpc.retrieval.vector import validate_vector_matrix

INDEX_SCHEMA_VERSION: Final = 1
APPLICATION_COMPATIBILITY: Final = {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"}
_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)
_DOCUMENT_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".markdown", ".rst", ".txt"})
_ROOT_REPOSITORY_METADATA: Final[frozenset[str]] = frozenset(
    {"pyproject.toml", "package.json", "Cargo.toml", "go.mod", "requirements.txt"}
)


class IndexBuildError(RuntimeError):
    """A safe build failure whose code is suitable for logs/status only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("index build failed")


@dataclass(frozen=True, slots=True)
class SkippedSource:
    """A body-free skipped-file summary."""

    repository_slug: str
    path: str
    reason_code: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class IndexBuildResult:
    """Deterministic build output metadata used by the bundle serializer."""

    database_path: Path
    embedding: EmbeddingIdentity
    repository_count: int
    source_count: int
    evidence_count: int
    skipped_sources: tuple[SkippedSource, ...]


@dataclass(frozen=True, slots=True)
class CollectedRepositorySource:
    """One eligible decoded source plus its production evidence records."""

    path: str
    content: str
    language: str
    source_type: str
    evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class RepositoryEvidenceCollection:
    """Reusable selected-repository output before database or provider work."""

    sources: tuple[CollectedRepositorySource, ...]
    evidence: tuple[EvidenceRecord, ...]
    skipped_sources: tuple[SkippedSource, ...]
    included_text_bytes: int


def create_schema(connection: sqlite3.Connection) -> None:
    """Create exactly the required schema-v1 logical tables and FTS channels."""

    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE bundle_meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE repositories (
          repo_id INTEGER PRIMARY KEY,
          slug TEXT NOT NULL UNIQUE,
          commit_sha TEXT NOT NULL CHECK(length(commit_sha) = 40),
          default_branch TEXT,
          github_html_url TEXT NOT NULL,
          summary_zh_tw TEXT,
          summary_en TEXT
        );
        CREATE TABLE sources (
          source_id INTEGER PRIMARY KEY,
          repo_id INTEGER NOT NULL REFERENCES repositories(repo_id),
          path TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          language TEXT,
          source_type TEXT NOT NULL,
          UNIQUE(repo_id, path, content_sha256)
        );
        CREATE TABLE evidence (
          evidence_id TEXT PRIMARY KEY,
          evidence_class TEXT NOT NULL CHECK(evidence_class IN
            ('OWNER_ASSERTION','REPOSITORY_FACT','MODEL_INFERENCE')),
          source_id INTEGER NOT NULL REFERENCES sources(source_id),
          owner_claim_id TEXT,
          title TEXT,
          symbol TEXT,
          content TEXT NOT NULL,
          start_line INTEGER NOT NULL CHECK(start_line >= 1),
          end_line INTEGER NOT NULL CHECK(end_line >= start_line),
          language TEXT,
          metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE VIRTUAL TABLE evidence_fts_terms USING fts5(
          evidence_id UNINDEXED, title, symbol, path, content,
          tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE evidence_fts_trigram USING fts5(
          evidence_id UNINDEXED, title, symbol, path, content,
          tokenize='trigram'
        );
        CREATE TABLE embeddings (
          evidence_id TEXT PRIMARY KEY REFERENCES evidence(evidence_id),
          model_id TEXT NOT NULL,
          dimension INTEGER NOT NULL,
          normalized INTEGER NOT NULL CHECK(normalized = 1),
          vector_f32_le BLOB NOT NULL
        );
        CREATE INDEX evidence_source_idx ON evidence(source_id);
        """
    )


class IndexDatabaseBuilder:
    """Build a new immutable index database from pinned source snapshots."""

    def __init__(self, embedding_provider: PassageEmbeddingProvider) -> None:
        self._embedding_provider = embedding_provider
        self._identity = embedding_provider.identity()

    @property
    def embedding_identity(self) -> EmbeddingIdentity:
        return self._identity

    def build(
        self,
        *,
        config: PublicConfig,
        configuration_source: ResolvedConfiguration,
        repositories: Iterable[ResolvedRepository],
        output_path: Path,
    ) -> IndexBuildResult:
        """Write and verify a fresh schema-v1 SQLite index atomically."""

        self._validate_embedding_contract(config)
        snapshots = self._validate_snapshots(config, repositories)
        output_path = Path(output_path)
        if output_path.name.casefold() != "index.sqlite":
            raise IndexBuildError("index_filename_invalid")
        if output_path.resolve(strict=False).name.casefold() != "index.sqlite":
            raise IndexBuildError("index_filename_invalid")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._temporary_database_path(output_path)
        try:
            result = self._build_temporary(
                config=config,
                configuration_source=configuration_source,
                snapshots=snapshots,
                database_path=temporary_path,
            )
            os.replace(temporary_path, output_path)
            return IndexBuildResult(
                database_path=output_path,
                embedding=result.embedding,
                repository_count=result.repository_count,
                source_count=result.source_count,
                evidence_count=result.evidence_count,
                skipped_sources=result.skipped_sources,
            )
        except IndexBuildError:
            temporary_path.unlink(missing_ok=True)
            raise
        except (OSError, sqlite3.Error, ValueError) as exc:
            temporary_path.unlink(missing_ok=True)
            raise IndexBuildError("index_build_failed") from exc

    def _build_temporary(
        self,
        *,
        config: PublicConfig,
        configuration_source: ResolvedConfiguration,
        snapshots: tuple[ResolvedRepository, ...],
        database_path: Path,
    ) -> IndexBuildResult:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("BEGIN IMMEDIATE")
            create_schema(connection)
            self._insert_meta(connection, config)
            source_count, evidence_rows, skipped = self._insert_repository_sources(
                connection,
                config,
                snapshots,
            )
            source_count, assertion_rows = self._insert_owner_assertions(
                connection,
                config,
                configuration_source,
                source_count=source_count,
            )
            all_evidence_rows = tuple(evidence_rows) + tuple(assertion_rows)
            self._insert_embeddings(connection, all_evidence_rows)
            connection.execute("COMMIT")
            self._quick_check(connection)
            return IndexBuildResult(
                database_path=database_path,
                embedding=self._identity,
                repository_count=len(snapshots),
                source_count=source_count,
                evidence_count=len(all_evidence_rows),
                skipped_sources=tuple(skipped),
            )
        except IndexBuildError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except (sqlite3.Error, ValueError) as exc:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise IndexBuildError("index_database_write_failed") from exc
        finally:
            connection.close()

    def _insert_meta(self, connection: sqlite3.Connection, config: PublicConfig) -> None:
        values = {
            "index_schema_version": str(INDEX_SCHEMA_VERSION),
            "application_compatibility": _canonical_json(APPLICATION_COMPATIBILITY),
            "embedding": _canonical_json(_embedding_payload(self._identity)),
            "config_schema_version": str(config.schema_version),
            "retrieval_policy": _canonical_json(
                {
                    "enabled_sources": list(config.retrieval.enabled_sources),
                    "fusion": config.retrieval.fusion.model_dump(mode="json"),
                    "source_weights": config.retrieval.source_weights.model_dump(mode="json"),
                }
            ),
        }
        connection.executemany(
            "INSERT INTO bundle_meta(key, value) VALUES (?, ?)",
            tuple(sorted(values.items())),
        )

    def _insert_repository_sources(
        self,
        connection: sqlite3.Connection,
        config: PublicConfig,
        snapshots: tuple[ResolvedRepository, ...],
    ) -> tuple[int, tuple[EvidenceRecord, ...], list[SkippedSource]]:
        configs = {
            repository.slug: repository for repository in config.repositories if repository.enabled
        }
        corpus_bytes = 0
        source_count = 0
        evidence_rows: list[EvidenceRecord] = []
        skipped: list[SkippedSource] = []
        for snapshot in snapshots:
            repository_config = configs[snapshot.slug]
            repo_id = self._insert_repository(
                connection,
                slug=snapshot.slug,
                commit_sha=snapshot.commit_sha,
                default_branch=snapshot.default_branch,
                github_html_url=snapshot.github_html_url,
                summary_zh_tw=repository_config.summary["zh-TW"],
                summary_en=repository_config.summary["en"],
            )
            collection = collect_repository_evidence(
                config=config,
                snapshot=snapshot,
                corpus_text_bytes_before=corpus_bytes,
            )
            corpus_bytes += collection.included_text_bytes
            skipped.extend(collection.skipped_sources)
            for source in collection.sources:
                source_id = self._insert_source(
                    connection,
                    repo_id=repo_id,
                    path=source.path,
                    content=source.content,
                    language=source.language,
                    source_type=source.source_type,
                )
                source_count += 1
                for evidence in source.evidence:
                    self._insert_evidence(connection, source_id, evidence)
                    evidence_rows.append(evidence)
        return source_count, tuple(evidence_rows), skipped

    def _insert_owner_assertions(
        self,
        connection: sqlite3.Connection,
        config: PublicConfig,
        configuration_source: ResolvedConfiguration,
        *,
        source_count: int,
    ) -> tuple[int, tuple[EvidenceRecord, ...]]:
        repo_id = self._insert_repository(
            connection,
            slug=configuration_source.repository_slug,
            commit_sha=configuration_source.commit_sha,
            default_branch=None,
            github_html_url=configuration_source.github_html_url,
            summary_zh_tw=None,
            summary_en=None,
        )
        source_id = self._insert_source(
            connection,
            repo_id=repo_id,
            path=configuration_source.path,
            content=configuration_source.content,
            language="yaml",
            source_type="owner_assertion",
        )
        assertions: list[EvidenceRecord] = []
        for field in ("headline", "bio"):
            start_line, end_line = _yaml_key_range(configuration_source.content, field)
            localized = getattr(config.profile, field)
            evidence = EvidenceRecord(
                evidence_class=EvidenceClass.OWNER_ASSERTION,
                repository_slug=configuration_source.repository_slug,
                commit_sha=configuration_source.commit_sha,
                path=configuration_source.path,
                start_line=start_line,
                end_line=end_line,
                content=_localized_claim_content(localized),
                owner_claim_id=f"profile_{field}",
                title=f"profile_{field}",
                language="yaml",
                metadata={"source_type": "owner_assertions"},
            )
            self._insert_evidence(connection, source_id, evidence)
            assertions.append(evidence)
        for repository in sorted(config.repositories, key=lambda item: item.slug):
            if not repository.enabled:
                continue
            for field in ("role", "summary"):
                start_line, end_line = _repository_key_range(
                    configuration_source.content, repository.slug, field
                )
                evidence = EvidenceRecord(
                    evidence_class=EvidenceClass.OWNER_ASSERTION,
                    repository_slug=configuration_source.repository_slug,
                    commit_sha=configuration_source.commit_sha,
                    path=configuration_source.path,
                    start_line=start_line,
                    end_line=end_line,
                    content=_localized_claim_content(getattr(repository, field)),
                    owner_claim_id=f"repository_{repository.slug}_{field}",
                    title=f"repository_{field}",
                    language="yaml",
                    metadata={
                        "repository_slug": repository.slug,
                        "source_type": "owner_assertions",
                    },
                )
                self._insert_evidence(connection, source_id, evidence)
                assertions.append(evidence)
            for claim in sorted(repository.claims, key=lambda item: item.id):
                start_line, end_line = _claim_line_range(configuration_source.content, claim.id)
                content = _localized_claim_content(claim.statement)
                evidence = EvidenceRecord(
                    evidence_class=EvidenceClass.OWNER_ASSERTION,
                    repository_slug=configuration_source.repository_slug,
                    commit_sha=configuration_source.commit_sha,
                    path=configuration_source.path,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    owner_claim_id=claim.id,
                    title=claim.kind,
                    language="yaml",
                    metadata={
                        "repository_slug": repository.slug,
                        "claim_kind": claim.kind,
                        "source_type": "owner_assertions",
                    },
                )
                self._insert_evidence(connection, source_id, evidence)
                assertions.append(evidence)
        return source_count + 1, tuple(assertions)

    @staticmethod
    def _insert_repository(
        connection: sqlite3.Connection,
        *,
        slug: str,
        commit_sha: str,
        default_branch: str | None,
        github_html_url: str,
        summary_zh_tw: str | None,
        summary_en: str | None,
    ) -> int:
        row = connection.execute(
            "SELECT repo_id, commit_sha, github_html_url FROM repositories WHERE slug = ?", (slug,)
        ).fetchone()
        if row is not None:
            if str(row[1]) != commit_sha or str(row[2]) != github_html_url:
                raise IndexBuildError("repository_commit_conflict")
            return int(row[0])
        cursor = connection.execute(
            """
            INSERT INTO repositories(
              slug, commit_sha, default_branch, github_html_url, summary_zh_tw, summary_en
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (slug, commit_sha, default_branch, github_html_url, summary_zh_tw, summary_en),
        )
        return _cursor_row_id(cursor)

    @staticmethod
    def _insert_source(
        connection: sqlite3.Connection,
        *,
        repo_id: int,
        path: str,
        content: str,
        language: str,
        source_type: str,
    ) -> int:
        content_sha256 = hashlib.sha256(normalize_content(content).encode("utf-8")).hexdigest()
        cursor = connection.execute(
            """
            INSERT INTO sources(repo_id, path, content_sha256, language, source_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (repo_id, path, content_sha256, language, source_type),
        )
        return _cursor_row_id(cursor)

    @staticmethod
    def _insert_evidence(
        connection: sqlite3.Connection,
        source_id: int,
        evidence: EvidenceRecord,
    ) -> None:
        connection.execute(
            """
            INSERT INTO evidence(
              evidence_id, evidence_class, source_id, owner_claim_id, title, symbol,
              content, start_line, end_line, language, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                evidence.evidence_class.value,
                source_id,
                evidence.owner_claim_id,
                evidence.title,
                evidence.symbol,
                evidence.content,
                evidence.start_line,
                evidence.end_line,
                evidence.language,
                _canonical_json(evidence.metadata),
            ),
        )
        connection.execute(
            "INSERT INTO evidence_fts_terms(evidence_id, title, symbol, path, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                evidence.evidence_id,
                evidence.title,
                evidence.symbol,
                evidence.path,
                evidence.content,
            ),
        )
        connection.execute(
            "INSERT INTO evidence_fts_trigram(evidence_id, title, symbol, path, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                evidence.evidence_id,
                evidence.title,
                evidence.symbol,
                evidence.path,
                evidence.content,
            ),
        )

    def _insert_embeddings(
        self,
        connection: sqlite3.Connection,
        evidence_rows: tuple[EvidenceRecord, ...],
    ) -> None:
        if not evidence_rows:
            raise IndexBuildError("index_has_no_evidence")
        ordered = tuple(sorted(evidence_rows, key=lambda item: item.evidence_id or ""))
        texts = [evidence.content for evidence in ordered]
        vectors = self._embedding_provider.embed_passages(texts)
        try:
            matrix = validate_vector_matrix(
                [str(evidence.evidence_id) for evidence in ordered],
                vectors,
                dimension=self._identity.dimension,
            )
        except (TypeError, ValueError) as exc:
            raise IndexBuildError("embedding_output_invalid") from exc
        for evidence_id, vector in zip(matrix.evidence_ids, matrix.values, strict=True):
            connection.execute(
                """
                INSERT INTO embeddings(evidence_id, model_id, dimension, normalized, vector_f32_le)
                VALUES (?, ?, ?, 1, ?)
                """,
                (
                    evidence_id,
                    self._identity.model_id,
                    self._identity.dimension,
                    vector.astype("<f4").tobytes(),
                ),
            )

    def _validate_embedding_contract(self, config: PublicConfig) -> None:
        configured = config.retrieval.embedding
        actual = self._identity
        if (
            configured.adapter != actual.adapter
            or configured.model != actual.model_id
            or configured.dimension != actual.dimension
            or configured.normalized != actual.normalized
            or configured.query_prefix != actual.query_prefix
            or configured.passage_prefix != actual.passage_prefix
        ):
            raise IndexBuildError("embedding_identity_mismatch")

    @staticmethod
    def _validate_snapshots(
        config: PublicConfig,
        repositories: Iterable[ResolvedRepository],
    ) -> tuple[ResolvedRepository, ...]:
        snapshots = tuple(sorted(repositories, key=lambda item: item.slug))
        expected = {item.slug for item in config.repositories if item.enabled}
        actual = {item.slug for item in snapshots}
        if not snapshots or actual != expected or len(actual) != len(snapshots):
            raise IndexBuildError("resolved_repository_set_invalid")
        return snapshots

    @staticmethod
    def _temporary_database_path(output_path: Path) -> Path:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output_path.stem}-",
            suffix=".sqlite.tmp",
            dir=output_path.parent,
            delete=False,
        ) as handle:
            return Path(handle.name)

    @staticmethod
    def _quick_check(connection: sqlite3.Connection) -> None:
        row = connection.execute("PRAGMA quick_check").fetchone()
        if row is None or str(row[0]).casefold() != "ok":
            raise IndexBuildError("index_integrity_failed")


def collect_repository_evidence(
    *,
    config: PublicConfig,
    snapshot: ResolvedRepository,
    corpus_text_bytes_before: int = 0,
) -> RepositoryEvidenceCollection:
    """Apply the production source policy and chunker without writing durable state."""

    repository_config = next(
        (
            repository
            for repository in config.repositories
            if repository.enabled and repository.slug == snapshot.slug
        ),
        None,
    )
    if repository_config is None:
        raise IndexBuildError("repository_snapshot_mismatch")
    if isinstance(corpus_text_bytes_before, bool) or corpus_text_bytes_before < 0:
        raise ValueError("corpus_text_bytes_before must be a non-negative integer")
    policy = ExclusionPolicy(
        include_patterns=repository_config.include,
        repository_exclude_patterns=repository_config.exclude,
        global_exclude_patterns=(),
        max_file_bytes=config.retrieval.limits.max_file_bytes,
        max_repository_text_bytes=config.retrieval.limits.max_repository_text_bytes,
        max_corpus_text_bytes=config.retrieval.limits.max_corpus_text_bytes,
    )
    repository_bytes = 0
    corpus_bytes = corpus_text_bytes_before
    sources: list[CollectedRepositorySource] = []
    evidence_rows: list[EvidenceRecord] = []
    skipped: list[SkippedSource] = []
    for blob in sorted(snapshot.blobs, key=lambda item: item.path):
        decoded = _decode_source(blob)
        metadata = SourceMetadata(
            entry_kind=blob.entry_kind,
            size_bytes=blob.size_bytes,
            is_binary=_is_binary(blob.content),
            is_decodable=decoded is not None,
            has_high_confidence_secret=_has_high_confidence_secret(decoded),
            repository_text_bytes_before=repository_bytes,
            corpus_text_bytes_before=corpus_bytes,
        )
        decision = classify_source(blob.path, metadata, policy)
        if not decision.include:
            skipped.append(
                SkippedSource(
                    repository_slug=snapshot.slug,
                    path=blob.path,
                    reason_code=decision.reason_code.value,
                    size_bytes=blob.size_bytes,
                )
            )
            continue
        if decoded is None:
            raise IndexBuildError("source_decode_invariant_failed")
        repository_bytes += blob.size_bytes
        corpus_bytes += blob.size_bytes
        language = _language_for_path(blob.path)
        evidence = tuple(
            _candidate_evidence(snapshot, blob.path, candidate)
            for candidate in chunk_source(
                decoded,
                path=blob.path,
                max_lines=config.retrieval.chunking.max_lines,
                max_characters=config.retrieval.chunking.max_characters,
                overlap_lines=config.retrieval.chunking.fallback_overlap_lines,
            )
        )
        if len(evidence_rows) + len(evidence) > config.retrieval.limits.max_evidence_records:
            raise IndexBuildError("index_evidence_limit_exceeded")
        source = CollectedRepositorySource(
            path=blob.path,
            content=decoded,
            language=language,
            source_type=_source_type(blob.path),
            evidence=evidence,
        )
        sources.append(source)
        evidence_rows.extend(evidence)
    return RepositoryEvidenceCollection(
        sources=tuple(sources),
        evidence=tuple(evidence_rows),
        skipped_sources=tuple(skipped),
        included_text_bytes=repository_bytes,
    )


def _candidate_evidence(
    snapshot: ResolvedRepository,
    path: str,
    candidate: ChunkCandidate,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_class=EvidenceClass.REPOSITORY_FACT,
        repository_slug=snapshot.slug,
        commit_sha=snapshot.commit_sha,
        path=path,
        start_line=candidate.start_line,
        end_line=candidate.end_line,
        content=candidate.content,
        title=candidate.symbol,
        symbol=candidate.symbol,
        language=candidate.language,
        metadata={"source_type": _source_type(path)},
    )


def _decode_source(blob: RepositoryBlob) -> str | None:
    if blob.content is None:
        return None
    try:
        return normalize_content(blob.content.decode("utf-8"))
    except UnicodeDecodeError:
        return None


def _is_binary(content: bytes | None) -> bool:
    return content is not None and b"\x00" in content


def _has_high_confidence_secret(content: str | None) -> bool:
    return content is not None and any(pattern.search(content) for pattern in _SECRET_PATTERNS)


def _language_for_path(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
        ".md": "markdown",
        ".markdown": "markdown",
    }.get(suffix, "text")


def _source_type(path: str) -> str:
    if path in _ROOT_REPOSITORY_METADATA:
        return "repository_metadata"
    return "documentation" if Path(path).suffix.casefold() in _DOCUMENT_SUFFIXES else "source_code"


def _claim_line_range(content: str, claim_id: str) -> tuple[int, int]:
    lines = normalize_content(content).split("\n")
    pattern = re.compile(rf"^\s*-\s+id:\s+{re.escape(claim_id)}\s*$")
    start = next((index for index, line in enumerate(lines, start=1) if pattern.match(line)), None)
    if start is None:
        raise IndexBuildError("owner_claim_source_range_missing")
    claim_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines) + 1):
        line = lines[index - 1]
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= claim_indent:
            end = index - 1
            break
    return start, end


def _yaml_key_range(content: str, key: str, *, start_at: int = 1) -> tuple[int, int]:
    lines = normalize_content(content).split("\n")
    pattern = re.compile(rf"^(\s*){re.escape(key)}:\s*")
    for number in range(start_at, len(lines) + 1):
        match = pattern.match(lines[number - 1])
        if match is None:
            continue
        indent = len(match.group(1))
        end = number
        for following in range(number + 1, len(lines) + 1):
            line = lines[following - 1]
            if line.strip() and len(line) - len(line.lstrip()) <= indent:
                break
            end = following
        return number, end
    raise IndexBuildError("owner_assertion_source_range_missing")


def _repository_key_range(content: str, slug: str, key: str) -> tuple[int, int]:
    lines = normalize_content(content).split("\n")
    slug_pattern = re.compile(rf"^\s*[- ]\s*slug:\s*{re.escape(slug)}\s*$")
    start = next((i for i, line in enumerate(lines, 1) if slug_pattern.match(line)), None)
    if start is None:
        raise IndexBuildError("owner_assertion_source_range_missing")
    return _yaml_key_range(content, key, start_at=start + 1)


def _localized_claim_content(statement: dict[str, str]) -> str:
    return "\n".join(f"{locale}: {statement[locale]}" for locale in sorted(statement))


def _embedding_payload(identity: EmbeddingIdentity) -> dict[str, object]:
    return {
        "adapter": identity.adapter,
        "model_id": identity.model_id,
        "dimension": identity.dimension,
        "normalized": identity.normalized,
        "query_prefix": identity.query_prefix,
        "passage_prefix": identity.passage_prefix,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cursor_row_id(cursor: sqlite3.Cursor) -> int:
    if cursor.lastrowid is None:
        raise IndexBuildError("index_database_write_failed")
    return int(cursor.lastrowid)
