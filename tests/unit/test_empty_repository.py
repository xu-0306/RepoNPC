"""Empty GitHub projects are permanent, body-free failures at every source boundary."""

from __future__ import annotations

import json
import time
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest
from starlette.requests import Request

import reponpc.admin.batch_resolver as resolver_module
import reponpc.indexing.github as github_module
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    BatchResolverError,
    CachePrediction,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
    ProviderReadiness,
    RepositoryMetadataHint,
    RepositorySelection,
    UrllibGitHubArchiveTransport,
)
from reponpc.admin.batch_runtime import BatchRuntimeError
from reponpc.admin.batches import BatchExecutionError, BatchPreflightInput
from reponpc.admin.embedding_profiles import EmbeddingProfileError
from reponpc.admin.onboarding import GuidedOnboardingError, _github_error
from reponpc.api.admin import _batch_error, _embedding_profile_error, _onboarding_error
from reponpc.indexing.github import GitHubSourceResolver, SourceResolutionError
from tests.unit.test_batches import _selection, _service
from tests.unit.test_github_rest_resolver import FakeTransport, MemoryCache, _repository, response

METADATA = {"id": 7, "private": False, "default_branch": "main", "archived": False}


@pytest.mark.parametrize("ref", [None, "release"])
@pytest.mark.parametrize(
    "message", ["Git Repository is empty.", " \nGIT repository IS EMPTY: no commits. "]
)
def test_empty_repository_commit_is_a_permanent_blocker(ref: str | None, message: str) -> None:
    transport = FakeTransport([response(METADATA), response({"message": message}, status=409)])
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=GitHubRateLimiter())
    result = resolver.resolve_all(selections=(RepositorySelection("owner/empty", ref=ref),))
    assert result.repositories == ()
    assert [(item.slug, item.code, item.retry_after_seconds) for item in result.blockers] == [
        ("owner/empty", "EMPTY_REPOSITORY", None)
    ]
    assert len(transport.calls) == 2
    assert transport.calls[-1][1].endswith(f"/commits/{ref or 'main'}")


def test_empty_metadata_blocker_preserves_other_selected_repositories() -> None:
    transport = FakeTransport(
        [
            response({"message": "Git Repository is empty."}, status=409),
            response(METADATA),
            response({"sha": "a" * 40}),
        ]
    )
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=GitHubRateLimiter())
    result = resolver.resolve_all(
        selections=(RepositorySelection("owner/empty"), RepositorySelection("owner/populated"))
    )
    assert [(item.slug, item.code) for item in result.blockers] == [
        ("owner/empty", "EMPTY_REPOSITORY")
    ]
    assert [item.slug for item in result.repositories] == ["owner/populated"]
    assert len(transport.calls) == 3


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (409, b'{"message":"Conflict"}', "GITHUB_ERROR"),
        (409, b"not-json", "GITHUB_ERROR"),
        (409, b"", "GITHUB_ERROR"),
        (409, b"[" * 10000, "GITHUB_ERROR"),
        (409, b'{"message":' + b"9" * 10000 + b"}", "GITHUB_ERROR"),
        (409, b"\xff", "GITHUB_ERROR"),
        (409, b"[]", "GITHUB_ERROR"),
        (409, b'{"message":42}', "GITHUB_ERROR"),
        (409, b"{}", "GITHUB_ERROR"),
        (404, b'{"message":"Git Repository is empty."}', "NOT_FOUND"),
        (500, b'{"message":"Git Repository is empty."}', "GITHUB_ERROR"),
    ],
)
def test_other_commit_failures_keep_their_existing_codes(
    status: int, body: bytes, code: str
) -> None:
    transport = FakeTransport([response(METADATA), GitHubHttpResponse(status, body, {})])
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=GitHubRateLimiter())
    if code == "NOT_FOUND":
        result = resolver.resolve_all(selections=(RepositorySelection("another/project"),))
        assert [(item.slug, item.code) for item in result.blockers] == [("another/project", code)]
    else:
        with pytest.raises(BatchResolverError) as raised:
            resolver.resolve_all(selections=(RepositorySelection("another/project"),))
        assert raised.value.code == code
    assert len(transport.calls) == 2


