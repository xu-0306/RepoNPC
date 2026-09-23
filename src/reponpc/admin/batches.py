"""Batch orchestration over the durable scheduler and bounded GitHub preflight.

This module is the composition boundary: it retains only short-lived safe
preflight metadata in memory, while all recoverable job/item/event/cache state
lives in ``runtime.sqlite``. Public GitHub source access is anonymous; the
separate writeback client is outside this boundary.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from reponpc.admin.analysis_selection import AnalysisModelPair
from reponpc.admin.batch_resolver import (
    BatchCapacity,
    BatchPreflightPlan,
    BatchPreflightPlanner,
    BatchResolverError,
    CachePrediction,
    RepositorySelection,
)
from reponpc.admin.batch_runtime import (
    BatchCreateRequest,
    BatchItemInput,
    BatchRuntimeError,
    BatchRuntimeStore,
    BatchSnapshot,
    ClaimedBatchItem,
    reanalysis_plan_id,
    reanalysis_request_hash,
)
from reponpc.admin.onboarding import (
    ANALYSIS_MAX_OUTPUT_TOKENS,
    ANALYSIS_OUTPUT_POLICY_VERSION,
    ANALYSIS_OUTPUT_SCHEMA_VERSION,
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_TERMINATION_VALIDATION_VERSION,
    ANALYSIS_TIMEOUT_SECONDS,
    ANALYSIS_TOKEN_ESTIMATOR_VERSION,
    analysis_generation_policy_identity,
    validate_analysis_output_budget,
)

SAFE_BATCH_ERROR_REASONS = frozenset(
    {
        "NO_ELIGIBLE_CONTENT",
        "PROVIDER_OUTPUT_SCHEMA_INVALID",
        "PROVIDER_OUTPUT_LIMIT_REACHED",
        "PROVIDER_EVIDENCE_ID_INVALID",
        "PROVIDER_PERSONAL_INFERENCE_REJECTED",
    }
)


class BatchExecutionError(RuntimeError):
    """Safe worker failure with no upstream body/path/token detail."""

    def __init__(
        self,
        code: str,
        *,
        reason: str | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.reason = reason if reason in SAFE_BATCH_ERROR_REASONS else None
        self.retry_after_seconds = retry_after_seconds
        super().__init__("analysis batch item execution failed")


class BatchItemRunner(Protocol):
    def __call__(
        self, item: ClaimedBatchItem, cancelled: Callable[[], bool]
    ) -> dict[str, object]: ...


class BatchStageGates:
    """Process-local stage caps shared by preflight and every worker.

    SQLite persists what may resume; semaphores intentionally do not survive a
    process restart because their only purpose is limiting contemporaneous
    in-flight work.  The configured capacities are validated by
    :class:`BatchCapacity` before gates are constructed.
    """

    def __init__(self, capacity: BatchCapacity) -> None:
        self._github = threading.BoundedSemaphore(capacity.github_requests)
        self._archive = threading.BoundedSemaphore(capacity.archive_staging)
        self._index = threading.BoundedSemaphore(capacity.index_work)

    @contextmanager
    def github_request(self):
        with self._github:
            yield

    @contextmanager
    def archive_staging(self):
        with self._archive:
            yield

    @contextmanager
    def index_work(self):
        with self._index:
            yield


@dataclass(frozen=True, slots=True)
class BatchPreflightInput:
    selections: tuple[RepositorySelection, ...]


@dataclass(frozen=True, slots=True)
class _StoredPlan:
    plan: BatchPreflightPlan
    selections: tuple[RepositorySelection, ...]
    analysis_pair: AnalysisModelPair | None
    analysis_policy_identity: str


class AnalysisBatchService:
    """Own preflight, idempotent creation, background dispatch, and actions."""

    def __init__(
        self,
        *,
        store: BatchRuntimeStore,
        planner: BatchPreflightPlanner,
        provider_ready_supplier: Callable[[], bool],
        capacity: BatchCapacity,
        runner: BatchItemRunner,
        parser_identity: str = "parser-v1",
        embedding_identity: str = "embedding-runtime",
        chat_model: str = "chat-runtime",
        prompt_version: str = ANALYSIS_PROMPT_VERSION,
        output_schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION,
        validation_version: str = "validation-v1",
        analysis_max_output_tokens: int = ANALYSIS_MAX_OUTPUT_TOKENS,
        analysis_timeout_seconds: int = int(ANALYSIS_TIMEOUT_SECONDS),
        analysis_generation_attempts: int = 3,
        token_estimator_version: str = ANALYSIS_TOKEN_ESTIMATOR_VERSION,
        termination_validation_version: str = ANALYSIS_TERMINATION_VALIDATION_VERSION,
        stage_gates: BatchStageGates | None = None,
        analysis_pair_supplier: Callable[[], AnalysisModelPair | None] | None = None,
        analysis_policy_supplier: Callable[[AnalysisModelPair | None], str] | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._planner = planner
        self._provider_ready_supplier = provider_ready_supplier
        self._capacity = capacity
        self._runner = runner
        self._parser_identity = parser_identity
        self._embedding_identity = embedding_identity
        self._chat_model = chat_model
        self._prompt_version = prompt_version
        self._output_schema_version = output_schema_version
        self._validation_version = validation_version
        validate_analysis_output_budget(analysis_max_output_tokens)
        if not 1 <= analysis_timeout_seconds <= 7200:
            raise ValueError("analysis timeout must be between one second and two hours")
        if not 1 <= analysis_generation_attempts <= 10:
            raise ValueError("analysis generation attempts must be between one and ten")
        runner_budget = getattr(runner, "analysis_max_output_tokens", None)
        if runner_budget is not None and runner_budget != analysis_max_output_tokens:
            raise ValueError("analysis output budget must match batch runner")
        self._analysis_max_output_tokens = analysis_max_output_tokens
        self._analysis_timeout_seconds = analysis_timeout_seconds
        self._analysis_generation_attempts = analysis_generation_attempts
        self._token_estimator_version = token_estimator_version
        self._termination_validation_version = termination_validation_version
        self._stage_gates = stage_gates or BatchStageGates(capacity)
        self._analysis_pair_supplier = analysis_pair_supplier
        self._analysis_policy_supplier = analysis_policy_supplier
        self._now = now
        self._plans: dict[str, _StoredPlan] = {}
        self._plans_lock = threading.RLock()
        self._workers: dict[str, threading.Thread] = {}
        self._workers_lock = threading.RLock()

    def preflight(self, request: BatchPreflightInput) -> BatchPreflightPlan:
        """Resolve exact public commits without starting source/model work."""

        try:
            policies = {selection.slug: selection for selection in request.selections}
            analysis_pair = self._analysis_pair()
            analysis_policy = self._analysis_policy(analysis_pair)
            with self._stage_gates.github_request():
                plan = self._planner.create(
                    selections=request.selections,
                    cache_prediction=lambda repository: self._cache_prediction(
                        repository,
                        policies[repository.slug],
                        analysis_pair,
                        analysis_policy,
                    ),
                    provider=_provider_readiness(
                        self._provider_ready_supplier()
                        and (self._analysis_pair_supplier is None or analysis_pair is not None)
                    ),
                    capacity=self._capacity,
                )
        except BatchResolverError:
            raise
        with self._plans_lock:
            self._plans[plan.plan_id] = _StoredPlan(
                plan,
                request.selections,
                analysis_pair,
                analysis_policy,
            )
            self._prune_expired_plans_locked()
        return plan

    def create(
        self,
        *,
        plan_id: str,
        selections: Sequence[RepositorySelection],
        idempotency_key: str,
    ) -> tuple[BatchSnapshot, bool]:
        """Create a persisted batch from an unexpired exact-selection plan."""

        existing = self._store.idempotent_create(
            idempotency_key=idempotency_key,
            plan_id=plan_id,
            selections=selections,
        )
        if existing is not None:
            return existing, False
        with self._plans_lock:
            stored = self._plans.get(plan_id)
            self._prune_expired_plans_locked()
        if stored is None or stored.plan.expires_at <= self._utc_now():
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        if tuple(selections) != stored.selections:
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        analysis_pair = self._analysis_pair()
        if (
            analysis_pair != stored.analysis_pair
            or self._analysis_policy(analysis_pair) != stored.analysis_policy_identity
        ):
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        plan = stored.plan
        if plan.blockers:
            codes = {blocker.code for blocker in plan.blockers}
            if "GITHUB_RATE_LIMITED" in codes:
                raise BatchRuntimeError("GITHUB_RATE_LIMITED")
            if "RATE_LIMITED" in codes:
                raise BatchRuntimeError("GITHUB_RATE_LIMITED")
            if "MODEL_UNAVAILABLE" in codes:
                raise BatchRuntimeError("MODEL_UNAVAILABLE")
            raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
        by_slug = {repository.slug: repository for repository in plan.repositories}
        items: list[BatchItemInput] = []
        for selection in stored.selections:
            repository = by_slug.get(selection.slug)
            if repository is None:
                raise BatchRuntimeError("ANALYSIS_PLAN_STALE")
            items.append(
                BatchItemInput(
                    slug=selection.slug,
                    ref=selection.ref,
                    include=selection.include,
                    exclude=selection.exclude,
                    commit_sha=repository.commit_sha,
                )
            )
        snapshot, created = self._store.create_batch(
            BatchCreateRequest(
                plan_id=plan.plan_id,
                selection_hash=plan.selection_hash,
                idempotency_key=idempotency_key,
                items=tuple(items),
                maximum_generation_attempts=plan.maximum_generation_attempts,
                execution_budget_seconds=self._analysis_timeout_seconds,
                analysis_model_pair=(
                    stored.analysis_pair.safe_dict() if stored.analysis_pair is not None else None
                ),
            )
        )
        if created:
            self._start_worker(snapshot.batch_id)
        return snapshot, created

    def active(self) -> BatchSnapshot:
        snapshot = self._store.active_batch()
        return self._store.get_batch(
            snapshot.batch_id,
            execution_budget_seconds=self._analysis_timeout_seconds,
            maximum_generation_attempts=self._analysis_generation_attempts,
        )

    def get(self, batch_id: str) -> BatchSnapshot:
        return self._store.get_batch(
            batch_id,
            execution_budget_seconds=self._analysis_timeout_seconds,
            maximum_generation_attempts=self._analysis_generation_attempts,
        )

    def events(self, batch_id: str, *, after_event_id: int | None):
        return self._store.events_after(batch_id, after_event_id=after_event_id)

    def action(self, batch_id: str, *, action: str) -> BatchSnapshot:
        if action == "retry":
            snapshot = self._store.retry_items(
                batch_id,
                execution_budget_seconds=self._analysis_timeout_seconds,
                maximum_generation_attempts=self._analysis_generation_attempts,
            )
        else:
            snapshot = self._store.transition_batch(batch_id, action=action)
        if snapshot.state == "running":
            self._start_worker(batch_id)
        return snapshot

    def reanalyze(
        self,
        batch_id: str,
        *,
        item_ids: Sequence[str],
        idempotency_key: str,
        model_selection: str = "frozen",
        confirm_model_change: bool = False,
        expected_selection_generation: int | None = None,
    ) -> tuple[BatchSnapshot, bool]:
        """Create one explicit successor round without mutating source results."""

        if model_selection not in {"frozen", "current"}:
            raise BatchRuntimeError("VALIDATION_ERROR")
        existing = self._store.idempotent_reanalysis(
            idempotency_key=idempotency_key,
            source_batch_id=batch_id,
            item_ids=item_ids,
            model_selection=model_selection,
            confirm_model_change=confirm_model_change,
            expected_selection_generation=expected_selection_generation,
        )
        if existing is not None:
            return existing, False
        source = self._store.reanalysis_source(
            batch_id,
            item_ids=item_ids,
            execution_budget_seconds=self._analysis_timeout_seconds,
            maximum_generation_attempts=self._analysis_generation_attempts,
        )
        pair = source.analysis_model_pair
        if model_selection == "current":
            current = self._analysis_pair()
            if current is None:
                raise BatchRuntimeError("MODEL_UNAVAILABLE")
            if expected_selection_generation != current.selection_generation:
                raise BatchRuntimeError("ANALYSIS_MODEL_SELECTION_STALE")
            current_pair = current.safe_dict()
            if current_pair != pair and not confirm_model_change:
                raise BatchRuntimeError("ANALYSIS_MODEL_CHANGE_CONFIRMATION_REQUIRED")
            pair = current_pair
        elif pair is None and self._analysis_pair_supplier is not None:
            raise BatchRuntimeError("MODEL_UNAVAILABLE")

        selection_hash = hashlib.sha256(
            json.dumps(
                {
                    "source_batch_id": source.source_batch_id,
                    "analysis_round": source.analysis_round,
                    "source_item_ids": [item.source_item_id for item in source.items],
                    "model_pair": pair,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        snapshot, created = self._store.create_batch(
            BatchCreateRequest(
                plan_id=reanalysis_plan_id(
                    source_batch_id=source.source_batch_id,
                    analysis_round=source.analysis_round,
                    model_selection=model_selection,
                    confirm_model_change=confirm_model_change,
                    expected_selection_generation=expected_selection_generation,
                ),
                selection_hash=selection_hash,
                idempotency_key=idempotency_key,
                items=source.items,
                maximum_generation_attempts=self._analysis_generation_attempts,
                execution_budget_seconds=self._analysis_timeout_seconds,
                analysis_model_pair=pair,
                source_batch_id=source.source_batch_id,
                analysis_round=source.analysis_round,
                idempotency_request_hash=reanalysis_request_hash(
                    source_batch_id=source.source_batch_id,
                    item_ids=item_ids,
                    model_selection=model_selection,
                    confirm_model_change=confirm_model_change,
                    expected_selection_generation=expected_selection_generation,
                ),
            )
        )
        if created:
            self._start_worker(snapshot.batch_id)
        return snapshot, created

    def analyze_one_compatibility(
        self,
        *,
        selection: RepositorySelection,
        cancelled: Callable[[], bool],
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Adapt the legacy one-repository request to the durable batch path."""

        effective_timeout = (
            float(self._analysis_timeout_seconds) if timeout_seconds is None else timeout_seconds
        )
        if effective_timeout <= 0:
            raise BatchRuntimeError("VALIDATION_ERROR")
        plan = self.preflight(BatchPreflightInput((selection,)))
        snapshot, _created = self.create(
            plan_id=plan.plan_id,
            selections=(selection,),
            idempotency_key=secrets.token_urlsafe(24),
        )
        deadline = time.monotonic() + effective_timeout
        while time.monotonic() < deadline:
            if cancelled():
                self.action(snapshot.batch_id, action="cancel")
                raise BatchRuntimeError("CANCELLED")
            snapshot = self.get(snapshot.batch_id)
            item = snapshot.items[0]
            if item.state == "complete" and item.result is not None:
                return item.result
            if snapshot.state in {"cancelled", "completed_with_errors", "failed"}:
                raise BatchRuntimeError(item.error_code or "ANALYSIS_FAILED")
            threading.Event().wait(0.05)
        # The HTTP compatibility wait is bounded independently from the durable
        # batch.  A request timeout must not turn into an implicit owner cancel:
        # the active batch remains observable and recoverable through the batch
        # snapshot/event API until the owner explicitly cancels it.
        raise BatchRuntimeError("PROVIDER_TIMEOUT")

    def recover(self) -> tuple[str, ...]:
        """Recover non-generation leases and resume any runnable batch."""

        self._store.cleanup_expired()
        recovered = self._store.recover_after_restart()
        try:
            active = self._store.active_batch()
        except BatchRuntimeError:
            return recovered
        if active.state in {"queued", "running"}:
            self._start_worker(active.batch_id)
        return recovered

    def cleanup_expired(self) -> None:
        """Remove expired safe batch data without touching live leases."""

        self._store.cleanup_expired()

    @property
    def stage_gates(self) -> BatchStageGates:
        """Expose shared bounded stage permits to the configured runner."""

        return self._stage_gates

    def _start_worker(self, batch_id: str) -> None:
        with self._workers_lock:
            current = self._workers.get(batch_id)
            if current is not None and current.is_alive():
                return
            worker = threading.Thread(
                target=self._run_batch,
                args=(batch_id,),
                daemon=True,
                name=f"reponpc-analysis-{batch_id[:8]}",
            )
            self._workers[batch_id] = worker
            worker.start()

    def _analysis_pair(self) -> AnalysisModelPair | None:
        if self._analysis_pair_supplier is None:
            return None
        try:
            return self._analysis_pair_supplier()
        except Exception:
            return None

    def _analysis_policy(self, pair: AnalysisModelPair | None) -> str:
        if self._analysis_policy_supplier is not None:
            try:
                identity = self._analysis_policy_supplier(pair)
            except Exception:
                identity = ""
            if isinstance(identity, str) and identity:
                return identity
        return analysis_generation_policy_identity(
            self._analysis_max_output_tokens,
            None,
        )

    def _run_batch(self, batch_id: str) -> None:
        # Work-item concurrency is bounded independently from the runner's
        # GitHub/archive/index/provider semaphores.  The runner receives a
        # cancellation predicate and must release its staging in a finally.
        futures: set[Future[None]] = set()
        with ThreadPoolExecutor(
            max_workers=self._capacity.whole_job_items,
            thread_name_prefix="reponpc-analysis-item",
        ) as executor:
            while True:
                futures = {future for future in futures if not future.done()}
                try:
                    snapshot = self._store.get_batch(batch_id)
                except BatchRuntimeError:
                    return
                if snapshot.state not in {"queued", "running"}:
                    break
                while len(futures) < self._capacity.whole_job_items:
                    claimed = self._store.claim_next_item(batch_id)
                    if claimed is None:
                        break
                    futures.add(executor.submit(self._run_item, claimed))
                if not futures:
                    # All remaining work may be rate-paused or require an
                    # explicit reconnect/retry.  Park until the durable retry
                    # timestamp instead of polling GitHub or spinning.
                    retry_at = self._store.next_rate_retry_at(batch_id)
                    if retry_at is None:
                        return
                    seconds = max(0.1, (retry_at - self._utc_now()).total_seconds())
                    threading.Event().wait(min(seconds, 60.0))
                    continue
                for future in tuple(futures):
                    try:
                        future.result(timeout=0.05)
                    except TimeoutError:
                        continue
                    except Exception:
                        # `_run_item` maps all expected failures to durable
                        # state. An unexpected worker error is contained there.
                        continue

    def _run_item(self, item: ClaimedBatchItem) -> None:
        def cancelled() -> bool:
            try:
                return self._store.get_batch(item.batch_id).state in {
                    "cancelling",
                    "cancelled",
                }
            except BatchRuntimeError:
                return True

        try:
            if cancelled():
                self._store.cancel_item(item)
                return
            result = self._runner(item, cancelled)
            if cancelled():
                self._store.cancel_item(item)
                return
            self._store.complete_item(item, result=result)
        except BatchExecutionError as exc:
            if exc.code == "CANCELLED":
                self._store.cancel_item(item)
            elif exc.code == "GITHUB_RATE_LIMITED":
                retry = max(1, exc.retry_after_seconds or 60)
                self._store.advance_item(
                    item,
                    state="waiting_rate_limit",
                    error_code=exc.code,
                    retry_at=self._utc_now().replace(microsecond=0) + timedelta(seconds=retry),
                )
            elif exc.code == "GENERATION_DISPATCHED_INTERRUPTED":
                self._store.fail_item(
                    item,
                    code=exc.code,
                    reason=exc.reason,
                    retry_confirmation=True,
                )
            else:
                self._store.fail_item(item, code=exc.code, reason=exc.reason)
        except BatchRuntimeError as exc:
            # Stage transitions enforce cancellation and the per-item budgets
            # transactionally.  A rejected transition must stop the runner;
            # it must never fall through to a provider call or be rewritten as
            # an unrelated generic analysis failure.
            if exc.code in {"CANCELLED", "ANALYSIS_LEASE_LOST", "NOT_FOUND"}:
                return
            if exc.code in {
                "ANALYSIS_TIMEOUT",
                "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED",
            }:
                self._store.fail_item(item, code=exc.code)
                return
            self._store.fail_item(item, code="ANALYSIS_FAILED")
        except Exception:
            self._store.fail_item(item, code="ANALYSIS_FAILED")

    def _cache_prediction(
        self,
        repository,
        selection: RepositorySelection,
        pair: AnalysisModelPair | None,
        policy_identity: str | None = None,
    ) -> CachePrediction:
        # A deliberately strict key includes every identity component known at
        # preflight. The derived hit is an identity marker, not reopenable index
        # content; only a validated-result hit currently skips execution work.
        derived_key = _cache_key(
            repository.slug,
            repository.commit_sha,
            _selection_policy_identity(selection),
            self._parser_identity,
            pair.cache_embedding_identity() if pair is not None else self._embedding_identity,
        )
        result_key = _cache_key(
            derived_key,
            pair.cache_chat_identity() if pair is not None else self._chat_model,
            self._prompt_version,
            self._output_schema_version,
            self._validation_version,
            ANALYSIS_OUTPUT_POLICY_VERSION,
            str(self._analysis_max_output_tokens),
            self._token_estimator_version,
            self._termination_validation_version,
            policy_identity or self._analysis_policy(pair),
        )
        return CachePrediction(
            derived_index_hit=self._store.get_cache(derived_key) is not None,
            validated_analysis_hit=self._store.get_cache(result_key) is not None,
        )

    def _prune_expired_plans_locked(self) -> None:
        now = self._utc_now()
        for plan_id, stored in tuple(self._plans.items()):
            if stored.plan.expires_at <= now:
                self._plans.pop(plan_id, None)

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("batch clock must be timezone-aware")
        return value.astimezone(UTC)


def _provider_readiness(ready: bool):
    # Avoid importing provider runtime into this pure orchestration boundary.
    from reponpc.admin.batch_resolver import ProviderReadiness

    return ProviderReadiness(ready=ready, safe_reason=None if ready else "MODEL_UNAVAILABLE")


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _selection_policy_identity(selection: RepositorySelection) -> str:
    return json.dumps(
        {"include": selection.include, "exclude": selection.exclude},
        sort_keys=True,
        separators=(",", ":"),
    )
