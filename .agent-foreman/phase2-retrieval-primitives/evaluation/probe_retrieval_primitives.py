"""Fresh-context falsification probes for P2-03/P2-04 public primitives.

This evaluator-owned script intentionally does not import private helper symbols.
It writes durable JSON observations under this campaign's evaluation directory.
"""

from __future__ import annotations

import json
import math
import sqlite3
import argparse
from pathlib import Path

import numpy as np

from reponpc.retrieval.fts_query import FtsQueryMode, compile_fts_query
from reponpc.retrieval.vector import (
    ValidatedVectorMatrix,
    rank_vectors,
    validate_vector_matrix,
)


ARTIFACTS = Path(__file__).parent / "artifacts"


def _write(name: str, payload: dict[str, object]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fts_probe() -> bool:
    """Show that generated phrases resist a real FTS5 boolean injection shape."""
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE VIRTUAL TABLE evidence USING fts5(evidence_id UNINDEXED, content)")
        connection.executemany(
            "INSERT INTO evidence(evidence_id, content) VALUES (?, ?)",
            [
                ("E_literal", "alpha OR beta is documented literally"),
                ("E_alpha", "alpha appears without the operator word"),
                ("E_beta", "beta appears without the operator word"),
                ("E_decoy", "unrelated record"),
            ],
        )
        attack = 'alpha" OR "beta'
        compiled = compile_fts_query(attack)
        assert compiled.mode is FtsQueryMode.MATCH
        assert compiled.match_expression is not None
        compiled_result = [
            row[0]
            for row in connection.execute(
                "SELECT evidence_id FROM evidence WHERE evidence MATCH ? ORDER BY evidence_id",
                (compiled.match_expression,),
            )
        ]
        # Anti-oracle: executing attacker-shaped boolean syntax directly would
        # broaden the result. This direct call is deliberately not the claim.
        raw_result = [
            row[0]
            for row in connection.execute(
                "SELECT evidence_id FROM evidence WHERE evidence MATCH ? ORDER BY evidence_id",
                ("alpha OR beta",),
            )
        ]
        passed = compiled_result == ["E_literal"] and {"E_alpha", "E_beta"}.issubset(raw_result)
        _write(
            "probe-fts-no-raw-syntax.json",
            {
                "probe_id": "EVAL-PROBE-FTS-001",
                "invariant_id": "INV-FTS-NO-RAW-SYNTAX",
                "setup": "in-memory SQLite FTS5 virtual table with literal and decoy alpha/beta records",
                "fault_injection": attack,
                "trigger": "compile_fts_query followed by public SQLite MATCH with the generated expression as one bound value",
                "oracle": {"compiled_mode": compiled.mode.value, "compiled_result": compiled_result},
                "anti_oracle": {
                    "bypassed_compiler_expression": "alpha OR beta",
                    "raw_result": raw_result,
                    "reason": "direct FTS syntax broadens to operator-decoy records and is not evidence of safe compilation",
                },
                "expected": {"compiled_result": ["E_literal"], "raw_contains": ["E_alpha", "E_beta"]},
                "passed": passed,
            },
        )
        return passed
    finally:
        connection.close()


def _vector_probe() -> bool:
    """Falsify direct construction of a malformed public matrix container."""
    valid = validate_vector_matrix(
        ["E_valid"], np.array([[1.0, 0.0]], dtype=np.float32), dimension=2
    )
    rejected_by_validator = False
    try:
        validate_vector_matrix(
            ["E_nan"], np.array([[math.nan, 0.0]], dtype=np.float32), dimension=2
        )
    except ValueError:
        rejected_by_validator = True

    # Fault injection uses the public dataclass constructor. The container is
    # the ranker's public matrix boundary: rejection here prevents malformed
    # state from ever reaching rank_vectors.
    constructor_error: str | None = None
    forged_results: list[dict[str, object]] = []
    try:
        forged = ValidatedVectorMatrix(
            evidence_ids=("E_nan",),
            values=np.array([[math.nan, 0.0]], dtype=np.float32),
            dimension=2,
        )
    except ValueError as error:
        constructor_error = f"{type(error).__name__}: {error}"
    else:
        forged_results = [
            {"evidence_id": result.evidence_id, "score": result.score}
            for result in rank_vectors(forged, np.array([1.0, 0.0], dtype=np.float32))
        ]

    returned_non_finite = any(
        not math.isfinite(float(result["score"])) for result in forged_results
    )
    passed = rejected_by_validator and constructor_error is not None and not forged_results
    _write(
        "probe-vector-validation.json",
        {
            "probe_id": "EVAL-PROBE-VECTOR-001",
            "invariant_id": "INV-VECTOR-VALIDATION",
            "setup": "public validator creates a valid 2D float32 unit-vector matrix",
            "fault_injection": "NaN float32 row, first submitted to validate_vector_matrix and then placed in a directly constructed ValidatedVectorMatrix",
            "trigger": "public validate_vector_matrix and public ValidatedVectorMatrix constructor; rank_vectors is called only if malformed construction succeeds",
            "oracle": {
                "validator_rejected_nan": rejected_by_validator,
                "constructor_error": constructor_error,
                "forged_results": forged_results,
                "returned_non_finite_score": returned_non_finite,
            },
            "anti_oracle": {
                "bypassed_entrypoint": "numpy dot product over the malformed row",
                "reason": "a direct NumPy score is deliberately not an accepted ranking path",
            },
            "expected": "The public validated-matrix boundary rejects malformed state before rank_vectors can return any score",
            "passed": passed,
        },
    )
    return passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=("all", "fts", "vector"), default="all")
    args = parser.parse_args()

    fts_passed = _fts_probe() if args.probe in {"all", "fts"} else None
    vector_passed = _vector_probe() if args.probe in {"all", "vector"} else None
    passed = all(result is not False for result in (fts_passed, vector_passed))
    summary = {
        "fts_passed": fts_passed,
        "vector_passed": vector_passed,
        "deterministic_result": "passed" if passed else "failed",
    }
    _write("probe-summary.json", summary)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