def test_empty_repository_preflight_consumes_partial_hints_without_retry() -> None:
    selection = RepositorySelection("another/empty")
    cache = MemoryCache()
    cache.save_metadata(RepositoryMetadataHint(selection.slug, "node", "main", False))
    transport = FakeTransport([response({"message": "Git Repository is empty."}, status=409)])
    limiter = GitHubRateLimiter()
    planner = BatchPreflightPlanner(
        resolver=GitHubRESTMetadataResolver(transport=transport, limiter=limiter, cache=cache),
        limiter=limiter,
    )
    plan = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(False, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )
    assert [(item.slug, item.code, item.retry_after_seconds) for item in plan.blockers] == [
        (selection.slug, "EMPTY_REPOSITORY", None)
    ]
    assert plan.duration is None
    assert len(transport.calls) == 1
    assert cache.metadata_rows == {}


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (b'{"message":"Git Repository is empty."}', "EMPTY_REPOSITORY"),
        (b"not-json", "GITHUB_ERROR"),
    ],
)
def test_archive_and_source_resolvers_classify_the_same_conflict(
    monkeypatch: pytest.MonkeyPatch, body: bytes, code: str
) -> None:
    calls = []

    class Opener:
        def open(self, request, **_kwargs):
            calls.append(request.full_url)
            assert not request.has_header("Authorization")
            raise HTTPError(request.full_url, 409, "Conflict", Message(), BytesIO(body))

    monkeypatch.setattr(resolver_module, "build_opener", lambda *_args: Opener())
    with pytest.raises(BatchResolverError) as archive_error:
        list(
            UrllibGitHubArchiveTransport().stream(
                archive_url=_repository().archive_url,
                repository=_repository(),
                limiter=GitHubRateLimiter(),
            )
        )
    assert archive_error.value.code == code
    monkeypatch.setattr(github_module, "build_opener", lambda *_args: Opener())
    with pytest.raises(SourceResolutionError) as source_error:
        GitHubSourceResolver()._get_json("/repos/another/empty/commits/main")
    assert _github_error(source_error.value).code == code
    assert len(calls) == 2


@pytest.mark.parametrize(
    ("mapper", "error"),
    [
        (_onboarding_error, GuidedOnboardingError("EMPTY_REPOSITORY")),
        (_embedding_profile_error, EmbeddingProfileError("EMPTY_REPOSITORY")),
        (_batch_error, BatchResolverError("EMPTY_REPOSITORY")),
    ],
)
def test_empty_repository_admin_envelopes_are_422_without_retry(mapper, error) -> None:
    request = Request({"type": "http", "headers": [], "state": {"request_id": "empty-fixture"}})
    result = mapper(request, error)
    assert result.status_code == 422
    payload = json.loads(result.body)["error"]
    assert payload["code"] == "EMPTY_REPOSITORY"
    assert payload.get("retry_after_seconds") is None
    assert "retry-after" not in result.headers


def test_empty_repository_batch_failure_is_terminal_without_automatic_retry(tmp_path: Path) -> None:
    calls = []

    def runner(item, _cancelled):
        calls.append(item.item_id)
        raise BatchExecutionError("EMPTY_REPOSITORY")

    service = _service(tmp_path, runner=runner)
    plan = service.preflight(BatchPreflightInput((_selection(),)))
    batch, _created = service.create(
        plan_id=plan.plan_id, selections=(_selection(),), idempotency_key="empty-fixture-key"
    )
    deadline = time.monotonic() + 3
    snapshot = service.get(batch.batch_id)
    while time.monotonic() < deadline and snapshot.state in {"queued", "running"}:
        time.sleep(0.01)
        snapshot = service.get(batch.batch_id)
    assert snapshot.state == "failed"
    assert snapshot.items[0].state == "failed"
    assert snapshot.items[0].error_code == "EMPTY_REPOSITORY"
    assert snapshot.items[0].retry_at is None
    assert snapshot.items[0].retryable is False
    assert snapshot.items[0].reanalyzable is False
    with pytest.raises(BatchRuntimeError) as retry:
        service._store.retry_items(batch.batch_id)
    assert retry.value.code == "ANALYSIS_RETRY_NOT_AVAILABLE"
    with pytest.raises(BatchRuntimeError) as reanalyze:
        service._store.reanalysis_source(batch.batch_id, item_ids=(snapshot.items[0].item_id,))
    assert reanalyze.value.code == "ANALYSIS_REANALYZE_NOT_AVAILABLE"
    assert len(calls) == 1
