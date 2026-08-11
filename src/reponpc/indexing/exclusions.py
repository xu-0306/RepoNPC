"""Pure, fail-closed source eligibility classification for repository indexing.

This module deliberately receives metadata rather than paths on disk or source
bodies.  Callers are responsible for obtaining metadata and for honoring a
skip decision before they decode, scan, chunk, log, or persist source text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from functools import cache
from typing import Final


class SourceEntryKind(StrEnum):
    """The limited source-entry types accepted by the index intake boundary."""

    REGULAR_FILE = "regular_file"
    SYMLINK = "symlink"
    SUBMODULE = "submodule"
    OTHER = "other"


class ExclusionReason(StrEnum):
    """Stable, body-free eligibility outcomes for skipped-file summaries."""

    ELIGIBLE = "ELIGIBLE"
    INVALID_PATH = "INVALID_PATH"
    INVALID_METADATA = "INVALID_METADATA"
    SYMLINK = "SYMLINK"
    SUBMODULE = "SUBMODULE"
    NOT_REGULAR_FILE = "NOT_REGULAR_FILE"
    BINARY = "BINARY"
    UNDECODABLE = "UNDECODABLE"
    HIGH_CONFIDENCE_SECRET = "HIGH_CONFIDENCE_SECRET"
    ENVIRONMENT_FILE = "ENVIRONMENT_FILE"
    CREDENTIAL_OR_KEY = "CREDENTIAL_OR_KEY"
    GIT_METADATA = "GIT_METADATA"
    DEPENDENCY_OR_VENDOR = "DEPENDENCY_OR_VENDOR"
    BUILD_GENERATED_OR_CACHE = "BUILD_GENERATED_OR_CACHE"
    MINIFIED_OR_SOURCE_MAP = "MINIFIED_OR_SOURCE_MAP"
    ARCHIVE_MEDIA_OR_DATABASE = "ARCHIVE_MEDIA_OR_DATABASE"
    LOCK_FILE = "LOCK_FILE"
    GLOBAL_EXCLUDED = "GLOBAL_EXCLUDED"
    REPOSITORY_EXCLUDED = "REPOSITORY_EXCLUDED"
    NOT_INCLUDED = "NOT_INCLUDED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    REPOSITORY_TEXT_BUDGET_EXCEEDED = "REPOSITORY_TEXT_BUDGET_EXCEEDED"
    CORPUS_TEXT_BUDGET_EXCEEDED = "CORPUS_TEXT_BUDGET_EXCEEDED"


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Bounded facts about one candidate; source contents are intentionally absent."""

    entry_kind: SourceEntryKind
    size_bytes: int
    is_binary: bool = False
    is_decodable: bool = True
    has_high_confidence_secret: bool = False
    repository_text_bytes_before: int = 0
    corpus_text_bytes_before: int = 0


@dataclass(frozen=True, slots=True)
class ExclusionPolicy:
    """Immutable policy values already derived from validated public configuration.

    Positive pattern rules enable or exclude a match; a leading ``!`` reverses
    the preceding result in rule order.  Empty include rules are intentionally
    fail-closed.  Mandatory exclusions always run before these policy rules.
    """

    include_patterns: tuple[str, ...]
    repository_exclude_patterns: tuple[str, ...]
    global_exclude_patterns: tuple[str, ...]
    max_file_bytes: int
    max_repository_text_bytes: int
    max_corpus_text_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "include_patterns", _freeze_patterns(self.include_patterns))
        object.__setattr__(
            self,
            "repository_exclude_patterns",
            _freeze_patterns(self.repository_exclude_patterns),
        )
        object.__setattr__(
            self,
            "global_exclude_patterns",
            _freeze_patterns(self.global_exclude_patterns),
        )
        _validate_limit("max_file_bytes", self.max_file_bytes)
        _validate_limit("max_repository_text_bytes", self.max_repository_text_bytes)
        _validate_limit("max_corpus_text_bytes", self.max_corpus_text_bytes)


@dataclass(frozen=True, slots=True)
class ExclusionDecision:
    """A body-free include/skip result suitable for later summary serialization."""

    include: bool
    reason_code: ExclusionReason


