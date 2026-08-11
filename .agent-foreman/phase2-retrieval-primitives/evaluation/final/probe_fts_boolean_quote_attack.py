"""Fresh evaluator probe for the public FTS compiler boundary.

Uses real in-memory SQLite FTS5 and passes both the raw attack and the
compiler-produced expression as bound ``MATCH`` values.  The raw, quoted
boolean attack must broaden results; the compiled expression must require the
literal operator token and therefore be a strict subset.
"""

from __future__ import annotations

import json
import sqlite3

from reponpc.retrieval.fts_query import FtsQueryMode, compile_fts_query


def _match_ids(connection: sqlite3.Connection, expression: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT evidence_id FROM evidence_fts "
            "WHERE evidence_fts MATCH ? ORDER BY evidence_id",
            (expression,),
        )
    ]


def main() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE evidence_fts USING fts5(evidence_id UNINDEXED, content)"
        )
        connection.executemany(
            "INSERT INTO evidence_fts(evidence_id, content) VALUES (?, ?)",
            [
                ("E_literal", "alpha OR beta is a literal phrase"),
                ("E_alpha", "alpha is present without the operator token"),
                ("E_beta", "beta is present without the operator token"),
                ("E_decoy", "alpha beta has no literal operator token"),
            ],
        )

        attack = '"alpha" OR "beta"'
        compiled = compile_fts_query(attack)
        assert compiled.mode is FtsQueryMode.MATCH
        assert compiled.match_expression == '"alpha" AND "OR" AND "beta"'

        raw_ids = _match_ids(connection, attack)
        compiled_ids = _match_ids(connection, compiled.match_expression)

        assert compiled_ids == ["E_literal"]
        assert set(compiled_ids) < set(raw_ids)
        assert "E_decoy" in raw_ids
        assert "E_decoy" not in compiled_ids

        print(
            json.dumps(
                {
                    "probe": "FTS5 quoted boolean attack",
                    "attack": attack,
                    "compiled_mode": compiled.mode.value,
                    "compiled_expression": compiled.match_expression,
                    "raw_match_ids": raw_ids,
                    "compiled_match_ids": compiled_ids,
                    "oracle": "compiled result is a strict subset of raw boolean MATCH and excludes E_decoy",
                    "anti_oracle": "raw quoted boolean MATCH includes E_decoy",
                    "result": "passed",
                },
                ensure_ascii=True,
                indent=2,
            )
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
