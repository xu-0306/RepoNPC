"""Deterministic, bounded line-window chunking for unsupported source formats."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LineChunk:
    """A bounded excerpt with one-based, inclusive source-line coordinates."""

    start_line: int
    end_line: int
    content: str


def chunk_text(
    text: str,
    *,
    max_lines: int = 200,
    max_characters: int = 6_000,
    overlap_lines: int = 12,
) -> list[LineChunk]:
    """Split *text* into reproducible chunks bounded by lines and characters.

    CRLF and CR line endings are normalized to LF.  Chunks normally overlap by
    ``overlap_lines`` source lines; the progress guard keeps narrow character
    limits and large requested overlaps from looping forever.  A source line
    longer than ``max_characters`` is sliced into contiguous chunks that retain
    the original line's one-based inclusive range.
    """

    _validate_limits(max_lines, max_characters, overlap_lines)

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []

    lines = normalized.split("\n")
    if normalized.endswith("\n"):
        lines.pop()

    chunks: list[LineChunk] = []
    start = 0
    while start < len(lines):
        line = lines[start]
        if len(line) > max_characters:
            chunks.extend(
                LineChunk(start + 1, start + 1, line[offset : offset + max_characters])
                for offset in range(0, len(line), max_characters)
            )
            start += 1
            continue

        end = start
        content_length = 0
        while end < len(lines) and end - start < max_lines:
            candidate_length = content_length + (1 if end > start else 0) + len(lines[end])
            if candidate_length > max_characters:
                break
            content_length = candidate_length
            end += 1

        content = "\n".join(lines[start:end])
        if any(lines[start:end]):
            chunks.append(LineChunk(start + 1, end, content))
        if end == len(lines):
            break
        start = max(start + 1, end - overlap_lines)

    return chunks


def _validate_limits(max_lines: int, max_characters: int, overlap_lines: int) -> None:
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or max_lines <= 0:
        raise ValueError("max_lines must be a positive integer")
    if (
        isinstance(max_characters, bool)
        or not isinstance(max_characters, int)
        or max_characters <= 0
    ):
        raise ValueError("max_characters must be a positive integer")
    if isinstance(overlap_lines, bool) or not isinstance(overlap_lines, int) or overlap_lines < 0:
        raise ValueError("overlap_lines must be a non-negative integer")
