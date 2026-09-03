"""Durable frozen-profile reindex and last-known-good activation."""

from __future__ import annotations

import math
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileRegistry,
)
from reponpc.bundles.archive import BundleError, VerifiedBundle, verify_bundle_archive
from reponpc.bundles.manager import (
    ActivationTransition,
    BundleActivationError,
    BundleManager,
)
from reponpc.config.models import parse_public_config_bytes
from reponpc.indexing.github import GitHubSourceResolver, SourceResolutionError
from reponpc.indexing.pipeline import IndexPipelineError, build_index_bundle
from reponpc.indexing.sources import (
    EmbeddingProvider,
    ResolvedConfiguration,
    ResolvedRepository,
)
from reponpc.providers.contracts import ProviderError


class ReindexCancelled(RuntimeError):
    pass


class ReindexTimedOut(RuntimeError):
    pass


@dataclass(slots=True)
class ReindexCandidate:
    verified: VerifiedBundle
    workspace: Path


class FrozenProfileBuilder(Protocol):
    def __call__(
        self,
        profile: EmbeddingProfile,
        provider: EmbeddingProvider,
        cancel_requested: Callable[[], bool],
        deadline: float,
    ) -> ReindexCandidate: ...


class EmbeddingReindexCoordinator:
    """Own one bounded reindex lane and coordinate all mutable switch owners."""

    def __init__(
        self,
        *,
        registry: EmbeddingProfileRegistry,
        manager: BundleManager,
        builder: FrozenProfileBuilder,
        provider_transition: Callable[[EmbeddingProfile, EmbeddingProvider], Callable[[], None]],
        timeout_seconds: float = 30 * 60,
        monotonic: Callable[[], float] = time.monotonic,
        on_activated: Callable[[EmbeddingProfile, str], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("reindex timeout must be positive")
        self._registry = registry
        self._manager = manager
        self._builder = builder
        self._provider_transition = provider_transition
        self._timeout_seconds = timeout_seconds
        self._monotonic = monotonic
        self._on_activated = on_activated
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedding-reindex")
        self._lock = threading.RLock()
        self._futures: dict[str, Future[None]] = {}
        self._cancellations: dict[str, threading.Event] = {}
        self._closed = False

    def queue(self, profile_id: str) -> EmbeddingProfile:
        """Probe and either switch a compatible profile or queue a frozen reindex."""

        with self._lock:
            if self._closed:
                raise EmbeddingProfileError("SERVICE_NOT_READY")
            existing = self._futures.get(profile_id)
            if existing is not None and not existing.done():
                return self._registry.get(profile_id)
            if any(not future.done() for future in self._futures.values()):
                raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")

        profile = self._registry.probe(profile_id)
        if profile.last_error_code is not None:
            raise EmbeddingProfileError(profile.last_error_code)
        provider = self._registry.resolve_provider(profile)
        if provider is None or not isinstance(provider, EmbeddingProvider):
            raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED")

        if (
            profile.status == "ready"
            and self._manager.active_embedding_identity() == profile.identity
        ):
            rollback_provider = self._provider_transition(profile, provider)
            try:
                activated = self._registry.activate(profile_id)
            except Exception:
                rollback_provider()
                raise
            if self._on_activated is not None:
                bundle_id = self._manager.status().active_bundle_id
                if bundle_id is not None:
                    self._on_activated(activated, bundle_id)
            return activated

        frozen = self._registry.begin_reindex(profile_id)
        cancellation = threading.Event()
        with self._lock:
            if self._closed:
                self._registry.fail_reindex(
                    frozen.profile_id,
                    frozen.reindex_generation,
                    "EMBEDDING_REINDEX_CANCELLED",
                )
                raise EmbeddingProfileError("SERVICE_NOT_READY")
            self._cancellations[profile_id] = cancellation
            self._futures[profile_id] = self._executor.submit(
                self._run,
                frozen,
                provider,
                cancellation,
            )
        return self._registry.get(profile_id)

    def cancel(self, profile_id: str) -> bool:
        """Request cooperative cancellation of one known in-process generation."""

        with self._lock:
            cancellation = self._cancellations.get(profile_id)
            future = self._futures.get(profile_id)
            if cancellation is None or future is None or future.done():
                return False
            cancellation.set()
            return True

    def wait(self, profile_id: str, timeout: float | None = None) -> EmbeddingProfile:
        """Wait for a test/operator-owned in-process generation without exposing futures."""

        with self._lock:
            future = self._futures.get(profile_id)
        if future is not None:
            future.result(timeout=timeout)
        return self._registry.get(profile_id)

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for cancellation in self._cancellations.values():
                cancellation.set()
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _run(
        self,
        profile: EmbeddingProfile,
        provider: EmbeddingProvider,
        cancellation: threading.Event,
    ) -> None:
        candidate: ReindexCandidate | None = None
        deadline = self._monotonic() + self._timeout_seconds
        try:
            candidate = self._builder(
                profile,
                provider,
                cancellation.is_set,
                deadline,
            )
            _raise_if_stopped(cancellation.is_set, deadline, self._monotonic)
            bundle_id = candidate.verified.manifest.bundle_id

            def transition() -> ActivationTransition:
                profile_transition = self._registry.activate_reindexed(
                    profile.profile_id,
                    profile.reindex_generation,
                    bundle_id,
                )
                try:
                    rollback_provider = self._provider_transition(profile, provider)
                except Exception:
                    profile_transition.rollback()
                    raise

                def rollback() -> None:
                    rollback_provider()
                    profile_transition.rollback()

                return ActivationTransition(
                    rollback=rollback,
                    commit=profile_transition.commit,
                )

            self._manager.activate(
                candidate.verified,
                expected_embedding=profile.identity,
                state_transition=transition,
            )
            if self._on_activated is not None:
                self._on_activated(self._registry.get(profile.profile_id), bundle_id)
        except Exception as exc:
            self._registry.fail_reindex(
                profile.profile_id,
                profile.reindex_generation,
                _safe_reindex_error(exc),
            )
        finally:
            if candidate is not None:
                shutil.rmtree(candidate.workspace, ignore_errors=True)
            with self._lock:
                self._cancellations.pop(profile.profile_id, None)


class ProductionFrozenProfileBuilder:
    """Build from one immutable public GitHub snapshot and one frozen profile."""

    def __init__(
        self,
        *,
        data_directory: Path,
        config_repository: str,
        config_branch: str,
        github_api_url: str,
        max_bundle_bytes: int,
        source_resolver: GitHubSourceResolver | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._root = Path(data_directory) / "embedding-reindex"
        self._root.mkdir(parents=True, exist_ok=True)
        self._config_repository = config_repository
        self._config_branch = config_branch
        self._resolver = source_resolver or GitHubSourceResolver(api_base_url=github_api_url)
        self._max_bundle_bytes = max_bundle_bytes
        self._monotonic = monotonic

    def __call__(
        self,
        profile: EmbeddingProfile,
        provider: EmbeddingProvider,
        cancel_requested: Callable[[], bool],
        deadline: float,
    ) -> ReindexCandidate:
        workspace = Path(tempfile.mkdtemp(prefix="candidate-", dir=self._root))
        try:
            bounded = _BoundedResolver(
                self._resolver,
                cancel_requested=cancel_requested,
                deadline=deadline,
                monotonic=self._monotonic,
            )
            config_snapshot = bounded.resolve(
                slug=self._config_repository,
                ref=self._config_branch,
            )
            config_blob = next(
                (
                    blob
                    for blob in config_snapshot.blobs
                    if blob.path == "reponpc.yml" and blob.content is not None
                ),
                None,
            )
            if config_blob is None or config_blob.content is None:
                raise IndexPipelineError("configuration_revision_unavailable")
            _raise_if_stopped(cancel_requested, deadline, self._monotonic)
            config = parse_public_config_bytes(config_blob.content)
            config_path = workspace / "source" / "reponpc.yml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_bytes(config_blob.content)
            custom = config.character.custom
            if custom is not None:
                sprite_blob = next(
                    (
                        blob
                        for blob in config_snapshot.blobs
                        if blob.path == custom.sprite_path and blob.content is not None
                    ),
                    None,
                )
                if sprite_blob is None or sprite_blob.content is None:
                    raise IndexPipelineError("public_assets_unavailable")
                sprite_path = workspace / "source" / custom.sprite_path
                sprite_path.parent.mkdir(parents=True, exist_ok=True)
                sprite_path.write_bytes(sprite_blob.content)
            source = ResolvedConfiguration(
                repository_slug=config_snapshot.slug,
                commit_sha=config_snapshot.commit_sha,
                path="reponpc.yml",
                content=config_blob.content.decode("utf-8"),
                github_html_url=config_snapshot.github_html_url,
            )
            built = build_index_bundle(
                config_path,
                workspace / "build",
                resolver=bounded,
                embedding_provider=provider,
                configuration_source=source,
                built_at=datetime.now(UTC),
                embedding_identity_override=profile.identity,
            )
            _raise_if_stopped(cancel_requested, deadline, self._monotonic)
            verified = verify_bundle_archive(
                archive_path=built.archive_path,
                staging_directory=workspace / "candidate",
                expected_outer_sha256=built.archive_sha256,
                expected_embedding=profile.identity,
                max_bundle_bytes=self._max_bundle_bytes,
            )
            query = provider.embed_query(["RepoNPC semantic activation smoke"])
            if query.shape != (1, profile.dimension) or not all(
                math.isfinite(float(value)) for value in query.flat
            ):
                verified.close()
                raise IndexPipelineError("embedding_output_invalid")
            if not verified.index.hybrid_candidates(
                "retrieval",
                query_vector=query[0],
            ):
                verified.close()
                raise IndexPipelineError("bundle_smoke_query_failed")
            _raise_if_stopped(cancel_requested, deadline, self._monotonic)
            return ReindexCandidate(verified=verified, workspace=workspace)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise


@dataclass(frozen=True, slots=True)
class _BoundedResolver:
    delegate: GitHubSourceResolver
    cancel_requested: Callable[[], bool]
    deadline: float
    monotonic: Callable[[], float]

    def resolve(self, *, slug: str, ref: str | None) -> ResolvedRepository:
        _raise_if_stopped(self.cancel_requested, self.deadline, self.monotonic)
        return self.delegate.resolve(
            slug=slug,
            ref=ref,
            cancel_requested=self.cancel_requested,
            deadline=self.deadline,
        )


def _raise_if_stopped(
    cancel_requested: Callable[[], bool],
    deadline: float,
    monotonic: Callable[[], float],
) -> None:
    if cancel_requested():
        raise ReindexCancelled
    if monotonic() >= deadline:
        raise ReindexTimedOut


def _safe_reindex_error(error: Exception) -> str:
    if isinstance(error, ReindexCancelled):
        return "EMBEDDING_REINDEX_CANCELLED"
    if isinstance(error, ReindexTimedOut):
        return "EMBEDDING_REINDEX_TIMEOUT"
    if isinstance(error, EmbeddingProfileError):
        return error.code
    if isinstance(error, (BundleActivationError, BundleError)):
        return "EMBEDDING_ACTIVATION_FAILED"
    if isinstance(error, (IndexPipelineError, SourceResolutionError, ProviderError)):
        return "EMBEDDING_REINDEX_FAILED"
    return "EMBEDDING_REINDEX_FAILED"
