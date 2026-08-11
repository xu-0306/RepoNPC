"""Canonical immutable and stable bundle manifest value objects."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from reponpc.domain.evidence import COMMIT_RE
from reponpc.indexing.sources import EmbeddingIdentity

MANIFEST_SCHEMA_VERSION = 1
STABLE_MANIFEST_SCHEMA_VERSION = 1
_BUNDLE_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{12}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """A safe manifest validation failure."""


@dataclass(frozen=True, slots=True)
class FileDigest:
    """One declared immutable payload file."""

    path: str
    size: int
    sha256: str

    def __post_init__(self) -> None:
        _normal_relative_path(self.path)
        if isinstance(self.size, bool) or self.size < 0:
            raise ManifestError("manifest file size is invalid")
        if not _HEX64_RE.fullmatch(self.sha256):
            raise ManifestError("manifest file digest is invalid")

    def as_dict(self) -> dict[str, object]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class BundleManifest:
    """The canonical schema-v1 manifest embedded in every immutable bundle."""

    bundle_id: str
    built_at: str
    application_minimum: str
    application_maximum_exclusive: str
    config_repository: str
    config_commit_sha: str
    config_path: str
    config_sha256: str
    repositories: tuple[tuple[str, str], ...]
    embedding: EmbeddingIdentity
    statistics: tuple[tuple[str, int], ...]
    files: tuple[FileDigest, ...]

    def __post_init__(self) -> None:
        if not _BUNDLE_ID_RE.fullmatch(self.bundle_id):
            raise ManifestError("bundle ID is invalid")
        _parse_timestamp(self.built_at)
        _validate_version(self.application_minimum)
        _validate_version(self.application_maximum_exclusive)
        if _version_tuple(self.application_minimum) >= _version_tuple(
            self.application_maximum_exclusive
        ):
            raise ManifestError("application compatibility range is invalid")
        _validate_slug(self.config_repository)
        if not COMMIT_RE.fullmatch(self.config_commit_sha) or not _HEX64_RE.fullmatch(
            self.config_sha256
        ):
            raise ManifestError("configuration identity is invalid")
        _normal_relative_path(self.config_path)
        repository_slugs = [slug for slug, sha in self.repositories]
        if len(repository_slugs) != len(set(repository_slugs)) or not repository_slugs:
            raise ManifestError("manifest repositories are invalid")
        for slug, sha in self.repositories:
            _validate_slug(slug)
            if not COMMIT_RE.fullmatch(sha):
                raise ManifestError("repository commit is invalid")
        names = [name for name, value in self.statistics]
        if len(names) != len(set(names)) or not names:
            raise ManifestError("manifest statistics are invalid")
        if any(isinstance(value, bool) or value < 0 for _, value in self.statistics):
            raise ManifestError("manifest statistic is invalid")
        paths = [item.path for item in self.files]
        if len(paths) != len(set(paths)) or not paths or tuple(sorted(paths)) != tuple(paths):
            raise ManifestError("manifest file paths are invalid")

    def as_dict(self) -> dict[str, object]:
        return {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "index_schema_version": 1,
            "bundle_id": self.bundle_id,
            "built_at": self.built_at,
            "application_compatibility": {
                "minimum": self.application_minimum,
                "maximum_exclusive": self.application_maximum_exclusive,
            },
            "config": {
                "repository": self.config_repository,
                "commit_sha": self.config_commit_sha,
                "path": self.config_path,
                "sha256": self.config_sha256,
            },
            "repositories": [{"slug": slug, "commit_sha": sha} for slug, sha in self.repositories],
            "embedding": embedding_as_dict(self.embedding),
            "statistics": dict(self.statistics),
            "files": [file.as_dict() for file in self.files],
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())


@dataclass(frozen=True, slots=True)
class StableManifest:
    """The small mutable pointer to an immutable Release asset."""

    bundle_id: str
    release_tag: str
    asset_url: str
    asset_size: int
    asset_sha256: str
    published_at: str

    def __post_init__(self) -> None:
        if not _BUNDLE_ID_RE.fullmatch(self.bundle_id) or not self.release_tag:
            raise ManifestError("stable manifest bundle identity is invalid")
        parsed = urlsplit(self.asset_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ManifestError("stable manifest asset URL is invalid")
        if isinstance(self.asset_size, bool) or self.asset_size <= 0:
            raise ManifestError("stable manifest asset size is invalid")
        if not _HEX64_RE.fullmatch(self.asset_sha256):
            raise ManifestError("stable manifest asset digest is invalid")
        _parse_timestamp(self.published_at)

    def as_dict(self) -> dict[str, object]:
        return {
            "stable_manifest_schema_version": STABLE_MANIFEST_SCHEMA_VERSION,
            "bundle_id": self.bundle_id,
            "release_tag": self.release_tag,
            "asset_url": self.asset_url,
            "asset_size": self.asset_size,
            "asset_sha256": self.asset_sha256,
            "published_at": self.published_at,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.as_dict())


def bundle_id_for(
    *,
    built_at: datetime,
    configuration_bytes: bytes,
    repositories: tuple[tuple[str, str], ...],
    embedding: EmbeddingIdentity,
    parser_chunker_version: str,
) -> str:
    """Return UTC timestamp plus a deterministic suffix from identity inputs."""

    instant = _as_utc(built_at)
    identity = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
        "repositories": [{"slug": slug, "commit_sha": sha} for slug, sha in repositories],
        "embedding": embedding_as_dict(embedding),
        "parser_chunker_version": parser_chunker_version,
    }
    suffix = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()[:12]
    return instant.strftime("%Y%m%dT%H%M%SZ") + "-" + suffix


def canonical_json_bytes(value: object) -> bytes:
    """Serialize public manifest values with one deterministic UTF-8 encoding."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def parse_bundle_manifest(value: bytes) -> BundleManifest:
    """Parse only the exact schema-v1 internal manifest shape."""

    raw = _load_object(value, "manifest")
    expected_keys = {
        "manifest_schema_version",
        "index_schema_version",
        "bundle_id",
        "built_at",
        "application_compatibility",
        "config",
        "repositories",
        "embedding",
        "statistics",
        "files",
    }
    if set(raw) != expected_keys or raw["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ManifestError("manifest schema is incompatible")
    if raw["index_schema_version"] != 1:
        raise ManifestError("index schema is incompatible")
    compatibility = _object(raw["application_compatibility"], "application compatibility")
    config = _object(raw["config"], "configuration")
    if set(compatibility) != {"minimum", "maximum_exclusive"} or set(config) != {
        "repository",
        "commit_sha",
        "path",
        "sha256",
    }:
        raise ManifestError("manifest object shape is invalid")
    repositories = raw["repositories"]
    files = raw["files"]
    statistics = raw["statistics"]
    if (
        not isinstance(repositories, list)
        or not isinstance(files, list)
        or not isinstance(statistics, dict)
    ):
        raise ManifestError("manifest collection is invalid")
    parsed_repositories: list[tuple[str, str]] = []
    for item in repositories:
        record = _object(item, "repository")
        if set(record) != {"slug", "commit_sha"}:
            raise ManifestError("repository manifest record is invalid")
        parsed_repositories.append((str(record["slug"]), str(record["commit_sha"])))
    parsed_files: list[FileDigest] = []
    for item in files:
        record = _object(item, "file")
        if set(record) != {"path", "size", "sha256"}:
            raise ManifestError("file manifest record is invalid")
        parsed_files.append(
            FileDigest(
                path=str(record["path"]),
                size=_integer(record["size"]),
                sha256=str(record["sha256"]),
            )
        )
    embedding = embedding_from_dict(_object(raw["embedding"], "embedding"))
    return BundleManifest(
        bundle_id=str(raw["bundle_id"]),
        built_at=str(raw["built_at"]),
        application_minimum=str(compatibility["minimum"]),
        application_maximum_exclusive=str(compatibility["maximum_exclusive"]),
        config_repository=str(config["repository"]),
        config_commit_sha=str(config["commit_sha"]),
        config_path=str(config["path"]),
        config_sha256=str(config["sha256"]),
        repositories=tuple(parsed_repositories),
        embedding=embedding,
        statistics=tuple(sorted((str(key), _integer(item)) for key, item in statistics.items())),
        files=tuple(parsed_files),
    )


def parse_stable_manifest(value: bytes) -> StableManifest:
    """Parse only the exact stable-manifest schema shape."""

    raw = _load_object(value, "stable manifest")
    expected_keys = {
        "stable_manifest_schema_version",
        "bundle_id",
        "release_tag",
        "asset_url",
        "asset_size",
        "asset_sha256",
        "published_at",
    }
    if (
        set(raw) != expected_keys
        or raw["stable_manifest_schema_version"] != STABLE_MANIFEST_SCHEMA_VERSION
    ):
        raise ManifestError("stable manifest schema is incompatible")
    return StableManifest(
        bundle_id=str(raw["bundle_id"]),
        release_tag=str(raw["release_tag"]),
        asset_url=str(raw["asset_url"]),
        asset_size=_integer(raw["asset_size"]),
        asset_sha256=str(raw["asset_sha256"]),
        published_at=str(raw["published_at"]),
    )


def embedding_as_dict(identity: EmbeddingIdentity) -> dict[str, object]:
    return {
        "adapter": identity.adapter,
        "model_id": identity.model_id,
        "dimension": identity.dimension,
        "normalized": identity.normalized,
        "query_prefix": identity.query_prefix,
        "passage_prefix": identity.passage_prefix,
    }


def embedding_from_dict(value: dict[str, Any]) -> EmbeddingIdentity:
    if set(value) != {
        "adapter",
        "model_id",
        "dimension",
        "normalized",
        "query_prefix",
        "passage_prefix",
    }:
        raise ManifestError("embedding manifest record is invalid")
    if not isinstance(value["normalized"], bool):
        raise ManifestError("embedding normalization is invalid")
    return EmbeddingIdentity(
        adapter=str(value["adapter"]),
        model_id=str(value["model_id"]),
        dimension=_integer(value["dimension"]),
        normalized=value["normalized"],
        query_prefix=str(value["query_prefix"]),
        passage_prefix=str(value["passage_prefix"]),
    )


def compatible_application(manifest: BundleManifest, application_version: str) -> bool:
    """Return whether a manifest's half-open compatibility range contains the app."""

    version = _version_tuple(application_version)
    return (
        _version_tuple(manifest.application_minimum)
        <= version
        < _version_tuple(manifest.application_maximum_exclusive)
    )


def _load_object(value: bytes, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{label} is invalid") from exc
    return _object(decoded, label)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} is invalid")
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError("manifest integer is invalid")
    return value


def _normal_relative_path(path: str) -> None:
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
        raise ManifestError("manifest path is invalid")
    pure = PurePosixPath(path)
    if str(pure) != path or any(part in {"", ".", ".."} for part in pure.parts):
        raise ManifestError("manifest path is invalid")


def _validate_slug(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ManifestError("repository slug is invalid")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestError("manifest timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ManifestError("manifest timestamp is invalid")
    return parsed


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ManifestError("build timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _validate_version(value: str) -> None:
    _version_tuple(value)


def _version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ManifestError("application version is invalid")
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]
