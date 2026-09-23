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
from reponpc.admin.batch_runtime import (
    BatchCreateRequest,
    BatchItemInput,
    BatchRuntimeError,
    BatchRuntimeStore,
)
from reponpc.admin.batches import AnalysisBatchService, BatchExecutionError, BatchPreflightInput
from reponpc.admin.onboarding import analysis_generation_policy_identity
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers.contracts import ProviderCapabilities
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


class _BudgetedRunner:
    def __init__(self, budget: int) -> None:
        self.analysis_max_output_tokens = budget

    def __call__(self, item, _cancelled):
        return {"repository": {"slug": item.input.slug}}


def _service(
    tmp_path,
    *,
    status: int = 200,
    runner=None,
    analysis_pair_supplier=None,
    analysis_policy_supplier=None,
):
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
        analysis_policy_supplier=analysis_policy_supplier,
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


def test_current_model_reanalysis_rejects_a_stale_confirmed_generation(tmp_path) -> None:
    current = [_pair(2)]
    service = _service(tmp_path, analysis_pair_supplier=lambda: current[0])
    store = service._store
    original, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="source-plan",
            selection_hash="a" * 64,
            idempotency_key="source-idempotency",
            maximum_generation_attempts=3,
            analysis_model_pair=_pair(1).safe_dict(),
            items=(
                BatchItemInput(
                    slug="octocat/demo",
                    ref="main",
                    include=(),
                    exclude=(),
                    commit_sha=SHA,
                ),
            ),
        )
    )
    claimed = store.claim_next_item(original.batch_id)
    assert claimed is not None
    for _attempt in range(3):
        store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")

    with pytest.raises(BatchRuntimeError) as error:
        service.reanalyze(
            original.batch_id,
            item_ids=(claimed.item_id,),
            idempotency_key="current-successor-key",
            model_selection="current",
            confirm_model_change=True,
            expected_selection_generation=1,
        )

    assert error.value.code == "ANALYSIS_MODEL_SELECTION_STALE"
    with pytest.raises(BatchRuntimeError) as no_successor:
        store.active_batch()
    assert no_successor.value.code == "NOT_FOUND"


def test_current_model_idempotency_binds_the_confirmed_generation(tmp_path) -> None:
    current = [_pair(2)]
    successor_calls: list[str] = []

    def runner(item, _cancelled):
        successor_calls.append(item.input.slug)
        return {"repository": {"slug": item.input.slug}}

    service = _service(
        tmp_path,
        runner=runner,
        analysis_pair_supplier=lambda: current[0],
    )
    store = service._store
    original, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="source-plan",
            selection_hash="a" * 64,
            idempotency_key="source-idempotency-generation",
            maximum_generation_attempts=3,
            analysis_model_pair=_pair(1).safe_dict(),
            items=(
                BatchItemInput(
                    slug="octocat/demo",
                    ref="main",
                    include=(),
                    exclude=(),
                    commit_sha=SHA,
                ),
            ),
        )
    )
    claimed = store.claim_next_item(original.batch_id)
    assert claimed is not None
    for _attempt in range(3):
        store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")

    accepted, created = service.reanalyze(
        original.batch_id,
        item_ids=(claimed.item_id,),
        idempotency_key="current-successor-generation-key",
        model_selection="current",
        confirm_model_change=True,
        expected_selection_generation=2,
    )
    deduped, deduped_created = service.reanalyze(
        original.batch_id,
        item_ids=(claimed.item_id,),
        idempotency_key="second-equivalent-generation-key",
        model_selection="current",
        confirm_model_change=True,
        expected_selection_generation=2,
    )
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and service.get(accepted.batch_id).state != "completed":
        time.sleep(0.01)
    current[0] = _pair(3)
    repeated, repeated_created = service.reanalyze(
        original.batch_id,
        item_ids=(claimed.item_id,),
        idempotency_key="current-successor-generation-key",
        model_selection="current",
        confirm_model_change=True,
        expected_selection_generation=2,
    )
    with pytest.raises(BatchRuntimeError) as conflict:
        service.reanalyze(
            original.batch_id,
            item_ids=(claimed.item_id,),
            idempotency_key="current-successor-generation-key",
            model_selection="current",
            confirm_model_change=True,
            expected_selection_generation=3,
        )

    assert created is True
    assert deduped_created is False
    assert deduped.batch_id == accepted.batch_id
    assert repeated_created is False
    assert repeated.batch_id == accepted.batch_id
    assert conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    with pytest.raises(BatchRuntimeError) as second_key_conflict:
        service.reanalyze(
            original.batch_id,
            item_ids=(claimed.item_id,),
            idempotency_key="second-equivalent-generation-key",
            model_selection="current",
            confirm_model_change=True,
            expected_selection_generation=3,
        )
    assert second_key_conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    for changed_model, changed_confirmation, changed_generation in (
        ("frozen", False, None),
        ("current", False, 2),
    ):
        with pytest.raises(BatchRuntimeError) as changed_conflict:
            service.reanalyze(
                original.batch_id,
                item_ids=(claimed.item_id,),
                idempotency_key="second-equivalent-generation-key",
                model_selection=changed_model,
                confirm_model_change=changed_confirmation,
                expected_selection_generation=changed_generation,
            )
        assert changed_conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    with pytest.raises(BatchRuntimeError) as item_set_conflict:
        store.idempotent_reanalysis(
            idempotency_key="second-equivalent-generation-key",
            source_batch_id=original.batch_id,
            item_ids=(claimed.item_id, "different-item"),
            model_selection="current",
            confirm_model_change=True,
            expected_selection_generation=2,
        )
    assert item_set_conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    with pytest.raises(BatchRuntimeError) as general_create_conflict:
        service.create(
            plan_id="different-general-plan",
            selections=(_selection(),),
            idempotency_key="second-equivalent-generation-key",
        )
    assert general_create_conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    with pytest.raises(BatchRuntimeError) as transactional_create_conflict:
        store.create_batch(
            BatchCreateRequest(
                plan_id="different-general-plan",
                selection_hash="f" * 64,
                idempotency_key="second-equivalent-generation-key",
                items=(
                    BatchItemInput(
                        slug="octocat/other",
                        ref="main",
                        include=(),
                        exclude=(),
                        commit_sha="b" * 40,
                    ),
                ),
            )
        )
    assert transactional_create_conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"
    assert successor_calls == ["octocat/demo"]


