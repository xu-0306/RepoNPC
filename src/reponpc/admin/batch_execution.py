"""Pinned archive execution for durable guided-analysis batch items.

This is deliberately separate from the legacy REST/tree/blob resolver. A
batch item is rebuilt only from its persisted immutable commit and selection
policy, then fetched anonymously as one exact-SHA archive.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager

from reponpc.admin.analysis_selection import AnalysisModelPair, AnalysisSelectionError
from reponpc.admin.batch_resolver import (
    GITHUB_ARCHIVE_BASE_URL,
    BatchResolverError,
    GitHubArchiveSource,
    ResolvedRepository,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchRuntimeStore, ClaimedBatchItem
from reponpc.admin.batches import BatchExecutionError, BatchStageGates
from reponpc.admin.onboarding import (
    ANALYSIS_MAX_OUTPUT_TOKENS,
    ANALYSIS_OUTPUT_POLICY_VERSION,
    ANALYSIS_OUTPUT_SCHEMA_VERSION,
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_TERMINATION_VALIDATION_VERSION,
    ANALYSIS_TOKEN_ESTIMATOR_VERSION,
    GuidedOnboardingError,
    GuidedOnboardingService,
    analysis_generation_policy_identity,
    validate_analysis_output_budget,
)
from reponpc.providers.runtime import ProviderRuntime


class PinnedBatchItemRunner:
    """Fetch and analyze exact-SHA public archives with bounded stage caps."""

    def __init__(
        self,
        *,
        store: BatchRuntimeStore,
        source: GitHubArchiveSource,
        onboarding: GuidedOnboardingService,
        gates: BatchStageGates,
        parser_identity: str = "parser-v1",
        embedding_identity: str = "embedding-runtime",
        chat_model: str = "chat-runtime",
        prompt_version: str = ANALYSIS_PROMPT_VERSION,
        output_schema_version: str = ANALYSIS_OUTPUT_SCHEMA_VERSION,
        validation_version: str = "validation-v1",
        analysis_max_output_tokens: int = ANALYSIS_MAX_OUTPUT_TOKENS,
        token_estimator_version: str = ANALYSIS_TOKEN_ESTIMATOR_VERSION,
        termination_validation_version: str = ANALYSIS_TERMINATION_VALIDATION_VERSION,
        runtime_resolver: Callable[[AnalysisModelPair], ProviderRuntime | None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._source = source
        self._onboarding = onboarding
        self._gates = gates
        self._parser_identity = parser_identity
        self._embedding_identity = embedding_identity
        self._chat_model = chat_model
        self._prompt_version = prompt_version
        self._output_schema_version = output_schema_version
        self._validation_version = validation_version
        validate_analysis_output_budget(analysis_max_output_tokens)
        onboarding_budget = getattr(onboarding, "analysis_max_output_tokens", None)
        if onboarding_budget is not None and onboarding_budget != analysis_max_output_tokens:
            raise ValueError("analysis output budget must match onboarding")
        self._analysis_max_output_tokens = analysis_max_output_tokens
        self._token_estimator_version = token_estimator_version
        self._termination_validation_version = termination_validation_version
        self._runtime_resolver = runtime_resolver
        self._monotonic = monotonic

    @property
    def analysis_max_output_tokens(self) -> int:
        """Expose the budget shared with the onboarding generation service."""

        return self._analysis_max_output_tokens

    def __call__(self, item: ClaimedBatchItem, cancelled: Callable[[], bool]) -> dict[str, object]:
        if item.execution_budget_seconds <= 0:
            raise BatchExecutionError("ANALYSIS_TIMEOUT")
        deadline = _ExtendableDeadline(
            seconds=item.execution_budget_seconds,
            monotonic=self._monotonic,
        )
        try:
            if cancelled():
                raise BatchExecutionError("CANCELLED")
            pair = self._frozen_pair(item)
            runtime = self._frozen_runtime(pair)
            derived_key, result_key = self._cache_keys(item, pair, runtime)
            cached = self._store.get_cache(result_key)
            if (
                cached is not None
                and cached.cache_kind == "validated_analysis"
                and _cache_matches_item(cached.payload, item)
            ):
                return _cached_result(cached.payload)
            repository = _immutable_repository(item)
            self._store.advance_item(item, state="fetching_source")
            with self._excluded_wait(item, deadline, self._gates.archive_staging):
                snapshot = self._source.fetch(
                    repository=repository,
                    cancel_requested=cancelled,
                    deadline=deadline.value(),
                    monotonic=self._monotonic,
                )
            result = self._onboarding.analyze_resolved_repository(
                snapshot=snapshot,
                include=item.input.include,
                exclude=item.input.exclude,
                cancel_requested=cancelled,
                stage_changed=lambda stage: self._store.advance_item(item, state=stage),
                index_permit=lambda: self._excluded_wait(item, deadline, self._gates.index_work),
                execution_deadline=deadline.value,
                wait_excluded=lambda seconds: self._exclude_wait_seconds(item, deadline, seconds),
                providers=runtime,
            )
            self._store.advance_item(item, state="cleaning_up")
            self._store.put_cache(
                cache_key=derived_key,
                cache_kind="derived_index",
                derived_index_key=derived_key,
                metadata={
                    "repository": item.input.slug,
                    "commit": item.input.commit_sha,
                    "parser": self._parser_identity,
                    "embedding": (
                        pair.cache_embedding_identity()
                        if pair is not None
                        else self._embedding_identity
                    ),
                },
                payload={"commit": item.input.commit_sha, "validated": True},
            )
            self._store.put_cache(
                cache_key=result_key,
                cache_kind="validated_analysis",
                derived_index_key=derived_key,
                metadata={
                    "repository": item.input.slug,
                    "commit": item.input.commit_sha,
                    "chat_model": (
                        pair.cache_chat_identity() if pair is not None else self._chat_model
                    ),
                    "prompt_version": self._prompt_version,
                    "output_schema_version": self._output_schema_version,
                    "validation_version": self._validation_version,
                    "analysis_output_policy_version": ANALYSIS_OUTPUT_POLICY_VERSION,
                    "analysis_max_output_tokens": self._analysis_max_output_tokens,
                    "token_estimator_version": self._token_estimator_version,
                    "termination_validation_version": self._termination_validation_version,
                    "analysis_generation_policy": analysis_generation_policy_identity(
                        self._analysis_max_output_tokens,
                        runtime,
                    ),
                },
                payload=_cacheable_result(result),
            )
            return result
        except BatchExecutionError:
            raise
        except BatchResolverError as exc:
            raise _batch_error(exc) from exc
        except GuidedOnboardingError as exc:
            raise _onboarding_error(exc) from exc
        except BatchRuntimeError:
            # A lost lease means another terminal action already owns the
            # outcome.  Never attempt another upstream/provider call.
            raise BatchExecutionError("CANCELLED") from None

    @contextmanager
    def _excluded_wait(
        self,
        item: ClaimedBatchItem,
        deadline: _ExtendableDeadline,
        permit: Callable[[], AbstractContextManager[object]],
    ):
        started = self._monotonic()
        with permit():
            waited = max(0.0, self._monotonic() - started)
            self._exclude_wait_seconds(item, deadline, waited)
            yield

    def _exclude_wait_seconds(
        self,
        item: ClaimedBatchItem,
        deadline: _ExtendableDeadline,
        seconds: float,
    ) -> None:
        deadline.extend(seconds)
        self._store.exclude_item_wait(item, seconds=seconds)

    def _frozen_pair(self, item: ClaimedBatchItem) -> AnalysisModelPair | None:
        if item.analysis_model_pair is None:
            return None
        try:
            return AnalysisModelPair.from_safe_dict(item.analysis_model_pair)
        except AnalysisSelectionError as exc:
            raise BatchExecutionError("MODEL_UNAVAILABLE") from exc

    def _frozen_runtime(self, pair: AnalysisModelPair | None) -> ProviderRuntime | None:
        if self._runtime_resolver is None:
            return None
        if pair is None:
            raise BatchExecutionError("MODEL_UNAVAILABLE")
        runtime = self._runtime_resolver(pair)
        if runtime is None:
            raise BatchExecutionError("MODEL_UNAVAILABLE")
        return runtime

    def _cache_keys(
        self,
        item: ClaimedBatchItem,
        pair: AnalysisModelPair | None,
        runtime: ProviderRuntime | None = None,
    ) -> tuple[str, str]:
        policy = json.dumps(
            {"include": item.input.include, "exclude": item.input.exclude},
            separators=(",", ":"),
            sort_keys=True,
        )
        derived = _cache_key(
            item.input.slug,
            item.input.commit_sha,
            policy,
            self._parser_identity,
            pair.cache_embedding_identity() if pair is not None else self._embedding_identity,
        )
        return derived, _cache_key(
            derived,
            pair.cache_chat_identity() if pair is not None else self._chat_model,
            self._prompt_version,
            self._output_schema_version,
            self._validation_version,
            ANALYSIS_OUTPUT_POLICY_VERSION,
            str(self._analysis_max_output_tokens),
            self._token_estimator_version,
            self._termination_validation_version,
            analysis_generation_policy_identity(self._analysis_max_output_tokens, runtime),
        )


def _immutable_repository(item: ClaimedBatchItem) -> ResolvedRepository:
    slug = item.input.slug
    owner, name = slug.split("/", 1)
    commit = item.input.commit_sha
    return ResolvedRepository(
        slug=slug,
        node_id=f"batch-{hashlib.sha256(slug.encode()).hexdigest()[:16]}",
        default_branch="unknown",
        commit_sha=commit,
        is_archived=False,
        archive_url=f"{GITHUB_ARCHIVE_BASE_URL}/repos/{owner}/{name}/tarball/{commit}",
    )


def _cache_matches_item(payload: dict[str, object], item: ClaimedBatchItem) -> bool:
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        return False
    return (
        repository.get("slug") == item.input.slug
        and repository.get("commit_sha") == item.input.commit_sha
    )


def _batch_error(error: BatchResolverError) -> BatchExecutionError:
    if error.code in {"RATE_LIMITED", "GITHUB_RATE_LIMITED"}:
        return BatchExecutionError(
            "GITHUB_RATE_LIMITED", retry_after_seconds=error.retry_after_seconds
        )
    if error.code == "CANCELLED":
        return BatchExecutionError(error.code)
    return BatchExecutionError(error.code)


def _onboarding_error(error: GuidedOnboardingError) -> BatchExecutionError:
    if error.code in {"CANCELLED", "RATE_LIMITED", "PROVIDER_TIMEOUT"}:
        return BatchExecutionError(
            "CANCELLED" if error.code == "CANCELLED" else error.code,
            reason=error.reason,
            retry_after_seconds=error.retry_after_seconds,
        )
    return BatchExecutionError(error.code, reason=error.reason)


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


class _ExtendableDeadline:
    """An active-work deadline that can exclude scheduler semaphore waits."""

    def __init__(self, *, seconds: float, monotonic: Callable[[], float]) -> None:
        self._monotonic = monotonic
        self._deadline = monotonic() + seconds

    def value(self) -> float:
        return self._deadline

    def extend(self, seconds: float) -> None:
        self._deadline += max(0.0, seconds)


def _cacheable_result(result: dict[str, object]) -> dict[str, object]:
    """Persist validated model result metadata but never repository text/excerpts."""

    repository = result.get("repository")
    inferences = result.get("inferences")
    skipped = result.get("skipped_summary")
    if (
        not isinstance(repository, dict)
        or not isinstance(inferences, list)
        or not isinstance(skipped, dict)
    ):
        raise BatchExecutionError("ANALYSIS_FAILED")
    return {
        "repository": repository,
        "inferences": inferences,
        "skipped_summary": skipped,
    }


def _cached_result(payload: dict[str, object]) -> dict[str, object]:
    required = ("repository", "inferences", "skipped_summary")
    if any(key not in payload for key in required):
        raise BatchExecutionError("ANALYSIS_FAILED")
    # Cached results contain no raw evidence excerpts. A later analysis may
    # rebuild sources to refresh displayed evidence, but cache reuse is safe
    # because outputs are already schema-validated and commit-bound.
    return {**payload, "facts": []}
