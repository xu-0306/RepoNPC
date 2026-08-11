"""Validate normalized embedding vectors and rank them deterministically."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

_UNIT_NORM_RTOL = 1e-5
_UNIT_NORM_ATOL = 1e-6


@dataclass(frozen=True, slots=True)
class ValidatedVectorMatrix:
    """An immutable, row-aligned matrix of already normalized vectors."""

    evidence_ids: tuple[str, ...]
    values: NDArray[np.float32]
    dimension: int

    def __post_init__(self) -> None:
        """Reject forged or mutable invalid state at the public container boundary."""
        _validate_dimension(self.dimension)
        evidence_ids = _validate_evidence_ids(self.evidence_ids)
        matrix = _copy_float32_matrix(self.values, dimension=self.dimension)
        if len(evidence_ids) != matrix.shape[0]:
            raise ValueError("evidence_ids must have one entry for every vector row")
        _validate_unit_norms(matrix, label="vector rows")

        matrix.setflags(write=False)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "values", matrix)


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """One deterministic vector-search result."""

    evidence_id: str
    score: float


def validate_vector_matrix(
    evidence_ids: Sequence[str], values: NDArray[np.float32], *, dimension: int
) -> ValidatedVectorMatrix:
    """Validate a row-aligned float32 unit-vector matrix without normalizing it.

    The returned matrix is an independent read-only copy. Rejecting rather
    than fixing malformed values keeps bundle/provider compatibility failures
    visible to their future owner.
    """
    ids = _validate_evidence_ids(evidence_ids)
    return ValidatedVectorMatrix(evidence_ids=ids, values=values, dimension=dimension)


def validate_query_vector(value: NDArray[np.float32], *, dimension: int) -> NDArray[np.float32]:
    """Validate one float32 normalized query vector and return a read-only copy."""
    _validate_dimension(dimension)
    if not isinstance(value, np.ndarray) or value.dtype != np.dtype(np.float32):
        raise ValueError("query vector must be a NumPy float32 array")
    if value.ndim != 1 or value.shape[0] != dimension:
        raise ValueError("query vector must have exactly the declared dimension")

    query = value.copy()
    _validate_unit_norms(query.reshape(1, dimension), label="query vector")
    query.setflags(write=False)
    return query


def rank_vectors(
    matrix: ValidatedVectorMatrix,
    query: NDArray[np.float32],
    *,
    limit: int | None = None,
) -> list[VectorMatch]:
    """Rank a validated matrix by dot/cosine score with an explicit stable tie-break."""
    if not isinstance(matrix, ValidatedVectorMatrix):
        raise TypeError("matrix must be a ValidatedVectorMatrix")
    normalized_query = validate_query_vector(query, dimension=matrix.dimension)
    result_limit = _validate_limit(limit, size=len(matrix.evidence_ids))
    if result_limit == 0:
        return []

    scores = matrix.values @ normalized_query
    ordering = sorted(
        range(len(matrix.evidence_ids)),
        key=lambda index: (-float(scores[index]), matrix.evidence_ids[index]),
    )
    return [
        VectorMatch(evidence_id=matrix.evidence_ids[index], score=float(scores[index]))
        for index in ordering[:result_limit]
    ]


def _validate_dimension(dimension: int) -> None:
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension <= 0:
        raise ValueError("dimension must be a positive integer")


def _validate_evidence_ids(evidence_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(evidence_ids, (str, bytes)):
        raise ValueError("evidence_ids must be a sequence of strings")

    ids = tuple(evidence_ids)
    if any(not isinstance(evidence_id, str) or not evidence_id for evidence_id in ids):
        raise ValueError("evidence_ids must contain non-empty strings")
    if len(set(ids)) != len(ids):
        raise ValueError("evidence_ids must be unique")
    return ids


def _copy_float32_matrix(values: NDArray[np.float32], *, dimension: int) -> NDArray[np.float32]:
    if not isinstance(values, np.ndarray) or values.dtype != np.dtype(np.float32):
        raise ValueError("vector matrix must be a NumPy float32 array")
    if values.ndim != 2 or values.shape[1] != dimension:
        raise ValueError("vector matrix must have exactly the declared dimension")

    matrix = values.copy()
    if not np.isfinite(matrix).all():
        raise ValueError("vector matrix values must be finite")
    return matrix


def _validate_unit_norms(values: NDArray[np.float32], *, label: str) -> None:
    if not np.isfinite(values).all():
        raise ValueError(f"{label} values must be finite")
    norms = np.linalg.vector_norm(values, axis=1)
    if not np.allclose(norms, 1.0, rtol=_UNIT_NORM_RTOL, atol=_UNIT_NORM_ATOL):
        raise ValueError(f"{label} must have nonzero unit norms")


def _validate_limit(limit: int | None, *, size: int) -> int:
    if limit is None:
        return size
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer or None")
    return min(limit, size)
