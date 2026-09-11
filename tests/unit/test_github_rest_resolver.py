from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

import reponpc.admin.batch_resolver as resolver_module
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    BatchResolverError,
    CachePrediction,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRateResource,
    GitHubRESTMetadataResolver,
    ProviderReadiness,
    RepositoryMetadataHint,
    RepositorySelection,
    ResolvedRepository,
    UrllibGitHubArchiveTransport,
    UrllibGitHubRESTTransport,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)
RESET = int((NOW + timedelta(hours=1)).timestamp())


class Clock:
    def __init__(self) -> None:
        self.value = NOW

    def __call__(self) -> datetime:
        return self.value


class MemoryCache:
    def __init__(self) -> None:
        self.metadata_rows: dict[str, RepositoryMetadataHint] = {}
        self.resolved_rows: dict[tuple[str, str | None], ResolvedRepository] = {}

    def metadata(self, slug: str) -> RepositoryMetadataHint | None:
        return self.metadata_rows.get(slug)

    def resolved(self, selection: RepositorySelection) -> ResolvedRepository | None:
        return self.resolved_rows.get((selection.slug, selection.ref))

    def save_metadata(self, metadata: RepositoryMetadataHint) -> None:
        self.metadata_rows[metadata.slug] = metadata

    def save_resolved(self, selection: RepositorySelection, repository: ResolvedRepository) -> None:
        self.resolved_rows[(selection.slug, selection.ref)] = repository

    def discard(self, selections) -> None:
        for selection in selections:
            self.metadata_rows.pop(selection.slug, None)
            self.resolved_rows.pop((selection.slug, selection.ref), None)


class FakeTransport:
    def __init__(self, responses: list[GitHubHttpResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(self, *, method: str, url: str, headers, body):
        self.calls.append((method, url, dict(headers), body))
        response_value = self.responses.pop(0)
        if isinstance(response_value, Exception):
            raise response_value
        return response_value


class BudgetTransport:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.remaining = 60
        self.calls: list[str] = []

    def reset(self) -> None:
        self.remaining = 60

    def request(self, *, method: str, url: str, headers, body):
        del method, headers, body
        self.calls.append(url)
        self.remaining -= 1
        slug = url.split("/repos/", 1)[1].split("/commits/", 1)[0]
        payload = (
            {"sha": _sha(slug)}
            if "/commits/" in url
            else {
                "id": slug,
                "private": False,
                "default_branch": "main",
                "archived": False,
            }
        )
        return response(
            payload,
            headers={
                "X-RateLimit-Resource": "core",
                "X-RateLimit-Limit": "60",
                "X-RateLimit-Remaining": str(self.remaining),
                "X-RateLimit-Reset": str(int((self.clock() + timedelta(hours=1)).timestamp())),
            },
        )


def response(payload, status: int = 200, headers=None) -> GitHubHttpResponse:
    return GitHubHttpResponse(status, json.dumps(payload).encode(), headers or {})


def _sha(slug: str) -> str:
    return f"{abs(hash(slug)):040x}"[-40:]


def _repository(slug: str = "owner/repo", sha: str = "a" * 40) -> ResolvedRepository:
    owner, name = slug.split("/")
    return ResolvedRepository(
        slug=slug,
        node_id="node",
        default_branch="main",
        commit_sha=sha,
        is_archived=False,
        archive_url=f"https://api.github.com/repos/{owner}/{name}/tarball/{sha}",
    )


def test_rest_resolves_default_and_explicit_refs_without_authorization() -> None:
    transport = FakeTransport(
        [
            response({"id": 7, "private": False, "default_branch": "main", "archived": False}),
            response({"sha": "a" * 40}),
            response({"id": 8, "private": False, "default_branch": "main", "archived": False}),
            response({"sha": "b" * 40}),
        ]
    )
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=GitHubRateLimiter())

    result = resolver.resolve_all(
        selections=(
            RepositorySelection("owner/one"),
            RepositorySelection("owner/two", ref="v1"),
        )
    )

    assert [item.commit_sha for item in result.repositories] == ["a" * 40, "b" * 40]
    assert transport.calls[1][1].endswith("/commits/main")
    assert transport.calls[3][1].endswith("/commits/v1")
    assert all(
        "authorization" not in {key.casefold() for key in call[2]} for call in transport.calls
    )


@pytest.mark.parametrize("status", [401, 404])
def test_private_missing_and_inaccessible_are_non_disclosing(status: int) -> None:
    resolver = GitHubRESTMetadataResolver(
        transport=FakeTransport([response({}, status=status)]), limiter=GitHubRateLimiter()
    )
    result = resolver.resolve_all(selections=(RepositorySelection("owner/repo"),))
    assert [(item.slug, item.code) for item in result.blockers] == [("owner/repo", "NOT_FOUND")]


@pytest.mark.parametrize(
    ("status", "headers", "payload"),
    [
        (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(RESET)}, {}),
        (403, {"Retry-After": "120"}, {"message": "secondary rate limit"}),
        (403, {}, {"message": "You have exceeded a secondary rate limit."}),
        (429, {}, {}),
    ],
)
def test_primary_and_secondary_limits_are_retryable(status, headers, payload) -> None:
    resolver = GitHubRESTMetadataResolver(
        transport=FakeTransport([response(payload, status=status, headers=headers)]),
        limiter=GitHubRateLimiter(now=lambda: NOW),
    )
    with pytest.raises(BatchResolverError) as raised:
        resolver.resolve_all(selections=(RepositorySelection("owner/repo"),))
    assert raised.value.code == "GITHUB_RATE_LIMITED"
    assert raised.value.retry_after_seconds


