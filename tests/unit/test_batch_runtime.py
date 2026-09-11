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
) -> BatchCreateRequest:
    return BatchCreateRequest(
        plan_id="plan-safe-id",
        selection_hash=_hash(selection),
        idempotency_key=key,
        maximum_generation_attempts=maximum_generation_attempts,
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
    batch, created = store.create_batch(
        replace(_request(), analysis_model_pair=pair.safe_dict())
    )

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

    assert error.value.code == "VALIDATION_ERROR"
    snapshot = store.get_batch(batch.batch_id)
    assert snapshot.items[0].state == "needs_retry_confirmation"
    assert store.claim_next_item(batch.batch_id) is None


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
    assert resumed.execution_budget_seconds == 83


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
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_cache_entries SET payload_json = '{}' WHERE cache_key = ?", (key,)
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
