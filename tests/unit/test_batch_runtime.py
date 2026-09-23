from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from reponpc.admin.analysis_selection import AnalysisModelPair
from reponpc.admin.batch_resolver import (
    GitHubRateLimiter,
    GitHubRateResource,
    RepositoryMetadataHint,
    RepositorySelection,
    ResolvedRepository,
)
from reponpc.admin.batch_runtime import (
    BatchCreateRequest,
    BatchItemInput,
    BatchRuntimeError,
    BatchRuntimeStore,
    SQLiteGitHubRateStateStore,
    SQLiteGitHubResolutionCache,
)
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 16, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, **kwargs: int) -> None:
        self.value += timedelta(**kwargs)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _request(
    *,
    slug: str = "octocat/demo",
    key: str = "idempotency",
    selection: str = "selection",
    maximum_generation_attempts: int = 1,
    execution_budget_seconds: int = 1800,
) -> BatchCreateRequest:
    return BatchCreateRequest(
        plan_id="plan-safe-id",
        selection_hash=_hash(selection),
        idempotency_key=key,
        maximum_generation_attempts=maximum_generation_attempts,
        execution_budget_seconds=execution_budget_seconds,
        items=(
            BatchItemInput(
                slug=slug,
                ref="main",
                include=("src/**",),
                exclude=("dist/**",),
                commit_sha="a" * 40,
            ),
        ),
    )


def _store(tmp_path, clock: Clock) -> BatchRuntimeStore:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    return BatchRuntimeStore(database, now=clock)


def test_idempotency_active_owner_boundary_and_safe_events(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)

    first, created = store.create_batch(_request())
    repeated, created_again = store.create_batch(_request())

    assert created is True
    assert created_again is False
    assert repeated.batch_id == first.batch_id
    assert store.events_after(first.batch_id, after_event_id=None)[0].payload == {
        "items": 1,
        "state": "queued",
    }
    with pytest.raises(BatchRuntimeError) as active:
        store.create_batch(_request(slug="octocat/other", key="other-key"))
    assert active.value.code == "ANALYSIS_BATCH_ACTIVE"


def test_batch_accepts_a_frozen_pair_with_legal_empty_embedding_prefixes(tmp_path) -> None:
    pair = AnalysisModelPair(
        1,
        "chat-a",
        "chat-connection",
        1,
        "ollama",
        "chat-model",
        "embed-a",
        "embedding-connection",
        1,
        "ollama",
        EmbeddingIdentity("ollama", "embed-model", 2, True, "", ""),
    )

    store = _store(tmp_path, Clock())
    batch, created = store.create_batch(replace(_request(), analysis_model_pair=pair.safe_dict()))

    assert created is True
    assert batch.state == "queued"
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    assert claimed.analysis_model_pair == pair.safe_dict()


def test_item_completion_transitions_to_durable_terminal_snapshot(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())

    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    assert claimed.input.include == ("src/**",)
    store.advance_item(claimed, state="fetching_source")
    store.advance_item(claimed, state="filtering")
    store.complete_item(
        claimed,
        result={"repository": {"slug": "octocat/demo", "commit_sha": "a" * 40}},
    )

    terminal = store.get_batch(batch.batch_id)
    assert terminal.state == "completed"
    assert terminal.items[0].state == "complete"
    assert terminal.items[0].result == {
        "repository": {"slug": "octocat/demo", "commit_sha": "a" * 40}
    }
    events = store.events_after(batch.batch_id, after_event_id=0)
    assert [event.event_id for event in events] == sorted(event.event_id for event in events)
    assert all("token" not in event.payload for event in events)


@pytest.mark.parametrize(
    "reason", ["PROVIDER_OUTPUT_SCHEMA_INVALID", "PROVIDER_OUTPUT_LIMIT_REACHED"]
)
def test_item_failure_reason_survives_snapshot_event_and_restart(tmp_path, reason: str) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    store.fail_item(
        claimed,
        code="PROVIDER_ERROR",
        reason=reason,
    )

    restarted = BatchRuntimeStore(database, now=clock)
    terminal = restarted.get_batch(batch.batch_id)
    assert terminal.items[0].error_code == "PROVIDER_ERROR"
    assert terminal.items[0].error_reason == reason
    assert restarted.events_after(batch.batch_id, after_event_id=0)[-2].payload == {
        "state": "failed",
        "error_code": "PROVIDER_ERROR",
        "error_reason": reason,
    }


