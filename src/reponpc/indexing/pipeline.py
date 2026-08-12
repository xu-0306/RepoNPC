"""Executable Phase 2 index build and split publication workflow."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
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
    ManifestError,
    bundle_id_for,
    canonical_json_bytes,
    embedding_as_dict,
    parse_stable_manifest,
)
from reponpc.cards.production import build_public_card_assets
from reponpc.config.models import PublicConfig, load_public_config
from reponpc.domain.evidence import COMMIT_RE
from reponpc.indexing.github import GitHubSourceResolver
from reponpc.indexing.github_publication import (
    GitHubReleasePublisher,
    UrllibGitHubReleaseTransport,
)
from reponpc.indexing.index_database import IndexDatabaseBuilder
from reponpc.indexing.public_profile import build_public_profile_bytes
from reponpc.indexing.publication import (
    PublicationCoordinator,
    ReleasePublisher,
)
from reponpc.indexing.sources import (
    EmbeddingIdentity,
    EmbeddingProvider,
    ResolvedConfiguration,
    ResolvedRepository,
)
from reponpc.providers.local_sentence_transformers import (
    LocalSentenceTransformersEmbeddingProvider,
)

BUILD_RECEIPT_NAME = "bundle-build.json"
PENDING_MANIFEST_NAME = "pending-stable-manifest.json"
PARSER_CHUNKER_VERSION = "p2-02-v1"
MAX_BUNDLE_BYTES = 536_870_912
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


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
    embedding_provider: EmbeddingProvider | None = None,
    configuration_source: ResolvedConfiguration | None = None,
    built_at: datetime | None = None,
    public_directory: str | Path | None = None,
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
    source_resolver = resolver or GitHubSourceResolver()
    snapshots = tuple(
        source_resolver.resolve(slug=repository.slug, ref=repository.ref)
        for repository in config.repositories
        if repository.enabled
    )
    instant = built_at or datetime.now(UTC)
    if instant.tzinfo is None:
        raise IndexPipelineError("build_timestamp_invalid")
    bundle_id = bundle_id_for(
        built_at=instant,
        configuration_bytes=content.encode("utf-8"),
        repositories=tuple((snapshot.slug, snapshot.commit_sha) for snapshot in snapshots),
        embedding=provider.identity(),
        parser_chunker_version=PARSER_CHUNKER_VERSION,
    )
    index_result = IndexDatabaseBuilder(provider).build(
        config=config,
        configuration_source=source,
        repositories=snapshots,
        output_path=output / "index.sqlite",
    )
    assets = (
        _load_public_assets(Path(public_directory).resolve())
        if public_directory is not None
        else build_public_card_assets(config, config_directory=config_path.parent)
    )
    assets["public/profile.json"] = build_public_profile_bytes(
        config=config,
        index_version=bundle_id,
        built_at=instant,
        repository_count=index_result.repository_count,
    )
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=source,
        repositories=snapshots,
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


def publish_index_bundle(
    bundle_directory: str | Path,
    *,
    publisher: ReleasePublisher | None = None,
    now: datetime | None = None,
) -> Path:
    """Publish and verify immutable bytes, then create only a local pending pointer."""

    directory = Path(bundle_directory).resolve()
    receipt, bundle = _load_built_bundle(directory)
    selected_publisher = publisher or _default_publisher(receipt.config_repository)
    result = PublicationCoordinator(selected_publisher).publish_immutable(
        bundle,
        now=now or datetime.now(UTC),
    )
    pending_path = directory / PENDING_MANIFEST_NAME
    _write_new_file(
        pending_path,
        result.stable_manifest.canonical_bytes(),
        conflict_code="pending_manifest_exists",
    )
    return pending_path


def publish_pending_manifest(
    bundle_directory: str | Path,
    *,
    publisher: ReleasePublisher | None = None,
) -> None:
    """Accept one verified pending artifact and perform the sole pointer mutation."""

    directory = Path(bundle_directory).resolve()
    receipt, _ = _load_built_bundle(directory)
    pending_path = directory / PENDING_MANIFEST_NAME
    try:
        pending = parse_stable_manifest(pending_path.read_bytes())
    except (OSError, ManifestError) as exc:
        raise IndexPipelineError("pending_manifest_invalid") from exc
    if (
        pending.bundle_id != receipt.bundle_id
        or pending.release_tag != f"index-{receipt.bundle_id}"
        or pending.asset_size != receipt.archive_size
        or pending.asset_sha256 != receipt.archive_sha256
    ):
        raise IndexPipelineError("pending_manifest_invalid")
    selected_publisher = publisher or _default_publisher(receipt.config_repository)
    PublicationCoordinator(selected_publisher).publish_manifest(pending)


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


def _load_built_bundle(directory: Path) -> tuple[BuildReceipt, BuiltBundle]:
    receipt = _parse_build_receipt(directory / BUILD_RECEIPT_NAME)
    archive_path = directory / receipt.archive_name
    try:
        archive_size = archive_path.stat().st_size
        archive_sha256 = _file_sha256(archive_path)
    except OSError as exc:
        raise IndexPipelineError("built_bundle_unavailable") from exc
    if archive_size != receipt.archive_size or archive_sha256 != receipt.archive_sha256:
        raise IndexPipelineError("built_bundle_receipt_mismatch")
    try:
        with tempfile.TemporaryDirectory(prefix=".publish-verify-", dir=directory) as temporary:
            verified = verify_bundle_archive(
                archive_path=archive_path,
                staging_directory=Path(temporary) / "candidate",
                expected_outer_sha256=receipt.archive_sha256,
                expected_embedding=receipt.embedding,
                max_bundle_bytes=MAX_BUNDLE_BYTES,
            )
            try:
                manifest = verified.manifest
            finally:
                verified.close()
    except (BundleError, OSError) as exc:
        raise IndexPipelineError("built_bundle_verification_failed") from exc
    if (
        manifest.bundle_id != receipt.bundle_id
        or manifest.config_repository != receipt.config_repository
        or manifest.embedding != receipt.embedding
    ):
        raise IndexPipelineError("built_bundle_receipt_mismatch")
    return receipt, BuiltBundle(
        archive_path=archive_path,
        manifest=manifest,
        archive_sha256=archive_sha256,
        archive_size=archive_size,
    )


def _parse_build_receipt(path: Path) -> BuildReceipt:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "build_receipt_schema_version",
            "bundle_id",
            "archive_name",
            "archive_size",
            "archive_sha256",
            "config_repository",
            "embedding",
        }
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError
        embedding = raw["embedding"]
        if not isinstance(embedding, dict) or set(embedding) != {
            "adapter",
            "model_id",
            "dimension",
            "normalized",
            "query_prefix",
            "passage_prefix",
        }:
            raise ValueError
        archive_size = raw["archive_size"]
        if (
            raw["build_receipt_schema_version"] != 1
            or not isinstance(raw["bundle_id"], str)
            or not isinstance(raw["archive_name"], str)
            or Path(raw["archive_name"]).name != raw["archive_name"]
            or not raw["archive_name"].startswith("reponpc-index-")
            or not raw["archive_name"].endswith(".tar.zst")
            or isinstance(archive_size, bool)
            or not isinstance(archive_size, int)
            or archive_size <= 0
            or not isinstance(raw["archive_sha256"], str)
            or not _HEX64_RE.fullmatch(raw["archive_sha256"])
            or not isinstance(raw["config_repository"], str)
            or not _REPOSITORY_RE.fullmatch(raw["config_repository"])
        ):
            raise ValueError
        identity = EmbeddingIdentity(
            adapter=_required_string(embedding, "adapter"),
            model_id=_required_string(embedding, "model_id"),
            dimension=_required_integer(embedding, "dimension"),
            normalized=_required_boolean(embedding, "normalized"),
            query_prefix=_required_string(embedding, "query_prefix", allow_empty=True),
            passage_prefix=_required_string(embedding, "passage_prefix", allow_empty=True),
        )
        receipt = BuildReceipt(
            bundle_id=raw["bundle_id"],
            archive_name=raw["archive_name"],
            archive_size=archive_size,
            archive_sha256=raw["archive_sha256"],
            config_repository=raw["config_repository"],
            embedding=identity,
        )
        if receipt.archive_name != f"reponpc-index-{receipt.bundle_id}.tar.zst":
            raise ValueError
        return receipt
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise IndexPipelineError("build_receipt_invalid") from exc


def _default_publisher(repository_slug: str) -> ReleasePublisher:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise IndexPipelineError("github_publication_token_unavailable")
    allowed_hosts = frozenset({"api.github.com", "uploads.github.com", "github.com"})
    return GitHubReleasePublisher(
        repository_slug=repository_slug,
        token=token,
        transport=UrllibGitHubReleaseTransport(allowed_hosts=allowed_hosts),
        allowed_hosts=allowed_hosts,
    )


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _required_string(value: dict[str, object], key: str, *, allow_empty: bool = False) -> str:
    candidate = value.get(key)
    if not isinstance(candidate, str) or (not allow_empty and not candidate):
        raise ValueError
    return candidate


def _required_integer(value: dict[str, object], key: str) -> int:
    candidate = value.get(key)
    if isinstance(candidate, bool) or not isinstance(candidate, int):
        raise ValueError
    return candidate


def _required_boolean(value: dict[str, object], key: str) -> bool:
    candidate = value.get(key)
    if not isinstance(candidate, bool):
        raise ValueError
    return candidate
