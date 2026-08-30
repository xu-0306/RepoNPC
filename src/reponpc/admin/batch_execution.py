"""Pinned archive execution for durable guided-analysis batch items.

This is deliberately separate from the legacy REST/tree/blob resolver.  A
batch item is rebuilt only from its persisted immutable commit and selection
policy, then fetched through the selected public-read credential as one exact
SHA archive.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable

from reponpc.admin.batch_resolver import (
    GITHUB_ARCHIVE_BASE_URL,
    BatchResolverError,
    GitHubArchiveSource,
    PublicReadCredential,
    ResolvedRepository,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchRuntimeStore, ClaimedBatchItem
from reponpc.admin.batches import BatchExecutionError, BatchStageGates
from reponpc.admin.onboarding import GuidedOnboardingError, GuidedOnboardingService


class PinnedBatchItemRunner:
    """Fetch and analyze items using one selected credential and stage caps."""

    def __init__(
        self,
        *,
        store: BatchRuntimeStore,
        source: GitHubArchiveSource,
        onboarding: GuidedOnboardingService,
        credentials_supplier: Callable[[], Iterable[PublicReadCredential]],
        gates: BatchStageGates,
        parser_identity: str = "parser-v1",
        embedding_identity: str = "embedding-runtime",
        chat_model: str = "chat-runtime",
        prompt_version: str = "onboarding-prompt-v1",
        output_schema_version: str = "analysis-schema-v1",
        validation_version: str = "validation-v1",
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._source = source
        self._onboarding = onboarding
        self._credentials_supplier = credentials_supplier
        self._gates = gates
        self._parser_identity = parser_identity
        self._embedding_identity = embedding_identity
        self._chat_model = chat_model
        self._prompt_version = prompt_version
        self._output_schema_version = output_schema_version
        self._validation_version = validation_version
        self._monotonic = monotonic

    def __call__(self, item: ClaimedBatchItem, cancelled: Callable[[], bool]) -> dict[str, object]:
        if item.execution_budget_seconds <= 0:
            raise BatchExecutionError("PROVIDER_TIMEOUT")
        deadline = self._monotonic() + item.execution_budget_seconds
        try:
            if cancelled():
                raise BatchExecutionError("CANCELLED")
            derived_key, result_key = self._cache_keys(item)
            cached = self._store.get_cache(result_key)
            if (
                cached is not None
                and cached.cache_kind == "validated_analysis"
                and _cache_matches_item(cached.payload, item)
            ):
                return _cached_result(cached.payload)
            credential = self._selected_credential(item.batch_id)
            repository = _immutable_repository(item)
            self._store.advance_item(item, state="fetching_source")
            with self._gates.archive_staging():
                snapshot = self._source.fetch(
                    repository=repository,
                    credential=credential,
                    cancel_requested=cancelled,
                    deadline=deadline,
                    monotonic=self._monotonic,
                )
            result = self._onboarding.analyze_resolved_repository(
                snapshot=snapshot,
                include=item.input.include,
                exclude=item.input.exclude,
                cancel_requested=cancelled,
                stage_changed=lambda stage: self._store.advance_item(item, state=stage),
                index_permit=self._gates.index_work,
                execution_deadline=deadline,
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
                    "embedding": self._embedding_identity,
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
                    "chat_model": self._chat_model,
                    "prompt_version": self._prompt_version,
                    "output_schema_version": self._output_schema_version,
                    "validation_version": self._validation_version,
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

    def _selected_credential(self, batch_id: str) -> PublicReadCredential:
        selected_id = self._store.selected_credential_id(batch_id)
        for credential in self._credentials_supplier():
            if credential.credential_id == selected_id:
                if credential.status == "ready":
                    return credential
                break
        # Deliberately no fallback, including another OAuth/PAT row and every
        # writeback credential. Reconnection must be explicit.
        raise BatchExecutionError("GITHUB_CONNECTION_REQUIRED")

    def _cache_keys(self, item: ClaimedBatchItem) -> tuple[str, str]:
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
            self._embedding_identity,
        )
        return derived, _cache_key(
            derived,
            self._chat_model,
            self._prompt_version,
            self._output_schema_version,
            self._validation_version,
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
    if error.code in {"GITHUB_CONNECTION_REQUIRED", "CANCELLED"}:
        return BatchExecutionError(error.code)
    return BatchExecutionError(error.code)


def _onboarding_error(error: GuidedOnboardingError) -> BatchExecutionError:
    if error.code in {"CANCELLED", "RATE_LIMITED", "PROVIDER_TIMEOUT"}:
        return BatchExecutionError(
            "CANCELLED" if error.code == "CANCELLED" else error.code,
            retry_after_seconds=error.retry_after_seconds,
        )
    return BatchExecutionError(error.code)


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


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
