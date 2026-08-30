"""Bounded GitHub metadata resolution and safe batch-preflight primitives.

This module deliberately owns no database rows and no HTTP routes.  The admin
orchestrator supplies decrypted *public-read* credentials from mutable runtime
state, persists the resulting plan, and records a connection as unavailable on
``GITHUB_CONNECTION_REQUIRED``.  Keeping those integrations outside this
module prevents a resolver failure from silently changing credential purpose or
mutating batch state.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import shutil
import tarfile
import tempfile
import threading
import time
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.indexing.exclusions import SourceEntryKind
from reponpc.indexing.sources import RepositoryBlob
from reponpc.indexing.sources import ResolvedRepository as IndexedRepository

GITHUB_GRAPHQL_URL: Final = "https://api.github.com/graphql"
GITHUB_ARCHIVE_BASE_URL: Final = "https://api.github.com"
MAX_GRAPHQL_PAGE_SIZE: Final = 100
MAX_GRAPHQL_RESPONSE_BYTES: Final = 1024 * 1024
DEFAULT_PREFLIGHT_PLAN_TTL: Final = timedelta(minutes=5)
_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_OWNER_RE: Final = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY_RE: Final = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class BatchResolverError(RuntimeError):
    """A stable failure that excludes credentials, raw responses, and paths."""

    def __init__(
        self,
        code: str,
        *,
        retry_after_seconds: int | None = None,
        credential_id: int | None = None,
    ) -> None:
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        self.credential_id = credential_id
        super().__init__("GitHub batch resolver operation failed")


class CredentialPurpose(StrEnum):
    """The only credential purposes eligible for public repository analysis."""

    IDENTITY_PUBLIC_READ = "identity_public_read"
    PUBLIC_READ = "public_read"
    WRITEBACK = "writeback"


@dataclass(frozen=True, slots=True)
class PublicReadCredential:
    """Server-only decrypted credential candidate.

    ``token`` is intentionally omitted from the representation so accidental
    exception or test output cannot expose it.  Callers must never serialize
    this object into an API response, event, log, or persisted preflight plan.
    """

    credential_id: int
    purpose: CredentialPurpose
    status: str
    token: str = field(repr=False, compare=False)
    github_login: str | None = None

    def __post_init__(self) -> None:
        if self.credential_id <= 0 or not self.token:
            raise ValueError("credential is invalid")
        if self.status not in {"ready", "connection_required", "invalid"}:
            raise ValueError("credential status is invalid")


@dataclass(frozen=True, slots=True)
class CredentialSelection:
    """Safe selected-credential metadata suitable for a preflight response."""

    credential_id: int
    purpose: CredentialPurpose
    github_login: str | None


def select_public_read_credential(
    candidates: Iterable[PublicReadCredential],
) -> tuple[PublicReadCredential, CredentialSelection]:
    """Select one ready read credential without a writeback fallback.

    OAuth public-read credentials are preferred because a PAT is explicitly a
    fallback connection method.  Within a purpose, the smallest persisted ID
    makes the result deterministic.  A failed selected credential must be
    marked connection-required by the caller and explicitly reconnected; this
    function never tries a second credential after a request has begun.
    """

    available = tuple(
        credential
        for credential in candidates
        if credential.status == "ready"
        and credential.purpose
        in {CredentialPurpose.IDENTITY_PUBLIC_READ, CredentialPurpose.PUBLIC_READ}
    )
    for purpose in (CredentialPurpose.IDENTITY_PUBLIC_READ, CredentialPurpose.PUBLIC_READ):
        matching = sorted(
            (credential for credential in available if credential.purpose is purpose),
            key=lambda credential: credential.credential_id,
        )
        if matching:
            selected = matching[0]
            return selected, CredentialSelection(
                credential_id=selected.credential_id,
                purpose=selected.purpose,
                github_login=selected.github_login,
            )
    raise BatchResolverError("GITHUB_CONNECTION_REQUIRED")


@dataclass(frozen=True, slots=True)
class RepositorySelection:
    """One browser-confirmed repository candidate, before source access."""

    slug: str
    ref: str | None = None
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    confirmed: bool = True

    def __post_init__(self) -> None:
        normalized = normalize_repository_slug(self.slug)
        object.__setattr__(self, "slug", normalized)
        if self.ref is not None and (not self.ref.strip() or len(self.ref) > 255):
            raise ValueError("repository ref is invalid")
        if len(self.include) > 100 or len(self.exclude) > 100:
            raise ValueError("repository path policy is invalid")


@dataclass(frozen=True, slots=True)
class ResolvedRepository:
    """A public repository proven eligible for exact-SHA archive retrieval."""

    slug: str
    node_id: str
    default_branch: str
    commit_sha: str
    is_archived: bool
    archive_url: str


@dataclass(frozen=True, slots=True)
class ResolutionBlocker:
    slug: str
    code: str


@dataclass(frozen=True, slots=True)
class MetadataResolution:
    repositories: tuple[ResolvedRepository, ...]
    blockers: tuple[ResolutionBlocker, ...]


@dataclass(frozen=True, slots=True)
class GitHubHttpResponse:
    """Bounded response metadata supplied by an allowlisted transport."""

    status: int
    body: bytes
    headers: Mapping[str, str]


class GitHubGraphQLTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> GitHubHttpResponse: ...


class _NoRedirect(HTTPRedirectHandler):
    """Return the redirect response to the caller instead of following it."""

    def redirect_request(self, *args: object, **kwargs: object) -> Request | None:
        del args, kwargs
        return None


class UrllibGitHubGraphQLTransport:
    """Production GraphQL transport restricted to GitHub's fixed API endpoint."""

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("GitHub GraphQL timeout must be positive")
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> GitHubHttpResponse:
        _validate_github_api_url(url, expected_path="/graphql")
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with build_opener(_NoRedirect()).open(
                request, timeout=self._timeout_seconds
            ) as response:
                _validate_github_api_url(response.geturl(), expected_path="/graphql")
                payload = response.read(MAX_GRAPHQL_RESPONSE_BYTES + 1)
                if len(payload) > MAX_GRAPHQL_RESPONSE_BYTES:
                    raise BatchResolverError("GITHUB_ERROR")
                return GitHubHttpResponse(
                    status=int(response.status),
                    body=payload,
                    headers={key: value for key, value in response.headers.items()},
                )
        except BatchResolverError:
            raise
        except HTTPError as exc:
            payload = exc.read(MAX_GRAPHQL_RESPONSE_BYTES + 1)
            return GitHubHttpResponse(
                status=int(exc.code),
                body=payload if len(payload) <= MAX_GRAPHQL_RESPONSE_BYTES else b"",
                headers={key: value for key, value in exc.headers.items()},
            )
        except (URLError, OSError, TimeoutError) as exc:
            raise BatchResolverError("GITHUB_ERROR") from exc


