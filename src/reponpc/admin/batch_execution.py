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
from reponpc.domain.evidence import EVIDENCE_ID_RE
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
            if cached is not None:
                cached_result = None
                if (
                    cached.cache_kind == "validated_analysis"
                    and cached.derived_index_key == derived_key
                    and cached.metadata == self._result_cache_metadata(item, pair, runtime)
                ):
                    cached_result = _cached_result(cached.payload, item)
                if cached_result is not None:
                    return cached_result
                self._store.delete_cache(result_key)
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
                metadata=self._result_cache_metadata(item, pair, runtime),
                payload=_cacheable_result(result, item),
            )
            return result
        except BatchExecutionError:
            raise
        except BatchResolverError as exc:
            raise _batch_error(exc) from exc
        except GuidedOnboardingError as exc:
            raise _onboarding_error(exc) from exc
        except BatchRuntimeError as exc:
            # A lost lease means another terminal action already owns the
            # outcome.  Never attempt another upstream/provider call.
            if exc.code in {
                "ANALYSIS_TIMEOUT",
                "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED",
            }:
                raise BatchExecutionError(exc.code) from None
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

    def _result_cache_metadata(
        self,
        item: ClaimedBatchItem,
        pair: AnalysisModelPair | None,
        runtime: ProviderRuntime | None,
    ) -> dict[str, object]:
        return {
            "repository": item.input.slug,
            "commit": item.input.commit_sha,
            "chat_model": pair.cache_chat_identity() if pair is not None else self._chat_model,
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
        }


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


def _cacheable_result(result: dict[str, object], item: ClaimedBatchItem) -> dict[str, object]:
    """Persist validated model result metadata but never repository text/excerpts."""

    cached = _parse_cached_payload(
        {
            "repository": result.get("repository"),
            "inferences": result.get("inferences"),
            "skipped_summary": result.get("skipped_summary"),
        },
        item,
    )
    if cached is None:
        raise BatchExecutionError("ANALYSIS_FAILED")
    return cached


def _cached_result(payload: dict[str, object], item: ClaimedBatchItem) -> dict[str, object] | None:
    cached = _parse_cached_payload(payload, item)
    if cached is None:
        return None
    # Cached results contain no raw evidence excerpts. A later analysis may
    # rebuild sources to refresh displayed evidence, but cache reuse is safe
    # because outputs are already schema-validated and commit-bound.
    return {**cached, "facts": []}


def _parse_cached_payload(
    payload: dict[str, object], item: ClaimedBatchItem
) -> dict[str, object] | None:
    if set(payload) != {"repository", "inferences", "skipped_summary"}:
        return None
    repository = payload.get("repository")
    inferences = payload.get("inferences")
    skipped = payload.get("skipped_summary")
    if not isinstance(repository, dict) or not _valid_cached_repository(repository, item):
        return None
    if not isinstance(inferences, list) or len(inferences) > 6:
        return None
    normalized_inferences: list[dict[str, object]] = []
    for inference in inferences:
        normalized = _valid_cached_inference(inference)
        if normalized is None:
            return None
        normalized_inferences.append(normalized)
    normalized_skipped = _valid_cached_skipped_summary(skipped)
    if normalized_skipped is None:
        return None
    return {
        "repository": dict(repository),
        "inferences": normalized_inferences,
        "skipped_summary": normalized_skipped,
    }


def _valid_cached_repository(value: object, item: ClaimedBatchItem) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = {"slug", "commit_sha", "default_branch", "html_url"}
    if not {"slug", "commit_sha"}.issubset(value) or not set(value).issubset(allowed):
        return False
    if value.get("slug") != item.input.slug or value.get("commit_sha") != item.input.commit_sha:
        return False
    return all(
        isinstance(field, str) and 0 < len(field) <= maximum
        for key, maximum in (("slug", 201), ("commit_sha", 40))
        if (field := value.get(key)) is not None
    ) and all(
        optional is None or (isinstance(optional, str) and 0 < len(optional) <= maximum)
        for key, maximum in (("default_branch", 255), ("html_url", 2048))
        if (optional := value.get(key)) is not None
    )


def _valid_cached_inference(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or set(value) != {
        "evidence_class",
        "statement",
        "supporting_evidence_ids",
    }:
        return None
    statement = value.get("statement")
    evidence_ids = value.get("supporting_evidence_ids")
    if value.get("evidence_class") != "MODEL_INFERENCE":
        return None
    if not isinstance(statement, dict) or set(statement) != {"zh-TW", "en"}:
        return None
    if not all(isinstance(text, str) and 0 < len(text) <= 2000 for text in statement.values()):
        return None
    if (
        not isinstance(evidence_ids, list)
        or not 1 <= len(evidence_ids) <= 8
        or not all(
            isinstance(evidence_id, str) and EVIDENCE_ID_RE.fullmatch(evidence_id)
            for evidence_id in evidence_ids
        )
    ):
        return None
    return {
        "evidence_class": "MODEL_INFERENCE",
        "statement": {"zh-TW": statement["zh-TW"], "en": statement["en"]},
        "supporting_evidence_ids": list(evidence_ids),
    }


def _valid_cached_skipped_summary(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict) or set(value) != {"count", "reasons"}:
        return None
    count = value.get("count")
    reasons = value.get("reasons")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return None
    if (
        not isinstance(reasons, list)
        or len(reasons) > 20
        or not all(isinstance(reason, str) and 0 < len(reason) <= 100 for reason in reasons)
    ):
        return None
    return {"count": count, "reasons": list(reasons)}