def test_pause_cancel_retry_and_restart_never_auto_retries_generation(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request(maximum_generation_attempts=2))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    assert store.transition_batch(batch.batch_id, action="pause").state == "paused"
    assert store.claim_next_item(batch.batch_id) is None
    assert store.transition_batch(batch.batch_id, action="resume").state == "running"
    store.advance_item(claimed, state="generating")
    recovered = store.recover_after_restart()

    assert claimed.item_id in recovered
    after_restart = store.get_batch(batch.batch_id)
    assert after_restart.items[0].state == "needs_retry_confirmation"
    retried = store.retry_items(batch.batch_id)
    assert retried.state == "running"
    assert retried.items[0].state == "queued"
    assert store.transition_batch(batch.batch_id, action="cancel").state == "cancelled"


def test_recovery_of_a_cancelling_batch_never_resurrects_leased_work(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    assert store.transition_batch(batch.batch_id, action="cancel").state == "cancelling"
    store.recover_after_restart()

    recovered = store.get_batch(batch.batch_id)
    assert recovered.state == "cancelled"
    assert recovered.items[0].state == "cancelled"
    assert store.claim_next_item(batch.batch_id) is None


def test_cancellation_intercepts_the_next_stage_before_work_can_continue(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    assert store.transition_batch(batch.batch_id, action="cancel").state == "cancelling"
    with pytest.raises(BatchRuntimeError) as error:
        store.advance_item(claimed, state="fetching_source")

    assert error.value.code == "CANCELLED"
    cancelled = store.get_batch(batch.batch_id)
    assert cancelled.state == "cancelled"
    assert cancelled.items[0].state == "cancelled"


def test_retry_items_does_not_exceed_the_generation_attempt_limit(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request(maximum_generation_attempts=1))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="GENERATION_DISPATCHED_INTERRUPTED", retry_confirmation=True)

    with pytest.raises(BatchRuntimeError) as error:
        store.retry_items(batch.batch_id)

    assert error.value.code == "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED"
    snapshot = store.get_batch(batch.batch_id)
    assert snapshot.items[0].state == "needs_retry_confirmation"
    assert snapshot.items[0].retryable is False
    assert snapshot.items[0].reanalyzable is True
    assert snapshot.items[0].retry_blocker == "ATTEMPTS_EXHAUSTED"
    assert snapshot.items[0].failure_stage == "generating"
    assert store.claim_next_item(batch.batch_id) is None


def test_effective_current_policy_matches_snapshot_and_retry_transaction(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request(maximum_generation_attempts=1))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")

    frozen = store.get_batch(batch.batch_id)
    current = store.get_batch(batch.batch_id, maximum_generation_attempts=3)
    assert frozen.items[0].retryable is False
    assert current.items[0].retryable is True
    assert current.maximum_generation_attempts == 1
    assert current.recovery_maximum_generation_attempts == 3

    retried = store.retry_items(batch.batch_id, maximum_generation_attempts=3)
    assert retried.items[0].generation_attempt_count == 1
    assert retried.items[0].state == "queued"


def test_reanalysis_is_hidden_until_every_source_item_is_terminal(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    first = _request(maximum_generation_attempts=1).items[0]
    request = replace(
        _request(maximum_generation_attempts=1),
        items=(first, replace(first, slug="octocat/other", commit_sha="b" * 40)),
    )
    batch, _ = store.create_batch(request)
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")

    snapshot = store.get_batch(batch.batch_id)
    failed = next(item for item in snapshot.items if item.item_id == claimed.item_id)
    assert snapshot.state == "running"
    assert failed.retryable is False
    assert failed.reanalyzable is False
    with pytest.raises(BatchRuntimeError) as error:
        store.reanalysis_source(batch.batch_id, item_ids=(claimed.item_id,))
    assert error.value.code == "ANALYSIS_SOURCE_BATCH_NOT_TERMINAL"


def test_cancelled_batch_cannot_be_revived_by_retry(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())
    assert store.transition_batch(batch.batch_id, action="cancel").state == "cancelled"

    with pytest.raises(BatchRuntimeError) as error:
        store.retry_items(batch.batch_id)
    assert error.value.code == "ANALYSIS_RETRY_NOT_AVAILABLE"


def test_retry_reports_another_active_batch_as_a_conflict(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.fail_item(claimed, code="PROVIDER_ERROR")
    active, _ = store.create_batch(
        _request(slug="octocat/other", key="other-key", selection="other-selection")
    )
    assert active.state == "queued"

    with pytest.raises(BatchRuntimeError) as error:
        store.retry_items(batch.batch_id)
    assert error.value.code == "ANALYSIS_BATCH_ACTIVE"


def test_terminal_elapsed_time_freezes_and_blocks_same_round_retry(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request(execution_budget_seconds=10))
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="fetching_source")
    clock.advance(seconds=12)
    store.fail_item(claimed, code="ANALYSIS_TIMEOUT")

    terminal = store.get_batch(batch.batch_id)
    clock.advance(minutes=5)
    later = store.get_batch(batch.batch_id)

    assert terminal.items[0].execution_elapsed_seconds == 12
    assert later.items[0].execution_elapsed_seconds == 12
    assert later.items[0].retryable is False
    assert later.items[0].reanalyzable is True
    assert later.items[0].retry_blocker == "EXECUTION_BUDGET_EXHAUSTED"
    assert later.items[0].failure_stage == "fetching_source"
    with pytest.raises(BatchRuntimeError) as error:
        store.retry_items(batch.batch_id)
    assert error.value.code == "ANALYSIS_EXECUTION_BUDGET_EXHAUSTED"


def test_reanalysis_source_preserves_commit_policy_and_lineage(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    original, _ = store.create_batch(_request(maximum_generation_attempts=1))
    claimed = store.claim_next_item(original.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")

    source = store.reanalysis_source(
        original.batch_id,
        item_ids=(claimed.item_id,),
    )
    successor_request = BatchCreateRequest(
        plan_id="successor-plan",
        selection_hash=_hash("successor-selection"),
        idempotency_key="successor-idempotency",
        maximum_generation_attempts=1,
        execution_budget_seconds=1800,
        items=source.items,
        source_batch_id=source.source_batch_id,
        analysis_round=source.analysis_round,
        analysis_model_pair=source.analysis_model_pair,
    )
    successor, created = store.create_batch(successor_request)
    repeated, repeated_created = store.create_batch(
        replace(successor_request, idempotency_key="second-browser-key")
    )

    assert created is True
    assert repeated_created is False
    assert repeated.batch_id == successor.batch_id
    assert successor.source_batch_id == original.batch_id
    assert successor.analysis_round == 2
    assert successor.items[0].source_item_id == claimed.item_id
    assert successor.items[0].commit_sha == "a" * 40
    assert successor.items[0].execution_elapsed_seconds == 0
    assert successor.items[0].generation_attempt_count == 0
    assert store.get_batch(original.batch_id).items[0].state == "failed"


def test_source_item_with_successor_cannot_be_retried_under_a_larger_policy(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    original, _ = store.create_batch(_request(maximum_generation_attempts=1))
    claimed = store.claim_next_item(original.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")
    source = store.reanalysis_source(original.batch_id, item_ids=(claimed.item_id,))
    successor, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="successor-plan",
            selection_hash=_hash("successor-selection"),
            idempotency_key="successor-key",
            maximum_generation_attempts=1,
            items=source.items,
            source_batch_id=source.source_batch_id,
            analysis_round=source.analysis_round,
        )
    )
    successor_item = store.claim_next_item(successor.batch_id)
    assert successor_item is not None
    store.fail_item(successor_item, code="PROVIDER_ERROR")

    projected = store.get_batch(original.batch_id, maximum_generation_attempts=3)
    assert projected.maximum_generation_attempts == 1
    assert projected.recovery_maximum_generation_attempts == 3
    assert projected.items[0].retryable is False
    assert projected.items[0].reanalyzable is False
    assert projected.items[0].retry_blocker == "SUCCESSOR_EXISTS"
    with pytest.raises(BatchRuntimeError) as error:
        store.retry_items(original.batch_id, maximum_generation_attempts=3)
    assert error.value.code == "ANALYSIS_SUCCESSOR_CONFLICT"
    preserved = store.get_batch(original.batch_id)
    assert preserved.items[0].state == "failed"
    assert preserved.items[0].error_code == "PROVIDER_ERROR"


def test_source_successor_marker_survives_child_cleanup_and_other_item_activity(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    first = _request(maximum_generation_attempts=1).items[0]
    original, _ = store.create_batch(
        replace(
            _request(maximum_generation_attempts=1),
            items=(
                first,
                replace(first, slug="octocat/other", commit_sha="b" * 40),
            ),
        )
    )
    failed_ids: list[str] = []
    for _ in range(2):
        claimed = store.claim_next_item(original.batch_id)
        assert claimed is not None
        failed_ids.append(claimed.item_id)
        store.advance_item(claimed, state="generating")
        store.fail_item(claimed, code="PROVIDER_ERROR")

    source = store.reanalysis_source(original.batch_id, item_ids=(failed_ids[0],))
    child, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="successor-cleanup-plan",
            selection_hash=_hash("successor-cleanup"),
            idempotency_key="successor-cleanup-key",
            maximum_generation_attempts=1,
            items=source.items,
            source_batch_id=source.source_batch_id,
            analysis_round=source.analysis_round,
            idempotency_request_hash=_hash("successor-cleanup-request"),
        )
    )
    child_item = store.claim_next_item(child.batch_id)
    assert child_item is not None
    store.fail_item(child_item, code="PROVIDER_ERROR")
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM analysis_batch_idempotency_receipts"
            ).fetchone()[0]
            == 1
        )
        connection.execute(
            "UPDATE analysis_batches SET expires_at = ? WHERE batch_id = ?",
            ((clock.value - timedelta(seconds=1)).isoformat(), child.batch_id),
        )
        connection.execute(
            "UPDATE analysis_batches SET expires_at = ? WHERE batch_id = ?",
            ((clock.value + timedelta(hours=1)).isoformat(), original.batch_id),
        )

    store.cleanup_expired()

    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM analysis_batch_idempotency_receipts"
            ).fetchone()[0]
            == 0
        )

    with pytest.raises(BatchRuntimeError) as missing_child:
        store.get_batch(child.batch_id)
    assert missing_child.value.code == "NOT_FOUND"
    projected = store.get_batch(original.batch_id, maximum_generation_attempts=2)
    assert projected.items[0].retry_blocker == "SUCCESSOR_EXISTS"
    assert projected.items[0].reanalyzable is False
    retried = store.retry_items(original.batch_id, maximum_generation_attempts=2)
    assert retried.items[0].state == "failed"
    assert retried.items[1].state == "queued"