class GitHubArchiveTransport(Protocol):
    """A fixed-URL archive transport that yields untrusted bytes in chunks."""

    def stream(
        self,
        *,
        archive_url: str,
        credential: PublicReadCredential,
        limiter: GitHubRateLimiter,
    ) -> Iterable[bytes]: ...


class UrllibGitHubArchiveTransport:
    """Stream one immutable archive without forwarding credentials on redirects.

    GitHub's archive endpoint normally redirects to ``codeload.github.com``.
    We make that redirect explicit, accept only that single HTTPS host, and
    deliberately remove Authorization on the second request.  This keeps the
    OAuth/PAT scoped to the fixed GitHub API host.
    """

    def __init__(self, *, timeout_seconds: float = 20.0, chunk_bytes: int = 64 * 1024) -> None:
        if timeout_seconds <= 0 or chunk_bytes <= 0:
            raise ValueError("archive transport limits must be positive")
        self._timeout_seconds = timeout_seconds
        self._chunk_bytes = chunk_bytes

    def stream(
        self,
        *,
        archive_url: str,
        credential: PublicReadCredential,
        limiter: GitHubRateLimiter,
    ) -> Iterable[bytes]:
        _validate_exact_archive_url(archive_url)
        if (
            credential.purpose
            not in {
                CredentialPurpose.IDENTITY_PUBLIC_READ,
                CredentialPurpose.PUBLIC_READ,
            }
            or credential.status != "ready"
        ):
            raise BatchResolverError(
                "GITHUB_CONNECTION_REQUIRED", credential_id=credential.credential_id
            )
        admission = limiter.admit(GitHubRateResource.CORE)
        if not admission.allowed:
            raise BatchResolverError(
                "GITHUB_RATE_LIMITED",
                retry_after_seconds=admission.retry_after_seconds,
                credential_id=credential.credential_id,
            )

        request = Request(
            archive_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {credential.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method="GET",
        )
        opener = build_opener(_NoRedirect())
        response = None
        try:
            try:
                response = opener.open(request, timeout=self._timeout_seconds)
            except HTTPError as exc:
                if exc.code not in {301, 302, 303, 307, 308}:
                    self._raise_archive_http_error(exc, credential, limiter)
                location = exc.headers.get("Location")
                _validate_archive_redirect(location)
                redirect = Request(
                    str(location),
                    headers={"Accept": "application/vnd.github+json"},
                    method="GET",
                )
                response = opener.open(redirect, timeout=self._timeout_seconds)
            _validate_archive_final_url(response.geturl())
            limiter.observe(
                resource=GitHubRateResource.CORE,
                status=int(response.status),
                headers={key: value for key, value in response.headers.items()},
            )
            if int(response.status) != 200:
                raise BatchResolverError("GITHUB_ERROR", credential_id=credential.credential_id)
            while True:
                chunk = response.read(self._chunk_bytes)
                if not chunk:
                    return
                yield chunk
        except BatchResolverError:
            raise
        except HTTPError as exc:
            self._raise_archive_http_error(exc, credential, limiter)
        except (URLError, OSError, TimeoutError) as exc:
            raise BatchResolverError(
                "GITHUB_ERROR", credential_id=credential.credential_id
            ) from exc
        finally:
            if response is not None:
                response.close()

    @staticmethod
    def _raise_archive_http_error(
        error: HTTPError,
        credential: PublicReadCredential,
        limiter: GitHubRateLimiter,
    ) -> None:
        headers = {key: value for key, value in error.headers.items()}
        limiter.observe(
            resource=GitHubRateResource.CORE,
            status=int(error.code),
            headers=headers,
        )
        if error.code == 401:
            raise BatchResolverError(
                "GITHUB_CONNECTION_REQUIRED", credential_id=credential.credential_id
            )
        admission = limiter.admit(GitHubRateResource.CORE)
        if error.code in {403, 429} and not admission.allowed:
            raise BatchResolverError(
                "GITHUB_RATE_LIMITED",
                retry_after_seconds=admission.retry_after_seconds,
                credential_id=credential.credential_id,
            )
        raise BatchResolverError("GITHUB_ERROR", credential_id=credential.credential_id)


class GitHubRateResource(StrEnum):
    GRAPHQL = "graphql"
    CORE = "core"


@dataclass(frozen=True, slots=True)
class RateBudget:
    resource: GitHubRateResource
    limit: int | None
    remaining: int | None
    reset_at: datetime | None


@dataclass(frozen=True, slots=True)
class RateAdmission:
    allowed: bool
    retry_at: datetime | None = None
    retry_after_seconds: int | None = None
    reason: str | None = None


class GitHubRateStatePersistence(Protocol):
    """Sanitized runtime persistence for shared rate admission state."""

    def load(self) -> tuple[RateBudget, RateBudget, datetime | None]: ...

    def save(
        self,
        *,
        graphql: RateBudget,
        core: RateBudget,
        secondary_retry_at: datetime | None,
    ) -> None: ...


class GitHubRateLimiter:
    """Read GitHub headers and expose non-blocking admission decisions.

    GraphQL and REST/core primary budgets are independent.  GitHub secondary
    limits are intentionally shared, so one response can pause both request
    classes.  The limiter never sleeps or calls ``/rate_limit``; schedulers use
    the returned retry time to pause admission without a busy loop.
    """

    def __init__(
        self,
        *,
        safety_reserve: int = 25,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        persistence: GitHubRateStatePersistence | None = None,
    ) -> None:
        if isinstance(safety_reserve, bool) or safety_reserve < 0:
            raise ValueError("rate-limit safety reserve is invalid")
        self._safety_reserve = safety_reserve
        self._now = now
        self._persistence = persistence
        self._budgets = {
            GitHubRateResource.GRAPHQL: RateBudget(GitHubRateResource.GRAPHQL, None, None, None),
            GitHubRateResource.CORE: RateBudget(GitHubRateResource.CORE, None, None, None),
        }
        self._secondary_retry_at: datetime | None = None
        self._lock = threading.RLock()
        if persistence is not None:
            graphql, core, secondary = persistence.load()
            self._budgets = {
                GitHubRateResource.GRAPHQL: graphql,
                GitHubRateResource.CORE: core,
            }
            self._secondary_retry_at = secondary

    def observe(
        self,
        *,
        resource: GitHubRateResource,
        status: int,
        headers: Mapping[str, str],
        observed_at: datetime | None = None,
    ) -> None:
        """Record response budgets and a shared secondary-limit pause."""

        now = _as_utc(observed_at or self._now())
        normalized = _normalized_headers(headers)
        reported_resource = normalized.get("x-ratelimit-resource", "").casefold()
        effective_resource = (
            GitHubRateResource.GRAPHQL
            if reported_resource == GitHubRateResource.GRAPHQL
            else GitHubRateResource.CORE
            if reported_resource == GitHubRateResource.CORE
            else resource
        )
        with self._lock:
            prior = self._budgets[effective_resource]
            reported_reset = _header_epoch(normalized, "x-ratelimit-reset")
            reported_remaining = _header_integer(normalized, "x-ratelimit-remaining")
            same_window = (
                reported_reset is not None
                and prior.reset_at is not None
                and reported_reset == prior.reset_at
            )
            if same_window and prior.remaining is not None and reported_remaining is not None:
                reported_remaining = min(prior.remaining, reported_remaining)
            self._budgets[effective_resource] = RateBudget(
                resource=effective_resource,
                limit=_header_integer(normalized, "x-ratelimit-limit") or prior.limit,
                remaining=reported_remaining if reported_remaining is not None else prior.remaining,
                reset_at=reported_reset or prior.reset_at,
            )

            retry_at = _retry_at(normalized.get("retry-after"), now)
            # A Retry-After response is a secondary-limit signal even when GitHub
            # also happens to send primary headers. A bare 429 gets a conservative
            # one-minute pause rather than immediately retrying.
            if retry_at is not None or status == 429:
                candidate = retry_at or now + timedelta(seconds=60)
                if self._secondary_retry_at is None or candidate > self._secondary_retry_at:
                    self._secondary_retry_at = candidate
            self._persist()

    def admit(
        self,
        resource: GitHubRateResource,
        *,
        observed_at: datetime | None = None,
    ) -> RateAdmission:
        """Return whether a request may start now; no wait occurs here."""

        now = _as_utc(observed_at or self._now())
        with self._lock:
            pauses: list[tuple[datetime, str]] = []
            if self._secondary_retry_at is not None:
                if self._secondary_retry_at > now:
                    pauses.append((self._secondary_retry_at, "secondary"))
                else:
                    self._secondary_retry_at = None
                    self._persist()
            budget = self._budgets[resource]
            if (
                budget.remaining is not None
                and budget.remaining <= self._safety_reserve
                and budget.reset_at is not None
                and budget.reset_at > now
            ):
                pauses.append((budget.reset_at, "primary"))
            if not pauses:
                return RateAdmission(True)
            retry_at, reason = max(pauses, key=lambda value: value[0])
            return RateAdmission(
                False,
                retry_at=retry_at,
                retry_after_seconds=max(1, math.ceil((retry_at - now).total_seconds())),
                reason=reason,
            )

    def snapshot(self) -> tuple[RateBudget, RateBudget, datetime | None]:
        """Return safe rate metadata for preflight responses and persistence."""

        with self._lock:
            return (
                self._budgets[GitHubRateResource.GRAPHQL],
                self._budgets[GitHubRateResource.CORE],
                self._secondary_retry_at,
            )

    def _persist(self) -> None:
        if self._persistence is not None:
            self._persistence.save(
                graphql=self._budgets[GitHubRateResource.GRAPHQL],
                core=self._budgets[GitHubRateResource.CORE],
                secondary_retry_at=self._secondary_retry_at,
            )


class GitHubGraphQLMetadataResolver:
    """Resolve one page of confirmed public repositories through GraphQL."""

    def __init__(
        self,
        *,
        transport: GitHubGraphQLTransport,
        limiter: GitHubRateLimiter,
        api_url: str = GITHUB_GRAPHQL_URL,
        allow_archived: bool = False,
    ) -> None:
        _validate_github_api_url(api_url, expected_path="/graphql")
        self._transport = transport
        self._limiter = limiter
        self._api_url = api_url
        self._allow_archived = allow_archived

    def resolve_page(
        self,
        *,
        selections: Sequence[RepositorySelection],
        credential: PublicReadCredential,
    ) -> MetadataResolution:
        """Resolve at most 100 confirmed selections without source retrieval."""

        if not 1 <= len(selections) <= MAX_GRAPHQL_PAGE_SIZE:
            raise ValueError("GraphQL metadata page must contain 1 to 100 repositories")
        if any(not selection.confirmed for selection in selections):
            raise ValueError("unconfirmed repositories cannot be resolved for analysis")
        if (
            credential.purpose
            not in {
                CredentialPurpose.IDENTITY_PUBLIC_READ,
                CredentialPurpose.PUBLIC_READ,
            }
            or credential.status != "ready"
        ):
            raise BatchResolverError(
                "GITHUB_CONNECTION_REQUIRED", credential_id=credential.credential_id
            )

        admission = self._limiter.admit(GitHubRateResource.GRAPHQL)
        if not admission.allowed:
            raise BatchResolverError(
                "RATE_LIMITED",
                retry_after_seconds=admission.retry_after_seconds,
                credential_id=credential.credential_id,
            )

        query, variables = build_metadata_query(selections)
        request_body = json.dumps(
            {"query": query, "variables": variables}, separators=(",", ":")
        ).encode("utf-8")
        try:
            response = self._transport.request(
                method="POST",
                url=self._api_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {credential.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Content-Type": "application/json",
                },
                body=request_body,
            )
        except BatchResolverError:
            raise
        except Exception as exc:
            raise BatchResolverError(
                "GITHUB_ERROR", credential_id=credential.credential_id
            ) from exc
        self._limiter.observe(
            resource=GitHubRateResource.GRAPHQL,
            status=response.status,
            headers=response.headers,
        )
        if response.status == 401:
            raise BatchResolverError(
                "GITHUB_CONNECTION_REQUIRED", credential_id=credential.credential_id
            )
        admission = self._limiter.admit(GitHubRateResource.GRAPHQL)
        if response.status in {403, 429} and not admission.allowed:
            raise BatchResolverError(
                "RATE_LIMITED",
                retry_after_seconds=admission.retry_after_seconds,
                credential_id=credential.credential_id,
            )
        if response.status != 200 or len(response.body) > MAX_GRAPHQL_RESPONSE_BYTES:
            raise BatchResolverError("GITHUB_ERROR", credential_id=credential.credential_id)
        try:
            payload = json.loads(response.body.decode("utf-8"))
            data = payload["data"]
        except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BatchResolverError(
                "GITHUB_ERROR", credential_id=credential.credential_id
            ) from exc
        if not isinstance(data, dict):
            raise BatchResolverError("GITHUB_ERROR", credential_id=credential.credential_id)
        resolution = _metadata_resolution(
            selections=selections,
            data=data,
            allow_archived=self._allow_archived,
        )
        return MetadataResolution(
            _deduplicate_repositories(resolution.repositories), resolution.blockers
        )

    def resolve_all(
        self,
        *,
        selections: Sequence[RepositorySelection],
        credential: PublicReadCredential,
    ) -> MetadataResolution:
        """Resolve every selection in GraphQL pages of at most 100 entries."""

        repositories: list[ResolvedRepository] = []
        blockers: list[ResolutionBlocker] = []
        for start in range(0, len(selections), MAX_GRAPHQL_PAGE_SIZE):
            page = self.resolve_page(
                selections=selections[start : start + MAX_GRAPHQL_PAGE_SIZE], credential=credential
            )
            repositories.extend(page.repositories)
            blockers.extend(page.blockers)
        return MetadataResolution(_deduplicate_repositories(repositories), tuple(blockers))


def build_metadata_query(
    selections: Sequence[RepositorySelection],
) -> tuple[str, dict[str, str]]:
    """Build a variable-only GraphQL page; slugs/refs never become query text."""

    definitions: list[str] = []
    fields: list[str] = []
    variables: dict[str, str] = {}
    for index, selection in enumerate(selections):
        owner, repository = selection.slug.split("/", 1)
        owner_name = f"owner{index}"
        repository_name = f"repository{index}"
        definitions.extend((f"${owner_name}: String!", f"${repository_name}: String!"))
        variables[owner_name] = owner
        variables[repository_name] = repository
        object_field = ""
        if selection.ref is not None:
            ref_name = f"ref{index}"
            definitions.append(f"${ref_name}: String!")
            variables[ref_name] = selection.ref
            object_field = (
                f" object(expression: ${ref_name}) {{"
                " ... on Commit { oid }"
                " ... on Tag { target { ... on Commit { oid } } }"
                " }"
            )
        fields.append(
            f"repo{index}: repository(owner: ${owner_name}, name: ${repository_name}) {{"
            " id nameWithOwner isPrivate isArchived"
            " defaultBranchRef { name target { ... on Commit { oid } } }"
            f"{object_field}"
            " }"
        )
    return (
        f"query BatchRepositoryMetadata({', '.join(definitions)}) {{ {' '.join(fields)} }}",
        variables,
    )


@dataclass(frozen=True, slots=True)
class ArchiveSafetyLimits:
    """Caller-configured bounds for one untrusted GitHub archive."""

    max_compressed_bytes: int
    max_uncompressed_bytes: int
    max_entries: int
    max_single_file_bytes: int = 5 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (
            self.max_compressed_bytes,
            self.max_uncompressed_bytes,
            self.max_entries,
            self.max_single_file_bytes,
        )
        if any(isinstance(value, bool) or value <= 0 for value in values):
            raise ValueError("archive safety limits must be positive")


@dataclass(frozen=True, slots=True)
class StagedArchive:
    directory: Path
    archive_path: Path
    compressed_bytes: int


@dataclass(frozen=True, slots=True)
class ArchiveInspection:
    entry_count: int
    uncompressed_bytes: int
    paths: tuple[str, ...]


def stage_archive_stream(
    chunks: Iterable[bytes],
    *,
    staging_root: Path,
    limits: ArchiveSafetyLimits,
    cancel_requested: Callable[[], bool] | None = None,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> StagedArchive:
    """Write a bounded archive stream into a unique staging directory.

    Any failure deletes the newly created directory.  The caller must invoke
    :func:`cleanup_staged_archive` after processing a successful result.
    """

    root = Path(staging_root)
    root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="github-archive-", dir=root))
    archive_path = directory / "source.archive"
    written = 0
    try:
        with archive_path.open("xb") as output:
            for chunk in chunks:
                _check_stream_cancellation(
                    cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
                )
                if not isinstance(chunk, bytes):
                    raise BatchResolverError("GITHUB_ERROR")
                written += len(chunk)
                if written > limits.max_compressed_bytes:
                    raise BatchResolverError("ARCHIVE_TOO_LARGE")
                output.write(chunk)
        _check_stream_cancellation(
            cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
        )
        if written == 0:
            raise BatchResolverError("GITHUB_ERROR")
        return StagedArchive(directory, archive_path, written)
    except Exception:
        _safe_staging_cleanup(directory, root)
        raise


