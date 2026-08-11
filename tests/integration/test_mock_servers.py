from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from tests.mocks import MockServerState, create_mock_app


@pytest.fixture
def mock_state() -> MockServerState:
    return MockServerState()


@pytest.fixture
def client(mock_state: MockServerState) -> TestClient:
    with TestClient(create_mock_app(mock_state)) as test_client:
        yield test_client


def test_provider_mock_covers_health_capabilities_generation_and_null_usage(
    client: TestClient,
    mock_state: MockServerState,
) -> None:
    assert client.get("/provider/health").json() == {"status": "ready"}
    assert client.get("/provider/capabilities").json() == {
        "capabilities": ["health_check", "structured_output", "usage_reporting"]
    }

    response = client.post(
        "/provider/generate",
        json={
            "messages": [{"role": "user", "content": "PROMPT_CANARY"}],
            "requested_capabilities": ["structured_output"],
        },
    )

    assert response.status_code == 200
    assert response.json()["usage"] == {"input_tokens": 5, "output_tokens": 3}
    assert "PROMPT_CANARY" not in response.text

    mock_state.provider_usage = None
    assert client.post("/provider/generate", json={}).json()["usage"] is None


@pytest.mark.parametrize(
    ("scenario", "status_code", "error_code"),
    [
        ("timeout", 504, "PROVIDER_TIMEOUT"),
        ("context_overflow", 422, "CONTEXT_OVERFLOW"),
        ("invalid", 502, "PROVIDER_INVALID_RESPONSE"),
        ("unavailable", 503, "PROVIDER_UNAVAILABLE"),
    ],
)
def test_provider_mock_normalizes_failure_scenarios(
    client: TestClient,
    mock_state: MockServerState,
    scenario: str,
    status_code: int,
    error_code: str,
) -> None:
    mock_state.provider_generation = scenario  # type: ignore[assignment]

    response = client.post("/provider/generate", json={})

    assert response.status_code == status_code
    assert response.json() == {"detail": {"code": error_code}}
    assert "https://" not in response.text


def test_provider_mock_rejects_unsupported_capabilities(client: TestClient) -> None:
    response = client.post(
        "/provider/generate",
        json={"requested_capabilities": ["streaming"]},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "UNSUPPORTED_CAPABILITY"}}


def test_github_contents_mock_enforces_repository_branch_path_and_expected_sha(
    client: TestClient,
    mock_state: MockServerState,
) -> None:
    initial = client.get("/github/repos/example/portfolio/contents/reponpc.yml?ref=main")
    assert initial.status_code == 200
    expected_sha = initial.json()["sha"]
    assert mock_state.mutation_count == 0

    stale = client.put(
        "/github/repos/example/portfolio/contents/reponpc.yml",
        json={
            "content": base64.b64encode(b"schema_version: 2\n").decode(),
            "sha": "stale-sha",
            "branch": "main",
            "message": "update config",
        },
    )
    assert stale.status_code == 409
    assert stale.json() == {"detail": {"code": "CONFIG_CONFLICT"}}
    assert mock_state.mutation_count == 0

    updated = client.put(
        "/github/repos/example/portfolio/contents/reponpc.yml",
        json={
            "content": base64.b64encode(b"schema_version: 1\nprofile: {}\n").decode(),
            "sha": expected_sha,
            "branch": "main",
            "message": "update config",
        },
    )
    assert updated.status_code == 200
    assert mock_state.content_mutation_count == 1

    for path in ("outside.yml", "assets/character/nested/hero.png"):
        denied = client.put(
            f"/github/repos/example/portfolio/contents/{path}",
            json={
                "content": base64.b64encode(b"x").decode(),
                "sha": None,
                "branch": "main",
                "message": "unknown operation",
            },
        )
        assert denied.status_code == 403
    wrong_branch = client.get("/github/repos/example/portfolio/contents/reponpc.yml?ref=other")
    wrong_repository = client.get("/github/repos/other/portfolio/contents/reponpc.yml?ref=main")
    assert wrong_branch.status_code == 404
    assert wrong_repository.status_code == 404
    assert mock_state.mutation_count == 1


def test_github_release_assets_and_workflow_dispatch_are_stateful_and_allowlisted(
    client: TestClient,
    mock_state: MockServerState,
) -> None:
    release = client.post(
        "/github/repos/example/portfolio/releases",
        json={"tag_name": "index-20260810", "name": "Index 20260810"},
    )
    assert release.status_code == 200
    release_id = release.json()["id"]

    asset = client.post(
        f"/github/repos/example/portfolio/releases/{release_id}/assets?name=reponpc-index-abc.tar.zst",
        content=b"bundle-bytes",
    )
    assert asset.status_code == 200
    assert asset.json()["size"] == len(b"bundle-bytes")

    dispatch = client.post(
        "/github/repos/example/portfolio/actions/workflows/build-index.yml/dispatches",
        json={"ref": "main", "inputs": {"reason": "test"}},
    )
    assert dispatch.status_code == 204
    assert mock_state.release_mutation_count == 2
    assert mock_state.workflow_dispatch_count == 1

    denied = client.post(
        "/github/repos/example/portfolio/actions/workflows/unknown.yml/dispatches",
        json={"ref": "main", "inputs": {}},
    )
    assert denied.status_code == 403
    assert mock_state.workflow_dispatch_count == 1
