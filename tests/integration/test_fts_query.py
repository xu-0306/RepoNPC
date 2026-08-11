"""Real SQLite FTS5 probes for the safe lexical query compiler."""

from __future__ import annotations

import sqlite3

import pytest

from reponpc.retrieval.fts_query import FtsQueryMode, compile_fts_query


@pytest.fixture
def fts_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE VIRTUAL TABLE terms USING fts5(evidence_id UNINDEXED, content)")
    connection.execute(
        "CREATE VIRTUAL TABLE trigrams "
        "USING fts5(evidence_id UNINDEXED, content, tokenize='trigram')"
    )
    rows = [
        ("E_literal", "alpha OR beta appears as literal text"),
        ("E_alpha", "alpha appears without the operator word"),
        ("E_beta", "beta appears without the operator word"),
        ("E_near", "alpha NEAR beta appears as literal text"),
        ("E_path", "src/api.py config_key handles 繁體中文 locale"),
        ("E_decoy", "alpha beta ordinary phrase"),
        ("E_alphabet", "alphabet is a distinct token"),
    ]
    connection.executemany("INSERT INTO terms(evidence_id, content) VALUES (?, ?)", rows)
    connection.executemany("INSERT INTO trigrams(evidence_id, content) VALUES (?, ?)", rows)
    yield connection
    connection.close()


def _match_ids(connection: sqlite3.Connection, table: str, expression: str) -> list[str]:
    sql_by_table = {
        "terms": "SELECT evidence_id FROM terms WHERE terms MATCH ? ORDER BY evidence_id",
        "trigrams": "SELECT evidence_id FROM trigrams WHERE trigrams MATCH ? ORDER BY evidence_id",
    }
    return [row[0] for row in connection.execute(sql_by_table[table], (expression,))]


@pytest.mark.parametrize("table", ["terms", "trigrams"])
def test_compiled_expression_runs_as_one_bound_value_on_real_fts5(
    fts_database: sqlite3.Connection, table: str
) -> None:
    compiled = compile_fts_query("src/api.py config_key 繁體中文")

    assert compiled.mode is FtsQueryMode.MATCH
    assert compiled.match_expression is not None
    assert _match_ids(fts_database, table, compiled.match_expression) == ["E_path"]


@pytest.mark.parametrize("table", ["terms", "trigrams"])
@pytest.mark.parametrize(
    ("question", "must_not_match"),
    [
        ("alpha OR beta", "E_decoy"),
        ("alpha NEAR beta", "E_decoy"),
        ('alpha" OR "beta', "E_decoy"),
        ("(alpha) OR (beta)", "E_decoy"),
        ("alpha\x00OR\x1fbeta", "E_decoy"),
    ],
)
def test_injection_shaped_input_cannot_broaden_beyond_literal_terms(
    fts_database: sqlite3.Connection, table: str, question: str, must_not_match: str
) -> None:
    compiled = compile_fts_query(question)

    assert compiled.mode is FtsQueryMode.MATCH
    assert compiled.match_expression is not None
    result_ids = _match_ids(fts_database, table, compiled.match_expression)

    assert must_not_match not in result_ids


def test_wildcard_is_stripped_before_a_term_fts5_match(fts_database: sqlite3.Connection) -> None:
    compiled = compile_fts_query("alpha*")

    assert compiled.match_expression == '"alpha"'
    assert "E_alphabet" not in _match_ids(fts_database, "terms", compiled.match_expression)


def test_short_queries_are_not_sent_to_match(fts_database: sqlite3.Connection) -> None:
    compiled = compile_fts_query("go")

    assert compiled.mode is FtsQueryMode.SHORT_EXACT
    assert compiled.match_expression is None
    assert compiled.exact_value == "go"
