"""Fresh evaluator probe for the public vector-container boundary."""

from __future__ import annotations

import json

import numpy as np

from reponpc.retrieval.vector import ValidatedVectorMatrix, rank_vectors


def main() -> None:
    nan_rejected = False
    try:
        ValidatedVectorMatrix(
            evidence_ids=("E_nan",),
            values=np.array([[np.nan, 0.0]], dtype=np.float32),
            dimension=2,
        )
    except ValueError as error:
        nan_rejected = "finite" in str(error)
    assert nan_rejected

    caller_owned_values = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    matrix = ValidatedVectorMatrix(
        evidence_ids=("E_alpha", "E_beta"),
        values=caller_owned_values,
        dimension=2,
    )
    caller_owned_values[0, :] = np.array([np.nan, np.nan], dtype=np.float32)

    write_attempt_rejected = False
    try:
        matrix.values[0, 0] = np.float32(0.0)
    except ValueError:
        write_attempt_rejected = True

    results = rank_vectors(matrix, np.array([1.0, 0.0], dtype=np.float32))
    scores = [match.score for match in results]

    assert matrix.values.flags.writeable is False
    assert not np.shares_memory(matrix.values, caller_owned_values)
    assert np.isfinite(matrix.values).all()
    assert write_attempt_rejected
    assert all(np.isfinite(scores))
    assert [(match.evidence_id, match.score) for match in results] == [
        ("E_alpha", 1.0),
        ("E_beta", 0.0),
    ]

    print(
        json.dumps(
            {
                "probe": "direct vector construction and mutable caller input",
                "nan_direct_construction": "rejected",
                "matrix_writeable": bool(matrix.values.flags.writeable),
                "shares_caller_memory": bool(np.shares_memory(matrix.values, caller_owned_values)),
                "matrix_is_finite_after_caller_nan_mutation": bool(np.isfinite(matrix.values).all()),
                "rank_scores": scores,
                "rank_scores_all_finite": bool(all(np.isfinite(scores))),
                "oracle": "NaN direct construction is rejected; valid direct construction copies to a read-only finite matrix and ranking stays finite",
                "anti_oracle": "caller source was changed to NaN after construction but matrix and scores stayed finite",
                "result": "passed",
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
