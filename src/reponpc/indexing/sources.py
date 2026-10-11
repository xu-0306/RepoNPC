"""Typed immutable inputs for the P2 index builder.

These values are deliberately transport-neutral.  A GitHub adapter may create
them from validated API responses, while deterministic tests may create them
from a checked-in fixture snapshot.  Neither representation grants callers a
filesystem or arbitrary-network capability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from reponpc.domain.evidence import COMMIT_RE, normalize_source_path
from reponpc.indexing.exclusions import SourceEntryKind

_REPOSITORY_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def optional_repository_language(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip()[:100] or None


def optional_repository_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2_147_483_647:
        return None
    return value


@dataclass(frozen=True, slots=True)
class EmbeddingIdentity:
    """The immutable embedding contract shared by an index and its reader."""

    adapter: str
    model_id: str
    dimension: int
    normalized: bool
    query_prefix: str
    passage_prefix: str

    def __post_init__(self) -> None:
        if not self.adapter or not self.model_id:
            raise ValueError("embedding adapter and model_id must be non-empty")
        if isinstance(self.dimension, bool) or self.dimension <= 0:
            raise ValueError("embedding dimension must be a positive integer")
        if not self.normalized:
            raise ValueError("RepoNPC bundle embeddings must be normalized")


class EmbeddingProviderError(RuntimeError):
    """Safe provider failure that never reflects model paths or upstream bodies."""

    def __init__(self, code: str) -> None:
        if not code:
            raise ValueError("embedding provider error code must be non-empty")
        self.code = code
        super().__init__("embedding provider failed")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Common batch embedding boundary shared by index and query consumers."""

    def identity(self) -> EmbeddingIdentity:
        """Return the exact provider identity used to create vectors."""

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        """Return one normalized float32 vector per prefixed query."""

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Return one normalized float32 vector per supplied passage."""


# Compatibility alias for the existing Phase 2 builder import. New adapters and
# later runtime consumers use the complete EmbeddingProvider name.
PassageEmbeddingProvider = EmbeddingProvider


@dataclass(frozen=True, slots=True)
class RepositoryBlob:
    """One repository-tree entry and bounded blob bytes, if it is a file."""

    path: str
    entry_kind: SourceEntryKind
    size_bytes: int
    content: bytes | None = None

    def __post_init__(self) -> None:
        normalize_source_path(self.path)
        if isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise ValueError("source size_bytes must be a non-negative integer")
        if self.entry_kind is SourceEntryKind.REGULAR_FILE:
            if self.content is None or len(self.content) != self.size_bytes:
                raise ValueError("regular file content must match its reported size")
        elif self.entry_kind is SourceEntryKind.OVERSIZED_FILE:
            if self.content is not None:
                raise ValueError("oversized source entries must not supply content")
        elif self.content is not None:
            raise ValueError("non-regular source entries must not supply content")


@dataclass(frozen=True, slots=True)
class ParticipationCommit:
    sha: str
    month: str

    def __post_init__(self) -> None:
        if not COMMIT_RE.fullmatch(self.sha) or not re.fullmatch(
            r"\d{4}-(0[1-9]|1[0-2])", self.month
        ):
            raise ValueError("participation commit is invalid")


@dataclass(frozen=True, slots=True)
class RepositoryParticipation:
    is_repository_owner: bool
    has_visible_commits: bool | None
    first_commit: ParticipationCommit | None
    last_commit: ParticipationCommit | None
    other_contributors_visible: bool | None

    def __post_init__(self) -> None:
        if self.has_visible_commits is True and (
            self.first_commit is None or self.last_commit is None
        ):
            raise ValueError("visible commits require both endpoints")
        if self.has_visible_commits is not True and (self.first_commit or self.last_commit):
            raise ValueError("unknown or empty commits cannot have endpoints")


@dataclass(frozen=True, slots=True)
class ResolvedRepository:
    """A configured repository pinned to a validated immutable commit."""

    slug: str
    commit_sha: str
    default_branch: str | None
    github_html_url: str
    blobs: tuple[RepositoryBlob, ...]
    participation: RepositoryParticipation | None = None
    language: str | None = None
    stars: int | None = None
    forks: int | None = None

    def __post_init__(self) -> None:
        if not _REPOSITORY_SLUG_RE.fullmatch(self.slug):
            raise ValueError("repository slug must be owner/name")
        if not COMMIT_RE.fullmatch(self.commit_sha):
            raise ValueError(
                "resolved repository commit must be 40 lowercase hexadecimal characters"
            )
        if not self.github_html_url.startswith("https://"):
            raise ValueError("repository HTML URL must use HTTPS")
        if self.language is not None and (
            not isinstance(self.language, str)
            or not self.language.strip()
            or len(self.language) > 100
        ):
            raise ValueError("repository language metadata is invalid")
        if any(
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 2_147_483_647
            )
            for value in (self.stars, self.forks)
        ):
            raise ValueError("repository count metadata is invalid")
        paths = [blob.path for blob in self.blobs]
        if len(paths) != len(set(paths)):
            raise ValueError("repository source paths must be unique")


@dataclass(frozen=True, slots=True)
class ResolvedConfiguration:
    """The public configuration source recorded as owner-assertion evidence."""

    repository_slug: str
    commit_sha: str
    path: str
    content: str
    github_html_url: str
    origin: str = "github"

    def __post_init__(self) -> None:
        if not _REPOSITORY_SLUG_RE.fullmatch(self.repository_slug):
            raise ValueError("configuration repository slug must be owner/name")
        if not COMMIT_RE.fullmatch(self.commit_sha):
            raise ValueError("configuration commit must be 40 lowercase hexadecimal characters")
        normalize_source_path(self.path)
        if not self.content:
            raise ValueError("configuration content must be non-empty")
        if self.origin not in {"github", "local"}:
            raise ValueError("unsupported configuration origin")
        if self.origin == "local" and (
            self.repository_slug != "local/portfolio" or self.github_html_url != "/"
        ):
            raise ValueError("local configuration origin is invalid")
        if self.origin == "github" and not self.github_html_url.startswith("https://"):
            raise ValueError("configuration HTML URL must use HTTPS")
