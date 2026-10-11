"""Owner-scoped encrypted backups and stopped-lifecycle runtime replacement."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import tempfile
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI

from reponpc.admin.backup_encryption import MAGIC, MAX_SQLITE_BYTES, BackupMetadata, seal, unseal
from reponpc.admin.backup_validation import validate_backup
from reponpc.admin.maintenance_host import MaintenanceHost, Replacement
from reponpc.runtime.database import RuntimeDatabase


class MaintenanceError(ValueError):
    """A safe maintenance failure without a local path or uploaded content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("maintenance operation failed")


@dataclass(slots=True, repr=False)
class _Preview:
    preview_id: str
    session_hash: str
    directory: Path
    database_path: Path
    metadata: BackupMetadata
    expires_at: datetime
    database_sha256: str
    password: str = field(repr=False)

    def public(self) -> dict[str, object]:
        return {
            "preview_id": self.preview_id,
            **asdict(self.metadata),
            "expires_at": self.expires_at.isoformat(),
        }


def _safe_directory(path: Path) -> None:
    for item in (*reversed(path.parents), path):
        if item.is_symlink() or item.is_junction() or (item.exists() and not item.is_dir()):
            raise MaintenanceError("BACKUP_STORAGE_UNAVAILABLE")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise MaintenanceError("BACKUP_STORAGE_UNAVAILABLE")


def _read_regular(path: Path, maximum: int) -> bytes:
    info = path.lstat()
    if (
        path.is_symlink()
        or path.is_junction()
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_size > maximum
    ):
        raise MaintenanceError("BACKUP_STORAGE_UNAVAILABLE")
    with path.open("rb") as stream:
        result = stream.read(maximum + 1)
    if len(result) > maximum:
        raise MaintenanceError("BACKUP_TOO_LARGE")
    return result


