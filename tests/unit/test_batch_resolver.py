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
    GitHubArchiveSource,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRateResource,
    GitHubRESTMetadataResolver,
    ProviderReadiness,
    RepositorySelection,
    ResolutionBlocker,
    ResolvedRepository,
    cleanup_staged_archive,
    inspect_archive,
    selection_hash_for,
    stage_archive_stream,
)

SHA_A = "a" * 40
NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class RecordingRESTTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(self, **values: object) -> GitHubHttpResponse:
        self.calls.append(values)
        url = str(values["url"])
        payload = (
            {"sha": SHA_A}
            if "/commits/" in url
            else {"id": "R_1", "private": False, "archived": False, "default_branch": "main"}
        )
        return GitHubHttpResponse(
            200,
            json.dumps(payload).encode(),
            {"X-RateLimit-Resource": "core", "X-RateLimit-Remaining": "60"},
        )


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
    )

    assert resolved.commit_sha == SHA_A
    assert [(blob.path, blob.content) for blob in resolved.blobs] == [("README.md", b"# Demo\n")]
    assert list((tmp_path / "archives").iterdir()) == []


def test_rate_limiter_applies_secondary_pause_to_core_requests() -> None:
    limiter = GitHubRateLimiter(safety_reserve=10, now=lambda: NOW)
    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=429,
        headers={"Retry-After": "120", "X-RateLimit-Resource": "core"},
    )
    core = limiter.admit(GitHubRateResource.CORE)
    assert core.allowed is False
    assert core.reason == "secondary"
    assert core.retry_after_seconds == 120


def test_rate_limiter_understands_http_date_retry_after() -> None:
    limiter = GitHubRateLimiter(now=lambda: NOW)
    limiter.observe(
        resource=GitHubRateResource.CORE,
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

    core, _secondary = limiter.snapshot()
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
    transport = RecordingRESTTransport()
    limiter = GitHubRateLimiter(safety_reserve=5, now=lambda: NOW)
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=limiter)
    planner = BatchPreflightPlanner(
        resolver=resolver,
        limiter=limiter,
        now=lambda: NOW,
        plan_id_factory=lambda: "safe-plan-id",
    )
    selection = RepositorySelection("octocat/demo", include=("src/**",))

    plan = planner.create(
        selections=(selection,),
        cache_prediction=lambda _repository: CachePrediction(True, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 2, 1, 4),
    )

    assert plan.plan_id == "safe-plan-id"
    assert plan.selection_hash == selection_hash_for((selection,))
    assert plan.maximum_generation_attempts == 1
    assert plan.duration and plan.duration.confidence == "low"
    assert plan.warnings == ("ANONYMOUS_ARCHIVE_REQUESTS:0",)
    assert all(
        "authorization" not in {str(key).casefold() for key in call["headers"]}
        for call in transport.calls
    )


def test_preflight_does_not_contact_github_for_unconfirmed_selection() -> None:
    transport = RecordingRESTTransport()
    limiter = GitHubRateLimiter(safety_reserve=5, now=lambda: NOW)
    resolver = GitHubRESTMetadataResolver(transport=transport, limiter=limiter)
    planner = BatchPreflightPlanner(resolver=resolver, limiter=limiter, now=lambda: NOW)

    plan = planner.create(
        selections=(RepositorySelection("octocat/demo", confirmed=False),),
        cache_prediction=lambda _repository: CachePrediction(False, False),
        provider=ProviderReadiness(True),
        capacity=BatchCapacity(1, 1, 1, 1, 1),
    )

    assert transport.calls == []
    assert plan.blockers == (ResolutionBlocker("octocat/demo", "CONFIRMATION_REQUIRED"),)
    assert plan.duration is None
