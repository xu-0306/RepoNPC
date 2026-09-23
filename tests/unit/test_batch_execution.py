from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

import reponpc.admin.batch_execution as batch_execution
from reponpc.admin.analysis_selection import AnalysisModelPair
from reponpc.admin.batch_execution import PinnedBatchItemRunner
from reponpc.admin.batch_resolver import BatchCapacity
from reponpc.admin.batch_runtime import (
    BatchCreateRequest,
    BatchItemInput,
    BatchRuntimeStore,
)
from reponpc.admin.batches import BatchExecutionError, BatchStageGates
from reponpc.admin.onboarding import GuidedOnboardingError
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers.contracts import ProviderCapabilities
from reponpc.runtime.database import RuntimeDatabase


class Source:
    def __init__(self) -> None:
        self.calls = 0

    def fetch(self, **_values: object) -> object:
        self.calls += 1
        return object()


class Onboarding:
    def __init__(self, failure: GuidedOnboardingError | None = None) -> None:
        self.calls = 0
        self.providers: list[object] = []
        self.failure = failure

    def analyze_resolved_repository(self, **values: object) -> dict[str, object]:
        self.calls += 1
        self.providers.append(values["providers"])
        if self.failure is not None:
            raise self.failure
        stage_changed = values["stage_changed"]
        assert callable(stage_changed)
        stage_changed("filtering")
        stage_changed("indexing")
        stage_changed("embedding")
        stage_changed("generating")
        stage_changed("validating")
        return {
            "repository": {"slug": "octocat/demo", "commit_sha": "a" * 40},
            "facts": [{"excerpt": "untrusted repository source must not persist"}],
            "inferences": [
                {
                    "evidence_class": "MODEL_INFERENCE",
                    "statement": {"zh-TW": "摘要", "en": "Summary"},
                    "supporting_evidence_ids": [f"E_{'1' * 24}"],
                }
            ],
            "skipped_summary": {"count": 0, "reasons": []},
            "archive_body": "archive-body-canary",
            "prompt_context": "prompt-context-canary",
            "provider_body": "provider-body-canary",
            "credential": "credential-canary",
        }


class BudgetedOnboarding(Onboarding):
    def __init__(self, budget: int) -> None:
        super().__init__()
        self.analysis_max_output_tokens = budget


def _request(key: str, *, maximum_generation_attempts: int = 3) -> BatchCreateRequest:
    return BatchCreateRequest(
        plan_id=f"plan-{key}",
        selection_hash=hashlib.sha256(b"selection").hexdigest(),
        idempotency_key=key,
        maximum_generation_attempts=maximum_generation_attempts,
        items=(
            BatchItemInput(
                slug="octocat/demo",
                ref="main",
                include=("src/**",),
                exclude=(),
                commit_sha="a" * 40,
            ),
        ),
    )


def _runner(store: BatchRuntimeStore, onboarding: object) -> PinnedBatchItemRunner:
    return PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )


