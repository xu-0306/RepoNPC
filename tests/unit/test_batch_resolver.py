"""Focused security and contract coverage for the Milestone D resolver leaf."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from reponpc.admin.batch_resolver import (
    ArchiveSafetyLimits,
    BatchCapacity,
    BatchPreflightPlanner,
    BatchResolverError,
    CachePrediction,
    CredentialPurpose,
    GitHubArchiveSource,
    GitHubGraphQLMetadataResolver,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRateResource,
    ProviderReadiness,
    PublicReadCredential,
    RepositorySelection,
    ResolutionBlocker,
    ResolvedRepository,
    UrllibGitHubGraphQLTransport,
    cleanup_staged_archive,
    inspect_archive,
    select_public_read_credential,
    selection_hash_for,
    stage_archive_stream,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class RecordingTransport:
    def __init__(self, response: GitHubHttpResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def request(self, **values: object) -> GitHubHttpResponse:
        self.calls.append(values)
        return self.response


class _Response:
    def __init__(self, *, payload: bytes, url: str = "https://api.github.com/graphql") -> None:
        self.status = 200
        self.headers = {"X-RateLimit-Remaining": "4999"}
        self._payload = payload
        self._url = url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_values: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def read(self, _size: int) -> bytes:
        return self._payload


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response

    def open(self, _request: object, *, timeout: float) -> _Response:
        assert timeout == 20.0
        return self.response


def _credential(
    *,
    credential_id: int = 1,
    purpose: CredentialPurpose = CredentialPurpose.IDENTITY_PUBLIC_READ,
    status: str = "ready",
) -> PublicReadCredential:
    return PublicReadCredential(
        credential_id=credential_id,
        purpose=purpose,
        status=status,
        token="resolver-canary-token",
        github_login="octocat",
    )


def _response(
    *, status: int = 200, body: object | None = None, headers: dict[str, str] | None = None
):
    return GitHubHttpResponse(
        status=status,
        body=json.dumps(body if body is not None else {"data": {}}).encode(),
        headers=headers or {"X-RateLimit-Resource": "graphql", "X-RateLimit-Remaining": "4999"},
    )


def _resolver(
    transport: RecordingTransport,
    limiter: GitHubRateLimiter | None = None,
    *,
    allow_archived: bool = False,
):
    selected_limiter = limiter or GitHubRateLimiter(safety_reserve=5, now=lambda: NOW)
    return GitHubGraphQLMetadataResolver(
        transport=transport,
        limiter=selected_limiter,
        allow_archived=allow_archived,
    ), selected_limiter


def test_credential_selection_prefers_oauth_and_never_uses_writeback() -> None:
    oauth = _credential(credential_id=4)
    pat = _credential(credential_id=2, purpose=CredentialPurpose.PUBLIC_READ)
    writeback = _credential(credential_id=1, purpose=CredentialPurpose.WRITEBACK)

    selected, public = select_public_read_credential((writeback, pat, oauth))

    assert selected is oauth
    assert public.credential_id == 4
    assert public.purpose is CredentialPurpose.IDENTITY_PUBLIC_READ
    assert "resolver-canary-token" not in repr(selected)


def test_urllib_graphql_transport_enforces_fixed_endpoint_and_response_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import reponpc.admin.batch_resolver as resolver_module

    opener = _Opener(_Response(payload=b"{}"))
    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: opener)
    transport = UrllibGitHubGraphQLTransport()

    response = transport.request(
        method="POST",
        url="https://api.github.com/graphql",
        headers={},
        body=b"{}",
    )

    assert response.body == b"{}"
    with pytest.raises(ValueError):
        transport.request(method="POST", url="https://example.test/graphql", headers={}, body=b"{}")

    oversized = _Opener(_Response(payload=b"x" * (1024 * 1024 + 1)))
    monkeypatch.setattr(resolver_module, "build_opener", lambda *_handlers: oversized)
    with pytest.raises(BatchResolverError) as error:
        transport.request(
            method="POST",
            url="https://api.github.com/graphql",
            headers={},
            body=b"{}",
        )
    assert error.value.code == "GITHUB_ERROR"


def test_credential_selection_fails_closed_without_public_read_connection() -> None:
    with pytest.raises(BatchResolverError) as error:
        select_public_read_credential((_credential(purpose=CredentialPurpose.WRITEBACK),))

    assert error.value.code == "GITHUB_CONNECTION_REQUIRED"


def test_archive_source_rebuilds_only_safe_regular_files_and_cleans_staging(tmp_path: Path) -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as handle:
        payload = b"# Demo\n"
        entry = tarfile.TarInfo("demo-sha/README.md")
        entry.size = len(payload)
        handle.addfile(entry, io.BytesIO(payload))

    class StaticArchiveTransport:
        def stream(self, **_values: object):
            yield archive.getvalue()

    source = GitHubArchiveSource(
        transport=StaticArchiveTransport(),  # type: ignore[arg-type]
        limiter=GitHubRateLimiter(now=lambda: NOW),
        staging_root=tmp_path / "archives",
        limits=ArchiveSafetyLimits(
            max_compressed_bytes=1024 * 1024,
            max_uncompressed_bytes=1024 * 1024,
            max_entries=10,
            max_single_file_bytes=1024,
        ),
    )
    resolved = source.fetch(
        repository=ResolvedRepository(
            slug="octocat/demo",
            node_id="R_demo",
            default_branch="main",
            commit_sha=SHA_A,
            is_archived=False,
            archive_url=f"https://api.github.com/repos/octocat/demo/tarball/{SHA_A}",
        ),
        credential=_credential(),
    )

    assert resolved.commit_sha == SHA_A
    assert [(blob.path, blob.content) for blob in resolved.blobs] == [("README.md", b"# Demo\n")]
    assert list((tmp_path / "archives").iterdir()) == []


def test_metadata_query_uses_variables_and_resolves_default_branch_head_exact_sha() -> None:
    body = {
        "data": {
            "repo0": {
                "id": "R_1",
                "nameWithOwner": "octocat/demo",
                "isPrivate": False,
                "isArchived": False,
                "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
            }
        }
    }
    transport = RecordingTransport(_response(body=body))
    resolver, _limiter = _resolver(transport)

    result = resolver.resolve_page(
        selections=(RepositorySelection("octocat/demo"),), credential=_credential()
    )

    assert result.blockers == ()
    assert result.repositories[0].commit_sha == SHA_A
    assert result.repositories[0].archive_url.endswith(f"/tarball/{SHA_A}")
    request = transport.calls[0]
    request_body = request["body"]
    assert isinstance(request_body, bytes)
    payload = json.loads(request_body.decode())
    assert "octocat" not in payload["query"]
    assert payload["variables"]["owner0"] == "octocat"
    assert request["headers"] and "resolver-canary-token" in str(request["headers"])


def test_metadata_resolution_uses_tag_target_for_explicit_ref_and_blocks_private() -> None:
    body = {
        "data": {
            "repo0": {
                "id": "R_1",
                "nameWithOwner": "octocat/demo",
                "isPrivate": False,
                "isArchived": True,
                "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
                "object": {"target": {"oid": SHA_B}},
            },
            "repo1": {
                "id": "R_2",
                "nameWithOwner": "octocat/private",
                "isPrivate": True,
                "isArchived": False,
                "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
            },
        }
    }
    transport = RecordingTransport(_response(body=body))
    resolver, _limiter = _resolver(transport, allow_archived=True)

    result = resolver.resolve_page(
        selections=(
            RepositorySelection("octocat/demo", ref="v1.0.0"),
            RepositorySelection("octocat/private"),
        ),
        credential=_credential(),
    )

    assert [(item.slug, item.commit_sha, item.is_archived) for item in result.repositories] == [
        ("octocat/demo", SHA_B, True)
    ]
    assert result.blockers[0].code == "NOT_FOUND"


def test_archived_repository_is_blocked_by_default_and_never_enters_preflight() -> None:
    body = {
        "data": {
            "repo0": {
                "id": "R_1",
                "nameWithOwner": "octocat/archive",
                "isPrivate": False,
                "isArchived": True,
                "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
            }
        }
    }
    transport = RecordingTransport(_response(body=body))
    resolver, limiter = _resolver(transport)
    planner = BatchPreflightPlanner(
        resolver=resolver,
        limiter=limiter,
        now=lambda: NOW,
        plan_id_factory=lambda: "safe-plan-id",
    )

    plan = planner.create(
        selections=(RepositorySelection("octocat/archive"),),
        credentials=(_credential(),),
        cache_prediction=lambda _repository: CachePrediction(False, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )

    assert plan.repositories == ()
    assert plan.blockers == (ResolutionBlocker("octocat/archive", "ARCHIVED_NOT_ALLOWED"),)
    assert plan.duration is None


def test_unauthorized_selected_credential_requires_reconnection_without_pat_retry() -> None:
    transport = RecordingTransport(_response(status=401))
    resolver, _limiter = _resolver(transport)

    with pytest.raises(BatchResolverError) as error:
        resolver.resolve_page(
            selections=(RepositorySelection("octocat/demo"),),
            credential=_credential(credential_id=77),
        )

    assert error.value.code == "GITHUB_CONNECTION_REQUIRED"
    assert error.value.credential_id == 77
    assert len(transport.calls) == 1


def test_metadata_resolution_deduplicates_same_repository_at_same_exact_commit() -> None:
    metadata = {
        "id": "R_1",
        "nameWithOwner": "octocat/demo",
        "isPrivate": False,
        "isArchived": False,
        "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
    }
    transport = RecordingTransport(_response(body={"data": {"repo0": metadata, "repo1": metadata}}))
    resolver, _limiter = _resolver(transport)

    result = resolver.resolve_page(
        selections=(RepositorySelection("octocat/demo"), RepositorySelection("octocat/demo")),
        credential=_credential(),
    )

    assert len(result.repositories) == 1
    assert result.repositories[0].commit_sha == SHA_A


def test_resolver_refuses_unconfirmed_selection_without_contacting_github() -> None:
    transport = RecordingTransport(_response())
    resolver, _limiter = _resolver(transport)

    with pytest.raises(ValueError, match="unconfirmed"):
        resolver.resolve_page(
            selections=(RepositorySelection("octocat/demo", confirmed=False),),
            credential=_credential(),
        )

    assert transport.calls == []


def test_metadata_resolution_fails_closed_on_malformed_visibility_flag() -> None:
    transport = RecordingTransport(
        _response(
            body={
                "data": {
                    "repo0": {
                        "id": "R_1",
                        "nameWithOwner": "octocat/demo",
                        "isPrivate": "false",
                        "isArchived": False,
                        "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
                    }
                }
            }
        )
    )
    resolver, _limiter = _resolver(transport)

    result = resolver.resolve_page(
        selections=(RepositorySelection("octocat/demo"),), credential=_credential()
    )

    assert result.repositories == ()
    assert result.blockers == (ResolutionBlocker("octocat/demo", "GITHUB_ERROR"),)


def test_rate_limiter_keeps_primary_budgets_separate_and_shares_secondary_pause() -> None:
    limiter = GitHubRateLimiter(safety_reserve=10, now=lambda: NOW)
    limiter.observe(
        resource=GitHubRateResource.GRAPHQL,
        status=200,
        headers={
            "X-RateLimit-Resource": "graphql",
            "X-RateLimit-Remaining": "10",
            "X-RateLimit-Reset": str(int((NOW + timedelta(seconds=90)).timestamp())),
        },
    )
    assert limiter.admit(GitHubRateResource.GRAPHQL).allowed is False
    assert limiter.admit(GitHubRateResource.CORE).allowed is True

    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=429,
        headers={"Retry-After": "120", "X-RateLimit-Resource": "core"},
    )
    graph = limiter.admit(GitHubRateResource.GRAPHQL)
    core = limiter.admit(GitHubRateResource.CORE)
    assert graph.allowed is False and graph.reason == "secondary"
    assert core.allowed is False and core.retry_after_seconds == 120


def test_rate_limiter_understands_http_date_retry_after() -> None:
    limiter = GitHubRateLimiter(now=lambda: NOW)
    limiter.observe(
        resource=GitHubRateResource.GRAPHQL,
        status=403,
        headers={"Retry-After": "Sat, 16 Aug 2026 12:01:00 GMT"},
    )

    admission = limiter.admit(GitHubRateResource.CORE)

    assert admission.allowed is False
    assert admission.retry_after_seconds == 60


def test_rate_limiter_merges_out_of_order_responses_conservatively_within_reset_window() -> None:
    reset_at = NOW + timedelta(seconds=90)
    limiter = GitHubRateLimiter(safety_reserve=5, now=lambda: NOW)

    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=200,
        observed_at=NOW + timedelta(seconds=10),
        headers={
            "X-RateLimit-Resource": "core",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "7",
            "X-RateLimit-Reset": str(int(reset_at.timestamp())),
        },
    )
    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=200,
        observed_at=NOW + timedelta(seconds=20),
        headers={
            "X-RateLimit-Resource": "core",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "42",
            "X-RateLimit-Reset": str(int(reset_at.timestamp())),
        },
    )

    _graphql, core, _secondary = limiter.snapshot()
    assert core.remaining == 7
    assert core.reset_at == reset_at


@pytest.mark.parametrize(
    ("kwargs", "expected_code"),
    [
        ({"cancel_requested": lambda: True}, "CANCELLED"),
        ({"deadline": 10.0, "monotonic": lambda: 10.0}, "GITHUB_TIMEOUT"),
    ],
)
def test_archive_inspection_stops_on_cancellation_or_deadline(
    tmp_path: Path,
    kwargs: dict[str, object],
    expected_code: str,
) -> None:
    source = tmp_path / "many-entries.tar.gz"
    _write_tar(
        source,
        [(f"repo/file-{index}.txt", b"safe", None) for index in range(3)],
    )

    with pytest.raises(BatchResolverError) as error:
        inspect_archive(source, limits=_limits(), **kwargs)

    assert error.value.code == expected_code


def _limits() -> ArchiveSafetyLimits:
    return ArchiveSafetyLimits(
        max_compressed_bytes=4096, max_uncompressed_bytes=4096, max_entries=3
    )


def _write_tar(path: Path, entries: list[tuple[str, bytes, str | None]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, content, linkname in entries:
            info = tarfile.TarInfo(name)
            if linkname is not None:
                info.type = tarfile.SYMTYPE
                info.linkname = linkname
                archive.addfile(info)
            else:
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))


def test_archive_stream_and_inspection_accept_safe_regular_tar(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    _write_tar(source, [("repo-a/README.md", b"safe", None)])

    staged = stage_archive_stream(
        (source.read_bytes(),), staging_root=tmp_path / "staging", limits=_limits()
    )
    inspection = inspect_archive(staged.archive_path, limits=_limits())

    assert inspection.paths == ("repo-a/README.md",)
    assert inspection.uncompressed_bytes == 4
    cleanup_staged_archive(staged, staging_root=tmp_path / "staging")
    assert not staged.directory.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "repo\\windows.txt"])
def test_archive_inspection_rejects_traversal_absolute_and_backslash_paths(
    tmp_path: Path, name: str
) -> None:
    source = tmp_path / "unsafe.tar.gz"
    _write_tar(source, [(name, b"unsafe", None)])

    with pytest.raises(BatchResolverError) as error:
        inspect_archive(source, limits=_limits())

    assert error.value.code == "ARCHIVE_UNSAFE"


def test_archive_inspection_rejects_symlink_and_zip_bomb_budget(tmp_path: Path) -> None:
    symlink = tmp_path / "symlink.tar.gz"
    _write_tar(symlink, [("repo/link", b"", "../../etc/passwd")])
    with pytest.raises(BatchResolverError) as error:
        inspect_archive(symlink, limits=_limits())
    assert error.value.code == "ARCHIVE_UNSAFE"

    archive = tmp_path / "large.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("repo/large.txt", b"x" * 4097)
    with pytest.raises(BatchResolverError) as error:
        inspect_archive(archive, limits=_limits())
    assert error.value.code == "ARCHIVE_TOO_LARGE"


def test_cancelled_archive_stream_cleans_its_unique_directory(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    with pytest.raises(BatchResolverError) as error:
        stage_archive_stream(
            (b"part-one", b"part-two"),
            staging_root=root,
            limits=_limits(),
            cancel_requested=lambda: True,
        )

    assert error.value.code == "CANCELLED"
    assert root.exists()
    assert list(root.iterdir()) == []


def test_preflight_binds_selection_hash_and_reports_cache_capacity_duration() -> None:
    body = {
        "data": {
            "repo0": {
                "id": "R_1",
                "nameWithOwner": "octocat/demo",
                "isPrivate": False,
                "isArchived": False,
                "defaultBranchRef": {"name": "main", "target": {"oid": SHA_A}},
            }
        }
    }
    transport = RecordingTransport(_response(body=body))
    resolver, limiter = _resolver(transport)
    planner = BatchPreflightPlanner(
        resolver=resolver,
        limiter=limiter,
        now=lambda: NOW,
        plan_id_factory=lambda: "safe-plan-id",
    )
    selection = RepositorySelection("octocat/demo", include=("src/**",))

    plan = planner.create(
        selections=(selection,),
        credentials=(_credential(),),
        cache_prediction=lambda _repository: CachePrediction(True, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 2, 1, 4),
    )

    assert plan.plan_id == "safe-plan-id"
    assert plan.selection_hash == selection_hash_for((selection,))
    assert plan.selected_credential and plan.selected_credential.purpose == "identity_public_read"
    assert plan.maximum_generation_attempts == 1
    assert plan.duration and plan.duration.confidence == "low"
    assert plan.warnings == ()
    assert "resolver-canary-token" not in repr(plan)


def test_preflight_does_not_contact_github_for_unconfirmed_selection() -> None:
    transport = RecordingTransport(_response())
    resolver, limiter = _resolver(transport)
    planner = BatchPreflightPlanner(resolver=resolver, limiter=limiter, now=lambda: NOW)

    plan = planner.create(
        selections=(RepositorySelection("octocat/demo", confirmed=False),),
        credentials=(_credential(),),
        cache_prediction=lambda _repository: CachePrediction(False, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )

    assert transport.calls == []
    assert plan.blockers == (ResolutionBlocker("octocat/demo", "CONFIRMATION_REQUIRED"),)
    assert plan.duration is None
