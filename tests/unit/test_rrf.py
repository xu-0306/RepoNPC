"""Tests for deterministic Reciprocal Rank Fusion."""

from __future__ import annotations

import math

import pytest

from reponpc.retrieval.rrf import fuse_rankings, rrf_scores


def test_fuse_rankings_uses_one_based_weighted_rrf_scores() -> None:
    result = fuse_rankings(
        [["E_alpha", "E_beta"], ["E_beta", "E_gamma"]],
        [2.0, 1.0],
        k=2,
    )

    # E_beta: 2 / (2 + 2) + 1 / (2 + 1) = 5 / 6, the highest score.
    assert result == ["E_beta", "E_alpha", "E_gamma"]


def test_rrf_scores_sum_every_channel_before_deterministic_ordering() -> None:
    scores = rrf_scores(
        [["E_alpha", "E_beta"], ["E_beta", "E_gamma"]],
        [2.0, 1.0],
        k=2,
    )

    assert scores == {
        "E_alpha": 2.0 / 3.0,
        "E_beta": 2.0 / 4.0 + 1.0 / 3.0,
        "E_gamma": 1.0 / 4.0,
    }
    assert fuse_rankings([["E_alpha", "E_beta"], ["E_beta", "E_gamma"]], [2.0, 1.0], k=2) == [
        "E_beta",
        "E_alpha",
        "E_gamma",
    ]


def test_fuse_rankings_returns_empty_list_for_empty_channels() -> None:
    assert fuse_rankings([[], []], [1.0, 0.0]) == []


def test_fuse_rankings_orders_equal_scores_by_evidence_id() -> None:
    assert fuse_rankings([["E_zeta"], ["E_alpha"]], [1.0, 1.0], k=1) == [
        "E_alpha",
        "E_zeta",
    ]


@pytest.mark.parametrize("k", [0, -1, math.inf, -math.inf, math.nan])
def test_fuse_rankings_rejects_non_positive_or_non_finite_k(k: float) -> None:
    with pytest.raises(ValueError, match="k must be a positive finite number"):
        fuse_rankings([["E_alpha"]], [1.0], k=k)


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        (None, "weights are required"),
        ([1.0], "weights must have one entry"),
        ([-1.0, 1.0], "weights must be non-negative finite numbers"),
        ([math.inf, 1.0], "weights must be non-negative finite numbers"),
        ([math.nan, 1.0], "weights must be non-negative finite numbers"),
    ],
)
def test_fuse_rankings_rejects_missing_or_invalid_weights(
    weights: list[float] | None, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        fuse_rankings([["E_alpha"], ["E_beta"]], weights)


def test_fuse_rankings_rejects_duplicate_evidence_ids_within_a_channel() -> None:
    with pytest.raises(ValueError, match="must not contain duplicate"):
        fuse_rankings([["E_alpha", "E_alpha"], ["E_alpha"]], [1.0, 1.0])
