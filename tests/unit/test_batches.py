from __future__ import annotations

import json
import threading
import time

import pytest

from reponpc.admin.analysis_selection import AnalysisModelPair
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlanner,
    GitHubHttpResponse,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
    RepositorySelection,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchRuntimeStore
from reponpc.admin.batches import AnalysisBatchService, BatchExecutionError, BatchPreflightInput
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase

SHA = "a" * 40


class RESTTransport:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def request(self, **values: object) -> GitHubHttpResponse:
        url = str(values["url"])
        body = (
            {"sha": SHA}
            if "/commits/" in url
            else {"id": "R_demo", "private": False, "archived": False, "default_branch": "main"}
        )
        return GitHubHttpResponse(
            status=self.status,
            body=json.dumps(body).encode(),
            headers={"X-RateLimit-Resource": "core", "X-RateLimit-Remaining": "60"},
        )


def _service(tmp_path, *, status: int = 200, runner=None, analysis_pair_supplier=None):
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    limiter = GitHubRateLimiter()
    planner = BatchPreflightPlanner(
        resolver=GitHubRESTMetadataResolver(
            transport=RESTTransport(status),  # type: ignore[arg-type]
            limiter=limiter,
        ),
        limiter=limiter,
    )
    service = AnalysisBatchService(
        store=BatchRuntimeStore(database),
        planner=planner,
        provider_ready_supplier=lambda: True,
        capacity=BatchCapacity(1, 1, 2, 1, 4),
        runner=runner or (lambda item, cancelled: {"repository": {"slug": item.input.slug}}),
        analysis_pair_supplier=analysis_pair_supplier,
    )
    return service


def _selection() -> RepositorySelection:
    return RepositorySelection(slug="octocat/demo", confirmed=True)


def _pair(generation: int) -> AnalysisModelPair:
    return AnalysisModelPair(
        selection_generation=generation,
        chat_profile_id="chat",
        chat_connection_id="chat-connection",
        chat_connection_revision=generation,
        chat_provider="ollama",
        chat_model_id="chat-model",
        embedding_profile_id="embedding",
        embedding_connection_id="embedding-connection",
        embedding_connection_revision=generation,
        embedding_provider="ollama",
        embedding_identity=EmbeddingIdentity(
            adapter="ollama",
            model_id="embedding-model",
            dimension=2,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        ),
    )


def test_preflight_is_selection_bound_idempotent_and_emits_safe_terminal_events(tmp_path) -> None:
    service = _service(tmp_path)
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


def test_inaccessible_repository_plan_is_non_disclosing_and_never_creates(tmp_path) -> None:
    service = _service(tmp_path, status=401)
    plan = service.preflight(BatchPreflightInput((_selection(),)))

    with pytest.raises(BatchRuntimeError) as error:
        service.create(
            plan_id=plan.plan_id,
            selections=(_selection(),),
            idempotency_key="test-idempotency-key",
        )

    assert error.value.code == "ANALYSIS_PLAN_STALE"
    assert [(blocker.slug, blocker.code) for blocker in plan.blockers] == [
        ("octocat/demo", "NOT_FOUND")
    ]


def test_changed_model_pair_stales_the_preflight_plan(tmp_path) -> None:
    current_pair = _pair(1)
    service = _service(tmp_path, analysis_pair_supplier=lambda: current_pair)
    plan = service.preflight(BatchPreflightInput((_selection(),)))
    current_pair = _pair(2)

    with pytest.raises(BatchRuntimeError) as error:
        service.create(
            plan_id=plan.plan_id,
            selections=(_selection(),),
            idempotency_key="pair-change",
        )

    assert error.value.code == "ANALYSIS_PLAN_STALE"


def test_runner_rate_waits_without_busy_loop_then_resumes(tmp_path) -> None:
    attempts = 0

    def runner(_item, _cancelled):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise BatchExecutionError("GITHUB_RATE_LIMITED", retry_after_seconds=1)
        return {"repository": {"slug": "octocat/demo"}}

    service = _service(tmp_path, runner=runner)
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
        if snapshot.state == "completed":
            break
        time.sleep(0.02)

    assert attempts == 2
    assert snapshot.items[0].state == "complete"


def test_compatibility_timeout_keeps_durable_batch_recoverable(tmp_path) -> None:
    runner_started = threading.Event()
    release_runner = threading.Event()

    def runner(item, _cancelled):
        runner_started.set()
        release_runner.wait(timeout=2)
        return {"repository": {"slug": item.input.slug}}

    service = _service(tmp_path, runner=runner)
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
