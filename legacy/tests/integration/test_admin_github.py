from __future__ import annotations

import base64
import json

import pytest

from reponpc.admin.github import GitHubAdminClient, GitHubAdminError, GitHubResponse


class RecordingTransport:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []
        self.content = b"schema_version: 1\n"
        self.sha = "a" * 40
        self.commit_sha = "b" * 40

    def request(
        self, *, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> GitHubResponse:
        self.requests.append((method, url, headers, body))
        if method == "GET":
            if "/commits/" in url:
                return GitHubResponse(
                    200,
                    json.dumps(
                        {
                            "sha": self.commit_sha,
                            "commit": {"committer": {"date": "2026-08-13T00:00:00Z"}},
                        }
                    ).encode(),
                )
            return GitHubResponse(
                200,
                json.dumps(
                    {
                        "content": base64.b64encode(self.content).decode(),
                        "sha": self.sha,
                    }
                ).encode(),
            )
        if method == "PUT":
            return GitHubResponse(
                200,
                json.dumps({"commit": {"sha": "c" * 40}, "content": {"sha": "d" * 40}}).encode(),
            )
        return GitHubResponse(204, b"")


def _client(transport: RecordingTransport) -> GitHubAdminClient:
    return GitHubAdminClient(
        repository="owner/profile",
        branch="main",
        workflow="build-index.yml",
        token="canary-secret-token",
        transport=transport,
    )


def test_write_uses_fixed_scope_and_expected_blob_sha() -> None:
    transport = RecordingTransport()
    result = _client(transport).write(
        path="reponpc.yml",
        content=b"new config",
        expected_blob_sha="a" * 40,
        commit_message=" Update   portfolio ",
    )
    assert result.commit_sha == "c" * 40
    assert transport.requests[0][1].endswith("/commits/main")
    assert transport.requests[1][1].endswith(f"?ref={'b' * 40}")
    method, url, headers, body = transport.requests[-1]
    assert method == "PUT"
    assert url.startswith("https://api.github.com/repos/owner/profile/contents/reponpc.yml")
    assert headers["Authorization"] == "Bearer canary-secret-token"
    payload = json.loads(body or b"")
    assert payload["branch"] == "main"
    assert payload["sha"] == "a" * 40
    assert payload["message"] == "Update portfolio"


def test_stale_sha_and_unsafe_paths_never_mutate() -> None:
    transport = RecordingTransport()
    client = _client(transport)
    with pytest.raises(GitHubAdminError) as conflict:
        client.write(
            path="reponpc.yml",
            content=b"new",
            expected_blob_sha="f" * 40,
            commit_message="save",
        )
    assert conflict.value.code == "CONFIG_CONFLICT"
    assert [request[0] for request in transport.requests] == ["GET", "GET"]

    for path in ("../workflow.yml", "assets/character/nested/hero.png", "README.md"):
        with pytest.raises(GitHubAdminError) as denied:
            client.write(path=path, content=b"x", expected_blob_sha=None, commit_message="x")
        assert denied.value.code == "WRITE_NOT_ALLOWED"
    assert [request[0] for request in transport.requests] == ["GET", "GET"]


def test_read_returns_branch_commit_separately_from_blob_sha() -> None:
    transport = RecordingTransport()
    result = _client(transport).read_config()

    assert result.blob_sha == "a" * 40
    assert result.commit_sha == "b" * 40
    assert result.updated_at == "2026-08-13T00:00:00Z"


def test_dispatch_uses_fixed_workflow_and_branch() -> None:
    transport = RecordingTransport()
    _client(transport).dispatch_index()
    method, url, _headers, body = transport.requests[-1]
    assert method == "POST"
    assert url.endswith("/actions/workflows/build-index.yml/dispatches")
    assert json.loads(body or b"") == {"ref": "main"}
