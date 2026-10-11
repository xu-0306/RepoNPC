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
    assert compiled.fallback_fragments == ()


def test_compile_fts_query_prepares_bounded_non_ascii_trigram_recovery() -> None:
    compiled = compile_fts_query("請比較架構與資料儲存方式")

    assert compiled.mode is FtsQueryMode.MATCH
    assert compiled.match_expression == '"請比較架構與資料儲存方式"'
    trigram_fragments = [value for value, _, width in compiled.fallback_fragments if width == 3]
    assert len(trigram_fragments) >= 2
    assert all(
        expression.startswith('"') and expression.endswith('"') for expression in trigram_fragments
    )
    assert all(
        " OR " not in expression and "NEAR" not in expression for expression in trigram_fragments
    )
    exact_values = {value for value, _, width in compiled.fallback_fragments if width == 2}
    assert "儲存" in exact_values
    assert all(len(value) == 2 for value in exact_values)


def test_compile_fts_query_does_not_relax_mixed_ascii_path_queries() -> None:
    compiled = compile_fts_query("請比較架構 src/api.py")

    assert compiled.fallback_fragments
    assert compiled.fallback_required_expression == '"src/api.py"'


def test_compile_fts_query_keeps_later_fragments_after_duplicate_prefixes() -> None:
    compiled = compile_fts_query("甲乙丙丁戊己庚辛壬。丁戊己甲乙丙癸子丑")

    trigram_fragments = {value for value, _, width in compiled.fallback_fragments if width == 3}
    assert '"庚辛壬"' in trigram_fragments
    assert '"癸子丑"' in trigram_fragments


def test_compile_fts_query_deduplicates_repeated_short_values() -> None:
    compiled = compile_fts_query("架構架構")

    assert [value for value, _, width in compiled.fallback_fragments if width == 2].count(
        "架構"
    ) == 1


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


@pytest.mark.parametrize(
    "question", ["請比較QuartzRepo架構", "請比較 QuartzRepo 架構", "請說明第2026版架構"]
)
def test_mixed_queries_keep_non_ascii_fragments_and_optional_ascii_channels(question: str) -> None:
    compiled = compile_fts_query(question)
    assert compiled.fallback_fragments
    assert compiled.fallback_ascii_terms
    assert compiled.fallback_required_expression is None
    assert len(compiled.fallback_fragments) + len(compiled.fallback_ascii_terms) <= MAX_FTS_TERMS


@pytest.mark.parametrize("path", ["src/not-present.py", "not-present.py", r"src\not-present.py"])
def test_path_structure_remains_required_next_to_non_ascii_text(path: str) -> None:
    compiled = compile_fts_query(f"請說明繁體中文{path}")
    assert compiled.fallback_required_expression == f'"{path}"'
    assert not compiled.fallback_ascii_terms


def test_mixed_fragment_budget_includes_ascii_channels_and_path_requirements() -> None:
    compiled = compile_fts_query(
        "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥QuartzRepo OtherRepo src/file.py"
    )
    assert (
        len(compiled.fallback_fragments) + len(compiled.fallback_ascii_terms) + 1 <= MAX_FTS_TERMS
    )
