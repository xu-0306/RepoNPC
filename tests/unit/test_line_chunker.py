from __future__ import annotations

import pytest

from reponpc.indexing.line_chunker import LineChunk, chunk_text


def test_chunk_text_normalizes_line_endings_and_uses_one_based_inclusive_ranges() -> None:
    chunks = chunk_text("one\r\ntwo\rthree", max_lines=2, max_characters=20, overlap_lines=1)

    assert chunks == [
        LineChunk(1, 2, "one\ntwo"),
        LineChunk(2, 3, "two\nthree"),
    ]


def test_chunk_text_returns_no_chunks_for_empty_input() -> None:
    assert chunk_text("") == []


def test_chunk_text_returns_no_chunks_for_blank_only_input() -> None:
    assert chunk_text("\n") == []


def test_chunk_text_skips_a_leading_blank_window_before_an_oversized_line() -> None:
    assert chunk_text("\nabcdef", max_lines=5, max_characters=3, overlap_lines=1) == [
        LineChunk(2, 2, "abc"),
        LineChunk(2, 2, "def"),
    ]


def test_chunk_text_obeys_both_bounds_and_makes_progress_with_large_overlap() -> None:
    chunks = chunk_text("aa\nbb\ncc", max_lines=3, max_characters=2, overlap_lines=99)

    assert chunks == [
        LineChunk(1, 1, "aa"),
        LineChunk(2, 2, "bb"),
        LineChunk(3, 3, "cc"),
    ]
    assert all(chunk.end_line - chunk.start_line + 1 <= 3 for chunk in chunks)
    assert all(len(chunk.content) <= 2 for chunk in chunks)


def test_chunk_text_splits_an_oversized_source_line_deterministically() -> None:
    chunks = chunk_text("abcdefgh\nxy", max_lines=5, max_characters=3, overlap_lines=1)

    assert chunks == [
        LineChunk(1, 1, "abc"),
        LineChunk(1, 1, "def"),
        LineChunk(1, 1, "gh"),
        LineChunk(2, 2, "xy"),
    ]
    assert all(len(chunk.content) <= 3 for chunk in chunks)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_lines": 0}, "max_lines"),
        ({"max_characters": 0}, "max_characters"),
        ({"overlap_lines": -1}, "overlap_lines"),
    ],
)
def test_chunk_text_rejects_invalid_limits(kwargs: dict[str, int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        chunk_text("content", **kwargs)
