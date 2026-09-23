"""Durable frozen-profile reindex and last-known-good activation."""

from __future__ import annotations

import logging
import math
import shutil
import tempfile
import threading
import time
import traceback
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


class CancellableSourceResolver(Protocol):
    def resolve(
        self,
        *,
        slug: str,
        ref: str | None,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> ResolvedRepository: ...


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
        # A cancellation remains effective until the activation commit
        # boundary is acquired.  Once ``committing`` is recorded under the
        # same lock used by ``cancel``, the active pointer/provider/profile
        # transition is no longer cancellable and cancel() must return False.
        self._activation_phases: dict[str, str] = {}
        self._closed = False

    def queue(
        self,
        profile_id: str,
        *,
        builder: FrozenProfileBuilder | None = None,
        force: bool = False,
        transition: Callable[[EmbeddingProfile, EmbeddingProvider], Callable[[], None]]
        | None = None,
        on_finished: Callable[[str | None, str | None], None] | None = None,
    ) -> EmbeddingProfile:
        """Probe and either switch a compatible profile or queue a frozen reindex."""

        with self._lock:
            if self._closed:
                raise EmbeddingProfileError("SERVICE_NOT_READY")
            existing = self._futures.get(profile_id)
            if existing is not None and not existing.done():
                if force:
                    raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")
                return self._registry.get(profile_id)
            if any(not future.done() for future in self._futures.values()):
                raise EmbeddingProfileError("EMBEDDING_REINDEX_ACTIVE")

            profile = self._registry.get(profile_id)
            if not force or profile.last_probed_at is None:
                profile = self._registry.probe(profile_id)
            if profile.last_error_code is not None:
                raise EmbeddingProfileError(profile.last_error_code)
            provider = self._registry.resolve_provider(profile)
            if provider is None or not isinstance(provider, EmbeddingProvider):
                raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED")

            if (
                not force
                and profile.status == "ready"
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

            frozen = (
                profile if force and profile.active else self._registry.begin_reindex(profile_id)
            )
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
                self._activation_phases[profile_id] = "building"
                self._futures[profile_id] = self._executor.submit(
                    self._run,
                    frozen,
                    provider,
                    cancellation,
                    builder or self._builder,
                    transition or self._provider_transition,
                    on_finished,
                )
            return self._registry.get(profile_id)

    def cancel(self, profile_id: str) -> bool:
        """Request cooperative cancellation of one known in-process generation."""

        with self._lock:
            cancellation = self._cancellations.get(profile_id)
            future = self._futures.get(profile_id)
            phase = self._activation_phases.get(profile_id)
            if (
                cancellation is None
                or future is None
                or future.done()
                or phase is None
                or phase == "committing"
            ):
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
        builder: FrozenProfileBuilder,
        provider_transition: Callable[[EmbeddingProfile, EmbeddingProvider], Callable[[], None]],
        on_finished: Callable[[str | None, str | None], None] | None,
    ) -> None:
        candidate: ReindexCandidate | None = None
        activated_bundle_id: str | None = None
        deadline = self._monotonic() + self._timeout_seconds
        try:
            candidate = builder(
                profile,
                provider,
                cancellation.is_set,
                deadline,
            )
            _raise_if_stopped(cancellation.is_set, deadline, self._monotonic)
            bundle_id = candidate.verified.manifest.bundle_id

            def transition() -> ActivationTransition:
                previous_bundle = self._manager.status().active_bundle_id
                if profile.active and self._registry.get(profile.profile_id) != profile:
                    raise EmbeddingProfileError("EMBEDDING_REINDEX_STALE")
                profile_transition = (
                    ActivationTransition(
                        rollback=lambda: self._registry.reconcile_active_bundle(
                            profile.identity, previous_bundle
                        ),
                        commit=lambda: self._registry.reconcile_active_bundle(
                            profile.identity, bundle_id
                        ),
                    )
                    if profile.active
                    else self._registry.activate_reindexed(
                        profile.profile_id, profile.reindex_generation, bundle_id
                    )
                )
                try:
                    rollback_provider = provider_transition(profile, provider)
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

            def before_commit() -> None:
                # Serialize cancellation admission with the irreversible
                # bundle pointer write.  If cancellation won, raising here
                # makes BundleManager run the transition rollback hooks while
                # its active/previous pointers are still unchanged.
                with self._lock:
                    _raise_if_stopped(cancellation.is_set, deadline, self._monotonic)
                    if self._activation_phases.get(profile.profile_id) != "building":
                        raise ReindexCancelled
                    self._activation_phases[profile.profile_id] = "committing"

            self._manager.activate(
                candidate.verified,
                expected_embedding=profile.identity,
                state_transition=transition,
                before_commit=before_commit,
            )
            activated_bundle_id = bundle_id
            if self._on_activated is not None:
                self._on_activated(self._registry.get(profile.profile_id), bundle_id)
            if on_finished is not None:
                on_finished(bundle_id, None)
        except Exception as exc:
            # Record only code locations and closed typed failures; never exception text.
            frames = traceback.extract_tb(exc.__traceback__)
            logging.getLogger(__name__).warning(
                "Reindex failed type=%s code=%s cause=%s location=%s",
                type(exc).__name__,
                _safe_reindex_error(exc),
                (
                    exc.__cause__.code
                    if isinstance(exc.__cause__, BundleError)
                    else type(exc.__cause__).__name__
                ),
                ";".join(f"{Path(frame.filename).name}:{frame.lineno}" for frame in frames[-4:]),
            )
            # Notification failures cannot undo a committed verified activation.
            if activated_bundle_id is not None:
                if on_finished is not None:
                    on_finished(activated_bundle_id, None)
                return
            self._registry.fail_reindex(
                profile.profile_id,
                profile.reindex_generation,
                _safe_reindex_error(exc),
            )
            if on_finished is not None:
                on_finished(None, _safe_reindex_error(exc))
        finally:
            if candidate is not None:
                shutil.rmtree(candidate.workspace, ignore_errors=True)
            with self._lock:
                self._cancellations.pop(profile.profile_id, None)
                self._activation_phases.pop(profile.profile_id, None)


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
    delegate: CancellableSourceResolver
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
    if isinstance(error, ProviderError) and error.code.value == "timeout":
        return "EMBEDDING_REINDEX_TIMEOUT"
    if isinstance(error, EmbeddingProfileError):
        return error.code
    if isinstance(error, BundleActivationError) and isinstance(error.__cause__, ReindexTimedOut):
        return "EMBEDDING_REINDEX_TIMEOUT"
    if isinstance(error, BundleActivationError) and isinstance(error.__cause__, ReindexCancelled):
        return "EMBEDDING_REINDEX_CANCELLED"
    if isinstance(error, (BundleActivationError, BundleError)):
        return "EMBEDDING_ACTIVATION_FAILED"
    if isinstance(error, (IndexPipelineError, SourceResolutionError, ProviderError)):
        return "EMBEDDING_REINDEX_FAILED"
    return "EMBEDDING_REINDEX_FAILED"