class MaintenanceService:
    """One bounded password-bearing preview; passwords exist only in process memory."""

    def __init__(
        self,
        database: RuntimeDatabase,
        *,
        resource_check: Callable[[Path], None],
        application_factory: Callable[[], FastAPI],
        idle_check: Callable[[], None],
    ) -> None:
        self.database = database
        self._root = database.database_path.parent / "private" / "maintenance"
        self._resources = resource_check
        self._factory = application_factory
        self._idle = idle_check
        self._preview: _Preview | None = None
        self._preview_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._restoring = False

    def _working_directory(self) -> Path:
        _safe_directory(self._root)
        return Path(tempfile.mkdtemp(prefix="preview-", dir=self._root))

    def _discard(self) -> None:
        timer, self._preview_timer = self._preview_timer, None
        if timer is not None:
            timer.cancel()
        preview, self._preview = self._preview, None
        if preview is not None:
            preview.password = ""
            # This exact fresh directory is owned by this service, never an uploaded path.
            if preview.directory.parent != self._root or preview.directory.is_symlink():
                raise MaintenanceError("BACKUP_STORAGE_UNAVAILABLE")
            shutil.rmtree(preview.directory)

    def _expire(self, preview_id: str) -> None:
        with self._lock:
            if self._preview is not None and self._preview.preview_id == preview_id:
                self._preview.password = ""
                if not self._restoring:
                    self._discard()

    def close(self, *, abort_restore: bool = False) -> None:
        with self._lock:
            if abort_restore:
                self._restoring = False
            if not self._restoring:
                self._discard()

    def reconcile_host(self, host: MaintenanceHost) -> None:
        if self._restoring and not host.busy and host.last_error is not None:
            with self._lock:
                self._restoring = False
                if self._preview is not None and self._preview.expires_at <= datetime.now(UTC):
                    self._discard()

    def _metadata(self) -> BackupMetadata:
        return BackupMetadata(
            datetime.now(UTC).isoformat(), self.database.schema_version(), version("reponpc")
        )

    def _encrypted_snapshot(self, directory: Path, password: str) -> bytes:
        destination = directory / f"snapshot-{secrets.token_hex(8)}.sqlite"
        try:
            _read_regular(self.database.database_path, MAX_SQLITE_BYTES)
            self.database.backup_to(destination)
            if os.name != "nt":
                destination.chmod(0o600)
            return seal(_read_regular(destination, MAX_SQLITE_BYTES), password, self._metadata())
        finally:
            destination.unlink(missing_ok=True)

    def backup(self, password: str) -> bytes:
        return self.backup_for_download(password)[0]

    def backup_for_download(self, password: str) -> tuple[bytes, str]:
        if not self._lock.acquire(blocking=False):
            raise MaintenanceError("MAINTENANCE_BUSY")
        directory: Path | None = None
        try:
            if self._restoring:
                raise MaintenanceError("MAINTENANCE_BUSY")
            directory = self._working_directory()
            artifact = self._encrypted_snapshot(directory, password)
            # A successful ciphertext is kept locally as an additional recovery copy.
            stored = self._save_encrypted(artifact)
            return artifact, stored.name.removeprefix("backup-").removesuffix(".reponpc-backup")
        finally:
            if directory is not None:
                shutil.rmtree(directory)
            self._lock.release()

    def read_backup(self, backup_id: str) -> bytes:
        if re.fullmatch(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{16}", backup_id) is None:
            raise MaintenanceError("BACKUP_FORMAT_INVALID")
        _safe_directory(self._root)
        path = self._root / f"backup-{backup_id}.reponpc-backup"
        if not path.exists():
            raise MaintenanceError("BACKUP_DOWNLOAD_UNAVAILABLE")
        content = _read_regular(path, MAX_SQLITE_BYTES + 8192)
        if not content.startswith(MAGIC):
            raise MaintenanceError("BACKUP_FORMAT_INVALID")
        return content

    def _save_encrypted(self, artifact: bytes) -> Path:
        _safe_directory(self._root)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        name = f"backup-{stamp}-{secrets.token_hex(8)}.reponpc-backup"
        path = self._root / name
        temporary = path.with_suffix(".tmp")
        try:
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(artifact)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def last_backup_at(self) -> str | None:
        if not self._root.exists():
            return None
        _safe_directory(self._root)
        files = list(self._root.glob("backup-*.reponpc-backup"))
        times = [
            item.lstat().st_mtime for item in files if item.is_file() and not item.is_symlink()
        ]
        return datetime.fromtimestamp(max(times), UTC).isoformat() if times else None

    def inspect(self, artifact: bytes, password: str, session_hash: str) -> dict[str, object]:
        if not self._lock.acquire(blocking=False):
            raise MaintenanceError("MAINTENANCE_BUSY")
        directory: Path | None = None
        try:
            if self._restoring:
                raise MaintenanceError("MAINTENANCE_BUSY")
            self._discard()
            metadata, content = unseal(artifact, password)
            if metadata.application_version != version("reponpc"):
                raise MaintenanceError("BACKUP_VERSION_UNSUPPORTED")
            directory = self._working_directory()
            validated = validate_backup(content, directory)
            if validated.schema_version != metadata.schema_version:
                raise MaintenanceError("BACKUP_METADATA_INVALID")
            self._resources(validated.path)
            preview = _Preview(
                secrets.token_urlsafe(32),
                session_hash,
                directory,
                validated.path,
                metadata,
                datetime.now(UTC) + timedelta(minutes=10),
                hashlib.sha256(_read_regular(validated.path, MAX_SQLITE_BYTES)).hexdigest(),
                password,
            )
            self._preview = preview
            self._preview_timer = threading.Timer(600, self._expire, args=(preview.preview_id,))
            self._preview_timer.daemon = True
            self._preview_timer.start()
            directory = None
            return preview.public()
        finally:
            if directory is not None:
                shutil.rmtree(directory)
            self._lock.release()

    def _selected(self, preview_id: str, session_hash: str) -> _Preview:
        preview = self._preview
        if preview is not None and preview.expires_at <= datetime.now(UTC) and not self._restoring:
            self._discard()
            preview = None
        if (
            preview is None
            or not secrets.compare_digest(preview.preview_id, preview_id)
            or not secrets.compare_digest(preview.session_hash, session_hash)
            or preview.expires_at <= datetime.now(UTC)
        ):
            raise MaintenanceError("RESTORE_PREVIEW_EXPIRED")
        return preview

    def cancel(self, preview_id: str, session_hash: str) -> None:
        with self._lock:
            if self._restoring:
                raise MaintenanceError("MAINTENANCE_BUSY")
            self._selected(preview_id, session_hash)
            self._discard()

    def restore(self, preview_id: str, session_hash: str, host: MaintenanceHost) -> None:
        with self._lock:
            preview = self._selected(preview_id, session_hash)
            if self._restoring or host.busy:
                raise MaintenanceError("MAINTENANCE_BUSY")
            self._restoring = True

            def before_stop() -> None:
                try:
                    with self._lock:
                        self._selected(preview.preview_id, preview.session_hash)
                    self._check_candidate(preview)
                    self._idle()
                    self._resources(preview.database_path)
                except Exception:
                    with self._lock:
                        self._restoring = False
                        if preview.expires_at <= datetime.now(UTC):
                            self._discard()
                    raise

            try:
                host.schedule(lambda: self._replace(preview), before_stop=before_stop)
            except Exception:
                self._restoring = False
                raise

    def verify_restore(self, preview_id: str, session_hash: str) -> None:
        with self._lock:
            if self._restoring:
                raise MaintenanceError("MAINTENANCE_BUSY")
            preview = self._selected(preview_id, session_hash)
            self._check_candidate(preview)
            self._idle()
            self._resources(preview.database_path)

    @staticmethod
    def _check_candidate(preview: _Preview) -> None:
        actual = hashlib.sha256(_read_regular(preview.database_path, MAX_SQLITE_BYTES)).hexdigest()
        if not secrets.compare_digest(actual, preview.database_sha256):
            raise MaintenanceError("BACKUP_SQLITE_INVALID")

    def _replace(self, preview: _Preview) -> Replacement:
        """Called only after every request and old application lifespan has stopped."""
        current = self.database.database_path
        pointer = current.parent / "bundles" / "active.json"
        old_pointer = _read_regular(pointer, 4096) if pointer.exists() else None
        rollback_path = preview.directory / "rollback.sqlite"
        swapped = False

        def rollback() -> FastAPI:
            if swapped:
                os.replace(rollback_path, current)
                self._write_pointer(pointer, old_pointer)
            self._restoring = False
            with self._lock:
                self._discard()
            return self._factory()

        try:
            with self._lock:
                self._selected(preview.preview_id, preview.session_hash)
            self._check_candidate(preview)
            self._resources(preview.database_path)
            with self._lock:
                self._selected(preview.preview_id, preview.session_hash)
            artifact = self._encrypted_snapshot(preview.directory, preview.password)
            self._save_encrypted(artifact)
            with self.database.connection() as connection:
                row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if row is None or int(row[0]) != 0:
                    raise MaintenanceError("MAINTENANCE_BUSY")
            # No connection or worker may remain; nonempty WAL must never be discarded.
            wal = current.with_name(current.name + "-wal")
            if wal.exists() and wal.stat().st_size:
                raise MaintenanceError("MAINTENANCE_BUSY")
            self.database.backup_to(rollback_path)
            with closing(sqlite3.connect(preview.database_path)) as connection, connection:
                connection.execute(
                    """UPDATE visitor_gateway_settings SET enabled=0, revision=revision+1,
                    verification_gateway_origin=NULL, verification_pages_origin=NULL,
                    verification_bundle_id=NULL, verified_at=NULL, verification_method=NULL"""
                )
                row = connection.execute(
                    "SELECT active_bundle_id, pinned_bundle_id "
                    "FROM bundle_state WHERE state_key='current'"
                ).fetchone()
            selected = (row[1] or row[0]) if row is not None else None
            target_pointer = json.dumps({"bundle_id": selected}).encode() if selected else None
            os.replace(preview.database_path, current)
            swapped = True
            self._write_pointer(pointer, target_pointer)
            fresh = self._factory()

            def commit() -> None:
                self._restoring = False
                with self._lock:
                    self._discard()

            return Replacement(fresh, rollback, commit)
        except Exception:
            if swapped:
                os.replace(rollback_path, current)
                self._write_pointer(pointer, old_pointer)
            self._restoring = False
            with self._lock:
                self._discard()
            raise MaintenanceError("RESTORE_FAILED") from None

    @staticmethod
    def _write_pointer(pointer: Path, payload: bytes | None) -> None:
        if payload is None:
            pointer.unlink(missing_ok=True)
            return
        # Parent has already passed the retained-resource boundary.
        temporary = pointer.with_name(f".restore-{secrets.token_hex(12)}.json")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, pointer)
        finally:
            temporary.unlink(missing_ok=True)