def test_successor_items_cannot_overlap_across_different_requests(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    first = _request(maximum_generation_attempts=1).items[0]
    original, _ = store.create_batch(
        replace(
            _request(maximum_generation_attempts=1),
            items=(first, replace(first, slug="octocat/other", commit_sha="b" * 40)),
        )
    )
    source_item_ids: list[str] = []
    for _position in range(2):
        claimed = store.claim_next_item(original.batch_id)
        assert claimed is not None
        source_item_ids.append(claimed.item_id)
        store.advance_item(claimed, state="generating")
        store.fail_item(claimed, code="PROVIDER_ERROR")

    first_source = store.reanalysis_source(original.batch_id, item_ids=(source_item_ids[0],))
    store.create_batch(
        BatchCreateRequest(
            plan_id="successor-first",
            selection_hash=_hash("successor-first"),
            idempotency_key="successor-first-key",
            maximum_generation_attempts=1,
            items=first_source.items,
            source_batch_id=first_source.source_batch_id,
            analysis_round=first_source.analysis_round,
        )
    )
    with pytest.raises(BatchRuntimeError) as error:
        store.reanalysis_source(
            original.batch_id,
            item_ids=tuple(source_item_ids),
        )
    assert error.value.code == "ANALYSIS_REANALYZE_NOT_AVAILABLE"


def test_explicit_retry_can_adopt_the_current_larger_execution_policy(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(
        _request(maximum_generation_attempts=1, execution_budget_seconds=120)
    )
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_TIMEOUT")

    retried = store.retry_items(
        batch.batch_id,
        execution_budget_seconds=1800,
        maximum_generation_attempts=3,
    )
    reclaimed = store.claim_next_item(batch.batch_id)

    assert retried.maximum_generation_attempts == 3
    assert retried.items[0].execution_budget_seconds == 1800
    assert reclaimed is not None
    assert reclaimed.execution_budget_seconds == 1800


def test_execution_elapsed_and_remaining_budget_survive_restart(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    clock.advance(seconds=37)
    restarted = BatchRuntimeStore(database, now=clock)
    restarted.recover_after_restart()
    resumed = restarted.claim_next_item(batch.batch_id)

    assert resumed is not None
    assert resumed.execution_elapsed_seconds == 37
    assert resumed.execution_budget_seconds == 1763


def test_scheduler_wait_is_excluded_from_active_execution_budget(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None

    clock.advance(seconds=30)
    store.exclude_item_wait(claimed, seconds=20)
    store.advance_item(claimed, state="fetching_source")

    snapshot = store.get_batch(batch.batch_id)
    assert snapshot.items[0].execution_elapsed_seconds == 10
    assert snapshot.items[0].execution_budget_seconds == 1800


def test_idempotency_key_reuse_rejects_a_different_batch_payload(tmp_path) -> None:
    clock = Clock()
    store = _store(tmp_path, clock)
    original, _ = store.create_batch(_request())

    with pytest.raises(BatchRuntimeError):
        store.create_batch(
            _request(
                slug="octocat/other",
                key="idempotency",
                selection="different-selection",
            )
        )

    assert store.get_batch(original.batch_id) == original


def test_cache_requires_integrity_and_expires_without_touching_batch(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    key = _hash("validated-result")
    derived = _hash("derived")

    store.put_cache(
        cache_key=key,
        cache_kind="validated_analysis",
        derived_index_key=derived,
        metadata={"commit": "a" * 40, "prompt": "v1"},
        payload={"validated": True},
        ttl=timedelta(seconds=30),
    )
    assert store.get_cache(key) is not None
    clock.advance(seconds=1)
    assert store.get_cache(key) is not None
    with database.connection() as connection:
        touched_at = connection.execute(
            "SELECT last_accessed_at FROM analysis_cache_entries WHERE cache_key = ?", (key,)
        ).fetchone()[0]
    assert touched_at == clock.value.isoformat().replace("+00:00", "Z")
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_cache_entries SET metadata_json = '{}' WHERE cache_key = ?", (key,)
        )
    assert store.get_cache(key) is None
    store.put_cache(
        cache_key=key,
        cache_kind="validated_analysis",
        derived_index_key=derived,
        metadata={"commit": "a" * 40},
        payload={"validated": True},
    )
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_cache_entries SET derived_index_key = ? WHERE cache_key = ?",
            (_hash("tampered-derived"), key),
        )
    assert store.get_cache(key) is None
    store.put_cache(
        cache_key=key,
        cache_kind="validated_analysis",
        derived_index_key=derived,
        metadata={"commit": "a" * 40},
        payload={"validated": True},
    )
    with database.connection() as connection:
        payload = connection.execute(
            "SELECT payload_json FROM analysis_cache_entries WHERE cache_key = ?", (key,)
        ).fetchone()[0]
        connection.execute(
            "UPDATE analysis_cache_entries SET payload_sha256 = ? WHERE cache_key = ?",
            (hashlib.sha256(payload.encode()).hexdigest(), key),
        )
    assert store.get_cache(key) is None
    store.put_cache(
        cache_key=key,
        cache_kind="validated_analysis",
        derived_index_key=derived,
        metadata={"commit": "a" * 40},
        payload={"validated": True},
        ttl=timedelta(seconds=1),
    )
    clock.advance(seconds=2)
    store.cleanup_expired()
    assert store.get_cache(key) is None


def test_delete_cache_rejects_invalid_keys_and_removes_exact_entry(tmp_path) -> None:
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database)
    key = _hash("delete-cache")
    store.put_cache(
        cache_key=key,
        cache_kind="derived_index",
        derived_index_key=key,
        metadata={"kind": "marker"},
        payload={"validated": False},
    )

    with pytest.raises(BatchRuntimeError) as invalid:
        store.delete_cache("not-a-hash")
    assert invalid.value.code == "VALIDATION_ERROR"

    store.delete_cache(key)
    assert store.get_cache(key) is None


def test_expired_source_results_are_bounded_while_active_successor_survives(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    original, _ = store.create_batch(_request(maximum_generation_attempts=1))
    claimed = store.claim_next_item(original.batch_id)
    assert claimed is not None
    store.advance_item(claimed, state="generating")
    store.fail_item(claimed, code="PROVIDER_ERROR")
    source = store.reanalysis_source(original.batch_id, item_ids=(claimed.item_id,))
    successor, _ = store.create_batch(
        BatchCreateRequest(
            plan_id="bounded-lineage-successor",
            selection_hash=_hash("bounded-lineage-successor"),
            idempotency_key="bounded-lineage-successor-key",
            maximum_generation_attempts=1,
            items=source.items,
            source_batch_id=source.source_batch_id,
            analysis_round=source.analysis_round,
        )
    )
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_batches SET expires_at = ? WHERE batch_id = ?",
            ((clock.value - timedelta(seconds=1)).isoformat(), original.batch_id),
        )

    store.cleanup_expired()

    with pytest.raises(BatchRuntimeError) as missing:
        store.get_batch(original.batch_id)
    assert missing.value.code == "NOT_FOUND"
    surviving = store.get_batch(successor.batch_id)
    assert surviving.state == "queued"
    assert surviving.source_batch_id == original.batch_id
    assert surviving.items[0].source_item_id == claimed.item_id
    assert surviving.items[0].commit_sha == "a" * 40


def test_expired_terminal_snapshot_is_removed_instead_of_returned(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    store = BatchRuntimeStore(database, now=clock)
    batch, _ = store.create_batch(_request())
    claimed = store.claim_next_item(batch.batch_id)
    assert claimed is not None
    store.fail_item(claimed, code="PROVIDER_ERROR")
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_batches SET expires_at = ? WHERE batch_id = ?",
            ((clock.value - timedelta(seconds=1)).isoformat(), batch.batch_id),
        )

    with pytest.raises(BatchRuntimeError) as expired:
        store.get_batch(batch.batch_id)

    assert expired.value.code == "NOT_FOUND"
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM analysis_batches WHERE batch_id = ?",
                (batch.batch_id,),
            ).fetchone()[0]
            == 0
        )


