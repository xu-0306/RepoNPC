"""Concrete GitHub REST publication adapter tests at the mutation boundary."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml

from reponpc.indexing.github_publication import (
    GitHubHttpResponse,
    GitHubReleasePublisher,
)
from reponpc.indexing.publication import PublicationCoordinator, PublicationError
from tests.integration.test_bundle_producer_consumer import _bundle


def test_index_build_workflow_enforces_immutable_publication_order() -> None:
    workflow_path = Path(".github/workflows/build-index.yml")
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)

    assert isinstance(workflow, dict)
    assert workflow["permissions"] == {"contents": "write"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert set(triggers) == {"workflow_dispatch", "push"}
    push = triggers["push"]
    assert isinstance(push, dict)
    assert push["paths"] == ["reponpc.yml", "assets/character/**"]

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["build-and-publish"]
    assert isinstance(job, dict)
    steps = job["steps"]
    assert isinstance(steps, list)
    names = [step["name"] for step in steps if isinstance(step, dict) and "name" in step]
    required_names = [
        "Validate configuration",
        "Build immutable index bundle",
        "Publish immutable release asset",
        "Advance stable manifest last",
    ]
    assert [name for name in names if name in required_names] == required_names
    assert names[-1] == "Advance stable manifest last"

    checkout = next(step for step in steps if step.get("name") == "Check out configuration")
    assert checkout["with"]["persist-credentials"] == "false"
    assert (
        next(step for step in steps if step.get("name") == "Install locked dependencies")["run"]
        == "uv sync --locked --extra indexer"
    )

    for step in steps:
        if "uses" in step:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])

    assert "continue-on-error" not in workflow_text
    assert "|| true" not in workflow_text
    assert "set +e" not in workflow_text
    assert "always()" not in workflow_text

    immutable_name = "Publish immutable release asset"
    stable_name = "Advance stable manifest last"
    immutable_index = names.index(immutable_name)
    stable_index = names.index(stable_name)
    assert immutable_index < stable_index
    immutable_step = next(step for step in steps if step.get("name") == immutable_name)
    stable_step = next(step for step in steps if step.get("name") == stable_name)
    assert immutable_step["run"] == "uv run reponpc index publish --bundle-dir dist"
    assert stable_step["run"] == "uv run reponpc index publish-manifest --bundle-dir dist"
    assert immutable_step["run"] != stable_step["run"]
    for step in steps:
        if step.get("name") in {immutable_name, stable_name}:
            assert step["env"] == {"GH_TOKEN": "${{ github.token }}"}
        else:
            assert "GH_TOKEN" not in step.get("env", {})


@dataclass(slots=True)
class RecordingGitHubTransport:
    """A deterministic GitHub REST boundary; no network is available to tests."""

    existing_manifest: bool = False
    fail_upload: bool = False
    calls: list[tuple[str, str, bytes | None, Mapping[str, str]]] = field(default_factory=list)
    asset_content: bytes = b""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> GitHubHttpResponse:
        self.calls.append((method, url, body, headers))
        if method == "POST" and url.endswith("/releases"):
            return _response(
                201,
                {
                    "id": 17,
                    "upload_url": "https://uploads.github.com/repos/example/portfolio/"
                    "releases/17/assets{?name,label}",
                },
            )
        if method == "POST" and "uploads.github.com" in url:
            if self.fail_upload:
                return _response(422, {"message": "rejected"})
            assert body is not None
            self.asset_content = body
            asset_name = parse_qs(urlsplit(url).query)["name"][0]
            return _response(
                201,
                {
                    "browser_download_url": "https://github.com/example/portfolio/releases/"
                    f"download/index-test/{asset_name}",
                    "name": asset_name,
                    "size": len(body),
                },
            )
        if method == "GET" and url.startswith("https://github.com/"):
            return GitHubHttpResponse(status=200, headers={}, body=self.asset_content)
        if method == "GET" and "/contents/stable-manifest.json" in url:
            if self.existing_manifest:
                return _response(200, {"sha": "a" * 40})
            return GitHubHttpResponse(status=404, headers={}, body=b"")
        if method == "PUT" and "/contents/stable-manifest.json" in url:
            return _response(200, {"commit": {"sha": "b" * 40}})
        raise AssertionError(f"unexpected GitHub request: {method} {url}")


def _response(status: int, payload: dict[str, object]) -> GitHubHttpResponse:
    return GitHubHttpResponse(status=status, headers={}, body=json.dumps(payload).encode("utf-8"))


def _publisher(transport: RecordingGitHubTransport) -> GitHubReleasePublisher:
    return GitHubReleasePublisher(
        repository_slug="example/portfolio",
        token="fake-github-token-for-test-only",
        transport=transport,
    )


def test_concrete_publisher_releases_verifies_then_updates_only_the_fixed_pointer(tmp_path) -> None:
    bundle, _ = _bundle(tmp_path)
    transport = RecordingGitHubTransport()
    publisher = _publisher(transport)
    coordinator = PublicationCoordinator(publisher)
    result = coordinator.publish_immutable(
        bundle,
        now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )

    assert result.release_tag == f"index-{bundle.manifest.bundle_id}"
    assert [call[0] for call in transport.calls] == ["POST", "POST", "GET"]
    assert all("stable-manifest.json" not in call[1] for call in transport.calls)

    coordinator.publish_manifest(result.stable_manifest)

    assert [call[0] for call in transport.calls] == [
        "POST",
        "POST",
        "GET",
        "GET",
        "GET",
        "PUT",
    ]
    assert transport.calls[0][1] == "https://api.github.com/repos/example/portfolio/releases"
    assert transport.calls[1][1].startswith(
        "https://uploads.github.com/repos/example/portfolio/releases/17/assets?name="
    )
    assert transport.calls[-1][1] == (
        "https://api.github.com/repos/example/portfolio/contents/stable-manifest.json"
    )
    stable_write = json.loads((transport.calls[-1][2] or b"{}").decode("utf-8"))
    assert stable_write["branch"] == "reponpc-index"
    assert stable_write["message"] == "Publish immutable RepoNPC index manifest"
    assert "sha" not in stable_write
    assert all("fake-github-token-for-test-only" not in str(call[:3]) for call in transport.calls)


def test_existing_pointer_uses_its_current_blob_sha_only_at_final_mutation(tmp_path) -> None:
    bundle, _ = _bundle(tmp_path)
    transport = RecordingGitHubTransport(existing_manifest=True)

    coordinator = PublicationCoordinator(_publisher(transport))
    pending = coordinator.publish_immutable(
        bundle,
        now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    ).stable_manifest
    coordinator.publish_manifest(pending)

    stable_write = json.loads((transport.calls[-1][2] or b"{}").decode("utf-8"))
    assert stable_write["sha"] == "a" * 40


def test_upload_failure_never_reads_or_writes_the_stable_manifest(tmp_path) -> None:
    bundle, _ = _bundle(tmp_path)
    transport = RecordingGitHubTransport(fail_upload=True)

    with pytest.raises(PublicationError) as error:
        PublicationCoordinator(_publisher(transport)).publish_immutable(
            bundle,
            now=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        )

    assert error.value.code == "github_release_upload_failed"
    assert [call[0] for call in transport.calls] == ["POST", "POST"]
    assert all("stable-manifest.json" not in call[1] for call in transport.calls)
