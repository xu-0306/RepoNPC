"""Deterministic Reciprocal Rank Fusion for independently ranked channels."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite


def fuse_rankings(
    rankings: Sequence[Sequence[str]],
    weights: Sequence[float] | None,
    *,
    k: float = 60,
) -> list[str]:
    """Fuse ranked evidence-ID channels using one-based Reciprocal Rank Fusion.

    Each channel contributes ``weight / (k + rank)`` for every evidence ID,
    where the first item has rank one.  The returned IDs are ordered by
    descending fused score, then ascending evidence ID to make ties stable.

    Args:
        rankings: Independently ranked evidence-ID channels.
        weights: One non-negative, finite weight for every channel.
        k: Positive RRF rank constant.

    Raises:
        ValueError: If ``k`` is not positive, weights are absent or invalid,
            or a channel contains an evidence ID more than once.
    """
    scores = rrf_scores(rankings, weights, k=k)
    return sorted(scores, key=lambda evidence_id: (-scores[evidence_id], evidence_id))


def rrf_scores(
    rankings: Sequence[Sequence[str]],
    weights: Sequence[float] | None,
    *,
    k: float = 60,
) -> dict[str, float]:
    """Return exact, unrounded RRF scores keyed by evidence ID.

    This is the shared primitive for rank ordering and policy adjustments. It
    deliberately retains the validation rules of :func:`fuse_rankings`.
    """
    if not isinstance(k, (int, float)) or isinstance(k, bool) or not isfinite(k) or k <= 0:
        raise ValueError("k must be a positive finite number")

    if weights is None:
        raise ValueError("weights are required for every ranking channel")
    if len(weights) != len(rankings):
        raise ValueError("weights must have one entry for every ranking channel")

    scores: dict[str, float] = {}
    for channel, weight in zip(rankings, weights, strict=True):
        if (
            not isinstance(weight, (int, float))
            or isinstance(weight, bool)
            or not isfinite(weight)
            or weight < 0
        ):
            raise ValueError("weights must be non-negative finite numbers")

        seen_ids: set[str] = set()
        for rank, evidence_id in enumerate(channel, start=1):
            if evidence_id in seen_ids:
                raise ValueError("ranking channels must not contain duplicate evidence IDs")
            seen_ids.add(evidence_id)
            scores[evidence_id] = scores.get(evidence_id, 0.0) + weight / (k + rank)

    return scores