def test_cancelled_stage_admission_stops_before_generation_dispatch(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    batch, _ = store.create_batch(_request("cancel-before-dispatch"))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    class CancellingOnboarding(Onboarding):
        def analyze_resolved_repository(self, **values: object) -> dict[str, object]:
            stage_changed = values["stage_changed"]
            assert callable(stage_changed)
            stage_changed("filtering")
            store.transition_batch(batch.batch_id, action="cancel")
            stage_changed("generating")
            raise AssertionError("cancelled dispatch continued")

    with pytest.raises(BatchExecutionError) as error:
        _runner(store, CancellingOnboarding())(claimed, lambda: False)

    assert error.value.code == "CANCELLED"
    snapshot = store.get_batch(batch.batch_id)
    assert snapshot.state == "cancelled"
    assert snapshot.items[0].generation_attempt_count == 0


def test_runner_with_two_used_attempts_can_dispatch_only_once_more(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    batch, _ = store.create_batch(_request("one-attempt-left", maximum_generation_attempts=3))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_batch_items SET generation_attempt_count = 2 WHERE item_id = ?",
            (claimed.item_id,),
        )

    class RetryingOnboarding(Onboarding):
        def __init__(self) -> None:
            super().__init__()
            self.dispatches = 0

        def analyze_resolved_repository(self, **values: object) -> dict[str, object]:
            stage_changed = values["stage_changed"]
            assert callable(stage_changed)
            stage_changed("generating")
            self.dispatches += 1
            stage_changed("generating")
            self.dispatches += 1
            raise AssertionError("attempt limit allowed a fourth dispatch")

    onboarding = RetryingOnboarding()
    with pytest.raises(BatchExecutionError) as error:
        _runner(store, onboarding)(claimed, lambda: False)

    assert error.value.code == "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED"
    assert onboarding.dispatches == 1
    assert store.get_batch(batch.batch_id).items[0].generation_attempt_count == 3


def _pair(model: str, revision: int) -> AnalysisModelPair:
    return AnalysisModelPair(
        selection_generation=revision,
        chat_profile_id="chat",
        chat_connection_id="chat-connection",
        chat_connection_revision=revision,
        chat_provider="ollama",
        chat_model_id=model,
        embedding_profile_id="embedding",
        embedding_connection_id="embedding-connection",
        embedding_connection_revision=revision,
        embedding_provider="ollama",
        embedding_identity=EmbeddingIdentity(
            adapter="ollama",
            model_id=f"{model}-embedding",
            dimension=2,
            normalized=True,
            query_prefix="query: ",
            passage_prefix="passage: ",
        ),
    )


def test_validated_result_cache_is_commit_complete_and_excludes_source_excerpt(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    source = Source()
    onboarding = Onboarding()
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        parser_identity="parser-a",
        embedding_identity="embedding-a",
        chat_model="chat-a",
        prompt_version="prompt-a",
        output_schema_version="schema-a",
        validation_version="validation-a",
    )

    first, _ = store.create_batch(_request("key-one"))
    claimed = store.claim_next_item(first.batch_id)
    assert claimed is not None
    result = runner(claimed, lambda: False)
    store.complete_item(claimed, result=result)

    second, _ = store.create_batch(_request("key-two"))
    cached = store.claim_next_item(second.batch_id)
    assert cached is not None
    cached_result = runner(cached, lambda: False)

    assert source.calls == onboarding.calls == 1
    assert cached_result["facts"] == []
    with database.connection() as connection:
        rows = connection.execute(
            "SELECT metadata_json, payload_json FROM analysis_cache_entries"
        ).fetchall()
    serialized = "".join(str(value) for row in rows for value in row)
    for canary in (
        "untrusted repository source",
        "cache-test-token",
        "archive-body-canary",
        "prompt-context-canary",
        "provider-body-canary",
        "credential-canary",
    ):
        assert canary not in serialized


def test_validated_cache_reuses_after_restart_and_tamper_rebuilds(tmp_path) -> None:
    runtime_path = tmp_path / "runtime"
    database = RuntimeDatabase(runtime_path)
    database.initialize()
    first_store = BatchRuntimeStore(database)
    first_source = Source()
    first_onboarding = Onboarding()
    first_runner = PinnedBatchItemRunner(
        store=first_store,
        source=first_source,  # type: ignore[arg-type]
        onboarding=first_onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    first_batch, _ = first_store.create_batch(_request("restart-first"))
    first_item = first_store.claim_next_item(first_batch.batch_id)
    assert first_item is not None
    first_result = first_runner(first_item, lambda: False)
    first_store.complete_item(first_item, result=first_result)

    restarted_database = RuntimeDatabase(runtime_path)
    restarted_database.initialize()
    restarted_store = BatchRuntimeStore(restarted_database)
    warm_source = Source()
    warm_onboarding = Onboarding()
    warm_runner = PinnedBatchItemRunner(
        store=restarted_store,
        source=warm_source,  # type: ignore[arg-type]
        onboarding=warm_onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    warm_batch, _ = restarted_store.create_batch(_request("restart-warm"))
    warm_item = restarted_store.claim_next_item(warm_batch.batch_id)
    assert warm_item is not None
    warm_result = warm_runner(warm_item, lambda: False)
    restarted_store.complete_item(warm_item, result=warm_result)

    assert (first_source.calls, first_onboarding.calls) == (1, 1)
    assert (warm_source.calls, warm_onboarding.calls) == (0, 0)
    assert warm_result["facts"] == []

    _derived_key, result_key = warm_runner._cache_keys(warm_item, None)
    with restarted_database.connection() as connection:
        connection.execute(
            "UPDATE analysis_cache_entries SET metadata_json = ? WHERE cache_key = ?",
            ('{"commit":"tampered"}', result_key),
        )

    rebuilt_database = RuntimeDatabase(runtime_path)
    rebuilt_database.initialize()
    rebuilt_store = BatchRuntimeStore(rebuilt_database)
    rebuilt_source = Source()
    rebuilt_onboarding = Onboarding()
    rebuilt_runner = PinnedBatchItemRunner(
        store=rebuilt_store,
        source=rebuilt_source,  # type: ignore[arg-type]
        onboarding=rebuilt_onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    rebuilt_batch, _ = rebuilt_store.create_batch(_request("restart-rebuild"))
    rebuilt_item = rebuilt_store.claim_next_item(rebuilt_batch.batch_id)
    assert rebuilt_item is not None
    rebuilt_result = rebuilt_runner(rebuilt_item, lambda: False)

    assert rebuilt_result["facts"]
    assert (rebuilt_source.calls, rebuilt_onboarding.calls) == (1, 1)


def test_structurally_invalid_cache_rebuilds_instead_of_failing_batch(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    source = Source()
    onboarding = Onboarding()
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    batch, _ = store.create_batch(_request("invalid-cache"))
    item = store.claim_next_item(batch.batch_id)
    assert item is not None
    derived_key, result_key = runner._cache_keys(item, None)
    store.put_cache(
        cache_key=result_key,
        cache_kind="validated_analysis",
        derived_index_key=derived_key,
        metadata=runner._result_cache_metadata(item, None, None),
        payload={
            "repository": {"slug": item.input.slug, "commit_sha": item.input.commit_sha},
            "inferences": [{"facts": "raw-source-canary"}],
            "skipped_summary": {"count": 0, "reasons": []},
        },
    )

    result = runner(item, lambda: False)

    assert result["facts"]
    assert (source.calls, onboarding.calls) == (1, 1)
    assert store.get_cache(result_key) is not None


def test_derived_marker_does_not_skip_work_after_generation_failure(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    source = Source()
    onboarding = Onboarding(GuidedOnboardingError("PROVIDER_ERROR"))
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    first_batch, _ = store.create_batch(_request("failure-cold"))
    first_item = store.claim_next_item(first_batch.batch_id)
    assert first_item is not None
    derived_key, result_key = runner._cache_keys(first_item, None)
    store.put_cache(
        cache_key=derived_key,
        cache_kind="derived_index",
        derived_index_key=derived_key,
        metadata={"repository": first_item.input.slug, "commit": first_item.input.commit_sha},
        payload={"commit": first_item.input.commit_sha, "validated": True},
    )

    with pytest.raises(BatchExecutionError):
        runner(first_item, lambda: False)
    store.fail_item(first_item, code="ANALYSIS_FAILED")
    second_batch, _ = store.create_batch(_request("failure-retry"))
    second_item = store.claim_next_item(second_batch.batch_id)
    assert second_item is not None
    with pytest.raises(BatchExecutionError):
        runner(second_item, lambda: False)

    assert (source.calls, onboarding.calls) == (2, 2)
    assert store.get_cache(derived_key) is not None
    assert store.get_cache(result_key) is None


def test_cache_key_identity_matrix_covers_source_and_validation_inputs(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    batch, _ = store.create_batch(_request("identity-matrix"))
    item = store.claim_next_item(batch.batch_id)
    assert item is not None

    def configured_runner(**overrides: object) -> PinnedBatchItemRunner:
        values: dict[str, object] = {
            "store": store,
            "source": Source(),
            "onboarding": Onboarding(),
            "gates": BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
            "parser_identity": "parser-v1",
            "embedding_identity": "embedding-v1",
            "chat_model": "chat-v1",
            "prompt_version": "prompt-v1",
            "output_schema_version": "schema-v1",
            "validation_version": "validation-v1",
            "analysis_max_output_tokens": 8192,
            "token_estimator_version": "tokens-v1",
            "termination_validation_version": "termination-v1",
        }
        values.update(overrides)
        return PinnedBatchItemRunner(**values)  # type: ignore[arg-type]

    baseline = configured_runner()
    baseline_derived, baseline_result = baseline._cache_keys(item, None)
    source_changes = (
        (
            baseline,
            replace(item, input=replace(item.input, commit_sha="b" * 40)),
        ),
        (
            baseline,
            replace(item, input=replace(item.input, include=("docs/**",))),
        ),
        (configured_runner(parser_identity="parser-v2"), item),
        (configured_runner(embedding_identity="embedding-v2"), item),
    )
    for changed_runner, changed_item in source_changes:
        derived, result = changed_runner._cache_keys(changed_item, None)
        assert derived != baseline_derived
        assert result != baseline_result

    validation_changes = (
        configured_runner(chat_model="chat-v2"),
        configured_runner(prompt_version="prompt-v2"),
        configured_runner(output_schema_version="schema-v2"),
        configured_runner(validation_version="validation-v2"),
        configured_runner(analysis_max_output_tokens=16384),
        configured_runner(token_estimator_version="tokens-v2"),
        configured_runner(termination_validation_version="termination-v2"),
    )
    for changed_runner in validation_changes:
        derived, result = changed_runner._cache_keys(item, None)
        assert derived == baseline_derived
        assert result != baseline_result


def test_cache_key_tracks_model_pair_and_output_policy_identity(tmp_path, monkeypatch) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    batch, _ = store.create_batch(_request("pair-identity"))
    item = store.claim_next_item(batch.batch_id)
    assert item is not None
    runner = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )
    baseline_pair = _pair("chat-a", 1)
    chat_changed = replace(baseline_pair, chat_model_id="chat-b")
    embedding_changed = replace(
        baseline_pair,
        embedding_identity=replace(
            baseline_pair.embedding_identity,
            model_id="embedding-b",
        ),
    )

    baseline_derived, baseline_result = runner._cache_keys(item, baseline_pair)
    chat_derived, chat_result = runner._cache_keys(item, chat_changed)
    embedding_derived, embedding_result = runner._cache_keys(item, embedding_changed)

    assert chat_derived == baseline_derived
    assert chat_result != baseline_result
    assert embedding_derived != baseline_derived
    assert embedding_result != baseline_result

    monkeypatch.setattr(batch_execution, "ANALYSIS_OUTPUT_POLICY_VERSION", "policy-next")
    policy_derived, policy_result = runner._cache_keys(item, baseline_pair)
    assert policy_derived == baseline_derived
    assert policy_result != baseline_result


def test_analysis_cache_key_tracks_output_budget_and_validation_policy(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    request = _request("cache-policy")
    batch, _created = store.create_batch(request)
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    baseline = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        analysis_max_output_tokens=8192,
        token_estimator_version="utf8-bytes-v1",
        termination_validation_version="finish-reason-length-reject-v1",
    )
    changed_budget = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        analysis_max_output_tokens=16384,
        token_estimator_version="utf8-bytes-v1",
        termination_validation_version="finish-reason-length-reject-v1",
    )
    changed_termination_policy = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        analysis_max_output_tokens=8192,
        token_estimator_version="utf8-bytes-v1",
        termination_validation_version="finish-reason-length-reject-v2",
    )

    baseline_derived, baseline_result = baseline._cache_keys(claimed, None)
    budget_derived, budget_result = changed_budget._cache_keys(claimed, None)
    termination_derived, termination_result = changed_termination_policy._cache_keys(claimed, None)

    assert baseline_derived == budget_derived
    assert baseline_result != budget_result
    assert baseline_derived == termination_derived
    assert baseline_result != termination_result


class _ChatRuntime:
    def __init__(self, capabilities: ProviderCapabilities) -> None:
        self._capabilities = capabilities

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities


class _AnalysisRuntime:
    def __init__(self, capabilities: ProviderCapabilities) -> None:
        self.chat = _ChatRuntime(capabilities)


def test_analysis_cache_key_tracks_effective_provider_context_and_output_caps(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    batch, _created = store.create_batch(_request("cache-capability"))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    runner = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        analysis_max_output_tokens=8192,
    )
    wide = _AnalysisRuntime(ProviderCapabilities(False, True, True, True, True, 32768, 16384))
    narrow = _AnalysisRuntime(ProviderCapabilities(False, True, True, True, True, 8000, 8000))

    wide_derived, wide_result = runner._cache_keys(claimed, None, wide)  # type: ignore[arg-type]
    narrow_derived, narrow_result = runner._cache_keys(claimed, None, narrow)  # type: ignore[arg-type]

    assert wide_derived == narrow_derived
    assert wide_result != narrow_result


def test_runner_rejects_budget_different_from_onboarding(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()

    with pytest.raises(ValueError, match="match onboarding"):
        PinnedBatchItemRunner(
            store=BatchRuntimeStore(database),
            source=Source(),  # type: ignore[arg-type]
            onboarding=BudgetedOnboarding(8192),  # type: ignore[arg-type]
            gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
            analysis_max_output_tokens=16384,
        )


def test_runner_uses_the_pair_persisted_with_the_claimed_batch(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    source = Source()
    onboarding = Onboarding()
    original = _pair("chat-a", 1)
    runner = PinnedBatchItemRunner(
        store=store,
        source=source,  # type: ignore[arg-type]
        onboarding=onboarding,  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
        runtime_resolver=lambda pair: f"runtime:{pair.chat_model_id}",  # type: ignore[arg-type]
    )
    request = _request("frozen-pair")
    request = BatchCreateRequest(
        plan_id=request.plan_id,
        selection_hash=request.selection_hash,
        idempotency_key=request.idempotency_key,
        items=request.items,
        analysis_model_pair=original.safe_dict(),
    )

    batch, _created = store.create_batch(request)
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    assert claimed.analysis_model_pair == original.safe_dict()

    result = runner(claimed, lambda: False)

    assert result["repository"]["slug"] == "octocat/demo"
    assert onboarding.providers == ["runtime:chat-a"]


@pytest.mark.parametrize("reason", ["NO_ELIGIBLE_CONTENT", "PROVIDER_OUTPUT_LIMIT_REACHED"])
def test_runner_preserves_allowlisted_onboarding_failure_reason(tmp_path, reason: str) -> None:
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    store = BatchRuntimeStore(database)
    request = _request("safe-reason")
    batch, _ = store.create_batch(request)
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    runner = PinnedBatchItemRunner(
        store=store,
        source=Source(),  # type: ignore[arg-type]
        onboarding=Onboarding(
            GuidedOnboardingError(
                "CONFIG_INVALID",
                reason=reason,
            )
        ),  # type: ignore[arg-type]
        gates=BatchStageGates(BatchCapacity(1, 1, 2, 1, 4)),
    )

    with pytest.raises(BatchExecutionError) as error:
        runner(claimed, lambda: False)

    assert error.value.code == "CONFIG_INVALID"
    assert error.value.reason == reason
