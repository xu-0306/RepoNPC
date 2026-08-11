"""Allowlisted public GitHub source/ref resolution for the indexer."""

from __future__ import annotations

import base64
import binascii
import json
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

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("repository source is unavailable")


class _NoRedirect(HTTPRedirectHandler):
    """Fail closed rather than allowing urllib to follow an unchecked location."""

    def redirect_request(self, *args: object, **kwargs: object) -> Request | None:
        raise SourceResolutionError("github_redirect_rejected")


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

    def resolve(self, *, slug: str, ref: str | None) -> ResolvedRepository:
        """Resolve one configured ref and fetch only its recursively listed blobs."""

        owner, repository = _split_slug(slug)
        metadata = self._get_json(f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}")
        default_branch = _required_text(metadata, "default_branch", "github_repository_invalid")
        html_url = _required_text(metadata, "html_url", "github_repository_invalid")
        _validate_allowed_url(html_url, self.allowed_hosts)
        requested_ref = ref or default_branch
        commit = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/commits/"
            f"{quote(requested_ref, safe='')}"
        )
        commit_sha = _required_text(commit, "sha", "github_commit_invalid")
        if not COMMIT_RE.fullmatch(commit_sha):
            raise SourceResolutionError("github_commit_invalid")
        tree = self._get_json(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}/git/trees/{commit_sha}"
            "?recursive=1"
        )
        if tree.get("truncated") is True or not isinstance(tree.get("tree"), list):
            raise SourceResolutionError("github_tree_invalid")
        blobs = tuple(
            self._tree_entry_to_blob(owner, repository, item)
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
        payload = self._get_json(
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
        base = self.api_base_url.rstrip("/")
        url = base + api_path
        _validate_allowed_url(url, self.allowed_hosts)
        request = Request(url, headers={"Accept": "application/vnd.github+json"}, method="GET")
        try:
            opener = build_opener(_NoRedirect())
            with opener.open(request, timeout=self.timeout_seconds) as response:
                _validate_allowed_url(response.geturl(), self.allowed_hosts)
                if response.status != 200:
                    raise SourceResolutionError("github_response_invalid")
                payload = response.read(self.max_response_bytes + 1)
                if len(payload) > self.max_response_bytes:
                    raise SourceResolutionError("github_response_too_large")
        except SourceResolutionError:
            raise
        except (HTTPError, URLError, OSError) as exc:
            raise SourceResolutionError("github_request_failed") from exc
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceResolutionError("github_response_invalid") from exc
        if not isinstance(decoded, dict):
            raise SourceResolutionError("github_response_invalid")
        return decoded


def _split_slug(slug: str) -> tuple[str, str]:
    parts = slug.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        raise SourceResolutionError("github_repository_invalid")
    return parts[0], parts[1]


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
