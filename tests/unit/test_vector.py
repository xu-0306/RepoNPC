"""Unit tests for strict vector validation and deterministic ranking."""

from __future__ import annotations

import numpy as np
import pytest

from reponpc.retrieval.vector import (
    ValidatedVectorMatrix,
    rank_vectors,
    validate_query_vector,
    validate_vector_matrix,
)


def test_validate_vector_matrix_returns_an_independent_read_only_float32_copy() -> None:
    source = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    matrix = validate_vector_matrix(["E_beta", "E_alpha"], source, dimension=2)
    source[0, 0] = 0.0

    assert matrix.values.dtype == np.float32
    assert matrix.values.flags.writeable is False
    assert matrix.values[0, 0] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        matrix.values[0, 0] = 0.5


@pytest.mark.parametrize(
    ("evidence_ids", "values", "dimension", "message"),
    [
        (["E_alpha"], np.array([[1.0]], dtype=np.float64), 1, "float32"),
        (["E_alpha"], np.array([1.0], dtype=np.float32), 1, "declared dimension"),
        (["E_alpha"], np.array([[1.0, 0.0]], dtype=np.float32), 1, "declared dimension"),
        (["E_alpha"], np.array([[np.nan]], dtype=np.float32), 1, "finite"),
        (["E_alpha"], np.array([[np.inf]], dtype=np.float32), 1, "finite"),
        (["E_alpha"], np.array([[0.0]], dtype=np.float32), 1, "unit norms"),
        (["E_alpha"], np.array([[2.0]], dtype=np.float32), 1, "unit norms"),
        (["E_alpha", "E_alpha"], np.eye(2, dtype=np.float32), 2, "unique"),
        (["E_alpha"], np.eye(2, dtype=np.float32), 2, "one entry"),
    ],
)
def test_validate_vector_matrix_rejects_malformed_input(
    evidence_ids: list[str], values: np.ndarray, dimension: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_vector_matrix(evidence_ids, values, dimension=dimension)


@pytest.mark.parametrize("dimension", [0, -1, True])
def test_validate_vector_matrix_rejects_invalid_dimension(dimension: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        validate_vector_matrix([], np.empty((0, 1), dtype=np.float32), dimension=dimension)


def test_validate_query_vector_rejects_wrong_dtype_shape_and_non_unit_values() -> None:
    for query in (
        np.array([1.0, 0.0], dtype=np.float64),
        np.array([[1.0, 0.0]], dtype=np.float32),
        np.array([0.0, 0.0], dtype=np.float32),
    ):
        with pytest.raises(ValueError):
            validate_query_vector(query, dimension=2)


def test_validated_vector_matrix_rejects_directly_constructed_forged_state() -> None:
    with pytest.raises(ValueError, match="finite"):
        ValidatedVectorMatrix(
            evidence_ids=("E_nan",),
            values=np.array([[np.nan, 0.0]], dtype=np.float32),
            dimension=2,
        )


def test_rank_vectors_uses_dot_product_score_and_evidence_id_tie_breaker() -> None:
    matrix = validate_vector_matrix(
        ["E_zeta", "E_alpha", "E_orthogonal"],
        np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        dimension=2,
    )

    results = rank_vectors(matrix, np.array([1.0, 0.0], dtype=np.float32), limit=2)

    assert [(result.evidence_id, result.score) for result in results] == [
        ("E_alpha", pytest.approx(1.0)),
        ("E_zeta", pytest.approx(1.0)),
    ]


def test_rank_vectors_handles_empty_matrix_and_limits() -> None:
    empty = validate_vector_matrix([], np.empty((0, 2), dtype=np.float32), dimension=2)

    assert rank_vectors(empty, np.array([1.0, 0.0], dtype=np.float32)) == []

    matrix = validate_vector_matrix(
        ["E_alpha"], np.array([[1.0, 0.0]], dtype=np.float32), dimension=2
    )
    assert rank_vectors(matrix, np.array([1.0, 0.0], dtype=np.float32), limit=0) == []
    with pytest.raises(ValueError, match="non-negative integer"):
        rank_vectors(matrix, np.array([1.0, 0.0], dtype=np.float32), limit=-1)
    with pytest.raises(ValueError, match="non-negative integer"):
        rank_vectors(matrix, np.array([1.0, 0.0], dtype=np.float32), limit=True)