_DEPENDENCY_OR_VENDOR_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {
        "node_modules",
        "vendor",
        "vendors",
        "third_party",
        "third-party",
        "bower_components",
        ".venv",
        "venv",
        "site-packages",
    }
)
_BUILD_GENERATED_OR_CACHE_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {
        "__pycache__",
        "build",
        "dist",
        "out",
        "target",
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        "generated",
        "generated-docs",
        "site",
    }
)
_CREDENTIAL_OR_KEY_NAMES: Final[frozenset[str]] = frozenset(
    {
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
    }
)
_CREDENTIAL_OR_KEY_PREFIXES: Final[tuple[str, ...]] = (
    "credential.",
    "credentials.",
    "secret.",
    "secrets.",
    "token.",
)
_CREDENTIAL_OR_KEY_SUFFIXES: Final[tuple[str, ...]] = (
    ".cer",
    ".crt",
    ".der",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
)
_ARCHIVE_MEDIA_OR_DATABASE_SUFFIXES: Final[tuple[str, ...]] = (
    ".tar.zst",
    ".tar.bz2",
    ".tar.gz",
    ".7z",
    ".avif",
    ".bmp",
    ".bz2",
    ".db",
    ".dmg",
    ".flac",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mdb",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".parquet",
    ".pdf",
    ".png",
    ".rar",
    ".sqlite",
    ".sqlite3",
    ".svg",
    ".tar",
    ".tiff",
    ".wav",
    ".webm",
    ".webp",
    ".xz",
    ".zip",
    ".zst",
)
_LOCK_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "cargo.lock",
        "composer.lock",
        "gemfile.lock",
        "go.sum",
        "package-lock.json",
        "pipfile.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "yarn.lock",
    }
)


def classify_source(
    path: str,
    metadata: SourceMetadata,
    policy: ExclusionPolicy,
) -> ExclusionDecision:
    """Classify one candidate using only value arguments and deterministic rules.

    The precedence is intentionally stable: malformed input and mandatory
    exclusions win over configured rules, which win over size-budget checks.
    Therefore an include rule can never make an unsafe file eligible.
    """

    parts = _normalized_path_parts(path)
    if parts is None:
        return _skip(ExclusionReason.INVALID_PATH)
    if not _valid_metadata(metadata):
        return _skip(ExclusionReason.INVALID_METADATA)

    kind_reason = _entry_kind_reason(metadata.entry_kind)
    if kind_reason is not None:
        return _skip(kind_reason)
    if metadata.is_binary:
        return _skip(ExclusionReason.BINARY)
    if not metadata.is_decodable:
        return _skip(ExclusionReason.UNDECODABLE)
    if metadata.has_high_confidence_secret:
        return _skip(ExclusionReason.HIGH_CONFIDENCE_SECRET)

    mandatory_reason = _mandatory_path_reason(parts)
    if mandatory_reason is not None:
        return _skip(mandatory_reason)
    if _rules_match(path, policy.global_exclude_patterns):
        return _skip(ExclusionReason.GLOBAL_EXCLUDED)
    if _rules_match(path, policy.repository_exclude_patterns):
        return _skip(ExclusionReason.REPOSITORY_EXCLUDED)
    if not _rules_match(path, policy.include_patterns):
        return _skip(ExclusionReason.NOT_INCLUDED)
    if metadata.size_bytes > policy.max_file_bytes:
        return _skip(ExclusionReason.FILE_TOO_LARGE)
    if (
        metadata.repository_text_bytes_before + metadata.size_bytes
        > policy.max_repository_text_bytes
    ):
        return _skip(ExclusionReason.REPOSITORY_TEXT_BUDGET_EXCEEDED)
    if metadata.corpus_text_bytes_before + metadata.size_bytes > policy.max_corpus_text_bytes:
        return _skip(ExclusionReason.CORPUS_TEXT_BUDGET_EXCEEDED)
    return ExclusionDecision(include=True, reason_code=ExclusionReason.ELIGIBLE)


def _skip(reason_code: ExclusionReason) -> ExclusionDecision:
    return ExclusionDecision(include=False, reason_code=reason_code)


def _normalized_path_parts(path: str) -> tuple[str, ...] | None:
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
        return None
    if "//" in path or path.endswith("/") or any(ord(character) < 32 for character in path):
        return None
    parts = tuple(path.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if len(parts[0]) == 2 and parts[0][0].isalpha() and parts[0][1] == ":":
        return None
    return parts


def _valid_metadata(metadata: SourceMetadata) -> bool:
    if not isinstance(metadata, SourceMetadata) or not isinstance(
        metadata.entry_kind, SourceEntryKind
    ):
        return False
    numeric_values = (
        metadata.size_bytes,
        metadata.repository_text_bytes_before,
        metadata.corpus_text_bytes_before,
    )
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in numeric_values
    ):
        return False
    return all(
        isinstance(value, bool)
        for value in (
            metadata.is_binary,
            metadata.is_decodable,
            metadata.has_high_confidence_secret,
        )
    )


