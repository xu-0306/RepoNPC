"""Deterministic syntax-aware and fallback chunk candidates for eligible text.

This module deliberately receives source text as a value.  It neither opens a
repository path nor performs eligibility, secret scanning, persistence, or
evidence-ID work; those boundaries belong to their respective Phase 2 owners.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_rust
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from reponpc.indexing.line_chunker import chunk_text

SourceLanguage = Literal[
    "python",
    "javascript",
    "typescript",
    "tsx",
    "go",
    "rust",
    "markdown",
    "text",
]


@dataclass(frozen=True, slots=True)
class ChunkCandidate:
    """A bounded source excerpt with one-based, inclusive coordinates."""

    start_line: int
    end_line: int
    content: str
    language: SourceLanguage
    symbol: str | None = None


_PATH_LANGUAGES: Final[dict[str, SourceLanguage]] = {
    ".cjs": "javascript",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".markdown": "markdown",
    ".md": "markdown",
    ".mjs": "javascript",
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "tsx",
}
_LANGUAGES: Final[dict[SourceLanguage, Language]] = {
    "python": Language(tree_sitter_python.language()),
    "javascript": Language(tree_sitter_javascript.language()),
    "typescript": Language(tree_sitter_typescript.language_typescript()),
    "tsx": Language(tree_sitter_typescript.language_tsx()),
    "go": Language(tree_sitter_go.language()),
    "rust": Language(tree_sitter_rust.language()),
}
_SYMBOL_NODE_TYPES: Final[dict[SourceLanguage, frozenset[str]]] = {
    "python": frozenset({"class_definition", "decorated_definition", "function_definition"}),
    "javascript": frozenset(
        {"class_declaration", "function_declaration", "method_definition", "variable_declarator"}
    ),
    "typescript": frozenset(
        {
            "class_declaration",
            "enum_declaration",
            "function_declaration",
            "interface_declaration",
            "method_definition",
            "type_alias_declaration",
            "variable_declarator",
        }
    ),
    "tsx": frozenset(
        {
            "class_declaration",
            "enum_declaration",
            "function_declaration",
            "interface_declaration",
            "method_definition",
            "type_alias_declaration",
            "variable_declarator",
        }
    ),
    "go": frozenset({"function_declaration", "method_declaration", "type_declaration"}),
    "rust": frozenset(
        {"enum_item", "function_item", "impl_item", "mod_item", "struct_item", "trait_item"}
    ),
}
_NAME_NODE_TYPES: Final[frozenset[str]] = frozenset(
    {"field_identifier", "identifier", "property_identifier", "type_identifier"}
)
_MARKDOWN_HEADING: Final[re.Pattern[str]] = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")


def detect_language(path: str) -> SourceLanguage:
    """Return the deterministic parser/fallback selection for a POSIX path value."""

    if not isinstance(path, str):
        return "text"
    normalized = path.casefold()
    for suffix, language in sorted(
        _PATH_LANGUAGES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if normalized.endswith(suffix):
            return language
    return "text"


def chunk_source(
    text: str,
    *,
    path: str,
    max_lines: int = 200,
    max_characters: int = 6_000,
    overlap_lines: int = 12,
) -> list[ChunkCandidate]:
    """Return reproducible bounded candidates for already-eligible source text.

    The function normalizes line endings before parser dispatch.  Supported
    languages prefer complete named syntax nodes; malformed and unsupported
    text remains available through Markdown-aware or line-window fallbacks.
    """

    _validate_limits(max_lines, max_characters, overlap_lines)
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []

    language = detect_language(path)
    if language == "markdown":
        return _markdown_candidates(normalized, max_lines, max_characters, overlap_lines)
    if language == "text":
        return _fallback_candidates(
            normalized,
            language="text",
            base_line=1,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )
    return _syntax_candidates(
        normalized,
        language=language,
        max_lines=max_lines,
        max_characters=max_characters,
        overlap_lines=overlap_lines,
    )


def _syntax_candidates(
    text: str,
    *,
    language: SourceLanguage,
    max_lines: int,
    max_characters: int,
    overlap_lines: int,
) -> list[ChunkCandidate]:
    parser = Parser(_LANGUAGES[language])
    source_bytes = text.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    nodes = _symbol_nodes(root, language)
    if not nodes:
        return _fallback_candidates(
            text,
            language=language,
            base_line=1,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )

    candidates: list[ChunkCandidate] = []
    for node in nodes:
        candidates.extend(
            _node_candidates(
                node,
                source_bytes=source_bytes,
                language=language,
                max_lines=max_lines,
                max_characters=max_characters,
                overlap_lines=overlap_lines,
            )
        )
    return _deduplicate_candidates(candidates)


def _symbol_nodes(root: Node, language: SourceLanguage) -> list[Node]:
    target_types = _SYMBOL_NODE_TYPES[language]
    nodes: list[Node] = []

    def visit(node: Node) -> None:
        if node.type in target_types:
            if node.type != "variable_declarator" or _contains_function_value(node):
                nodes.append(node)
            if node.type == "decorated_definition":
                return
        for child in node.named_children:
            visit(child)

    visit(root)
    return nodes


def _contains_function_value(node: Node) -> bool:
    return any(
        descendant.type in {"arrow_function", "function", "function_expression"}
        for descendant in _descendants(node)
    )


def _descendants(node: Node) -> list[Node]:
    result: list[Node] = []
    for child in node.named_children:
        result.append(child)
        result.extend(_descendants(child))
    return result


def _node_candidates(
    node: Node,
    *,
    source_bytes: bytes,
    language: SourceLanguage,
    max_lines: int,
    max_characters: int,
    overlap_lines: int,
) -> list[ChunkCandidate]:
    content = source_bytes[node.start_byte : node.end_byte].decode("utf-8")
    symbol = _node_symbol(node, source_bytes)
    if _within_bounds(content, max_lines=max_lines, max_characters=max_characters):
        return [_candidate(source_bytes, node.start_byte, node.end_byte, language, symbol)]

    useful_children = [
        child
        for child in node.named_children
        if (child.start_byte, child.end_byte) != (node.start_byte, node.end_byte)
    ]
    if not useful_children:
        return _fallback_slice_candidates(
            source_bytes,
            node.start_byte,
            node.end_byte,
            language=language,
            symbol=symbol,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )

    candidates: list[ChunkCandidate] = []
    cursor = node.start_byte
    for child in useful_children:
        if cursor < child.start_byte:
            candidates.extend(
                _fallback_slice_candidates(
                    source_bytes,
                    cursor,
                    child.start_byte,
                    language=language,
                    symbol=symbol,
                    max_lines=max_lines,
                    max_characters=max_characters,
                    overlap_lines=overlap_lines,
                )
            )
        candidates.extend(
            _node_candidates(
                child,
                source_bytes=source_bytes,
                language=language,
                max_lines=max_lines,
                max_characters=max_characters,
                overlap_lines=overlap_lines,
            )
        )
        cursor = child.end_byte
    if cursor < node.end_byte:
        candidates.extend(
            _fallback_slice_candidates(
                source_bytes,
                cursor,
                node.end_byte,
                language=language,
                symbol=symbol,
                max_lines=max_lines,
                max_characters=max_characters,
                overlap_lines=overlap_lines,
            )
        )
    return candidates


def _node_symbol(node: Node, source_bytes: bytes) -> str | None:
    if node.type == "decorated_definition":
        definition = node.child_by_field_name("definition")
        if definition is not None:
            return _node_symbol(definition, source_bytes)
    named = node.child_by_field_name("name")
    if named is not None:
        return source_bytes[named.start_byte : named.end_byte].decode("utf-8")
    for descendant in _descendants(node):
        if descendant.type in _NAME_NODE_TYPES:
            return source_bytes[descendant.start_byte : descendant.end_byte].decode("utf-8")
    return None


def _fallback_slice_candidates(
    source_bytes: bytes,
    start_byte: int,
    end_byte: int,
    *,
    language: SourceLanguage,
    symbol: str | None,
    max_lines: int,
    max_characters: int,
    overlap_lines: int,
) -> list[ChunkCandidate]:
    content = source_bytes[start_byte:end_byte].decode("utf-8")
    base_line = _line_number(source_bytes, start_byte)
    return [
        ChunkCandidate(
            start_line=base_line + chunk.start_line - 1,
            end_line=base_line + chunk.end_line - 1,
            content=chunk.content,
            language=language,
            symbol=symbol,
        )
        for chunk in chunk_text(
            content,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )
    ]


def _markdown_candidates(
    text: str,
    max_lines: int,
    max_characters: int,
    overlap_lines: int,
) -> list[ChunkCandidate]:
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    headings = [
        (index, match.group(2))
        for index, line in enumerate(lines)
        if (match := _MARKDOWN_HEADING.match(line)) is not None
    ]
    if not headings:
        return _fallback_candidates(
            text,
            language="markdown",
            base_line=1,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )

    candidates: list[ChunkCandidate] = []
    for position, (start, heading) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        section = "\n".join(lines[start:end])
        candidates.extend(
            ChunkCandidate(
                start_line=start + chunk.start_line,
                end_line=start + chunk.end_line,
                content=chunk.content,
                language="markdown",
                symbol=heading,
            )
            for chunk in chunk_text(
                section,
                max_lines=max_lines,
                max_characters=max_characters,
                overlap_lines=overlap_lines,
            )
        )
    return _deduplicate_candidates(candidates)


def _fallback_candidates(
    text: str,
    *,
    language: SourceLanguage,
    base_line: int,
    max_lines: int,
    max_characters: int,
    overlap_lines: int,
) -> list[ChunkCandidate]:
    return [
        ChunkCandidate(
            start_line=base_line + chunk.start_line - 1,
            end_line=base_line + chunk.end_line - 1,
            content=chunk.content,
            language=language,
        )
        for chunk in chunk_text(
            text,
            max_lines=max_lines,
            max_characters=max_characters,
            overlap_lines=overlap_lines,
        )
    ]


def _candidate(
    source_bytes: bytes,
    start_byte: int,
    end_byte: int,
    language: SourceLanguage,
    symbol: str | None,
) -> ChunkCandidate:
    content = source_bytes[start_byte:end_byte].decode("utf-8")
    start_line = _line_number(source_bytes, start_byte)
    trimmed = content.rstrip("\n")
    end_line = start_line + trimmed.count("\n")
    return ChunkCandidate(start_line, end_line, content.rstrip("\n"), language, symbol)


def _line_number(source_bytes: bytes, byte_offset: int) -> int:
    return source_bytes[:byte_offset].decode("utf-8").count("\n") + 1


def _within_bounds(content: str, *, max_lines: int, max_characters: int) -> bool:
    return (
        bool(content.strip())
        and len(content.rstrip("\n")) <= max_characters
        and (content.rstrip("\n").count("\n") + 1 <= max_lines)
    )


def _deduplicate_candidates(candidates: list[ChunkCandidate]) -> list[ChunkCandidate]:
    unique = {
        (
            candidate.start_line,
            candidate.end_line,
            candidate.content,
            candidate.language,
            candidate.symbol,
        ): candidate
        for candidate in candidates
        if candidate.content
    }
    return sorted(
        unique.values(),
        key=lambda candidate: (
            candidate.start_line,
            candidate.end_line,
            candidate.symbol or "",
            candidate.content,
        ),
    )


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
