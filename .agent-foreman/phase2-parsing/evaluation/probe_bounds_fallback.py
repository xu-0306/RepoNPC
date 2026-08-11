"""Independent public-boundary probe for P2-02 bounds and fallback progress."""

from __future__ import annotations

import json
from collections import defaultdict

from reponpc.indexing.parsing import chunk_source


def _candidate_data(candidates: object) -> list[dict[str, object]]:
    return [
        {
            "start_line": candidate.start_line,
            "end_line": candidate.end_line,
            "content": candidate.content,
            "language": candidate.language,
            "symbol": candidate.symbol,
        }
        for candidate in candidates
    ]


def _assert_bounds(candidates: object, *, max_lines: int, max_characters: int) -> None:
    assert candidates, "non-empty eligible source must produce bounded candidates"
    for candidate in candidates:
        assert candidate.content
        assert len(candidate.content) <= max_characters
        assert candidate.end_line - candidate.start_line + 1 <= max_lines


def main() -> None:
    max_lines = 2
    max_characters = 24
    oversized_symbol_source = (
        "def outer():\n"
        '    first = "alpha"\n'
        '    second = "bravo"\n'
        '    third = "charlie"\n'
        "    return first + second + third\n"
    )
    symbol_candidates = chunk_source(
        oversized_symbol_source,
        path="src/oversized.py",
        max_lines=max_lines,
        max_characters=max_characters,
        overlap_lines=0,
    )
    _assert_bounds(symbol_candidates, max_lines=max_lines, max_characters=max_characters)
    assert any(candidate.symbol == "outer" for candidate in symbol_candidates)
    source_line_count = len(oversized_symbol_source.rstrip("\n").split("\n"))
    for line_number in range(1, source_line_count + 1):
        assert any(
            candidate.start_line <= line_number <= candidate.end_line
            for candidate in symbol_candidates
        ), "split symbol must retain every source-line coordinate"

    fallback_source = "def broken(\r\n" + ("你" * 19) + "\r\n"
    fallback_candidates = chunk_source(
        fallback_source,
        path="src/broken.py",
        max_lines=1,
        max_characters=5,
        overlap_lines=0,
    )
    _assert_bounds(fallback_candidates, max_lines=1, max_characters=5)
    assert all(candidate.symbol is None for candidate in fallback_candidates)
    per_line: dict[int, list[str]] = defaultdict(list)
    for candidate in fallback_candidates:
        assert candidate.start_line == candidate.end_line
        per_line[candidate.start_line].append(candidate.content)
    reconstructed = "\n".join("".join(per_line[line]) for line in sorted(per_line))
    expected = fallback_source.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    assert reconstructed == expected, "syntax-error fallback must retain all normalized source text"

    print(
        json.dumps(
            {
                "probe_id": "PROBE-P2-02-BOUNDS-FALLBACK",
                "symbol_candidate_count": len(symbol_candidates),
                "fallback_candidate_count": len(fallback_candidates),
                "fallback_reconstructed": reconstructed,
                "symbol_candidates": _candidate_data(symbol_candidates),
                "fallback_candidates": _candidate_data(fallback_candidates),
                "result": "PASS",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
