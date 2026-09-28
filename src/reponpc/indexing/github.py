"""Allowlisted public GitHub source/ref resolution for the indexer."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.admin.batch_resolver import GitHubRateLimiter, GitHubRateResource
from reponpc.domain.evidence import COMMIT_RE
from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.sources import (
    ParticipationCommit,
    RepositoryBlob,
    RepositoryParticipation,
    ResolvedRepository,
)


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
    metadata_observer: Callable[[PublicRepositoryMetadata], None] | None = None
    rate_limiter: GitHubRateLimiter | None = None

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
        if self.metadata_observer is not None:
            for repository in repositories:
                self.metadata_observer(repository)
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
        metadata = _repository_metadata(payload, self.allowed_hosts)
        if self.metadata_observer is not None:
            self.metadata_observer(metadata)
        return metadata

    def profile_card_metadata(self, *, account: str, filename: str) -> dict[str, object]:
        """Inspect public profile preparation without credentials, writes or branch guesses."""
        normalized = normalize_github_account(account)
        if filename != "reponpc-card.gif":
            raise SourceResolutionError("github_filename_invalid")
        slug = f"{normalized}/{normalized}"
        base = f"https://github.com/{slug}"
        result: dict[str, object] = {
            "account": normalized,
            "repository_url": base,
            "profile_url": f"https://github.com/{normalized}",
            "readme_url": base,
            "create_url": (
                f"https://github.com/new?name={quote(normalized, safe='')}&visibility=public"
            ),
            "profile_status": "unavailable",
            "image_status": "unchecked",
            "default_branch": None,
        }
        try:
            metadata = self.repository_metadata(repository=slug)
        except SourceResolutionError as exc:
            if exc.code == "github_not_found":
                result["profile_status"] = "missing"
            return result
        branch = metadata.default_branch
        result["default_branch"] = branch
        if not branch:
            return result
        result["profile_status"] = "ready"
        for name, field in (("README.md", "profile_status"), (filename, "image_status")):
            try:
                item = self._get_json(
                    f"/repos/{quote(normalized, safe='')}/{quote(normalized, safe='')}/contents/"
                    f"{quote(name, safe='')}?ref={quote(branch, safe='')}"
                )
                if item.get("type") != "file" or item.get("path") != name:
                    result[field] = "unavailable"
                else:
                    result[field] = "ready"
                    if name == "README.md":
                        result["readme_url"] = f"{base}/edit/{quote(branch, safe='')}/README.md"
            except SourceResolutionError as exc:
                result[field] = (
                    ("missing_readme" if name == "README.md" else "missing")
                    if exc.code == "github_not_found"
                    else "unavailable"
                )
        return result

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

    def participation(
        self,
        *,
        slug: str,
        pinned_sha: str,
        github_login: str,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> RepositoryParticipation:
        """Read only linked GitHub activity reachable from the pinned commit."""

        owner, repository = _split_slug(slug)
        login = normalize_github_account(github_login)
        if not COMMIT_RE.fullmatch(pinned_sha):
            raise SourceResolutionError("github_commit_invalid")
        base = f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
        commit_path = f"{base}/commits?author={quote(login, safe='')}&sha={pinned_sha}&per_page=1"
        has_visible: bool | None = None
        first: ParticipationCommit | None = None
        last: ParticipationCommit | None = None
        try:
            latest_payload, headers = self._request_json_with_headers(
                commit_path, cancel_requested=cancel_requested, deadline=deadline
            )
            if not isinstance(latest_payload, list) or len(latest_payload) > 1:
                raise SourceResolutionError("github_response_invalid")
            if not latest_payload:
                has_visible = False
            else:
                last = _participation_commit(latest_payload[0], login)
                link = next(
                    (value for key, value in headers.items() if key.casefold() == "link"), None
                )
                page = _last_page(link, self.api_base_url, commit_path)
                if page == 1:
                    first = last
                else:
                    earliest = self._request_json(
                        f"{commit_path}&page={page}",
                        cancel_requested=cancel_requested,
                        deadline=deadline,
                    )
                    if not isinstance(earliest, list) or len(earliest) != 1:
                        raise SourceResolutionError("github_response_invalid")
                    first = _participation_commit(earliest[0], login)
                has_visible = True
        except SourceResolutionError as exc:
            if exc.code == "github_cancelled":
                raise
            first = last = None

        other_contributors: bool | None = None
        try:
            contributors = self._get_json_list(
                f"{base}/contributors?per_page=2",
                cancel_requested=cancel_requested,
                deadline=deadline,
            )
            if len(contributors) > 2 or any(
                not isinstance(item.get("login"), str) for item in contributors
            ):
                raise SourceResolutionError("github_response_invalid")
            other_contributors = any(
                item["login"].casefold() != login.casefold() for item in contributors
            )
        except SourceResolutionError as exc:
            if exc.code == "github_cancelled":
                raise
            pass
        return RepositoryParticipation(
            is_repository_owner=owner.casefold() == login.casefold(),
            has_visible_commits=has_visible,
            first_commit=first,
            last_commit=last,
            other_contributors_visible=other_contributors,
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

    def _get_json_list(
        self,
        api_path: str,
        *,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._request_json(api_path, cancel_requested=cancel_requested, deadline=deadline)
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
        payload, _headers = self._request_json_with_headers(
            api_path, cancel_requested=cancel_requested, deadline=deadline
        )
        return payload

    def _request_json_with_headers(
        self,
        api_path: str,
        *,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> tuple[object, dict[str, str]]:
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
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "RepoNPC/0.2.1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        if self.rate_limiter is not None:
            admission = self.rate_limiter.admit(GitHubRateResource.CORE)
            if not admission.allowed:
                raise SourceResolutionError(
                    "github_rate_limited",
                    admission.retry_after_seconds,
                )
        try:
            opener = build_opener(_NoRedirect())
            with opener.open(request, timeout=timeout) as response:
                _validate_allowed_url(response.geturl(), self.allowed_hosts)
                response_headers = {
                    key: value for key, value in getattr(response, "headers", {}).items()
                }
                if self.rate_limiter is not None:
                    self.rate_limiter.observe(
                        resource=GitHubRateResource.CORE,
                        status=int(response.status),
                        headers=response_headers,
                    )
                payload = response.read(self.max_response_bytes + 1)
                if response.status != 200:
                    raise SourceResolutionError("github_response_invalid")
                if len(payload) > self.max_response_bytes:
                    raise SourceResolutionError("github_response_too_large")
        except SourceResolutionError:
            raise
        except HTTPError as exc:
            payload = exc.read(self.max_response_bytes + 1)
            headers = {key: value for key, value in exc.headers.items()}
            if self.rate_limiter is not None:
                self.rate_limiter.observe(
                    resource=GitHubRateResource.CORE,
                    status=int(exc.code),
                    headers=headers,
                )
            if exc.code == 404:
                raise SourceResolutionError("github_not_found") from exc
            if exc.code in {403, 429}:
                if (
                    exc.code == 403
                    and _is_secondary_limit_body(payload)
                    and self.rate_limiter is not None
                    and self.rate_limiter.admit(GitHubRateResource.CORE).allowed
                ):
                    headers.setdefault("Retry-After", "60")
                    self.rate_limiter.observe(
                        resource=GitHubRateResource.CORE,
                        status=int(exc.code),
                        headers=headers,
                    )
                rate_admission = (
                    self.rate_limiter.admit(GitHubRateResource.CORE)
                    if self.rate_limiter is not None
                    else None
                )
                raise SourceResolutionError(
                    "github_rate_limited",
                    (
                        rate_admission.retry_after_seconds
                        if rate_admission is not None and not rate_admission.allowed
                        else _retry_after_seconds(exc.headers)
                    ),
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
        return decoded, response_headers


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


def _participation_commit(value: object, login: str) -> ParticipationCommit:
    if not isinstance(value, dict) or not isinstance(value.get("author"), dict):
        raise SourceResolutionError("github_response_invalid")
    linked_login = value["author"].get("login")
    if not isinstance(linked_login, str) or linked_login.casefold() != login.casefold():
        # The author filter does not prove that an unlinked email belongs to this login.
        raise SourceResolutionError("github_response_invalid")
    commit = value.get("commit")
    author = commit.get("author") if isinstance(commit, dict) else None
    date = author.get("date") if isinstance(author, dict) else None
    sha = value.get("sha")
    if not isinstance(sha, str) or not COMMIT_RE.fullmatch(sha) or not isinstance(date, str):
        raise SourceResolutionError("github_response_invalid")
    try:
        parsed = datetime.fromisoformat(date.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return ParticipationCommit(sha=sha, month=parsed.strftime("%Y-%m"))
    except ValueError as exc:
        raise SourceResolutionError("github_response_invalid") from exc


def _last_page(link: str | None, api_base_url: str, request_path: str) -> int:
    if not link:
        return 1
    expected = urlsplit(api_base_url.rstrip("/") + request_path)
    expected_query = parse_qs(expected.query, strict_parsing=True)
    for part in link.split(","):
        match = re.fullmatch(r'<([^<>]+)>;\s*rel="last"', part.strip())
        if match is None:
            continue
        candidate = urlsplit(match.group(1))
        try:
            query = parse_qs(candidate.query, strict_parsing=True)
            page_values = query.pop("page")
            if (
                candidate.scheme != expected.scheme
                or candidate.netloc != expected.netloc
                or candidate.path != expected.path
                or candidate.fragment
                or query != expected_query
                or len(page_values) != 1
                or not page_values[0].isdigit()
                or not 1 <= int(page_values[0]) <= 1_000_000
            ):
                raise ValueError
            return int(page_values[0])
        except (KeyError, ValueError) as exc:
            raise SourceResolutionError("github_response_invalid") from exc
    # A Link header without "last" can mean GitHub cannot calculate the final page.
    raise SourceResolutionError("github_response_invalid")


def _is_secondary_limit_body(body: bytes) -> bool:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    message = payload.get("message")
    return isinstance(message, str) and (
        "secondary rate limit" in message.casefold() or "abuse detection" in message.casefold()
    )


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
