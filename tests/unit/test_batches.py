from __future__ import annotations

import json
import threading
import time

import pytest

from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    CredentialPurpose,
    GitHubGraphQLMetadataResolver,
    GitHubHttpResponse,
    GitHubRateLimiter,
    PublicReadCredential,
    RepositorySelection,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchRuntimeStore
from reponpc.admin.batches import AnalysisBatchService, BatchExecutionError, BatchPreflightInput
from reponpc.runtime.database import RuntimeDatabase

SHA = "a" * 40


class GraphQLTransport:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def request(self, **_values: object) -> GitHubHttpResponse:
        body = {
            "data": {
                "repo0": {
                    "id": "R_demo",
                    "nameWithOwner": "octocat/demo",
                    "isPrivate": False,
                    "isArchived": False,
                    "defaultBranchRef": {"name": "main", "target": {"oid": SHA}},
                }
            }
        }
        return GitHubHttpResponse(
            status=self.status,
            body=json.dumps(body).encode(),
            headers={"X-RateLimit-Remaining": "5000"},
        )


def _service(tmp_path, *, status: int = 200, runner=None):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    limiter = GitHubRateLimiter()
    planner = BatchPreflightPlanner(
        resolver=GitHubGraphQLMetadataResolver(
            transport=GraphQLTransport(status),  # type: ignore[arg-type]
            limiter=limiter,
        ),
        limiter=limiter,
    )
    marked: list[int] = []
    credential = PublicReadCredential(
        credential_id=7,
        purpose=CredentialPurpose.IDENTITY_PUBLIC_READ,
        status="ready",
        token="batch-test-token",
    )
    service = AnalysisBatchService(
        store=BatchRuntimeStore(database),
        planner=planner,
        credentials_supplier=lambda: (credential,),
        mark_connection_required=marked.append,
        provider_ready_supplier=lambda: True,
        capacity=BatchCapacity(1, 1, 2, 1, 4),
        runner=runner or (lambda item, cancelled: {"repository": {"slug": item.input.slug}}),
    )
    return service, marked


def _selection() -> RepositorySelection:
    return RepositorySelection(slug="octocat/demo", confirmed=True)


def test_preflight_is_selection_bound_idempotent_and_emits_safe_terminal_events(tmp_path) -> None:
    service, _marked = _service(tmp_path)
    plan = service.preflight(BatchPreflightInput((_selection(),)))

    first, created = service.create(
        plan_id=plan.plan_id,
        selections=(_selection(),),
        idempotency_key="test-idempotency-key",
    )
    repeated, repeated_created = service.create(
        plan_id=plan.plan_id,
        selections=(_selection(),),
        idempotency_key="test-idempotency-key",
    )

    deadline = time.monotonic() + 2
    snapshot = first
    while time.monotonic() < deadline:
        snapshot = service.get(first.batch_id)
        if snapshot.state == "completed":
            break
        time.sleep(0.01)
    assert created is True
    assert repeated_created is False
    assert repeated.batch_id == first.batch_id
    assert snapshot.state == "completed"
    event_ids = [event.event_id for event in service.events(first.batch_id, after_event_id=0)]
    assert event_ids == [1, 2, 3, 4]


def test_connection_required_plan_never_creates_or_falls_back(tmp_path) -> None:
    service, marked = _service(tmp_path, status=401)
    plan = service.preflight(BatchPreflightInput((_selection(),)))

    with pytest.raises(BatchRuntimeError) as error:
        service.create(
            plan_id=plan.plan_id,
            selections=(_selection(),),
            idempotency_key="test-idempotency-key",
        )

    assert error.value.code == "GITHUB_CONNECTION_REQUIRED"
    assert marked == [7]


def test_runner_rate_waits_without_busy_loop_and_reconnect_requires_action(tmp_path) -> None:
    attempts = 0

    def runner(_item, _cancelled):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise BatchExecutionError("GITHUB_RATE_LIMITED", retry_after_seconds=1)
        raise BatchExecutionError("GITHUB_CONNECTION_REQUIRED")

    service, marked = _service(tmp_path, runner=runner)
    plan = service.preflight(BatchPreflightInput((_selection(),)))
    batch, _created = service.create(
        plan_id=plan.plan_id,
        selections=(_selection(),),
        idempotency_key="test-idempotency-key",
    )
    deadline = time.monotonic() + 3
    snapshot = service.get(batch.batch_id)
    while time.monotonic() < deadline:
        snapshot = service.get(batch.batch_id)
        if snapshot.items[0].state == "waiting_reconnection":
            break
        time.sleep(0.02)

    assert attempts == 2
    assert snapshot.items[0].state == "waiting_reconnection"
    assert marked == [7]


def test_compatibility_timeout_keeps_durable_batch_recoverable(tmp_path) -> None:
    runner_started = threading.Event()
    release_runner = threading.Event()

    def runner(item, _cancelled):
        runner_started.set()
        release_runner.wait(timeout=2)
        return {"repository": {"slug": item.input.slug}}

    service, _marked = _service(tmp_path, runner=runner)
    try:
        with pytest.raises(BatchRuntimeError) as error:
            service.analyze_one_compatibility(
                selection=_selection(),
                cancelled=lambda: False,
                timeout_seconds=0.02,
            )

        assert error.value.code == "PROVIDER_TIMEOUT"
        assert runner_started.wait(timeout=1)
        active = service.active()
        assert active.state in {"queued", "running"}
        assert active.items[0].state not in {"cancelled", "failed"}
    finally:
        release_runner.set()

    deadline = time.monotonic() + 2
    snapshot = service.get(active.batch_id)
    while time.monotonic() < deadline:
        snapshot = service.get(snapshot.batch_id)
        if snapshot.state == "completed":
            break
        time.sleep(0.01)
    assert snapshot.state == "completed"