def _entry_kind_reason(entry_kind: SourceEntryKind) -> ExclusionReason | None:
    if entry_kind is SourceEntryKind.SYMLINK:
        return ExclusionReason.SYMLINK
    if entry_kind is SourceEntryKind.SUBMODULE:
        return ExclusionReason.SUBMODULE
    if entry_kind is SourceEntryKind.OTHER:
        return ExclusionReason.NOT_REGULAR_FILE
    return None


def _mandatory_path_reason(parts: tuple[str, ...]) -> ExclusionReason | None:
    lowercase_parts = tuple(part.casefold() for part in parts)
    filename = lowercase_parts[-1]
    if filename.startswith(".env"):
        return ExclusionReason.ENVIRONMENT_FILE
    if _is_credential_or_key(filename):
        return ExclusionReason.CREDENTIAL_OR_KEY
    if ".git" in lowercase_parts:
        return ExclusionReason.GIT_METADATA
    if any(part in _DEPENDENCY_OR_VENDOR_DIRECTORIES for part in lowercase_parts[:-1]):
        return ExclusionReason.DEPENDENCY_OR_VENDOR
    if any(part in _BUILD_GENERATED_OR_CACHE_DIRECTORIES for part in lowercase_parts[:-1]):
        return ExclusionReason.BUILD_GENERATED_OR_CACHE
    if filename.endswith((".min.js", ".min.css", ".map")):
        return ExclusionReason.MINIFIED_OR_SOURCE_MAP
    if filename.endswith(_ARCHIVE_MEDIA_OR_DATABASE_SUFFIXES):
        return ExclusionReason.ARCHIVE_MEDIA_OR_DATABASE
    if filename in _LOCK_FILE_NAMES or filename.endswith(".lock"):
        return ExclusionReason.LOCK_FILE
    return None


def _is_credential_or_key(filename: str) -> bool:
    return (
        filename in _CREDENTIAL_OR_KEY_NAMES
        or filename.startswith(_CREDENTIAL_OR_KEY_PREFIXES)
        or filename.endswith(_CREDENTIAL_OR_KEY_SUFFIXES)
    )


def _freeze_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(patterns, str):
        raise ValueError("patterns must be an iterable of strings")
    frozen = tuple(patterns)
    for pattern in frozen:
        _validate_pattern(pattern)
    return frozen


def _validate_limit(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _validate_pattern(pattern: str) -> None:
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    candidate = pattern[1:] if pattern.startswith("!") else pattern
    if not candidate or "\\" in candidate or candidate.startswith("/"):
        raise ValueError("pattern must be a repository-relative POSIX path")
    if candidate.endswith("/"):
        candidate = candidate[:-1]
    if not candidate or "//" in candidate or any(ord(character) < 32 for character in candidate):
        raise ValueError("pattern must be normalized")
    if any(part in {"", ".", ".."} for part in candidate.split("/")):
        raise ValueError("pattern must not traverse or alias a path")


def _rules_match(path: str, rules: tuple[str, ...]) -> bool:
    matched = False
    for rule in rules:
        negated = rule.startswith("!")
        pattern = rule[1:] if negated else rule
        if _pattern_matches(path, pattern):
            matched = not negated
    return matched


def _pattern_matches(path: str, pattern: str) -> bool:
    directory_only = pattern.endswith("/")
    bare_pattern = pattern[:-1] if directory_only else pattern
    pattern_parts = tuple(bare_pattern.split("/"))
    path_parts = tuple(path.split("/"))

    if len(pattern_parts) == 1 and pattern_parts[0] != "**":
        searchable_parts = path_parts[:-1] if directory_only else path_parts
        return any(fnmatchcase(part, pattern_parts[0]) for part in searchable_parts)
    if directory_only:
        parent_parts = path_parts[:-1]
        return any(
            _match_segments(pattern_parts, parent_parts[:end])
            for end in range(1, len(parent_parts) + 1)
        )
    return _match_segments(pattern_parts, path_parts)


def _match_segments(pattern_parts: tuple[str, ...], path_parts: tuple[str, ...]) -> bool:
    @cache
    def matches(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        pattern_part = pattern_parts[pattern_index]
        if pattern_part == "**":
            return matches(pattern_index + 1, path_index) or (
                path_index < len(path_parts) and matches(pattern_index, path_index + 1)
            )
        return (
            path_index < len(path_parts)
            and fnmatchcase(path_parts[path_index], pattern_part)
            and matches(pattern_index + 1, path_index + 1)
        )

    return matches(0, 0)
