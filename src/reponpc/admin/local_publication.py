"""Local preparation over the existing verified bundle activation lane."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from reponpc.admin.batch_resolver import (
    BatchResolverError,
    GitHubArchiveSource,
    GitHubRESTMetadataResolver,
    RepositorySelection,
)
from reponpc.admin.batches import BatchStageGates
from reponpc.admin.embedding_profiles import EmbeddingProfile, EmbeddingProfileRegistry
from reponpc.admin.embedding_reindex import (
    CancellableSourceResolver,
    EmbeddingReindexCoordinator,
    ReindexCandidate,
    ReindexOutcome,
    _BoundedResolver,
    _collect_participation,
    _raise_if_stopped,
)
from reponpc.admin.local_portfolio import (
    LocalPortfolioDraft,
    LocalPortfolioError,
    LocalPortfolioStore,
)
from reponpc.admin.scene import write_presentation_receipt
from reponpc.bundles.archive import verify_bundle_archive
from reponpc.bundles.manager import BundleManager
from reponpc.config.models import parse_public_config_bytes
from reponpc.indexing.github import GitHubSourceResolver
from reponpc.indexing.passage_cache import PassageVectorCache
from reponpc.indexing.pipeline import IndexPipelineError, build_index_bundle
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    EmbeddingProvider,
    RepositoryParticipation,
    ResolvedConfiguration,
    ResolvedRepository,
)


class LocalArchiveResolver:
    """Resolve a fresh commit, then use the shared bounded archive lane."""

    def __init__(
        self,
        metadata: GitHubRESTMetadataResolver,
        source: GitHubArchiveSource,
        gates: BatchStageGates,
    ) -> None:
        self.metadata, self.source, self.gates = metadata, source, gates

    def resolve(
        self,
        *,
        slug: str,
        ref: str | None,
        cancel_requested: Callable[[], bool] | None = None,
        deadline: float | None = None,
    ) -> ResolvedRepository:
        cancelled = cancel_requested or (lambda: False)
        expires = deadline if deadline is not None else math.inf
        _raise_if_stopped(cancelled, expires, time.monotonic)
        result = self.metadata.resolve_all(selections=(RepositorySelection(slug, ref),))
        if result.blockers or len(result.repositories) != 1:
            blocker = result.blockers[0] if result.blockers else None
            raise BatchResolverError(
                blocker.code if blocker is not None else "NOT_FOUND",
                retry_after_seconds=blocker.retry_after_seconds if blocker is not None else None,
            )
        with self.gates.archive_staging():
            _raise_if_stopped(cancelled, expires, time.monotonic)
            return self.source.fetch(
                repository=result.repositories[0], cancel_requested=cancelled, deadline=expires
            )


class _BoundedEmbeddingProvider:
    def __init__(
        self, provider: EmbeddingProvider, cancelled: Callable[[], bool], deadline: float
    ) -> None:
        self.provider, self.cancelled, self.deadline = provider, cancelled, deadline

    def identity(self) -> EmbeddingIdentity:
        return self.provider.identity()

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        _raise_if_stopped(self.cancelled, self.deadline, time.monotonic)
        result = self.provider.embed_passages(texts)
        _raise_if_stopped(self.cancelled, self.deadline, time.monotonic)
        return result

    def embed_query(self, texts: list[str]) -> NDArray[np.float32]:
        _raise_if_stopped(self.cancelled, self.deadline, time.monotonic)
        result = self.provider.embed_query(texts)
        _raise_if_stopped(self.cancelled, self.deadline, time.monotonic)
        return result


class LocalPortfolioBuilder:
    def __init__(
        self,
        draft: LocalPortfolioDraft,
        *,
        data_directory: Path,
        resolver: CancellableSourceResolver,
        max_bundle_bytes: int,
        participation_collector: Callable[..., RepositoryParticipation] | None = None,
    ) -> None:
        self.draft = draft
        self.root = data_directory / "local-builds"
        self.resolver = resolver
        self.participation_collector = participation_collector
        self.max_bundle_bytes = max_bundle_bytes
        self.cache = PassageVectorCache(data_directory / "passage-cache")

    def __call__(
        self,
        profile: EmbeddingProfile,
        provider: EmbeddingProvider,
        cancel_requested: Callable[[], bool],
        deadline: float,
    ) -> ReindexCandidate:
        self.root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="prepare-", dir=self.root))
        verified = None
        try:
            _raise_if_stopped(cancel_requested, deadline, time.monotonic)
            config = parse_public_config_bytes(self.draft.content.encode("utf-8"))
            source_root = workspace / "source"
            source_root.mkdir()
            config_path = source_root / "reponpc.yml"
            build_content = self.draft.content
            if config.character.custom is not None:
                if self.draft.sprite_base64 is None:
                    raise LocalPortfolioError("PORTFOLIO_ASSET_REQUIRED")
                asset = source_root / config.character.custom.sprite_path
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(base64.b64decode(self.draft.sprite_base64, validate=True))
            if self.draft.scene_background_base64 is not None:
                from reponpc.scene.images import validate_scene_image

                raw_background = base64.b64decode(self.draft.scene_background_base64, validate=True)
                suffix = "webp" if raw_background.startswith(b"RIFF") else "png"
                image = validate_scene_image(raw_background, filename=f"applied.{suffix}")
                relative = f"assets/scene/{image.sha256}.{image.format}"
                asset = source_root / relative
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(image.content)
                scene = config.character.scene.model_copy(update={"background_path": relative})
                config = config.model_copy(
                    update={"character": config.character.model_copy(update={"scene": scene})}
                )
                build_content = yaml.safe_dump(
                    config.model_dump(mode="json"),
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
            config_path.write_text(build_content, encoding="utf-8")
            source = ResolvedConfiguration(
                repository_slug="local/portfolio",
                commit_sha=hashlib.sha256(build_content.encode("utf-8")).hexdigest()[:40],
                path="reponpc.yml",
                content=build_content,
                github_html_url="/",
                origin="local",
            )
            built = build_index_bundle(
                config_path,
                workspace / "build",
                resolver=_BoundedResolver(
                    self.resolver,
                    cancel_requested,
                    deadline,
                    time.monotonic,
                ),
                participation_collector=(
                    partial(
                        _collect_participation,
                        self.participation_collector,
                        cancel_requested,
                        deadline,
                        time.monotonic,
                    )
                    if self.participation_collector is not None
                    else None
                ),
                embedding_provider=_BoundedEmbeddingProvider(provider, cancel_requested, deadline),
                configuration_source=source,
                embedding_identity_override=profile.identity,
                passage_cache=self.cache,
            )
            _raise_if_stopped(cancel_requested, deadline, time.monotonic)
            verified = verify_bundle_archive(
                archive_path=built.archive_path,
                staging_directory=workspace / "candidate",
                expected_outer_sha256=built.archive_sha256,
                expected_embedding=profile.identity,
                max_bundle_bytes=self.max_bundle_bytes,
            )
            query = provider.embed_query(["RepoNPC semantic activation smoke"])
            if query.shape != (1, profile.dimension) or not all(
                math.isfinite(float(v)) for v in query.flat
            ):
                raise IndexPipelineError("embedding_output_invalid")
            if not verified.index.hybrid_candidates("retrieval", query_vector=query[0]):
                raise IndexPipelineError("bundle_smoke_query_failed")
            write_presentation_receipt(
                data_directory=self.root.parent,
                bundle_directory=verified.directory,
                settings=config.character.scene,
            )
            _raise_if_stopped(cancel_requested, deadline, time.monotonic)
            return ReindexCandidate(verified, workspace)
        except Exception:
            if verified is not None:
                verified.close()
            shutil.rmtree(workspace, ignore_errors=True)
            raise


class LocalPublication:
    """Persist safe job receipts; preparation never holds an HTTP request open."""

    def __init__(
        self,
        *,
        store: LocalPortfolioStore,
        data_directory: Path,
        coordinator: EmbeddingReindexCoordinator,
        registry: EmbeddingProfileRegistry,
        manager: BundleManager,
        resolver: GitHubSourceResolver,
        max_bundle_bytes: int,
        transition_factory: Callable[
            [str], Callable[[EmbeddingProfile, EmbeddingProvider], Callable[[], None]]
        ],
        stop_remote: Callable[[], None],
        source_resolver: CancellableSourceResolver | None = None,
        participation_collector: Callable[..., RepositoryParticipation] | None = None,
    ) -> None:
        self.store, self.coordinator, self.registry, self.manager = (
            store,
            coordinator,
            registry,
            manager,
        )
        self.root, self.resolver, self.max_bundle_bytes = data_directory, resolver, max_bundle_bytes
        self.source_resolver = source_resolver or resolver
        self.participation_collector = participation_collector
        self.transition_factory, self.stop_remote = transition_factory, stop_remote
        self.lock = threading.RLock()
        self.path = data_directory / "local-portfolio" / "publication.json"
        self.job: dict[str, Any] = {"state": "idle", "revision": None, "error_code": None}
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    self.job = {
                        key: saved.get(key)
                        for key in (
                            "state",
                            "revision",
                            "error_code",
                            "retry_at",
                            "profile_id",
                            "chat_profile_id",
                            "bundle_id",
                        )
                    }
                if self.job.get("state") == "preparing":
                    self.job.update(
                        state="failed", error_code="EMBEDDING_REINDEX_INTERRUPTED", retry_at=None
                    )
                    self._persist()
            except OSError, ValueError:
                self.job = {"state": "failed", "error_code": "PORTFOLIO_CORRUPT", "revision": None}

    def status(self) -> dict[str, Any]:
        with self.lock:
            active = self.manager.status().active_bundle_id
            draft = self.store.read()
            return {
                **self.job,
                "retry_at": self.job.get("retry_at"),
                "active_bundle_id": active,
                "draft_revision": draft.revision if draft else None,
                "index_ready": active is not None,
                "draft_changed": draft is not None
                and (
                    draft.revision != self.job.get("revision")
                    or active is None
                    or active != self.job.get("bundle_id")
                ),
            }

    def prepare(
        self, *, expected_revision: str, embedding_profile_id: str, chat_profile_id: str
    ) -> dict[str, Any]:
        with self.lock:
            draft = self.store.read()
            if draft is None or draft.revision != expected_revision:
                raise LocalPortfolioError("PORTFOLIO_CONFLICT")
            if self.job.get("state") == "preparing":
                if (
                    self.job.get("revision") == draft.revision
                    and self.job.get("profile_id") == embedding_profile_id
                    and self.job.get("chat_profile_id") == chat_profile_id
                ):
                    return self.status()
                raise LocalPortfolioError("PORTFOLIO_BUSY")
            transition = self.transition_factory(chat_profile_id)
            profile = self.registry.get(embedding_profile_id)
            if profile.last_probed_at is None or profile.last_error_code is not None:
                raise LocalPortfolioError("EMBEDDING_PROBE_REQUIRED")
            self.stop_remote()
            self.job = {
                "state": "preparing",
                "revision": draft.revision,
                "profile_id": embedding_profile_id,
                "chat_profile_id": chat_profile_id,
                "error_code": None,
                "retry_at": None,
                "bundle_id": None,
            }
            self._persist()
            try:
                self.coordinator.queue(
                    embedding_profile_id,
                    force=True,
                    builder=LocalPortfolioBuilder(
                        draft,
                        data_directory=self.root,
                        resolver=self.source_resolver,
                        max_bundle_bytes=self.max_bundle_bytes,
                        participation_collector=self.participation_collector,
                    ),
                    transition=transition,
                    on_finished=self._finished,
                    source_failures_reported_by_caller=True,
                )
            except Exception:
                self.job.update(state="failed", error_code="PORTFOLIO_PREPARE_FAILED")
                self._persist()
                raise
            return self.status()

    def cancel(self) -> dict[str, Any]:
        with self.lock:
            if self.job.get("state") == "preparing":
                self.coordinator.cancel(str(self.job.get("profile_id", "")))
            return self.status()

    def _finished(self, outcome: ReindexOutcome) -> None:
        with self.lock:
            self.job.update(
                state="ready" if outcome.bundle_id else "failed",
                bundle_id=outcome.bundle_id,
                error_code=outcome.error_code,
                retry_at=outcome.retry_at,
            )
            self._persist()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix="publication-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.job, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)