def inspect_archive(
    archive_path: Path,
    *,
    limits: ArchiveSafetyLimits,
    cancel_requested: Callable[[], bool] | None = None,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> ArchiveInspection:
    """Validate paths/types/counts before any archive content is extracted."""

    path = Path(archive_path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise BatchResolverError("GITHUB_ERROR")
    if path.stat().st_size > limits.max_compressed_bytes:
        raise BatchResolverError("ARCHIVE_TOO_LARGE")
    try:
        if zipfile.is_zipfile(path):
            entries = _inspect_zip(
                path,
                limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
        else:
            entries = _inspect_tar(
                path,
                limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
    except BatchResolverError:
        raise
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise BatchResolverError("ARCHIVE_INVALID") from exc
    return ArchiveInspection(
        entry_count=len(entries),
        uncompressed_bytes=sum(size for _, size in entries),
        paths=tuple(path for path, _ in entries),
    )


def cleanup_staged_archive(staged: StagedArchive, *, staging_root: Path) -> None:
    """Remove exactly one resolver-created staging directory, never its root."""

    _safe_staging_cleanup(staged.directory, Path(staging_root))


class GitHubArchiveSource:
    """Turn one validated immutable GitHub archive into repository blobs.

    The archive staging directory is owned by this object and is deleted in a
    ``finally`` block once regular-file bytes have been bounded and copied into
    immutable in-memory source objects.  Callers never receive an archive path
    and cannot reuse an unvalidated archive between items.
    """

    def __init__(
        self,
        *,
        transport: GitHubArchiveTransport,
        limiter: GitHubRateLimiter,
        staging_root: Path,
        limits: ArchiveSafetyLimits,
    ) -> None:
        self._transport = transport
        self._limiter = limiter
        self._staging_root = Path(staging_root)
        self._limits = limits

    def fetch(
        self,
        *,
        repository: ResolvedRepository,
        credential: PublicReadCredential,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> IndexedRepository:
        """Fetch exactly ``repository.commit_sha`` and return safe source blobs."""

        _validate_exact_archive_url(repository.archive_url, repository=repository)
        staged = stage_archive_stream(
            self._transport.stream(
                archive_url=repository.archive_url,
                credential=credential,
                limiter=self._limiter,
            ),
            staging_root=self._staging_root,
            limits=self._limits,
            cancel_requested=cancel_requested,
            deadline=deadline,
            monotonic=monotonic,
        )
        try:
            inspection = inspect_archive(
                staged.archive_path,
                limits=self._limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
            _check_stream_cancellation(
                cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
            )
            blobs = _archive_blobs(
                staged.archive_path,
                inspection=inspection,
                limits=self._limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
            return IndexedRepository(
                slug=repository.slug,
                commit_sha=repository.commit_sha,
                default_branch=repository.default_branch,
                github_html_url=f"https://github.com/{repository.slug}",
                blobs=blobs,
            )
        finally:
            cleanup_staged_archive(staged, staging_root=self._staging_root)


@dataclass(frozen=True, slots=True)
class CachePrediction:
    derived_index_hit: bool
    validated_analysis_hit: bool

    def __post_init__(self) -> None:
        if self.validated_analysis_hit and not self.derived_index_hit:
            raise ValueError("validated analysis cache requires derived index cache")


@dataclass(frozen=True, slots=True)
class ProviderReadiness:
    ready: bool
    safe_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BatchCapacity:
    github_requests: int
    archive_staging: int
    index_work: int
    generation: int
    whole_job_items: int

    def __post_init__(self) -> None:
        values = (
            self.github_requests,
            self.archive_staging,
            self.index_work,
            self.generation,
            self.whole_job_items,
        )
        if any(isinstance(value, bool) or value <= 0 for value in values):
            raise ValueError("batch capacity must be positive")
        if self.github_requests > 2 or self.archive_staging > 2 or self.index_work > 2:
            raise ValueError("GitHub/archive/index capacity exceeds the approved hard boundary")

    @property
    def effective_work_items(self) -> int:
        return min(self.archive_staging, self.index_work, self.generation, self.whole_job_items)


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    minimum_seconds: int
    maximum_seconds: int
    confidence: str


@dataclass(frozen=True, slots=True)
class BatchPreflightPlan:
    """Safe, short-lived preflight data for persistence by the admin layer."""

    plan_id: str
    expires_at: datetime
    selection_hash: str
    selected_credential: CredentialSelection | None
    repositories: tuple[ResolvedRepository, ...]
    cache_predictions: Mapping[str, CachePrediction]
    graphql_budget: RateBudget
    core_budget: RateBudget
    secondary_retry_at: datetime | None
    provider_ready: bool
    server_capacity: BatchCapacity
    maximum_generation_attempts: int
    duration: DurationEstimate | None
    blockers: tuple[ResolutionBlocker, ...]
    warnings: tuple[str, ...]


class BatchPreflightPlanner:
    """Compose resolver/cache/provider facts into a non-persistent preflight plan."""

    def __init__(
        self,
        *,
        resolver: GitHubGraphQLMetadataResolver,
        limiter: GitHubRateLimiter,
        plan_ttl: timedelta = DEFAULT_PREFLIGHT_PLAN_TTL,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        plan_id_factory: Callable[[], str] = lambda: secrets.token_urlsafe(24),
    ) -> None:
        if plan_ttl <= timedelta(0):
            raise ValueError("preflight plan TTL must be positive")
        self._resolver = resolver
        self._limiter = limiter
        self._plan_ttl = plan_ttl
        self._now = now
        self._plan_id_factory = plan_id_factory

    def create(
        self,
        *,
        selections: Sequence[RepositorySelection],
        credentials: Iterable[PublicReadCredential],
        cache_prediction: Callable[[ResolvedRepository], CachePrediction],
        provider: ProviderReadiness,
        capacity: BatchCapacity,
    ) -> BatchPreflightPlan:
        """Create safe preflight data without dispatching archive/model work."""

        if not selections:
            raise ValueError("preflight requires at least one repository")
        selection_hash = selection_hash_for(selections)
        blockers: list[ResolutionBlocker] = [
            ResolutionBlocker(selection.slug, "CONFIRMATION_REQUIRED")
            for selection in selections
            if not selection.confirmed
        ]
        selected: CredentialSelection | None = None
        resolution = MetadataResolution((), ())
        if not blockers:
            try:
                credential, selected = select_public_read_credential(credentials)
                resolution = self._resolver.resolve_all(
                    selections=selections, credential=credential
                )
            except BatchResolverError as exc:
                blockers.append(ResolutionBlocker("github", exc.code))
        blockers.extend(resolution.blockers)
        if not provider.ready:
            blockers.append(
                ResolutionBlocker("provider", provider.safe_reason or "MODEL_UNAVAILABLE")
            )

        predictions: dict[str, CachePrediction] = {}
        warnings: list[str] = []
        for repository in resolution.repositories:
            prediction = cache_prediction(repository)
            predictions[f"{repository.slug}@{repository.commit_sha}"] = prediction
            if repository.is_archived:
                warnings.append(f"ARCHIVED_REPOSITORY:{repository.slug}")
        duration = (
            _estimate_duration(tuple(predictions.values()), capacity.effective_work_items)
            if not blockers
            else None
        )
        graphql_budget, core_budget, secondary_retry_at = self._limiter.snapshot()
        now = _as_utc(self._now())
        return BatchPreflightPlan(
            plan_id=self._plan_id_factory(),
            expires_at=now + self._plan_ttl,
            selection_hash=selection_hash,
            selected_credential=selected,
            repositories=resolution.repositories,
            cache_predictions=predictions,
            graphql_budget=graphql_budget,
            core_budget=core_budget,
            secondary_retry_at=secondary_retry_at,
            provider_ready=provider.ready,
            server_capacity=capacity,
            maximum_generation_attempts=1,
            duration=duration,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
        )


def selection_hash_for(selections: Sequence[RepositorySelection]) -> str:
    """Hash the canonical selection and policy so a submitted plan is bound to it."""

    canonical = [
        {
            "slug": selection.slug,
            "ref": selection.ref,
            "include": list(selection.include),
            "exclude": list(selection.exclude),
            "confirmed": selection.confirmed,
        }
        for selection in sorted(
            selections,
            key=lambda selection: (
                selection.slug,
                selection.ref or "",
                selection.include,
                selection.exclude,
                selection.confirmed,
            ),
        )
    ]
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def normalize_repository_slug(value: str) -> str:
    """Accept only one public GitHub ``owner/name`` shape."""

    if not isinstance(value, str):
        raise ValueError("repository slug is invalid")
    candidate = value.strip()
    parts = candidate.split("/")
    if (
        len(parts) != 2
        or not _OWNER_RE.fullmatch(parts[0])
        or not _REPOSITORY_RE.fullmatch(parts[1])
    ):
        raise ValueError("repository slug is invalid")
    return f"{parts[0]}/{parts[1]}"


def _metadata_resolution(
    *,
    selections: Sequence[RepositorySelection],
    data: Mapping[str, object],
    allow_archived: bool,
) -> MetadataResolution:
    repositories: list[ResolvedRepository] = []
    blockers: list[ResolutionBlocker] = []
    for index, selection in enumerate(selections):
        if not selection.confirmed:
            blockers.append(ResolutionBlocker(selection.slug, "CONFIRMATION_REQUIRED"))
            continue
        raw = data.get(f"repo{index}")
        if raw is None:
            blockers.append(ResolutionBlocker(selection.slug, "NOT_FOUND"))
            continue
        if not isinstance(raw, Mapping):
            blockers.append(ResolutionBlocker(selection.slug, "GITHUB_ERROR"))
            continue
        is_private = raw.get("isPrivate")
        if is_private is True:
            blockers.append(ResolutionBlocker(selection.slug, "NOT_FOUND"))
            continue
        if is_private is not False:
            blockers.append(ResolutionBlocker(selection.slug, "GITHUB_ERROR"))
            continue
        try:
            reported_slug = str(raw["nameWithOwner"])
            if normalize_repository_slug(reported_slug).casefold() != selection.slug.casefold():
                raise ValueError
            node_id = _required_text(raw, "id")
            branch = raw.get("defaultBranchRef")
            if not isinstance(branch, Mapping):
                raise ValueError
            default_branch = _required_text(branch, "name")
            commit_sha = _commit_from_repository(raw, selection.ref is not None)
            is_archived = raw.get("isArchived")
            if not isinstance(is_archived, bool):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            blockers.append(ResolutionBlocker(selection.slug, "GITHUB_ERROR"))
            continue
        if is_archived and not allow_archived:
            blockers.append(ResolutionBlocker(selection.slug, "ARCHIVED_NOT_ALLOWED"))
            continue
        owner, repository = selection.slug.split("/", 1)
        archive_url = (
            f"{GITHUB_ARCHIVE_BASE_URL}/repos/{quote(owner, safe='')}/"
            f"{quote(repository, safe='')}/tarball/{commit_sha}"
        )
        repositories.append(
            ResolvedRepository(
                slug=selection.slug,
                node_id=node_id,
                default_branch=default_branch,
                commit_sha=commit_sha,
                is_archived=is_archived,
                archive_url=archive_url,
            )
        )
    return MetadataResolution(tuple(repositories), tuple(blockers))


def _deduplicate_repositories(
    repositories: Iterable[ResolvedRepository],
) -> tuple[ResolvedRepository, ...]:
    unique: dict[tuple[str, str], ResolvedRepository] = {}
    for repository in repositories:
        unique.setdefault((repository.slug.casefold(), repository.commit_sha), repository)
    return tuple(unique.values())


def _commit_from_repository(repository: Mapping[str, object], requested_ref: bool) -> str:
    candidate: object = (
        repository.get("object") if requested_ref else repository.get("defaultBranchRef")
    )
    if not isinstance(candidate, Mapping):
        raise ValueError("commit target is missing")
    if not requested_ref:
        candidate = candidate.get("target")
    if not isinstance(candidate, Mapping):
        raise ValueError("commit target is missing")
    direct = candidate.get("oid")
    if isinstance(direct, str) and _SHA_RE.fullmatch(direct):
        return direct
    target = candidate.get("target")
    if isinstance(target, Mapping):
        nested = target.get("oid")
        if isinstance(nested, str) and _SHA_RE.fullmatch(nested):
            return nested
    raise ValueError("commit SHA is invalid")


def _required_text(value: Mapping[str, object], key: str) -> str:
    candidate = value[key]
    if not isinstance(candidate, str) or not candidate:
        raise ValueError("metadata text is invalid")
    return candidate


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        str(key).casefold(): str(value).strip()
        for key, value in headers.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _header_integer(headers: Mapping[str, str], name: str) -> int | None:
    value = headers.get(name)
    if value is None or not value.isdigit():
        return None
    return int(value)


def _header_epoch(headers: Mapping[str, str], name: str) -> datetime | None:
    value = _header_integer(headers, name)
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _retry_at(value: str | None, now: datetime) -> datetime | None:
    if not value:
        return None
    if value.isdigit():
        return now + timedelta(seconds=max(1, int(value)))
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(UTC)


def _validate_github_api_url(value: str, *, expected_path: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.path != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("GitHub API URL is invalid")


def _validate_exact_archive_url(
    value: str, *, repository: ResolvedRepository | None = None
) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.port not in {None, 443}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise BatchResolverError("ARCHIVE_UNSAFE")
    parts = parsed.path.split("/")
    if len(parts) != 6 or parts[:2] != ["", "repos"] or parts[4] != "tarball":
        raise BatchResolverError("ARCHIVE_UNSAFE")
    owner, name, commit = parts[2], parts[3], parts[5]
    if (
        not _OWNER_RE.fullmatch(owner)
        or not _REPOSITORY_RE.fullmatch(name)
        or not _SHA_RE.fullmatch(commit)
    ):
        raise BatchResolverError("ARCHIVE_UNSAFE")
    if repository is not None and (
        f"{owner}/{name}" != repository.slug or commit != repository.commit_sha
    ):
        raise BatchResolverError("ARCHIVE_UNSAFE")


def _validate_archive_redirect(value: str | None) -> None:
    if not value:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "codeload.github.com"
        or parsed.port not in {None, 443}
        or not parsed.path.startswith("/")
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise BatchResolverError("ARCHIVE_UNSAFE")


def _validate_archive_final_url(value: str) -> None:
    _validate_archive_redirect(value)


def _check_stream_cancellation(
    *,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> None:
    if cancel_requested is not None and cancel_requested():
        raise BatchResolverError("CANCELLED")
    if deadline is not None and monotonic() >= deadline:
        raise BatchResolverError("GITHUB_TIMEOUT")


def _inspect_tar(
    path: Path,
    limits: ArchiveSafetyLimits,
    *,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    total = 0
    with tarfile.open(path, mode="r:*") as archive:
        for member in archive:
            _check_stream_cancellation(
                cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
            )
            _validate_archive_path(member.name)
            if member.isdir():
                continue
            if not member.isreg() or member.issym() or member.islnk():
                raise BatchResolverError("ARCHIVE_UNSAFE")
            entries, total = _append_archive_entry(entries, total, member.name, member.size, limits)
    return entries


def _inspect_zip(
    path: Path,
    limits: ArchiveSafetyLimits,
    *,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            _check_stream_cancellation(
                cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
            )
            _validate_archive_path(info.filename)
            if info.is_dir():
                continue
            # Unix mode bits are present when an attacker creates a symlink ZIP.
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode != 0o100000:
                raise BatchResolverError("ARCHIVE_UNSAFE")
            entries, total = _append_archive_entry(
                entries, total, info.filename, info.file_size, limits
            )
    return entries


def _append_archive_entry(
    entries: list[tuple[str, int]],
    total: int,
    name: str,
    size: int,
    limits: ArchiveSafetyLimits,
) -> tuple[list[tuple[str, int]], int]:
    if isinstance(size, bool) or size < 0:
        raise BatchResolverError("ARCHIVE_INVALID")
    if size > limits.max_single_file_bytes:
        raise BatchResolverError("ARCHIVE_TOO_LARGE")
    normalized = _validate_archive_path(name)
    if any(existing == normalized for existing, _ in entries):
        raise BatchResolverError("ARCHIVE_UNSAFE")
    if len(entries) + 1 > limits.max_entries:
        raise BatchResolverError("ARCHIVE_TOO_LARGE")
    total += size
    if total > limits.max_uncompressed_bytes:
        raise BatchResolverError("ARCHIVE_TOO_LARGE")
    entries.append((normalized, size))
    return entries, total


def _validate_archive_path(value: str) -> str:
    if not value or "\x00" in value or "\\" in value:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise BatchResolverError("ARCHIVE_UNSAFE")
    return path.as_posix()


def _archive_blobs(
    archive_path: Path,
    *,
    inspection: ArchiveInspection,
    limits: ArchiveSafetyLimits,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> tuple[RepositoryBlob, ...]:
    paths = inspection.paths
    if not paths:
        raise BatchResolverError("ARCHIVE_INVALID")
    root = PurePosixPath(paths[0]).parts[0]
    if not root:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    try:
        if zipfile.is_zipfile(archive_path):
            blobs = _zip_archive_blobs(
                archive_path,
                root=root,
                limits=limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
        else:
            blobs = _tar_archive_blobs(
                archive_path,
                root=root,
                limits=limits,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=monotonic,
            )
    except BatchResolverError:
        raise
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        raise BatchResolverError("ARCHIVE_INVALID") from exc
    if len(blobs) != inspection.entry_count:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    return tuple(sorted(blobs, key=lambda blob: blob.path))


def _tar_archive_blobs(
    archive_path: Path,
    *,
    root: str,
    limits: ArchiveSafetyLimits,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> list[RepositoryBlob]:
    blobs: list[RepositoryBlob] = []
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive:
            _check_stream_cancellation(
                cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
            )
            if member.isdir():
                continue
            if not member.isreg() or member.issym() or member.islnk():
                raise BatchResolverError("ARCHIVE_UNSAFE")
            path = _archive_content_path(member.name, root)
            if member.size > limits.max_single_file_bytes:
                raise BatchResolverError("ARCHIVE_TOO_LARGE")
            handle = archive.extractfile(member)
            if handle is None:
                raise BatchResolverError("ARCHIVE_INVALID")
            with handle:
                content = _read_member_bytes(
                    handle,
                    expected_size=member.size,
                    cancel_requested=cancel_requested,
                    deadline=deadline,
                    monotonic=monotonic,
                )
            blobs.append(
                RepositoryBlob(
                    path=path,
                    entry_kind=SourceEntryKind.REGULAR_FILE,
                    size_bytes=member.size,
                    content=content,
                )
            )
    return blobs


def _zip_archive_blobs(
    archive_path: Path,
    *,
    root: str,
    limits: ArchiveSafetyLimits,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> list[RepositoryBlob]:
    blobs: list[RepositoryBlob] = []
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            _check_stream_cancellation(
                cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
            )
            if info.is_dir():
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode and mode != 0o100000:
                raise BatchResolverError("ARCHIVE_UNSAFE")
            path = _archive_content_path(info.filename, root)
            if info.file_size > limits.max_single_file_bytes:
                raise BatchResolverError("ARCHIVE_TOO_LARGE")
            with archive.open(info, mode="r") as handle:
                content = _read_member_bytes(
                    handle,
                    expected_size=info.file_size,
                    cancel_requested=cancel_requested,
                    deadline=deadline,
                    monotonic=monotonic,
                )
            blobs.append(
                RepositoryBlob(
                    path=path,
                    entry_kind=SourceEntryKind.REGULAR_FILE,
                    size_bytes=info.file_size,
                    content=content,
                )
            )
    return blobs


def _archive_content_path(value: str, root: str) -> str:
    normalized = _validate_archive_path(value)
    parts = PurePosixPath(normalized).parts
    if len(parts) < 2 or parts[0] != root:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    return PurePosixPath(*parts[1:]).as_posix()


def _read_member_bytes(
    handle: object,
    *,
    expected_size: int,
    cancel_requested: Callable[[], bool] | None,
    deadline: float | None,
    monotonic: Callable[[], float],
) -> bytes:
    reader = getattr(handle, "read", None)
    if not callable(reader):
        raise BatchResolverError("ARCHIVE_INVALID")
    chunks: list[bytes] = []
    remaining = expected_size
    while remaining:
        _check_stream_cancellation(
            cancel_requested=cancel_requested, deadline=deadline, monotonic=monotonic
        )
        chunk = reader(min(64 * 1024, remaining))
        if not isinstance(chunk, bytes) or not chunk:
            raise BatchResolverError("ARCHIVE_INVALID")
        chunks.append(chunk)
        remaining -= len(chunk)
    if reader(1):
        raise BatchResolverError("ARCHIVE_INVALID")
    return b"".join(chunks)


def _safe_staging_cleanup(directory: Path, root: Path) -> None:
    root_resolved = root.resolve(strict=False)
    directory_resolved = directory.resolve(strict=False)
    if directory_resolved == root_resolved or root_resolved not in directory_resolved.parents:
        raise BatchResolverError("ARCHIVE_UNSAFE")
    if directory.exists():
        shutil.rmtree(directory)


def _estimate_duration(
    predictions: Sequence[CachePrediction], effective_work_items: int
) -> DurationEstimate:
    # These deliberately conservative internal ranges are an estimate only;
    # callers expose the confidence alongside the range and may later replace
    # the estimator with measured deployment data without altering job state.
    minimum = 2
    maximum = 5
    for prediction in predictions:
        if prediction.validated_analysis_hit:
            minimum += 1
            maximum += 3
        elif prediction.derived_index_hit:
            minimum += 12
            maximum += 35
        else:
            minimum += 25
            maximum += 90
    return DurationEstimate(
        minimum_seconds=max(1, math.ceil(minimum / effective_work_items)),
        maximum_seconds=max(1, math.ceil(maximum / effective_work_items)),
        confidence="low",
    )