@pytest.mark.parametrize(
    ("responses", "code"),
    [
        ([response({}, status=500)], "GITHUB_ERROR"),
        ([GitHubHttpResponse(200, b"not-json", {})], "GITHUB_ERROR"),
        ([BatchResolverError("GITHUB_TIMEOUT")], "GITHUB_TIMEOUT"),
    ],
)
def test_transient_and_malformed_responses_are_not_not_found(responses, code) -> None:
    resolver = GitHubRESTMetadataResolver(
        transport=FakeTransport(responses), limiter=GitHubRateLimiter()
    )
    with pytest.raises(BatchResolverError) as raised:
        resolver.resolve_all(selections=(RepositorySelection("owner/repo"),))
    assert raised.value.code == code


@pytest.mark.parametrize("selection_count", [1, 17, 18, 50])
def test_one_to_fifty_selections_resume_without_repeating_resolved_calls(
    selection_count: int,
) -> None:
    clock = Clock()
    cache = MemoryCache()
    transport = BudgetTransport(clock)
    limiter = GitHubRateLimiter(now=clock)
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=limiter, cache=cache)
    selections = tuple(
        RepositorySelection(f"owner/repo-{index}") for index in range(selection_count)
    )

    for _attempt in range(4):
        try:
            result = resolver.resolve_all(selections=selections)
            break
        except BatchResolverError as error:
            assert error.code == "GITHUB_RATE_LIMITED"
            clock.value += timedelta(hours=1, seconds=1)
            transport.reset()
    else:
        pytest.fail("selection resolution did not make forward progress")

    assert len(result.repositories) == selection_count
    assert len(transport.calls) == selection_count * 2
    assert len(set(transport.calls)) == len(transport.calls)


def test_completed_resolution_does_not_reuse_a_mutable_ref_in_a_new_preflight() -> None:
    cache = MemoryCache()
    transport = FakeTransport(
        [
            response({"id": 7, "private": False, "default_branch": "main", "archived": False}),
            response({"sha": "a" * 40}),
            response({"id": 7, "private": False, "default_branch": "main", "archived": False}),
            response({"sha": "b" * 40}),
        ]
    )
    limiter = GitHubRateLimiter()
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=limiter, cache=cache)
    selection = RepositorySelection("owner/repo")
    planner = BatchPreflightPlanner(
        resolver=resolver,
        limiter=limiter,
        now=lambda: NOW,
    )

    first = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(True, True),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )
    second = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(True, True),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )

    assert first.repositories[0].commit_sha == "a" * 40
    assert second.repositories[0].commit_sha == "b" * 40
    assert len(transport.calls) == 4
    assert cache.resolved_rows == {}


def test_discovery_metadata_reduces_resolution_to_one_commit_request() -> None:
    cache = MemoryCache()
    cache.save_metadata(RepositoryMetadataHint("owner/repo", "node", "main", False))
    transport = FakeTransport([response({"sha": "a" * 40})])
    resolver = GitHubRESTMetadataResolver(
        transport=transport, limiter=GitHubRateLimiter(), cache=cache
    )
    result = resolver.resolve_all(selections=(RepositorySelection("owner/repo"),))
    assert result.repositories[0].commit_sha == "a" * 40
    assert len(transport.calls) == 1
    assert "/commits/main" in transport.calls[0][1]


