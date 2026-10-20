"""Executable immutable index build workflow."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from reponpc.bundles.archive import (
    REQUIRED_PAYLOAD_PATHS,
    BuiltBundle,
    BundleError,
    build_bundle,
    verify_bundle_archive,
)
from reponpc.bundles.manifest import (
    bundle_id_for,
    canonical_json_bytes,
    embedding_as_dict,
)
from reponpc.cards.production import build_public_card_assets
from reponpc.config.models import PublicConfig, load_public_config
from reponpc.domain.evidence import COMMIT_RE
from reponpc.indexing.github import GitHubSourceResolver
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.passage_cache import PassageVectorCache
from reponpc.indexing.public_profile import build_public_profile_bytes
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    EmbeddingProvider,
    RepositoryParticipation,
    ResolvedConfiguration,
    ResolvedRepository,
)
from reponpc.providers.local_sentence_transformers import (
    LocalSentenceTransformersEmbeddingProvider,
)

BUILD_RECEIPT_NAME = "bundle-build.json"
PARSER_CHUNKER_VERSION = "p2-02-v1"
MAX_BUNDLE_BYTES = 536_870_912
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class IndexPipelineError(RuntimeError):
    """Stable safe workflow failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("index workflow failed")


class RepositoryResolver(Protocol):
    def resolve(self, *, slug: str, ref: str | None) -> ResolvedRepository:
        """Resolve a configured public repository to one immutable snapshot."""


@dataclass(frozen=True, slots=True)
class BuildReceipt:
    bundle_id: str
    archive_name: str
    archive_size: int
    archive_sha256: str
    config_repository: str
    embedding: EmbeddingIdentity

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(
            {
                "build_receipt_schema_version": 1,
                "bundle_id": self.bundle_id,
                "archive_name": self.archive_name,
                "archive_size": self.archive_size,
                "archive_sha256": self.archive_sha256,
                "config_repository": self.config_repository,
                "embedding": embedding_as_dict(self.embedding),
            }
        )


def build_index_bundle(
    config_path: str | Path,
    output_directory: str | Path,
    *,
    resolver: RepositoryResolver | None = None,
    participation_collector: Callable[..., RepositoryParticipation] | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    configuration_source: ResolvedConfiguration | None = None,
    built_at: datetime | None = None,
    public_directory: str | Path | None = None,
    embedding_identity_override: EmbeddingIdentity | None = None,
    passage_cache: PassageVectorCache | None = None,
) -> BuiltBundle:
    """Resolve, index, bundle, and verify the complete production build path."""

    config_path = Path(config_path).resolve()
    output = Path(output_directory).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "index.sqlite").exists() or (output / BUILD_RECEIPT_NAME).exists():
        raise IndexPipelineError("build_output_conflict")
    if any(output.glob("reponpc-index-*.tar.zst")):
        raise IndexPipelineError("build_output_conflict")
    config = load_public_config(config_path)
    content = config_path.read_text(encoding="utf-8")
    source = configuration_source or _resolve_configuration_source(config_path, content)
    provider = embedding_provider or _embedding_provider(config)
    if embedding_identity_override is not None:
        if provider.identity() != embedding_identity_override:
            raise IndexPipelineError("embedding_identity_mismatch")
        identity = embedding_identity_override
        embedding_config = config.retrieval.embedding.model_copy(
            update={
                "adapter": identity.adapter,
                "model": identity.model_id,
                "dimension": identity.dimension,
                "normalized": identity.normalized,
                "query_prefix": identity.query_prefix,
                "passage_prefix": identity.passage_prefix,
            }
        )
        config = config.model_copy(
            update={
                "retrieval": config.retrieval.model_copy(update={"embedding": embedding_config})
            }
        )
    source_resolver = resolver or GitHubSourceResolver()
    snapshots: list[ResolvedRepository] = []
    for repository in config.repositories:
        if not repository.enabled:
            continue
        snapshot = source_resolver.resolve(slug=repository.slug, ref=repository.ref)
        if participation_collector is not None:
            collected = participation_collector(
                slug=snapshot.slug,
                pinned_sha=snapshot.commit_sha,
                github_login=config.profile.github_login,
            )
            if not isinstance(collected, RepositoryParticipation):
                raise IndexPipelineError("participation_invalid")
            snapshot = replace(snapshot, participation=collected)
        else:
            snapshot = replace(snapshot, participation=None)
        snapshots.append(snapshot)
    resolved_snapshots = tuple(snapshots)
    instant = built_at or datetime.now(UTC)
    if instant.tzinfo is None:
        raise IndexPipelineError("build_timestamp_invalid")
    bundle_id = bundle_id_for(
        built_at=instant,
        configuration_bytes=content.encode("utf-8"),
        repositories=tuple((snapshot.slug, snapshot.commit_sha) for snapshot in resolved_snapshots),
        embedding=provider.identity(),
        parser_chunker_version=PARSER_CHUNKER_VERSION,
    )
    index_result = IndexDatabaseBuilder(provider, passage_cache=passage_cache).build(
        config=config,
        configuration_source=source,
        repositories=resolved_snapshots,
        output_path=output / "index.sqlite",
    )
    assets = (
        _load_public_assets(Path(public_directory).resolve())
        if public_directory is not None
        else build_public_card_assets(config, config_directory=config_path.parent)
    )
    scene_paths = [path for path in assets if path.startswith("public/scene/")]
    if config.character.scene.background_path is None:
        if scene_paths:
            raise ValueError("scene background asset is unexpected")
        background_content = None
    else:
        if len(scene_paths) != 1:
            raise ValueError("scene background asset is missing")
        background_content = assets[scene_paths[0]]
    assets["public/profile.json"] = build_public_profile_bytes(
        config=config,
        index_version=bundle_id,
        built_at=instant,
        repository_count=index_result.repository_count,
        sprite_content=assets["public/character.png"],
        background_content=background_content,
        repository_snapshots=resolved_snapshots,
    )
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=source,
        repositories=resolved_snapshots,
        bundle_id=bundle_id,
        built_at=instant,
        public_files=assets,
        output_path=output / f"reponpc-index-{bundle_id}.tar.zst",
    )
    _verify_built_bundle(bundle, output)
    receipt = BuildReceipt(
        bundle_id=bundle.manifest.bundle_id,
        archive_name=bundle.archive_path.name,
        archive_size=bundle.archive_size,
        archive_sha256=bundle.archive_sha256,
        config_repository=bundle.manifest.config_repository,
        embedding=bundle.manifest.embedding,
    )
    _write_new_file(
        output / BUILD_RECEIPT_NAME,
        receipt.canonical_bytes(),
        conflict_code="build_output_conflict",
    )
    return bundle


