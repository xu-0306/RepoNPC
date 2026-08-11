"""Unit tests for the safe FTS5 query compiler."""

from __future__ import annotations

import pytest

from reponpc.retrieval.fts_query import (
    MAX_FTS_TERM_CHARACTERS,
    MAX_FTS_TERMS,
    FtsQueryMode,
    compile_fts_query,
)


def test_compile_fts_query_normalizes_and_generates_only_quoted_conjunctions() -> None:
    compiled = compile_fts_query("Cafe\u0301 src/api.py zh-TW")

    assert compiled.mode is FtsQueryMode.MATCH
    assert compiled.normalized_text == "Café src/api.py zh-TW"
    assert compiled.terms == ("Café", "src/api.py", "zh-TW")
    assert compiled.match_expression == '"Café" AND "src/api.py" AND "zh-TW"'
    assert compiled.exact_value is None


@pytest.mark.parametrize("question", ["", " \t\n", "\x00\x1f\u200b"])
def test_compile_fts_query_returns_no_query_for_empty_or_control_only_input(question: str) -> None:
    compiled = compile_fts_query(question)

    assert compiled.mode is FtsQueryMode.NO_QUERY
    assert compiled.terms == ()
    assert compiled.match_expression is None
    assert compiled.exact_value is None


@pytest.mark.parametrize("question", ["C", "go", "台灣"])
def test_compile_fts_query_uses_literal_short_value_fallback(question: str) -> None:
    compiled = compile_fts_query(question)

    assert compiled.mode is FtsQueryMode.SHORT_EXACT
    assert compiled.exact_value == question
    assert compiled.match_expression is None


@pytest.mark.parametrize(
    ("question", "expected_expression"),
    [
        ("alpha OR beta", '"alpha" AND "OR" AND "beta"'),
        ("alpha NEAR beta", '"alpha" AND "NEAR" AND "beta"'),
        ("alpha* (beta) {gamma}", '"alpha" AND "(beta)" AND "{gamma}"'),
        ("alpha\x00OR\x1fbeta", '"alpha" AND "OR" AND "beta"'),
        ('"alpha" OR "beta"', '"alpha" AND "OR" AND "beta"'),
    ],
)
def test_compile_fts_query_never_passes_raw_operator_syntax(
    question: str, expected_expression: str
) -> None:
    compiled = compile_fts_query(question)

    assert compiled.mode is FtsQueryMode.MATCH
    assert compiled.match_expression == expected_expression


def test_compile_fts_query_ignores_punctuation_without_searchable_content() -> None:
    compiled = compile_fts_query('* () {} \\ "')

    assert compiled.mode is FtsQueryMode.NO_QUERY


def test_compile_fts_query_rejects_non_text_and_oversized_fragments() -> None:
    with pytest.raises(TypeError, match="question must be a string"):
        compile_fts_query(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="128 characters"):
        compile_fts_query("a" * (MAX_FTS_TERM_CHARACTERS + 1))
    with pytest.raises(ValueError, match="32 searchable terms"):
        compile_fts_query(" ".join("term" for _ in range(MAX_FTS_TERMS + 1)))
