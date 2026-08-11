"""Independent public-boundary probe for P2-02 determinism and coordinates.

This evaluator probe deliberately imports only ``chunk_source``.  It does not
reach into parser implementation helpers or modify production state.
"""

from __future__ import annotations

import hashlib
import json

from reponpc.indexing.parsing import chunk_source


def _serialize(candidates: object) -> str:
    return json.dumps(
        [
            {
                "start_line": candidate.start_line,
                "end_line": candidate.end_line,
                "content": candidate.content,
                "language": candidate.language,
                "symbol": candidate.symbol,
            }
            for candidate in candidates
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> None:
    source = (
        "# leading comment\r\n"
        "class Café:\r\n"
        "    def greet(self, name: str) -> str:\r\n"
        "        return f'你好, {name}'\r\n"
        "\r\n"
        "def tail() -> str:\r\n"
        "    return '世界'\r\n"
    )
    normalized = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.rstrip("\n").split("\n")

    first = chunk_source(source, path="src/unicode_symbols.py")
    second = chunk_source(source, path="src/unicode_symbols.py")

    assert first == second, "identical source/path calls must return identical candidates"
    assert first, "named supported source must yield candidates"
    assert {"Café", "greet", "tail"}.issubset(
        {candidate.symbol for candidate in first}
    ), "complete named symbols must remain observable"
    coordinate_mismatches: list[dict[str, object]] = []
    for candidate in first:
        assert 1 <= candidate.start_line <= candidate.end_line <= len(lines)
        expected_line_span = "\n".join(lines[candidate.start_line - 1 : candidate.end_line])
        first_fragment = candidate.content.split("\n", maxsplit=1)[0]
        last_fragment = candidate.content.rsplit("\n", maxsplit=1)[-1]
        if (
            candidate.content not in expected_line_span
            or first_fragment not in lines[candidate.start_line - 1]
            or last_fragment not in lines[candidate.end_line - 1]
        ):
            coordinate_mismatches.append(
                {
                    "start_line": candidate.start_line,
                    "end_line": candidate.end_line,
                    "content": candidate.content,
                    "expected_line_span": expected_line_span,
                    "symbol": candidate.symbol,
                }
            )
        assert "\r" not in candidate.content, "returned content must be LF normalized"

    serialized = _serialize(first)
    result = {
        "probe_id": "PROBE-P2-02-DETERMINISM-COORDINATES",
        "calls_equal": first == second,
        "candidate_count": len(first),
        "candidate_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "coordinate_mismatches": coordinate_mismatches,
        "candidates": json.loads(serialized),
        "result": "PASS" if not coordinate_mismatches else "FAIL",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    assert not coordinate_mismatches, (
        "candidate content must be a contiguous source excerpt within its one-based inclusive lines"
    )


if __name__ == "__main__":
    main()
