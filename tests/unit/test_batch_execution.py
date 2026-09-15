from __future__ import annotations

import hashlib

import pytest

from reponpc.admin.analysis_selection import AnalysisModelPair
from reponpc.admin.batch_execution import PinnedBatchItemRunner
from reponpc.admin.batch_resolver import BatchCapacity
from reponpc.admin.batch_runtime import BatchCreateRequest, BatchItemInput, BatchRuntimeStore
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
            "inferences": [{"statement": {"zh-TW": "摘要", "en": "Summary"}}],
            "skipped_summary": {"count": 0, "reasons": []},
        }


class BudgetedOnboarding(Onboarding):
    def __init__(self, budget: int) -> None:
        super().__init__()
        self.analysis_max_output_tokens = budget


def _request(key: str) -> BatchCreateRequest:
    return BatchCreateRequest(
        plan_id=f"plan-{key}",
        selection_hash=hashlib.sha256(b"selection").hexdigest(),
        idempotency_key=key,
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
    raw_cache = database.connection()
    with raw_cache as connection:
        serialized = connection.execute(
            "SELECT payload_json FROM analysis_cache_entries "
            "WHERE cache_kind = 'validated_analysis'"
        ).fetchone()[0]
    assert "untrusted repository source" not in serialized
    assert "cache-test-token" not in serialized


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