def test_github_rate_state_survives_runtime_restart_without_credentials(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    limiter = GitHubRateLimiter(
        safety_reserve=5,
        now=clock,
        persistence=SQLiteGitHubRateStateStore(database, now=clock),
    )
    limiter.observe(
        resource=GitHubRateResource.CORE,
        status=200,
        headers={
            "X-RateLimit-Resource": "core",
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset": str(int((clock.value + timedelta(minutes=2)).timestamp())),
        },
    )

    restarted = GitHubRateLimiter(
        safety_reserve=5,
        now=clock,
        persistence=SQLiteGitHubRateStateStore(database, now=clock),
    )
    budget, secondary = restarted.snapshot()

    assert budget.remaining == 5
    assert secondary is None
    assert restarted.admit(GitHubRateResource.CORE).allowed is False


def test_anonymous_resolution_cache_survives_restart_and_expires(tmp_path) -> None:
    clock = Clock()
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    selection = RepositorySelection("octocat/demo", ref="release")
    metadata = RepositoryMetadataHint("octocat/demo", "R_demo", "main", False)
    resolved = ResolvedRepository(
        slug="octocat/demo",
        node_id="R_demo",
        default_branch="main",
        commit_sha="a" * 40,
        is_archived=False,
        archive_url=f"https://api.github.com/repos/octocat/demo/tarball/{'a' * 40}",
    )
    cache = SQLiteGitHubResolutionCache(database, ttl=timedelta(seconds=30), now=clock)
    cache.save_metadata(metadata)
    cache.save_resolved(selection, resolved)

    restarted = SQLiteGitHubResolutionCache(database, ttl=timedelta(seconds=30), now=clock)
    assert restarted.metadata(selection.slug) == metadata
    assert restarted.resolved(selection) == resolved

    clock.advance(seconds=31)
    assert restarted.metadata(selection.slug) is None
    assert restarted.resolved(selection) is None
    with database.connection() as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM github_public_resolution_cache"
        ).fetchone()
    assert remaining is not None and remaining[0] == 0
