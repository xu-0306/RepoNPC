"""Read-only host-resource checks for an already normalized runtime backup."""

from __future__ import annotations

import os
import re
import sqlite3
import stat
import time
from contextlib import closing
from pathlib import Path

from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.model_connections import ProtectedModelSecretStore
from reponpc.bundles.archive import ARCHIVE_FILE_LIMIT, verify_retained_bundle_directory
from reponpc.bundles.manifest import BundleManifest, parse_bundle_manifest
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase
from reponpc.scene.images import validate_scene_image

_BUNDLE_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{12}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_BYTES = 512 * 1024


class BackupResourceError(ValueError):
    """A safe failure which never contains resource paths or decrypted values."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("backup resources unavailable")


def _guard(path: Path, *, directory: bool = False) -> os.stat_result:
    if not path.is_absolute() or ".." in path.parts or path.anchor.startswith("\\\\"):
        raise ValueError("invalid resource")
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("invalid resource")
    info = path.lstat()
    if getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("invalid resource")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("invalid resource")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("invalid resource")
    return info


def _read(path: Path, maximum: int) -> bytes:
    original = _guard(path)
    if original.st_size > maximum:
        raise ValueError("invalid resource")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (original.st_dev, original.st_ino):
            raise ValueError("invalid resource")
        content = stream.read(maximum + 1)
    final = _guard(path)
    if len(content) > maximum or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != (
        original.st_dev,
        original.st_ino,
        original.st_size,
        original.st_mtime_ns,
    ):
        raise ValueError("invalid resource")
    return content


def _connection(path: Path, *, immutable: bool) -> sqlite3.Connection:
    _guard(path)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            _guard(sidecar)
    connection = sqlite3.connect(
        path.as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro"),
        uri=True,
        timeout=0.1,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.enable_load_extension(False)
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + 30
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        return connection
    except Exception:
        connection.close()
        raise


def _owner(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT created_at FROM admin_owner WHERE state_key='current'"
    ).fetchone()
    return None if row is None else str(row[0])


def _secrets(connection: sqlite3.Connection, data_directory: Path) -> None:
    rows = connection.execute("SELECT ciphertext FROM model_connection_secrets")
    row = rows.fetchone()
    if row is None:
        return
    try:
        key = data_directory / "model-secrets" / "master.key"
        if len(_read(key, 64)) != 44:
            raise ValueError("invalid resource")
        store = ProtectedModelSecretStore(key)
        while row is not None:
            store.decrypt(bytes(row[0]))
            row = rows.fetchone()
    except Exception:
        raise BackupResourceError("RESTORE_SECRET_UNAVAILABLE") from None


def _bundle(directory: Path, bundle_id: str) -> BundleManifest:
    try:
        if not _BUNDLE_ID.fullmatch(bundle_id):
            raise ValueError("invalid resource")
        root = directory / "bundles" / "validated" / bundle_id
        _guard(root, directory=True)
        # The existing verifier follows ordinary paths. Reject every link before
        # it opens payloads, including an otherwise unused linked directory.
        pending = [root]
        count = 0
        while pending:
            for path in pending.pop().iterdir():
                count += 1
                if count > ARCHIVE_FILE_LIMIT * 2:
                    raise ValueError("invalid resource")
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    _guard(path, directory=True)
                    pending.append(path)
                else:
                    _guard(path)
        manifest = parse_bundle_manifest(_read(root / "manifest.json", _MANIFEST_BYTES))
        if manifest.bundle_id != bundle_id:
            raise ValueError("invalid resource")
        verified = verify_retained_bundle_directory(
            directory=root, expected_embedding=manifest.embedding
        )
        try:
            return verified.manifest
        finally:
            verified.close()
    except Exception:
        raise BackupResourceError("RESTORE_BUNDLE_UNAVAILABLE") from None


def _resources(connection: sqlite3.Connection, data_directory: Path) -> None:
    if (
        connection.execute("SELECT 1 FROM embedding_switch_intent LIMIT 1").fetchone()
        or connection.execute(
            "SELECT 1 FROM scene_appearance_state WHERE journal_json IS NOT NULL LIMIT 1"
        ).fetchone()
        or connection.execute(
            "SELECT 1 FROM analysis_batches "
            "WHERE state IN ('queued','running','paused','cancelling') LIMIT 1"
        ).fetchone()
    ):
        raise BackupResourceError("RESTORE_WORK_PENDING")

    protected_ids: set[str] = set()
    bundle_ids: set[str] = set()
    for row in connection.execute(
        "SELECT active_bundle_id,previous_bundle_id,pinned_bundle_id FROM bundle_state"
    ):
        bundle_ids.update(value for value in row if value is not None)
        protected_ids.update(row[index] for index in (0, 2) if row[index] is not None)
    profiles = connection.execute("SELECT * FROM embedding_profiles WHERE active=1").fetchall()
    for profile in profiles:
        if profile["bundle_id"] is not None:
            bundle_ids.add(profile["bundle_id"])
            protected_ids.add(profile["bundle_id"])
    scene = connection.execute("SELECT * FROM scene_appearance_state").fetchone()
    if scene is not None and scene["source_bundle_id"] is not None:
        bundle_ids.add(scene["source_bundle_id"])
    bundle_ids.update(
        row[0]
        for row in connection.execute(
            "SELECT bundle_id FROM faq_entries WHERE review_state='approved'"
        )
    )
    manifests = {bundle_id: _bundle(data_directory, bundle_id) for bundle_id in sorted(bundle_ids)}
    if protected_ids:
        if len(profiles) != 1 or profiles[0]["dimension"] is None:
            raise BackupResourceError("RESTORE_EMBEDDING_INCOMPATIBLE")
        profile = profiles[0]
        try:
            identity = EmbeddingIdentity(
                adapter="openai_compatible"
                if profile["provider"] == "vllm"
                else profile["provider"],
                model_id=profile["model_id"],
                dimension=profile["dimension"],
                normalized=bool(profile["normalized"]),
                query_prefix=profile["query_prefix"],
                passage_prefix=profile["passage_prefix"],
            )
        except ValueError:
            raise BackupResourceError("RESTORE_EMBEDDING_INCOMPATIBLE") from None
        if any(manifests[bundle_id].embedding != identity for bundle_id in protected_ids):
            raise BackupResourceError("RESTORE_EMBEDDING_INCOMPATIBLE")

    if scene is not None and scene["source_bundle_id"] is not None:
        sprite = next(
            item
            for item in manifests[scene["source_bundle_id"]].files
            if item.path == "public/character.png"
        )
        if sprite.sha256 != scene["sprite_sha256"]:
            raise BackupResourceError("RESTORE_APPEARANCE_UNAVAILABLE")
        if scene["background_sha256"] is not None:
            try:
                digest, extension = scene["background_sha256"], scene["background_extension"]
                if not _HASH.fullmatch(digest) or extension not in {"png", "webp"}:
                    raise ValueError("invalid resource")
                content = _read(
                    data_directory / "scene-appearance" / "assets" / f"{digest}.{extension}",
                    2 * 1024 * 1024,
                )
                image = validate_scene_image(content, filename=f"background.{extension}")
                if image.sha256 != digest or image.content != content:
                    raise ValueError("invalid resource")
            except Exception:
                raise BackupResourceError("RESTORE_APPEARANCE_UNAVAILABLE") from None

    marker = data_directory / "local-portfolio" / "source-local"
    if marker.exists() or marker.is_symlink():
        try:
            _guard(marker)
            _guard(marker.with_name("draft.json"))
            if LocalPortfolioStore(data_directory).read() is None:
                raise ValueError("invalid resource")
        except Exception:
            raise BackupResourceError("RESTORE_PORTFOLIO_UNAVAILABLE") from None


def validate_restore_resources(
    candidate: Path, current: RuntimeDatabase, data_directory: Path
) -> None:
    """Validate retained host resources without activating, repairing or creating any.

    The caller seals the normalized candidate and holds its restore lifecycle
    gate through this check and replacement, preventing concurrent file changes.
    Gateway disablement and session revocation belong to that caller.
    """
    try:
        _guard(data_directory, directory=True)
        with (
            closing(_connection(candidate, immutable=True)) as proposed,
            closing(_connection(current.database_path, immutable=False)) as live,
        ):
            live.execute("BEGIN")
            if _owner(proposed) != _owner(live):
                raise BackupResourceError("RESTORE_OWNER_MISMATCH")
            _secrets(proposed, data_directory)
            _resources(proposed, data_directory)
    except BackupResourceError:
        raise
    except Exception:
        raise BackupResourceError("RESTORE_RESOURCE_INVALID") from None