def test_archive_cache_prediction_controls_immediate_capacity_blocker() -> None:
    limiter = GitHubRateLimiter(now=lambda: NOW)
    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=200,
        headers={"X-RateLimit-Remaining": "25", "X-RateLimit-Reset": str(RESET)},
    )
    cache = MemoryCache()
    selection = RepositorySelection("owner/repo")
    cache.save_resolved(selection, _repository())
    planner = BatchPreflightPlanner(
        resolver=GitHubRESTMetadataResolver(
            transport=FakeTransport([]), limiter=limiter, cache=cache
        ),
        limiter=limiter,
        now=lambda: NOW,
    )

    hit = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(True, True),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )
    cache.save_resolved(selection, _repository())
    miss = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(False, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )
    assert not hit.blockers
    assert [blocker.code for blocker in miss.blockers] == ["GITHUB_RATE_LIMITED"]


class FakeResponse:
    def __init__(self, url: str, body: bytes = b"ok", status: int = 200) -> None:
        self._url, self._body, self.status = url, body, status
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        if not self._body:
            return b""
        body, self._body = self._body[:size], self._body[size:]
        return body

    def close(self) -> None:
        pass


def test_production_rest_transport_strips_authorization_and_bounds_body(monkeypatch) -> None:
    calls = []

    class Opener:
        def open(self, request, timeout):
            del timeout
            calls.append(request)
            return FakeResponse(request.full_url, b"{}")

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: Opener())
    transport = UrllibGitHubRESTTransport(max_response_bytes=10)
    transport.request(
        method="GET",
        url="https://api.github.com/repos/owner/repo",
        headers={"Authorization": "Bearer WRITEBACK_CANARY", "User-Agent": "safe"},
        body=None,
    )
    headers = {key.casefold(): value for key, value in calls[0].header_items()}
    assert "authorization" not in headers
    assert "WRITEBACK_CANARY" not in repr(calls[0].header_items())


def test_production_rest_transport_classifies_timeout_and_oversize(monkeypatch) -> None:
    class TimeoutOpener:
        def open(self, request, timeout):
            del request, timeout
            raise TimeoutError

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: TimeoutOpener())
    with pytest.raises(BatchResolverError) as timeout:
        UrllibGitHubRESTTransport().request(
            method="GET", url="https://api.github.com/repos/o/r", headers={}, body=None
        )
    assert timeout.value.code == "GITHUB_TIMEOUT"

    class OversizeOpener:
        def open(self, request, timeout):
            del timeout
            return FakeResponse(request.full_url, b"12345")

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: OversizeOpener())
    with pytest.raises(BatchResolverError) as oversize:
        UrllibGitHubRESTTransport(max_response_bytes=4).request(
            method="GET", url="https://api.github.com/repos/o/r", headers={}, body=None
        )
    assert oversize.value.code == "GITHUB_ERROR"


def _redirect_error(url: str, location: str, extra_headers=None) -> HTTPError:
    headers = Message()
    headers["Location"] = location
    for key, value in (extra_headers or {}).items():
        headers[key] = value
    return HTTPError(url, 302, "redirect", headers, None)


def test_production_archive_transport_binds_redirect_and_sends_no_authorization(
    monkeypatch,
) -> None:
    repository = _repository()
    redirect = f"https://codeload.github.com/owner/repo/legacy.tar.gz/{repository.commit_sha}"
    calls = []

    class Opener:
        def open(self, request, timeout):
            del timeout
            calls.append(request)
            if len(calls) == 1:
                raise _redirect_error(request.full_url, redirect)
            return FakeResponse(redirect, b"archive")

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: Opener())
    chunks = list(
        UrllibGitHubArchiveTransport().stream(
            archive_url=repository.archive_url,
            repository=repository,
            limiter=GitHubRateLimiter(),
        )
    )
    assert b"".join(chunks) == b"archive"
    assert all(
        "authorization" not in {key.casefold() for key, _value in request.header_items()}
        for request in calls
    )


