"""Deterministic ``tar.zst`` production and fail-closed staged verification."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import tarfile
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from reponpc.bundles.index_reader import IndexReadError, ReadOnlyIndex
from reponpc.bundles.manifest import (
    BundleManifest,
    FileDigest,
    ManifestError,
    compatible_application,
    parse_bundle_manifest,
)
from reponpc.indexing.index_database import IndexBuildResult
from reponpc.indexing.sources import EmbeddingIdentity, ResolvedConfiguration, ResolvedRepository

APPLICATION_VERSION: Final = "0.1.0"
ARCHIVE_FILE_LIMIT: Final = 64
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_CARD_VARIANTS: Final = tuple(
    f"public/card-{theme}-{locale}.{extension}"
    for theme in ("light", "dark")
    for locale in ("zh-TW", "en")
    for extension in ("svg", "gif", "png")
)
REQUIRED_PAYLOAD_PATHS: Final = frozenset(
    {"index.sqlite", "public/profile.json", "public/character.png", *_CARD_VARIANTS}
)


class BundleError(RuntimeError):
    """A safe bundle failure code; values/paths must stay out of public output."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("bundle validation failed")


@dataclass(frozen=True, slots=True)
class BuiltBundle:
    """The immutable archive and manifest produced by the index side."""

    archive_path: Path
    manifest: BundleManifest
    archive_sha256: str
    archive_size: int


@dataclass(slots=True)
class VerifiedBundle:
    """A staged candidate with a read-only verified index handle."""

    directory: Path
    manifest: BundleManifest
    index: ReadOnlyIndex

    def close(self) -> None:
        self.index.close()


def build_bundle(
    *,
    index_result: IndexBuildResult,
    configuration_source: ResolvedConfiguration,
    repositories: tuple[ResolvedRepository, ...],
    bundle_id: str,
    built_at: datetime,
    public_files: dict[str, bytes],
    output_path: Path,
    application_minimum: str = APPLICATION_VERSION,
    application_maximum_exclusive: str = "0.2.0",
) -> BuiltBundle:
    """Build one deterministic archive from an integrity-checked index and assets."""

    index_path = Path(index_result.database_path)
    index_size = _validate_build_inputs(index_path, public_files)
    try:
        index_sha256 = _file_sha256(index_path)
    except OSError as exc:
        raise BundleError("bundle_payload_invalid") from exc
    files = tuple(
        sorted(
            (
                FileDigest(path="index.sqlite", size=index_size, sha256=index_sha256),
                *(
                    FileDigest(path=path, size=len(payload), sha256=_sha256(payload))
                    for path, payload in public_files.items()
                ),
            ),
            key=lambda item: item.path,
        )
    )
    manifest = BundleManifest(
        bundle_id=bundle_id,
        built_at=built_at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        application_minimum=application_minimum,
        application_maximum_exclusive=application_maximum_exclusive,
        config_repository=configuration_source.repository_slug,
        config_commit_sha=configuration_source.commit_sha,
        config_path=configuration_source.path,
        config_sha256=_sha256(configuration_source.content.encode("utf-8")),
        repositories=tuple(
            (item.slug, item.commit_sha) for item in sorted(repositories, key=lambda x: x.slug)
        ),
        embedding=index_result.embedding,
        statistics=(
            ("evidence_records", index_result.evidence_count),
            ("repositories", index_result.repository_count),
            ("sources", index_result.source_count),
        ),
        files=files,
    )
    manifest_bytes = manifest.canonical_bytes()
    checksums = {
        "manifest.json": _sha256(manifest_bytes),
        **{item.path: item.sha256 for item in files},
    }
    small_archive_contents = {
        "manifest.json": manifest_bytes,
        "checksums.sha256": _checksum_bytes(checksums),
        **public_files,
    }
    output_path = Path(output_path)
    if output_path.name != f"reponpc-index-{bundle_id}.tar.zst":
        raise BundleError("bundle_filename_invalid")
    temporary: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_path(output_path)
        with tarfile.open(temporary, "w:zst", format=tarfile.PAX_FORMAT) as archive:
            for path in sorted({"index.sqlite", *small_archive_contents}):
                member = tarfile.TarInfo(path)
                member.mode = 0o644
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                if path == "index.sqlite":
                    member.size = index_size
                    with index_path.open("rb") as source:
                        archive.addfile(member, source)
                else:
                    data = small_archive_contents[path]
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
        archive_sha256 = _file_sha256(temporary)
        archive_size = temporary.stat().st_size
        os.replace(temporary, output_path)
    except (OSError, tarfile.TarError) as exc:
        if temporary is not None:
            _remove_temporary(temporary)
        raise BundleError("bundle_archive_write_failed") from exc
    return BuiltBundle(
        archive_path=output_path,
        manifest=manifest,
        archive_sha256=archive_sha256,
        archive_size=archive_size,
    )