def _embedding_provider(config: PublicConfig) -> EmbeddingProvider:
    configured = config.retrieval.embedding
    if configured.adapter != "local_sentence_transformers":
        raise IndexPipelineError("embedding_adapter_unavailable")
    return LocalSentenceTransformersEmbeddingProvider(
        model_id=configured.model,
        dimension=configured.dimension,
        normalized=configured.normalized,
        query_prefix=configured.query_prefix,
        passage_prefix=configured.passage_prefix,
    )


def _load_public_assets(public_directory: Path) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    required = REQUIRED_PAYLOAD_PATHS - {"index.sqlite", "public/profile.json"}
    try:
        for bundle_path in sorted(required):
            relative = bundle_path.removeprefix("public/")
            assets[bundle_path] = (public_directory / relative).read_bytes()
    except OSError as exc:
        raise IndexPipelineError("public_assets_unavailable") from exc
    return assets


def _verify_built_bundle(bundle: BuiltBundle, output: Path) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=output) as temporary:
            verified = verify_bundle_archive(
                archive_path=bundle.archive_path,
                staging_directory=Path(temporary) / "candidate",
                expected_outer_sha256=bundle.archive_sha256,
                expected_embedding=bundle.manifest.embedding,
                max_bundle_bytes=MAX_BUNDLE_BYTES,
            )
            verified.close()
    except (BundleError, OSError) as exc:
        raise IndexPipelineError("built_bundle_verification_failed") from exc


def _resolve_configuration_source(config_path: Path, content: str) -> ResolvedConfiguration:
    repository_slug = os.environ.get("GITHUB_REPOSITORY")
    commit_sha = os.environ.get("GITHUB_SHA")
    workspace = os.environ.get("GITHUB_WORKSPACE")
    if (
        repository_slug
        and _REPOSITORY_RE.fullmatch(repository_slug)
        and commit_sha
        and COMMIT_RE.fullmatch(commit_sha)
        and workspace
    ):
        try:
            relative_path = config_path.relative_to(Path(workspace).resolve()).as_posix()
        except ValueError as exc:
            raise IndexPipelineError("configuration_revision_unavailable") from exc
        return ResolvedConfiguration(
            repository_slug=repository_slug,
            commit_sha=commit_sha,
            path=relative_path,
            content=content,
            github_html_url=f"https://github.com/{repository_slug}",
        )

    root = Path(_git_output(config_path.parent, "rev-parse", "--show-toplevel")).resolve()
    commit = _git_output(root, "rev-parse", "HEAD")
    remote = _git_output(root, "config", "--get", "remote.origin.url")
    if not COMMIT_RE.fullmatch(commit):
        raise IndexPipelineError("configuration_revision_unavailable")
    slug = _github_remote_slug(remote)
    try:
        relative_path = config_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise IndexPipelineError("configuration_revision_unavailable") from exc
    return ResolvedConfiguration(
        repository_slug=slug,
        commit_sha=commit,
        path=relative_path,
        content=content,
        github_html_url=f"https://github.com/{slug}",
    )


def _git_output(directory: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise IndexPipelineError("configuration_revision_unavailable") from exc
    output = completed.stdout.strip()
    if not output or len(output) > 4096:
        raise IndexPipelineError("configuration_revision_unavailable")
    return output


def _github_remote_slug(value: str) -> str:
    candidate: str | None = None
    if value.startswith("git@github.com:"):
        candidate = value.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(value)
        if (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and not parsed.username
            and not parsed.password
        ):
            candidate = parsed.path.lstrip("/")
    if candidate is None:
        raise IndexPipelineError("configuration_revision_unavailable")
    candidate = candidate.removesuffix(".git").rstrip("/")
    if not _REPOSITORY_RE.fullmatch(candidate):
        raise IndexPipelineError("configuration_revision_unavailable")
    return candidate


def _write_new_file(path: Path, payload: bytes, *, conflict_code: str) -> None:
    if path.exists():
        raise IndexPipelineError(conflict_code)
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise IndexPipelineError(conflict_code) from exc
    except OSError as exc:
        raise IndexPipelineError("local_artifact_write_failed") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
