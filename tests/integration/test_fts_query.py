"""Real SQLite FTS5 probes for the safe lexical query compiler."""

from __future__ import annotations

import sqlite3

import pytest

from reponpc.retrieval.fts_query import FtsQueryMode, compile_fts_query


@pytest.fixture
def fts_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE VIRTUAL TABLE evidence_fts_terms USING fts5("
        "evidence_id UNINDEXED, title, symbol, path, content)"
    )
    connection.execute(
        "CREATE VIRTUAL TABLE evidence_fts_trigram "
        "USING fts5(evidence_id UNINDEXED, title, symbol, path, content, tokenize='trigram')"
    )
    rows = [
        ("E_literal", "", "", "", "alpha OR beta appears as literal text"),
        ("E_alpha", "", "", "", "alpha appears without the operator word"),
        ("E_beta", "", "", "", "beta appears without the operator word"),
        ("E_near", "", "", "", "alpha NEAR beta appears as literal text"),
        ("E_path", "", "", "src/api.py", "config_key handles 繁體中文 locale"),
        ("E_decoy", "", "", "", "alpha beta ordinary phrase"),
        ("E_alphabet", "", "", "", "alphabet is a distinct token"),
        ("E_cjk_match", "", "", "", "系統採用架構與資料儲存方式"),
        ("E_cjk_one_fragment", "", "", "", "僅提到資料儲"),
        ("E_cjk_short_one_fragment", "", "", "", "僅提到儲存"),
        ("E_cjk_decoy", "", "", "", "請比較版本"),
    ]
    connection.executemany(
        "INSERT INTO evidence_fts_terms(evidence_id, title, symbol, path, content) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    connection.executemany(
        "INSERT INTO evidence_fts_trigram(evidence_id, title, symbol, path, content) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    yield connection
    connection.close()


def _match_ids(connection: sqlite3.Connection, table: str, expression: str) -> list[str]:
    sql_by_table = {
        "terms": (
            "SELECT evidence_id FROM evidence_fts_terms "
            "WHERE evidence_fts_terms MATCH ? ORDER BY evidence_id"
        ),
        "trigrams": (
            "SELECT evidence_id FROM evidence_fts_trigram "
            "WHERE evidence_fts_trigram MATCH ? ORDER BY evidence_id"
        ),
    }
    return [row[0] for row in connection.execute(sql_by_table[table], (expression,))]


def _short_match_ids(connection: sqlite3.Connection, value: str) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            """
            SELECT evidence_id FROM evidence_fts_terms
            WHERE instr(
              lower(COALESCE(title, '') || ' ' || COALESCE(symbol, '') ||
                ' ' || path || ' ' || content), lower(?)
            ) > 0
            ORDER BY evidence_id
            """,
            (value,),
        )
    ]


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


def test_non_ascii_fallback_requires_two_generated_fragments(
    fts_database: sqlite3.Connection,
) -> None:
    compiled = compile_fts_query("請比較架構與資料儲存方式")

    assert compiled.fallback_fragments
    hit_counts: dict[str, int] = {}
    for expression, _, width in compiled.fallback_fragments:
        if width != 3:
            continue
        for evidence_id in _match_ids(fts_database, "trigrams", expression):
            hit_counts[evidence_id] = hit_counts.get(evidence_id, 0) + 1

    assert hit_counts["E_cjk_match"] >= 2
    assert hit_counts["E_cjk_one_fragment"] == 1
    assert hit_counts["E_cjk_decoy"] == 1


def test_non_ascii_exact_fragments_cover_later_subject_without_accepting_one_short_value(
    fts_database: sqlite3.Connection,
) -> None:
    compiled = compile_fts_query("請比較架構與資料儲存方式")
    hit_positions: dict[str, list[int]] = {}
    for value, position, width in compiled.fallback_fragments:
        if width != 2:
            continue
        for evidence_id in _short_match_ids(fts_database, value):
            hit_positions.setdefault(evidence_id, []).append(position)

    exact_positions = sorted(set(hit_positions["E_cjk_match"]))
    assert len(exact_positions) >= 2
    assert exact_positions[-1] - exact_positions[0] >= 2
    assert hit_positions["E_cjk_short_one_fragment"] == [
        next(
            position
            for value, position, width in compiled.fallback_fragments
            if width == 2 and value == "儲存"
        )
    ]


@pytest.mark.parametrize(
    "question",
    [
        "請說明QuartzRepo繁體中文",
        "請說明 QuartzRepo 繁體中文",
        "請說明第2026版繁體中文",
        "這3個專案的繁體中文",
        "請說明繁體中文 src/api.py",
        "請說明繁體中文src/api.py",
    ],
)
def test_reader_recovers_mixed_queries(fts_database: sqlite3.Connection, question: str) -> None:
    from reponpc.bundles.index_reader import ReadOnlyIndex

    reader = object.__new__(ReadOnlyIndex)
    reader._connection = fts_database
    assert "E_path" in reader.lexical_candidates(question, limit=8)


def test_reader_filters_paths_before_limits_and_rejects_nonexistent_paths(
    fts_database: sqlite3.Connection,
) -> None:
    from reponpc.bundles.index_reader import ReadOnlyIndex

    reader = object.__new__(ReadOnlyIndex)
    reader._connection = fts_database
    rows = [(f"A_decoy_{i}", "", "", "elsewhere.md", "繁體中文") for i in range(10)]
    for table in ("terms", "trigram"):
        fts_database.executemany(f"INSERT INTO evidence_fts_{table} VALUES (?,?,?,?,?)", rows)
    assert reader.lexical_candidates("請說明繁體中文 src/api.py", limit=1) == ["E_path"]
    assert reader.lexical_candidates("請說明繁體中文 src/not-present.py", limit=8) == []
    assert reader.lexical_candidates("請說明繁體中文 src/api.py absent.md", limit=8) == []


def test_separate_repository_ascii_channels_supply_one_independent_hit(
    fts_database: sqlite3.Connection,
) -> None:
    from reponpc.bundles.index_reader import ReadOnlyIndex

    reader = object.__new__(ReadOnlyIndex)
    reader._connection = fts_database
    rows = [
        ("E_quartz", "", "", "one.md", "QuartzRepo 瑪瑙"),
        ("E_cobalt", "", "", "two.md", "CobaltRepo 琥珀"),
        ("E_ascii_only", "", "", "three.md", "QuartzRepo"),
        ("E_short_only", "", "", "four.md", "瑪瑙"),
        ("E_tri_only", "", "", "five.md", "瑪瑙和"),
    ]
    for table in ("terms", "trigram"):
        fts_database.executemany(f"INSERT INTO evidence_fts_{table} VALUES (?,?,?,?,?)", rows)
    assert set(reader.lexical_candidates("比較QuartzRepo和CobaltRepo瑪瑙和琥珀", limit=8)) == {
        "E_quartz",
        "E_cobalt",
    }


def test_mixed_query_fts_operators_are_literal_not_executed(
    fts_database: sqlite3.Connection,
) -> None:
    from reponpc.bundles.index_reader import ReadOnlyIndex

    reader = object.__new__(ReadOnlyIndex)
    reader._connection = fts_database
    assert (
        reader.lexical_candidates('請說明繁體中文 src/missing.py" OR "src/api.py*', limit=8) == []
    )
