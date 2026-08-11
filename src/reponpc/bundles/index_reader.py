"""Read-only schema-v1 index consumer used by bundle verification and runtime."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np

from reponpc.indexing.index_database import INDEX_SCHEMA_VERSION
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.retrieval.fts_query import FtsQueryMode, compile_fts_query
from reponpc.retrieval.rrf import fuse_rankings, rrf_scores
from reponpc.retrieval.vector import ValidatedVectorMatrix, rank_vectors, validate_vector_matrix


class IndexReadError(RuntimeError):
    """A safe immutable-index error without filesystem or SQL diagnostics."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("bundle index is unavailable")


@dataclass(frozen=True, slots=True)
class IndexedEvidence:
    """A normalized evidence row as consumed by retrieval/citation layers."""

    evidence_id: str
    evidence_class: str
    repository_slug: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    title: str | None
    symbol: str | None
    content: str
    language: str | None
    metadata: dict[str, object]

    @property
    def github_permalink(self) -> str:
        """Build an immutable GitHub link only from validated index columns."""

        fragment = f"#L{self.start_line}"
        if self.end_line != self.start_line:
            fragment += f"-L{self.end_line}"
        return (
            f"https://github.com/{self.repository_slug}/blob/{self.commit_sha}/"
            f"{quote(self.path, safe='/')}" + fragment
        )


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    repository_slug: str | None = None
    language: str | None = None
    evidence_class: str | None = None
    source_type: str | None = None


@dataclass(frozen=True, slots=True)
class PackedContext:
    text: str
    evidence_ids: tuple[str, ...]
    token_count: int