def verify_bundle_archive(
    *,
    archive_path: Path,
    staging_directory: Path,
    expected_outer_sha256: str,
    expected_embedding: EmbeddingIdentity,
    max_bundle_bytes: int,
    application_version: str = APPLICATION_VERSION,
) -> VerifiedBundle:
    """Verify outer bytes, safe members, internal checksums, assets, and index smoke."""

    archive_path = Path(archive_path)
    if (
        not archive_path.is_file()
        or archive_path.stat().st_size <= 0
        or archive_path.stat().st_size > max_bundle_bytes
        or _file_sha256(archive_path) != expected_outer_sha256
    ):
        raise BundleError("bundle_outer_checksum_invalid")
    staging_directory = Path(staging_directory)
    if staging_directory.exists():
        raise BundleError("bundle_staging_not_empty")
    staging_directory.mkdir(parents=True, exist_ok=False)
    try:
        _stage_safe_members(archive_path, staging_directory, max_bundle_bytes)
        manifest = parse_bundle_manifest((staging_directory / "manifest.json").read_bytes())
        if not compatible_application(manifest, application_version):
            raise BundleError("bundle_application_incompatible")
        if manifest.embedding != expected_embedding:
            raise BundleError("bundle_embedding_incompatible")
        _verify_layout_and_checksums(staging_directory, manifest)
        _verify_public_assets(staging_directory)
        try:
            index = ReadOnlyIndex.open(
                staging_directory / "index.sqlite", expected_embedding=expected_embedding
            )
        except IndexReadError as exc:
            raise BundleError("bundle_index_invalid") from exc
        if not index.lexical_candidates("retrieval", limit=1):
            index.close()
            raise BundleError("bundle_smoke_query_failed")
        return VerifiedBundle(directory=staging_directory, manifest=manifest, index=index)
    except (BundleError, ManifestError):
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise
    except (OSError, tarfile.TarError, ValueError, json.JSONDecodeError) as exc:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise BundleError("bundle_validation_failed") from exc


def verify_retained_bundle_directory(
    *,
    directory: Path,
    expected_embedding: EmbeddingIdentity,
    application_version: str = APPLICATION_VERSION,
) -> VerifiedBundle:
    """Re-verify a retained immutable bundle before it becomes live again.

    Retained bundles have already passed outer-archive verification before they
    were stored.  A restart or pin must nevertheless repeat every verification
    which remains meaningful for the extracted immutable layout, rather than
    trusting a directory merely because its name appears in runtime state.
    """

    directory = Path(directory)
    try:
        manifest = parse_bundle_manifest((directory / "manifest.json").read_bytes())
        if not compatible_application(manifest, application_version):
            raise BundleError("bundle_application_incompatible")
        if manifest.embedding != expected_embedding:
            raise BundleError("bundle_embedding_incompatible")
        _verify_layout_and_checksums(directory, manifest)
        _verify_public_assets(directory)
        try:
            index = ReadOnlyIndex.open(
                directory / "index.sqlite", expected_embedding=expected_embedding
            )
        except IndexReadError as exc:
            raise BundleError("bundle_index_invalid") from exc
        if not index.lexical_candidates("retrieval", limit=1):
            index.close()
            raise BundleError("bundle_smoke_query_failed")
        return VerifiedBundle(directory=directory, manifest=manifest, index=index)
    except (BundleError, ManifestError):
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise BundleError("bundle_validation_failed") from exc


