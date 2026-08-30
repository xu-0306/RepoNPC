"""Allowlisted public GitHub source/ref resolution for the indexer."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.domain.evidence import COMMIT_RE
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.sources import RepositoryBlob, ResolvedRepository


class SourceResolutionError(RuntimeError):
    """Safe source-resolution code without upstream body or URL reflection."""

    def __init__(self, code: str, retry_after_seconds: int | None = None) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__("repository source is unavailable")


class _NoRedirect(HTTPRedirectHandler):
    """Fail closed rather than allowing urllib to follow an unchecked location."""

    def redirect_request(self, *args: object, **kwargs: object) -> Request | None:
        raise SourceResolutionError("github_redirect_rejected")


@dataclass(frozen=True, slots=True)
class PublicRepositoryMetadata:
    """Bounded public metadata returned before any source access."""

    slug: str
    name: str
    description: str | None
    primary_language: str | None
    default_branch: str
    is_fork: bool
    is_archived: bool
    updated_at: str | None
    html_url: str


@dataclass(frozen=True, slots=True)
class RepositoryDiscoveryPage:
    repositories: tuple[PublicRepositoryMetadata, ...]
    page: int
    has_more: bool


@dataclass(frozen=True, slots=True)
class GitHubSourceResolver:
    """Resolve only a configured GitHub API host into pinned source snapshots."""

    api_base_url: str = "https://api.github.com"
    allowed_hosts: frozenset[str] = frozenset({"api.github.com", "github.com"})
    timeout_seconds: float = 15.0
    max_response_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        parsed = urlsplit(self.api_base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("GitHub API base URL must be an allowlisted HTTPS origin")
        if parsed.hostname.casefold() not in {host.casefold() for host in self.allowed_hosts}:
            raise ValueError("GitHub API host must be allowlisted")
        if self.timeout_seconds <= 0:
            raise ValueError("GitHub timeout must be positive")
        if isinstance(self.max_response_bytes, bool) or self.max_response_bytes <= 0:
            raise ValueError("GitHub response limit must be positive")

    def discover(self, *, account: str, page: int) -> RepositoryDiscoveryPage:
        """List one bounded page of public metadata without fetching repository source."""

        normalized = normalize_github_account(account)
        if isinstance(page, bool) or not 1 <= page <= 5:
            raise SourceResolutionError("github_page_invalid")
        payload = self._get_json_list(
            f"/users/{quote(normalized, safe='')}/repos"
            f"?type=public&sort=updated&direction=desc&per_page=50&page={page}"
        )
        repositories = tuple(
            _repository_metadata(item, self.allowed_hosts)
            for item in payload[:50]
            if item.get("private") is False
        )
        return RepositoryDiscoveryPage(
            repositories=repositories,
            page=page,
            has_more=len(payload) == 50 and page < 5,
        )

    def repository_metadata(self, *, repository: str) -> PublicRepositoryMetadata:
        """Resolve a manual slug/URL into normalized public metadata only."""

        slug = normalize_github_repository(repository)
        owner, name = _split_slug(slug)
        payload = self._get_json(f"/repos/{quote(owner, safe='')}/{quote(name, safe='')}")
        if payload.get("private") is True:
            raise SourceResolutionError("github_not_found")
        return _repository_metadata(payload, self.allowed_hosts)

    def resolve(
        self,
        *,
        slug: str,
        ref: str | None,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> ResolvedRepository:
        """Resolve one configured ref and fetch only its recursively listed blobs."""

        owner, repository = _split_slug(slug)
        getter: Callable[[str], dict[str, Any]] = self._get_json
        if cancel_requested is not None or deadline is not None:

            def bounded_getter(path: str) -> dict[str, Any]:
                return self._get_json_bounded(
                    path,
                    cancel_requested=cancel_requested,
                    deadline=deadline,
                )

            getter = bounded_getter
        metadata = getter(f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}")
        default_branch = _required_text(metadata, "default_branch", "github_repository_invalid")
        html_url = _required_text(metadata, "html_url", "github_repository_invalid")
        _validate_allowed_url(html_url, self.allowed_hosts)
        requested_ref = ref or default_branch
        commit = getter(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/commits/"
            f"{quote(requested_ref, safe='')}"
        )
        commit_sha = _required_text(commit, "sha", "github_commit_invalid")
        if not COMMIT_RE.fullmatch(commit_sha):
            raise SourceResolutionError("github_commit_invalid")
        tree = getter(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/git/trees/{commit_sha}"
            "?recursive=1"
        )
        if tree.get("truncated") is True or not isinstance(tree.get("tree"), list):
            raise SourceResolutionError("github_tree_invalid")
        blobs = tuple(
            self._tree_entry_to_blob(owner, repository, item, getter=getter)
            for item in sorted(tree["tree"], key=lambda entry: str(entry.get("path", "")))
            if isinstance(item, dict)
        )
        return ResolvedRepository(
            slug=slug,
            commit_sha=commit_sha,
            default_branch=default_branch,
            github_html_url=html_url,
            blobs=blobs,
        )

    def _tree_entry_to_blob(
        self,
        owner: str,
        repository: str,
        entry: dict[str, Any],
        *,
        getter: Callable[[str], dict[str, Any]] | None = None,
    ) -> RepositoryBlob:
        path = _required_text(entry, "path", "github_tree_invalid")
        mode = _required_text(entry, "mode", "github_tree_invalid")
        entry_type = _required_text(entry, "type", "github_tree_invalid")
        size = entry.get("size", 0)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise SourceResolutionError("github_tree_invalid")
        kind = {
            ("blob", "100644"): SourceEntryKind.REGULAR_FILE,
            ("blob", "100755"): SourceEntryKind.REGULAR_FILE,
            ("blob", "120000"): SourceEntryKind.SYMLINK,
            ("commit", "160000"): SourceEntryKind.SUBMODULE,
        }.get((entry_type, mode), SourceEntryKind.OTHER)
        if kind is not SourceEntryKind.REGULAR_FILE:
            return RepositoryBlob(path=path, entry_kind=kind, size_bytes=size)
        blob_sha = _required_text(entry, "sha", "github_tree_invalid")
        payload = (getter or self._get_json)(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/git/blobs/"
            f"{quote(blob_sha, safe='')}"
        )
        if payload.get("encoding") != "base64":
            raise SourceResolutionError("github_blob_invalid")
        content = _required_text(payload, "content", "github_blob_invalid").replace("\n", "")
        try:
            decoded = base64.b64decode(content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise SourceResolutionError("github_blob_invalid") from exc
        if len(decoded) != size:
            raise SourceResolutionError("github_blob_size_mismatch")
        return RepositoryBlob(path=path, entry_kind=kind, size_bytes=size, content=decoded)

    def _get_json(self, api_path: str) -> dict[str, Any]:
        payload = self._request_json(api_path)
        if not isinstance(payload, dict):
            raise SourceResolutionError("github_response_invalid")
        return payload

    def _get_json_list(self, api_path: str) -> list[dict[str, Any]]:
        payload = self._request_json(api_path)
        if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
            raise SourceResolutionError("github_response_invalid")
        return payload

    def _get_json_bounded(
        self,
        api_path: str,
        *,
        cancel_requested: Callable[[], bool] | None,
        deadline: float | None,
    ) -> dict[str, Any]:
        payload = self._request_json(
            api_path,
            cancel_requested=cancel_requested,
            deadline=deadline,
        )
        if not isinstance(payload, dict):
            raise SourceResolutionError("github_response_invalid")
        return payload

    def _request_json(
        self,
        api_path: str,
        *,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> object:
        base = self.api_base_url.rstrip("/")
        url = base + api_path
        _validate_allowed_url(url, self.allowed_hosts)
        if cancel_requested is not None and cancel_requested():
            raise SourceResolutionError("github_cancelled")
        timeout = self.timeout_seconds
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SourceResolutionError("github_timeout")
            timeout = min(timeout, remaining)
        request = Request(url, headers={"Accept": "application/vnd.github+json"}, method="GET")
        try:
            opener = build_opener(_NoRedirect())
            with opener.open(request, timeout=timeout) as response:
                _validate_allowed_url(response.geturl(), self.allowed_hosts)
                if response.status != 200:
                    raise SourceResolutionError("github_response_invalid")
                payload = response.read(self.max_response_bytes + 1)
                if len(payload) > self.max_response_bytes:
                    raise SourceResolutionError("github_response_too_large")
        except SourceResolutionError:
            raise
        except HTTPError as exc:
            if exc.code == 404:
                raise SourceResolutionError("github_not_found") from exc
            if exc.code in {403, 429}:
                raise SourceResolutionError(
                    "github_rate_limited",
                    _retry_after_seconds(exc.headers),
                ) from exc
            raise SourceResolutionError("github_request_failed") from exc
        except (URLError, OSError) as exc:
            raise SourceResolutionError("github_request_failed") from exc
        if cancel_requested is not None and cancel_requested():
            raise SourceResolutionError("github_cancelled")
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceResolutionError("github_response_invalid") from exc
        return decoded


_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def normalize_github_account(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("https://"):
        parsed = urlsplit(candidate)
        try:
            port = parsed.port
        except ValueError as exc:
            raise SourceResolutionError("github_account_invalid") from exc
        if (
            parsed.hostname is None
            or parsed.hostname.casefold() != "github.com"
            or parsed.username
            or parsed.password
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise SourceResolutionError("github_account_invalid")
        parts = tuple(part for part in parsed.path.split("/") if part)
        if len(parts) != 1:
            raise SourceResolutionError("github_account_invalid")
        candidate = parts[0]
    if not _ACCOUNT_RE.fullmatch(candidate):
        raise SourceResolutionError("github_account_invalid")
    return candidate


def normalize_github_repository(value: str) -> str:
    candidate = value.strip()
    if candidate.startswith("https://"):
        parsed = urlsplit(candidate)
        try:
            port = parsed.port
        except ValueError as exc:
            raise SourceResolutionError("github_repository_invalid") from exc
        if (
            parsed.hostname is None
            or parsed.hostname.casefold() != "github.com"
            or parsed.username
            or parsed.password
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise SourceResolutionError("github_repository_invalid")
        parts = tuple(part for part in parsed.path.split("/") if part)
        if len(parts) != 2:
            raise SourceResolutionError("github_repository_invalid")
        candidate = "/".join(parts)
    owner, repository = _split_slug(candidate)
    if not _ACCOUNT_RE.fullmatch(owner) or not _REPOSITORY_RE.fullmatch(repository):
        raise SourceResolutionError("github_repository_invalid")
    return f"{owner}/{repository}"


def _split_slug(slug: str) -> tuple[str, str]:
    parts = slug.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        raise SourceResolutionError("github_repository_invalid")
    return parts[0], parts[1]


def _repository_metadata(
    value: dict[str, Any], allowed_hosts: frozenset[str]
) -> PublicRepositoryMetadata:
    slug = _required_text(value, "full_name", "github_repository_invalid")
    normalized = normalize_github_repository(slug)
    name = _required_text(value, "name", "github_repository_invalid")
    default_branch = _required_text(value, "default_branch", "github_repository_invalid")
    html_url = _required_text(value, "html_url", "github_repository_invalid")
    _validate_allowed_url(html_url, allowed_hosts)
    description = value.get("description")
    language = value.get("language")
    updated_at = value.get("updated_at")
    if description is not None and not isinstance(description, str):
        raise SourceResolutionError("github_repository_invalid")
    if language is not None and not isinstance(language, str):
        raise SourceResolutionError("github_repository_invalid")
    if updated_at is not None and not isinstance(updated_at, str):
        raise SourceResolutionError("github_repository_invalid")
    is_fork = value.get("fork")
    is_archived = value.get("archived")
    if not isinstance(is_fork, bool) or not isinstance(is_archived, bool):
        raise SourceResolutionError("github_repository_invalid")
    return PublicRepositoryMetadata(
        slug=normalized,
        name=name[:100],
        description=description[:500] if description is not None else None,
        primary_language=language[:100] if language is not None else None,
        default_branch=default_branch[:255],
        is_fork=is_fork,
        is_archived=is_archived,
        updated_at=updated_at[:64] if updated_at is not None else None,
        html_url=html_url,
    )


def _retry_after_seconds(headers: Any) -> int | None:
    retry = headers.get("Retry-After") if headers is not None else None
    if isinstance(retry, str) and retry.isdigit():
        return max(1, min(int(retry), 3600))
    reset = headers.get("X-RateLimit-Reset") if headers is not None else None
    if isinstance(reset, str) and reset.isdigit():
        return max(1, min(int(reset) - int(time.time()), 3600))
    return None


def _required_text(value: dict[str, Any], key: str, code: str) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise SourceResolutionError(code)
    return candidate


def _validate_allowed_url(value: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urlsplit(value)
    allowed = {host.casefold() for host in allowed_hosts}
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.casefold() not in allowed
        or parsed.username
        or parsed.password
    ):
        raise SourceResolutionError("github_host_not_allowed")