def test_production_archive_transport_observes_api_redirect_rate_headers(monkeypatch) -> None:
    repository = _repository()
    redirect = f"https://codeload.github.com/owner/repo/legacy.tar.gz/{repository.commit_sha}"
    calls = []

    class Opener:
        def open(self, request, timeout):
            del timeout
            calls.append(request)
            if len(calls) == 1:
                raise _redirect_error(
                    request.full_url,
                    redirect,
                    {
                        "X-RateLimit-Resource": "core",
                        "X-RateLimit-Limit": "60",
                        "X-RateLimit-Remaining": "24",
                        "X-RateLimit-Reset": str(RESET),
                    },
                )
            return FakeResponse(redirect, b"archive")

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: Opener())
    limiter = GitHubRateLimiter(now=lambda: NOW)
    chunks = list(
        UrllibGitHubArchiveTransport().stream(
            archive_url=repository.archive_url,
            repository=repository,
            limiter=limiter,
        )
    )

    assert b"".join(chunks) == b"archive"
    budget, _secondary = limiter.snapshot()
    assert budget.remaining == 24
    assert limiter.admit(GitHubRateResource.CORE).allowed is False


def test_production_archive_transport_classifies_bare_secondary_limit(monkeypatch) -> None:
    repository = _repository()
    body = BytesIO(json.dumps({"message": "You have exceeded a secondary rate limit."}).encode())

    class Opener:
        def open(self, request, timeout):
            del timeout
            raise HTTPError(request.full_url, 403, "forbidden", Message(), body)

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: Opener())
    limiter = GitHubRateLimiter(now=lambda: NOW)

    with pytest.raises(BatchResolverError) as raised:
        list(
            UrllibGitHubArchiveTransport().stream(
                archive_url=repository.archive_url,
                repository=repository,
                limiter=limiter,
            )
        )

    assert raised.value.code == "GITHUB_RATE_LIMITED"
    assert raised.value.retry_after_seconds == 60


@pytest.mark.parametrize(
    "redirect",
    [
        "https://codeload.github.com/other/repo/legacy.tar.gz/" + "a" * 40,
        "https://codeload.github.com/owner/other/legacy.tar.gz/" + "a" * 40,
        "https://codeload.github.com/owner/repo/legacy.tar.gz/" + "b" * 40,
        "https://codeload.github.com/owner/repo/tar.gz/" + "a" * 40,
        "https://evil.example/owner/repo/legacy.tar.gz/" + "a" * 40,
        "https://user@codeload.github.com/owner/repo/legacy.tar.gz/" + "a" * 40,
        "https://codeload.github.com/owner/repo/legacy.tar.gz/" + "a" * 40 + "?x=1",
        "https://codeload.github.com/owner/repo/legacy.tar.gz/" + "a" * 40 + "#x",
    ],
)
def test_production_archive_transport_rejects_mismatched_redirects(
    monkeypatch, redirect: str
) -> None:
    repository = _repository()

    class Opener:
        def open(self, request, timeout):
            del timeout
            raise _redirect_error(request.full_url, redirect)

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: Opener())
    with pytest.raises(BatchResolverError) as raised:
        list(
            UrllibGitHubArchiveTransport().stream(
                archive_url=repository.archive_url,
                repository=repository,
                limiter=GitHubRateLimiter(),
            )
        )
    assert raised.value.code == "ARCHIVE_UNSAFE"


def test_production_archive_transport_rejects_second_redirect_and_final_mismatch(
    monkeypatch,
) -> None:
    repository = _repository()
    expected = f"https://codeload.github.com/owner/repo/legacy.tar.gz/{repository.commit_sha}"

    class SecondRedirectOpener:
        def open(self, request, timeout):
            del timeout
            raise _redirect_error(request.full_url, expected)

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: SecondRedirectOpener())
    with pytest.raises(BatchResolverError) as second:
        list(
            UrllibGitHubArchiveTransport().stream(
                archive_url=repository.archive_url,
                repository=repository,
                limiter=GitHubRateLimiter(),
            )
        )
    assert second.value.code == "ARCHIVE_UNSAFE"

    class FinalMismatchOpener:
        calls = 0

        def open(self, request, timeout):
            del timeout
            self.calls += 1
            if self.calls == 1:
                raise _redirect_error(request.full_url, expected)
            return FakeResponse("https://codeload.github.com/owner/other/legacy.tar.gz/" + "a" * 40)

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: FinalMismatchOpener())
    with pytest.raises(BatchResolverError) as mismatch:
        list(
            UrllibGitHubArchiveTransport().stream(
                archive_url=repository.archive_url,
                repository=repository,
                limiter=GitHubRateLimiter(),
            )
        )
    assert mismatch.value.code == "ARCHIVE_UNSAFE"
