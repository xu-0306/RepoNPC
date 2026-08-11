"""In-process deterministic mocks for future GitHub and provider adapters.

The mock app is test-only.  It owns all state in memory, exposes no route that
can initiate an outbound request, and uses unmistakably fake upstream values.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

FAKE_REPOSITORY = "example/portfolio"
FAKE_BRANCH = "main"
FAKE_WORKFLOW = "build-index.yml"
_PROVIDER_FAILURES = frozenset({"context_overflow", "invalid", "timeout", "unavailable"})


def _sha(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def _denied() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "WRITE_NOT_ALLOWED"},
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"})


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderGenerationRequest(StrictPayload):
    messages: tuple[dict[str, str], ...] = ()
    requested_capabilities: tuple[str, ...] = ()


class ContentWriteRequest(StrictPayload):
    content: str
    sha: str | None = None
    branch: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=200)


class ReleaseRequest(StrictPayload):
    tag_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)


class WorkflowDispatchRequest(StrictPayload):
    ref: str = Field(min_length=1, max_length=100)
    inputs: dict[str, str] = Field(default_factory=dict)


@dataclass(slots=True)
class MockServerState:
    """Frozen-config test state with explicit mutation accounting."""

    repository: str = FAKE_REPOSITORY
    branch: str = FAKE_BRANCH
    workflow: str = FAKE_WORKFLOW
    allowed_paths: frozenset[str] = frozenset({"reponpc.yml", "assets/character/hero.png"})
    provider_health: Literal["ready", "unavailable"] = "ready"
    provider_capabilities: frozenset[str] = frozenset(
        {"health_check", "structured_output", "usage_reporting"}
    )
    provider_generation: Literal[
        "success", "context_overflow", "invalid", "timeout", "unavailable"
    ] = "success"
    provider_usage: dict[str, int] | None = field(
        default_factory=lambda: {"input_tokens": 5, "output_tokens": 3}
    )
    contents: dict[str, bytes] = field(
        default_factory=lambda: {"reponpc.yml": b"schema_version: 1\n"}
    )
    releases: dict[int, dict[str, Any]] = field(default_factory=dict)
    next_release_id: int = 1
    mutation_count: int = 0
    content_mutation_count: int = 0
    release_mutation_count: int = 0
    workflow_dispatch_count: int = 0

    def content_sha(self, path: str) -> str | None:
        content = self.contents.get(path)
        return _sha(content) if content is not None else None


def _require_repository(state: MockServerState, owner: str, repository: str) -> None:
    if f"{owner}/{repository}" != state.repository:
        raise _not_found()


def _require_branch(state: MockServerState, branch: str | None) -> None:
    if branch != state.branch:
        raise _not_found()


def _require_path(state: MockServerState, path: str) -> None:
    if path not in state.allowed_paths:
        raise _denied()


def _provider_error(kind: str) -> HTTPException:
    if kind == "timeout":
        return HTTPException(status_code=504, detail={"code": "PROVIDER_TIMEOUT"})
    if kind == "context_overflow":
        return HTTPException(status_code=422, detail={"code": "CONTEXT_OVERFLOW"})
    if kind == "invalid":
        return HTTPException(status_code=502, detail={"code": "PROVIDER_INVALID_RESPONSE"})
    return HTTPException(status_code=503, detail={"code": "PROVIDER_UNAVAILABLE"})


def create_mock_app(state: MockServerState | None = None) -> FastAPI:
    """Create a no-network mock app bound to the supplied in-memory state."""

    server_state = state or MockServerState()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.mock_server = server_state

    @app.get("/provider/health")
    async def provider_health() -> dict[str, str]:
        if server_state.provider_health != "ready":
            raise _provider_error("unavailable")
        return {"status": "ready"}

    @app.get("/provider/capabilities")
    async def provider_capabilities() -> dict[str, list[str]]:
        return {"capabilities": sorted(server_state.provider_capabilities)}

    @app.post("/provider/generate")
    async def provider_generate(payload: ProviderGenerationRequest) -> dict[str, Any]:
        unsupported = set(payload.requested_capabilities) - server_state.provider_capabilities
        if unsupported:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNSUPPORTED_CAPABILITY"},
            )
        if server_state.provider_generation in _PROVIDER_FAILURES:
            raise _provider_error(server_state.provider_generation)
        return {
            "content": "mocked normalized generation",
            "finish_reason": "stop",
            "usage": server_state.provider_usage,
            "provider_request_id": "mock-provider-request-1",
        }

    @app.get("/github/repos/{owner}/{repository}/contents/{path:path}")
    async def get_content(
        owner: str,
        repository: str,
        path: str,
        ref: str | None = None,
    ) -> dict[str, str]:
        _require_repository(server_state, owner, repository)
        _require_branch(server_state, ref)
        _require_path(server_state, path)
        content = server_state.contents.get(path)
        if content is None:
            raise _not_found()
        return {
            "path": path,
            "sha": _sha(content),
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }

    @app.put("/github/repos/{owner}/{repository}/contents/{path:path}")
    async def put_content(
        owner: str,
        repository: str,
        path: str,
        payload: ContentWriteRequest,
    ) -> dict[str, str]:
        _require_repository(server_state, owner, repository)
        _require_path(server_state, path)
        _require_branch(server_state, payload.branch)
        current_sha = server_state.content_sha(path)
        if current_sha is None and payload.sha is not None:
            raise HTTPException(status_code=409, detail={"code": "CONFIG_CONFLICT"})
        if current_sha is not None and payload.sha != current_sha:
            raise HTTPException(status_code=409, detail={"code": "CONFIG_CONFLICT"})
        try:
            content = base64.b64decode(payload.content, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR"}) from None
        server_state.contents[path] = content
        server_state.mutation_count += 1
        server_state.content_mutation_count += 1
        return {"path": path, "sha": _sha(content), "commit_sha": _sha(payload.message.encode())}

    @app.post("/github/repos/{owner}/{repository}/releases")
    async def create_release(
        owner: str,
        repository: str,
        payload: ReleaseRequest,
    ) -> dict[str, Any]:
        _require_repository(server_state, owner, repository)
        release_id = server_state.next_release_id
        server_state.next_release_id += 1
        release = {
            "id": release_id,
            "tag_name": payload.tag_name,
            "name": payload.name,
            "assets": [],
        }
        server_state.releases[release_id] = release
        server_state.mutation_count += 1
        server_state.release_mutation_count += 1
        return release

    @app.post("/github/repos/{owner}/{repository}/releases/{release_id}/assets")
    async def publish_release_asset(
        owner: str,
        repository: str,
        release_id: int,
        request: Request,
        name: str,
    ) -> dict[str, Any]:
        _require_repository(server_state, owner, repository)
        release = server_state.releases.get(release_id)
        if (
            release is None
            or not name.startswith("reponpc-index-")
            or not name.endswith(".tar.zst")
        ):
            raise _denied()
        payload = await request.body()
        asset = {"name": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        release["assets"].append(asset)
        server_state.mutation_count += 1
        server_state.release_mutation_count += 1
        return asset

    @app.post("/github/repos/{owner}/{repository}/actions/workflows/{workflow}/dispatches")
    async def dispatch_workflow(
        owner: str,
        repository: str,
        workflow: str,
        payload: WorkflowDispatchRequest,
    ) -> Response:
        _require_repository(server_state, owner, repository)
        if workflow != server_state.workflow or payload.ref != server_state.branch:
            raise _denied()
        server_state.mutation_count += 1
        server_state.workflow_dispatch_count += 1
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
