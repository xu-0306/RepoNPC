from __future__ import annotations

import pytest

from reponpc.indexing.parsing import ChunkCandidate, chunk_source, detect_language


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/app.py", "python"),
        ("apps/web/src/app.tsx", "tsx"),
        ("src/server.mjs", "javascript"),
        ("cmd/main.go", "go"),
        ("src/lib.rs", "rust"),
        ("README.md", "markdown"),
        ("notes.txt", "text"),
    ],
)
def test_detect_language_uses_path_suffixes(path: str, expected: str) -> None:
    assert detect_language(path) == expected


@pytest.mark.parametrize(
    ("path", "source", "symbol"),
    [
        ("src/app.py", "class Service:\n    def run(self):\n        return 'ok'\n", "Service"),
        ("src/app.js", "function run() { return 'ok'; }\n", "run"),
        ("src/app.ts", "interface Service { run(): void }\n", "Service"),
        ("cmd/app.go", 'func Run() string { return "ok" }\n', "Run"),
        ("src/lib.rs", "pub struct Service {}\n", "Service"),
    ],
)
def test_supported_languages_prefer_named_symbols(path: str, source: str, symbol: str) -> None:
    candidates = chunk_source(source, path=path)

    assert any(candidate.symbol == symbol for candidate in candidates)
    assert all(
        candidate.start_line >= 1 and candidate.end_line >= candidate.start_line
        for candidate in candidates
    )
    assert all(candidate.content for candidate in candidates)


def test_supported_source_is_deterministic_and_normalizes_crlf_with_multibyte_text() -> None:
    source = "def say_hello():\r\n    return '你好'\r\n"

    first = chunk_source(source, path="src/greeting.py")
    second = chunk_source(source, path="src/greeting.py")

    assert first == second
    assert first == [
        ChunkCandidate(
            start_line=1,
            end_line=2,
            content="def say_hello():\n    return '你好'",
            language="python",
            symbol="say_hello",
        )
    ]


def test_syntax_error_falls_back_to_bounded_source_text() -> None:
    candidates = chunk_source("def broken(\n    return 1\n", path="src/broken.py")

    assert candidates == [
        ChunkCandidate(1, 2, "def broken(\n    return 1", "python"),
    ]


def test_markdown_sections_keep_heading_as_symbol_and_fallback_text_is_bounded() -> None:
    candidates = chunk_source("# Intro\n你好\n## Details\nMore\n", path="README.md")

    assert candidates == [
        ChunkCandidate(1, 2, "# Intro\n你好", "markdown", "Intro"),
        ChunkCandidate(3, 4, "## Details\nMore", "markdown", "Details"),
    ]


def test_oversized_syntax_nodes_split_on_child_boundaries_then_line_windows() -> None:
    source = "def outer():\n    first = 'abc'\n    second = 'def'\n    return first + second\n"
    candidates = chunk_source(
        source,
        path="src/app.py",
        max_lines=2,
        max_characters=25,
        overlap_lines=1,
    )

    assert candidates
    assert all(candidate.end_line - candidate.start_line + 1 <= 2 for candidate in candidates)
    assert all(len(candidate.content) <= 25 for candidate in candidates)
    assert "".join(candidate.content.replace("\n", "") for candidate in candidates)


def test_one_oversized_line_makes_progress_and_retains_coordinates() -> None:
    candidates = chunk_source(
        "def value():\n    return 'abcdefghij'\n",
        path="src/app.py",
        max_characters=5,
    )

    assert candidates
    assert all(len(candidate.content) <= 5 for candidate in candidates)
    assert all(candidate.start_line >= 1 for candidate in candidates)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_lines": 0},
        {"max_characters": 0},
        {"overlap_lines": -1},
    ],
)
def test_invalid_limits_are_rejected(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        chunk_source("content", path="notes.txt", **kwargs)