class ReadOnlyIndex:
    """A query-only SQLite connection plus validated in-process vector matrix."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        embedding: EmbeddingIdentity,
        vectors: ValidatedVectorMatrix,
    ) -> None:
        self._connection = connection
        self.embedding = embedding
        self.vectors = vectors
        self.retrieval_policy = self._retrieval_policy(connection)

    @classmethod
    def open(cls, path: Path, *, expected_embedding: EmbeddingIdentity) -> ReadOnlyIndex:
        """Open one built index with no write-capable SQLite path."""

        index_path = Path(path)
        if index_path.name != "index.sqlite" or not index_path.is_file():
            raise IndexReadError("index_missing")
        try:
            uri = f"file:{quote(index_path.resolve().as_posix())}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            connection.execute("PRAGMA foreign_keys = ON")
            cls._quick_check(connection)
            actual_embedding = cls._embedding_from_meta(connection)
            if actual_embedding != expected_embedding:
                raise IndexReadError("embedding_identity_mismatch")
            vectors = cls._load_vectors(connection, actual_embedding)
            cls._validate_query_schema(connection)
            return cls(connection, embedding=actual_embedding, vectors=vectors)
        except IndexReadError:
            if "connection" in locals():
                connection.close()
            raise
        except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
            if "connection" in locals():
                connection.close()
            raise IndexReadError("index_open_failed") from exc

    def close(self) -> None:
        """Close the immutable reader after its bundle handle is released."""

        self._connection.close()

    def evidence(self, evidence_id: str) -> IndexedEvidence | None:
        """Load one evidence record without accepting caller-controlled SQL."""

        row = self._connection.execute(
            """
            SELECT e.evidence_id, e.evidence_class, r.slug, r.commit_sha, s.path,
                   e.start_line, e.end_line, e.title, e.symbol, e.content, e.language,
                   e.metadata_json
            FROM evidence AS e
            JOIN sources AS s ON s.source_id = e.source_id
            JOIN repositories AS r ON r.repo_id = s.repo_id
            WHERE e.evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
        return _evidence_from_row(row) if row is not None else None

    def lexical_candidates(self, question: str, *, limit: int) -> list[str]:
        """Use both FTS tables with only P2-03-generated bound values."""

        if limit <= 0:
            raise ValueError("limit must be positive")
        compiled = compile_fts_query(question)
        if compiled.mode is FtsQueryMode.NO_QUERY:
            return []
        if compiled.mode is FtsQueryMode.SHORT_EXACT:
            value = compiled.exact_value
            if value is None:
                return []
            rows = self._connection.execute(
                """
                SELECT evidence_id FROM evidence_fts_terms
                WHERE instr(
                  lower(COALESCE(title, '') || ' ' || COALESCE(symbol, '') ||
                    ' ' || path || ' ' || content), lower(?)
                ) > 0
                ORDER BY evidence_id ASC LIMIT ?
                """,
                (value, limit),
            ).fetchall()
            return [str(row[0]) for row in rows]
        expression = compiled.match_expression
        if expression is None:
            return []
        term_rows = self._connection.execute(
            """
            SELECT evidence_id FROM evidence_fts_terms
            WHERE evidence_fts_terms MATCH ?
            ORDER BY bm25(evidence_fts_terms), evidence_id ASC LIMIT ?
            """,
            (expression, limit),
        ).fetchall()
        trigram_rows = self._connection.execute(
            """
            SELECT evidence_id FROM evidence_fts_trigram
            WHERE evidence_fts_trigram MATCH ?
            ORDER BY bm25(evidence_fts_trigram), evidence_id ASC LIMIT ?
            """,
            (expression, limit),
        ).fetchall()
        return fuse_rankings(
            ([str(row[0]) for row in term_rows], [str(row[0]) for row in trigram_rows]),
            (1.0, 1.0),
        )[:limit]

    def hybrid_candidates(
        self,
        question: str,
        *,
        query_vector: np.ndarray,
        lexical_limit: int | None = None,
        vector_limit: int | None = None,
        final_limit: int | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[str]:
        """Fuse the real lexical and vector channels with P2-04/P1 primitives."""

        fusion = self.retrieval_policy["fusion"]
        configured_channel = int(fusion["candidate_count_per_channel"])
        lexical_limit = _validated_retrieval_override(lexical_limit, configured_channel)
        vector_limit = _validated_retrieval_override(vector_limit, configured_channel)
        final_limit = _validated_retrieval_override(
            final_limit, int(fusion["final_context_records"])
        )
        lexical = self.lexical_candidates(question, limit=lexical_limit)
        semantic = [
            match.evidence_id
            for match in rank_vectors(self.vectors, query_vector, limit=vector_limit)
        ]
        scores = rrf_scores(
            (lexical, semantic),
            (float(fusion["lexical_weight"]), float(fusion["vector_weight"])),
            k=float(fusion["rrf_k"]),
        )
        ranked = sorted(scores, key=lambda evidence_id: (-scores[evidence_id], evidence_id))
        enabled_sources = set(self.retrieval_policy["enabled_sources"])
        evidence_rows: list[tuple[IndexedEvidence, float]] = []
        for evidence_id in ranked:
            evidence = self.evidence(evidence_id)
            if evidence is None or _source_category(evidence) not in enabled_sources:
                continue
            if filters is not None and not self._matches_filters(evidence, filters):
                continue
            evidence_rows.append((evidence, scores[evidence_id]))
        weights = self.retrieval_policy["source_weights"]
        adjusted = sorted(
            evidence_rows,
            key=lambda item: (
                -item[1] * float(weights[_source_category(item[0])]),
                item[0].evidence_id,
            ),
        )
        selected: list[str] = []
        ranges: list[IndexedEvidence] = []
        repository_counts: dict[str, int] = {}
        cap = int(fusion["max_records_per_repository"])
        for evidence, _ in adjusted:
            if any(_overlaps(evidence, existing) for existing in ranges):
                continue
            if (filters is None or filters.repository_slug is None) and repository_counts.get(
                evidence.repository_slug, 0
            ) >= cap:
                continue
            ranges.append(evidence)
            repository_counts[evidence.repository_slug] = (
                repository_counts.get(evidence.repository_slug, 0) + 1
            )
            selected.append(evidence.evidence_id)
            if len(selected) == final_limit:
                break
        return selected

    def pack_context(
        self,
        evidence_ids: Sequence[str],
        *,
        max_context_tokens: int,
        token_counter: Callable[[str], int],
    ) -> PackedContext:
        if (
            isinstance(max_context_tokens, bool)
            or not isinstance(max_context_tokens, int)
            or max_context_tokens <= 0
        ):
            raise ValueError("max_context_tokens must be a positive integer")
        records: list[IndexedEvidence] = []
        for evidence_id in evidence_ids:
            evidence = self.evidence(evidence_id)
            if evidence is None:
                raise IndexReadError("evidence_not_found")
            records.append(evidence)
        blocks: list[str] = []
        included: list[str] = []
        accepted_count = 0
        for ordinal, evidence in enumerate(records, start=1):
            block = (
                f"[UNTRUSTED DATA S{ordinal} persistent_id={evidence.evidence_id} "
                f"class={evidence.evidence_class} repository={evidence.repository_slug} "
                f"commit={evidence.commit_sha} path={evidence.path} "
                f"lines={evidence.start_line}-{evidence.end_line}]\n"
                f"{_escape_context_markers(evidence.content)}\n"
                "[/UNTRUSTED DATA]"
            )
            candidate = "\n\n".join((*blocks, block))
            count = token_counter(candidate)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("token_counter returned invalid count")
            if count > max_context_tokens:
                break
            blocks.append(block)
            included.append(evidence.evidence_id)
            accepted_count = count
        text = "\n\n".join(blocks)
        return PackedContext(text, tuple(included), accepted_count if text else 0)

    def _matches_filters(self, evidence: IndexedEvidence, filters: RetrievalFilters) -> bool:
        return all(
            (expected is None or actual == expected)
            for expected, actual in (
                (filters.repository_slug, evidence.repository_slug),
                (filters.language, evidence.language),
                (filters.evidence_class, evidence.evidence_class),
                (filters.source_type, str(evidence.metadata.get("source_type", ""))),
            )
        )

    @staticmethod
    def _retrieval_policy(connection: sqlite3.Connection) -> dict[str, Any]:
        row = connection.execute(
            "SELECT value FROM bundle_meta WHERE key = 'retrieval_policy'"
        ).fetchone()
        if row is None:
            raise IndexReadError("retrieval_policy_invalid")
        try:
            value = json.loads(str(row[0]))
            if not isinstance(value, dict) or set(value) != {
                "enabled_sources",
                "fusion",
                "source_weights",
            }:
                raise ValueError
            sources = value["enabled_sources"]
            fusion = value["fusion"]
            weights = value["source_weights"]
            categories = {
                "owner_assertions",
                "repository_metadata",
                "documentation",
                "source_code",
            }
            if (
                not isinstance(sources, list)
                or not sources
                or len(sources) != len(set(sources))
                or any(
                    not isinstance(source, str) or source not in categories for source in sources
                )
                or not isinstance(fusion, dict)
                or set(fusion)
                != {
                    "rrf_k",
                    "lexical_weight",
                    "vector_weight",
                    "candidate_count_per_channel",
                    "final_context_records",
                    "max_records_per_repository",
                }
                or not isinstance(weights, dict)
                or set(weights) != categories
            ):
                raise ValueError
            integer_fields = (
                "rrf_k",
                "candidate_count_per_channel",
                "final_context_records",
                "max_records_per_repository",
            )
            if any(not _positive_integer(fusion[field]) for field in integer_fields):
                raise ValueError
            channel_weights = (fusion["lexical_weight"], fusion["vector_weight"])
            if (
                any(not _nonnegative_finite_number(weight) for weight in channel_weights)
                or not any(float(weight) > 0 for weight in channel_weights)
                or any(not _nonnegative_finite_number(weight) for weight in weights.values())
            ):
                raise ValueError
            return value
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise IndexReadError("retrieval_policy_invalid") from exc

    @staticmethod
    def _quick_check(connection: sqlite3.Connection) -> None:
        row = connection.execute("PRAGMA quick_check").fetchone()
        if row is None or str(row[0]).casefold() != "ok":
            raise IndexReadError("index_integrity_failed")

    @staticmethod
    def _embedding_from_meta(connection: sqlite3.Connection) -> EmbeddingIdentity:
        values = {
            str(row["key"]): str(row["value"])
            for row in connection.execute("SELECT key, value FROM bundle_meta")
        }
        if values.get("index_schema_version") != str(INDEX_SCHEMA_VERSION):
            raise IndexReadError("index_schema_incompatible")
        raw_value = values.get("embedding")
        if raw_value is None:
            raise IndexReadError("embedding_metadata_invalid")
        raw_embedding = json.loads(raw_value)
        if not isinstance(raw_embedding, dict):
            raise IndexReadError("embedding_metadata_invalid")
        try:
            normalized = raw_embedding["normalized"]
            if normalized is not True:
                raise ValueError("normalized embedding metadata is required")
            return EmbeddingIdentity(
                adapter=str(raw_embedding["adapter"]),
                model_id=str(raw_embedding["model_id"]),
                dimension=int(raw_embedding["dimension"]),
                normalized=normalized,
                query_prefix=str(raw_embedding["query_prefix"]),
                passage_prefix=str(raw_embedding["passage_prefix"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IndexReadError("embedding_metadata_invalid") from exc

    @staticmethod
    def _validate_query_schema(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("SELECT evidence_id FROM evidence LIMIT 1").fetchone()
            connection.execute("SELECT evidence_id FROM evidence_fts_terms LIMIT 1").fetchone()
            connection.execute("SELECT evidence_id FROM evidence_fts_trigram LIMIT 1").fetchone()
        except sqlite3.Error as exc:
            raise IndexReadError("index_schema_incompatible") from exc

    @staticmethod
    def _load_vectors(
        connection: sqlite3.Connection,
        embedding: EmbeddingIdentity,
    ) -> ValidatedVectorMatrix:
        rows = connection.execute(
            """
            SELECT evidence_id, model_id, dimension, normalized, vector_f32_le
            FROM embeddings ORDER BY evidence_id ASC
            """
        ).fetchall()
        if not rows:
            raise IndexReadError("index_has_no_embeddings")
        evidence_ids: list[str] = []
        vectors: list[np.ndarray] = []
        expected_bytes = embedding.dimension * np.dtype("<f4").itemsize
        for row in rows:
            if (
                str(row["model_id"]) != embedding.model_id
                or int(row["dimension"]) != embedding.dimension
                or int(row["normalized"]) != 1
                or len(bytes(row["vector_f32_le"])) != expected_bytes
            ):
                raise IndexReadError("embedding_blob_incompatible")
            evidence_ids.append(str(row["evidence_id"]))
            vectors.append(
                np.frombuffer(bytes(row["vector_f32_le"]), dtype="<f4").astype(np.float32)
            )
        try:
            return validate_vector_matrix(
                evidence_ids,
                np.stack(vectors).astype(np.float32),
                dimension=embedding.dimension,
            )
        except ValueError as exc:
            raise IndexReadError("embedding_blob_invalid") from exc


def _source_category(evidence: IndexedEvidence) -> str:
    if evidence.evidence_class == "OWNER_ASSERTION":
        return "owner_assertions"
    value = evidence.metadata.get("source_type")
    return (
        str(value)
        if value in {"repository_metadata", "documentation", "source_code"}
        else "source_code"
    )


def _escape_context_markers(content: str) -> str:
    """Keep untrusted text visible without allowing it to impersonate a boundary."""

    return content.replace("[UNTRUSTED DATA", "[UNTRUSTED\\ DATA").replace(
        "[/UNTRUSTED DATA]", "[/UNTRUSTED\\ DATA]"
    )


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


def _validated_retrieval_override(value: int | None, configured: int) -> int:
    if value is None:
        return configured
    if not _positive_integer(value):
        raise ValueError("retrieval limits must be positive integers")
    return min(value, configured)


def _overlaps(left: IndexedEvidence, right: IndexedEvidence) -> bool:
    return (
        (left.repository_slug, left.commit_sha, left.path)
        == (right.repository_slug, right.commit_sha, right.path)
        and left.start_line <= right.end_line
        and right.start_line <= left.end_line
    )


def _evidence_from_row(row: sqlite3.Row) -> IndexedEvidence:
    metadata = json.loads(str(row["metadata_json"]))
    if not isinstance(metadata, dict):
        raise IndexReadError("evidence_metadata_invalid")
    return IndexedEvidence(
        evidence_id=str(row["evidence_id"]),
        evidence_class=str(row["evidence_class"]),
        repository_slug=str(row["slug"]),
        commit_sha=str(row["commit_sha"]),
        path=str(row["path"]),
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        title=str(row["title"]) if row["title"] is not None else None,
        symbol=str(row["symbol"]) if row["symbol"] is not None else None,
        content=str(row["content"]),
        language=str(row["language"]) if row["language"] is not None else None,
        metadata=metadata,
    )