def test_service_recovery_runs_bounded_cleanup_before_restart_recovery(
    tmp_path, monkeypatch
) -> None:
    service = _service(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(service._store, "cleanup_expired", lambda: calls.append("cleanup"))
    monkeypatch.setattr(
        service._store,
        "recover_after_restart",
        lambda: calls.append("recover") or (),
    )

    assert service.recover() == ()
    assert calls == ["cleanup", "recover"]


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


def test_accepted_create_survives_plan_cache_loss_and_rejects_changed_content(tmp_path) -> None:
    service = _service(tmp_path)
    plan = service.preflight(BatchPreflightInput((_selection(),)))
    accepted, created = service.create(
        plan_id=plan.plan_id,
        selections=(_selection(),),
        idempotency_key="restart-safe-idempotency",
    )
    with service._plans_lock:
        service._plans.clear()

    repeated, repeated_created = service.create(
        plan_id=plan.plan_id,
        selections=(_selection(),),
        idempotency_key="restart-safe-idempotency",
    )
    with pytest.raises(BatchRuntimeError) as conflict:
        service.create(
            plan_id=plan.plan_id,
            selections=(RepositorySelection(slug="octocat/other", confirmed=True),),
            idempotency_key="restart-safe-idempotency",
        )

    assert created is True
    assert repeated_created is False
    assert repeated.batch_id == accepted.batch_id
    assert conflict.value.code == "ANALYSIS_IDEMPOTENCY_CONFLICT"


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


def test_changed_provider_generation_caps_stale_the_preflight_plan(tmp_path) -> None:
    capabilities = ProviderCapabilities(False, True, True, True, True, 32768, 16384)
    service = _service(
        tmp_path,
        analysis_policy_supplier=lambda _pair: analysis_generation_policy_identity(
            8192, capabilities
        ),
    )
    plan = service.preflight(BatchPreflightInput((_selection(),)))
    capabilities = ProviderCapabilities(False, True, True, True, True, 8000, 8000)

    with pytest.raises(BatchRuntimeError) as error:
        service.create(
            plan_id=plan.plan_id,
            selections=(_selection(),),
            idempotency_key="capability-change",
        )

    assert error.value.code == "ANALYSIS_PLAN_STALE"


def test_batch_service_rejects_budget_different_from_runner(tmp_path) -> None:
    with pytest.raises(ValueError, match="match batch runner"):
        _service(tmp_path, runner=_BudgetedRunner(16384))


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