def _validate_build_inputs(index_path: Path, public_files: dict[str, bytes]) -> int:
    try:
        index_stat = index_path.stat()
    except OSError as exc:
        raise BundleError("bundle_payload_invalid") from exc
    if not stat.S_ISREG(index_stat.st_mode) or index_stat.st_size <= 0:
        raise BundleError("bundle_payload_invalid")
    if set(public_files) != REQUIRED_PAYLOAD_PATHS - {"index.sqlite"}:
        raise BundleError("bundle_payload_layout_invalid")
    if any(not isinstance(value, bytes) or not value for value in public_files.values()):
        raise BundleError("bundle_payload_invalid")
    return index_stat.st_size


def _remove_temporary(path: Path) -> None:
    with suppress(OSError):
        path.unlink(missing_ok=True)


def _stage_safe_members(archive_path: Path, staging: Path, max_size: int) -> None:
    with tarfile.open(archive_path, "r:zst") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(members) > ARCHIVE_FILE_LIMIT or len(names) != len(set(names)):
            raise BundleError("bundle_member_count_invalid")
        total_size = 0
        for member in members:
            if not member.isreg() or not _safe_member_name(member.name):
                raise BundleError("bundle_member_unsafe")
            total_size += member.size
            if member.size < 0 or total_size > max_size:
                raise BundleError("bundle_uncompressed_size_invalid")
        for member in members:
            source = archive.extractfile(member)
            if source is None:
                raise BundleError("bundle_member_unreadable")
            target = staging / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as destination:
                shutil.copyfileobj(source, destination, length=64 * 1024)


def _verify_layout_and_checksums(staging: Path, manifest: BundleManifest) -> None:
    expected_paths = {"manifest.json", "checksums.sha256", *(item.path for item in manifest.files)}
    actual_paths = {
        path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file()
    }
    if (
        actual_paths != expected_paths
        or {item.path for item in manifest.files} != REQUIRED_PAYLOAD_PATHS
    ):
        raise BundleError("bundle_layout_invalid")
    checksums = _parse_checksums((staging / "checksums.sha256").read_bytes())
    expected_checksums = {
        "manifest.json": _sha256((staging / "manifest.json").read_bytes()),
        **{item.path: item.sha256 for item in manifest.files},
    }
    if checksums != expected_checksums:
        raise BundleError("bundle_internal_checksum_invalid")
    for item in manifest.files:
        payload_path = staging / item.path
        if payload_path.stat().st_size != item.size or _file_sha256(payload_path) != item.sha256:
            raise BundleError("bundle_payload_checksum_invalid")


def _verify_public_assets(staging: Path) -> None:
    try:
        profile = json.loads((staging / "public/profile.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError("bundle_profile_invalid") from exc
    if not isinstance(profile, dict):
        raise BundleError("bundle_profile_invalid")
    if not (staging / "public/character.png").read_bytes().startswith(_PNG_SIGNATURE):
        raise BundleError("bundle_character_invalid")
    for path in _CARD_VARIANTS:
        payload = (staging / path).read_bytes()
        if not payload:
            raise BundleError("bundle_card_invalid")
        if path.endswith(".svg") and not payload.lstrip().startswith(b"<svg"):
            raise BundleError("bundle_card_invalid")


def _safe_member_name(name: str) -> bool:
    parts = name.split("/")
    return (
        bool(name)
        and not name.startswith("/")
        and "\\" not in name
        and ":" not in name
        and all(part not in {"", ".", ".."} for part in parts)
    )


def _checksum_bytes(checksums: dict[str, str]) -> bytes:
    return "".join(f"{digest}  {path}\n" for path, digest in sorted(checksums.items())).encode(
        "ascii"
    )


def _parse_checksums(value: bytes) -> dict[str, str]:
    try:
        lines = value.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise BundleError("bundle_checksums_invalid") from exc
    parsed: dict[str, str] = {}
    for line in lines:
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64 or not _safe_member_name(parts[1]):
            raise BundleError("bundle_checksums_invalid")
        if parts[1] in parsed or any(character not in "0123456789abcdef" for character in parts[0]):
            raise BundleError("bundle_checksums_invalid")
        parsed[parts[1]] = parts[0]
    return parsed


def _temporary_path(output_path: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    ) as handle:
        return Path(handle.name)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
