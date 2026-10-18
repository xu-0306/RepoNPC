"""Offline normalization of untrusted SQLite bytes in caller-owned private storage."""

from __future__ import annotations

import os
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase, RuntimeDatabaseError

MAX_BACKUP_BYTES = 128 * 1024 * 1024
VALIDATION_SECONDS = 30.0
_MAX_SCHEMA_OBJECTS = 256
_MIGRATION_TABLE = "runtime_schema_migrations"


class BackupValidationError(ValueError):
    """A stable internal failure without uploaded values, SQL, or filesystem paths."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("backup validation failed")


@dataclass(frozen=True, slots=True)
class ValidatedBackup:
    """Current normalized database path and the validated source schema version."""

    path: Path
    schema_version: int


def _check_time(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise BackupValidationError("BACKUP_VALIDATION_TIMEOUT")


def _check_directory(directory: Path, *, fresh: bool = False) -> None:
    if (
        not directory.is_absolute()
        or ".." in directory.parts
        or directory.anchor.startswith("\\\\")
        or directory.as_posix().startswith("//")
    ):
        raise BackupValidationError("BACKUP_WORKING_DIRECTORY_INVALID")
    for ancestor in (directory, *directory.parents):
        info = ancestor.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BackupValidationError("BACKUP_WORKING_DIRECTORY_INVALID")
    if os.name != "nt" and stat.S_IMODE(directory.stat().st_mode) & 0o077:
        raise BackupValidationError("BACKUP_WORKING_DIRECTORY_NOT_PRIVATE")
    if fresh and next(directory.iterdir(), None) is not None:
        raise BackupValidationError("BACKUP_WORKING_DIRECTORY_NOT_FRESH")


def _regular_file(path: Path, identity: tuple[int, int] | None = None) -> None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or getattr(info, "st_file_attributes", 0) & 0x400
        or (identity is not None and (info.st_dev, info.st_ino) != identity)
    ):
        raise BackupValidationError("BACKUP_PRIVATE_FILE_INVALID")


def _create_file(path: Path, content: bytes) -> tuple[int, int]:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    identity: tuple[int, int] | None = None
    complete = False
    try:
        info = os.fstat(descriptor)
        identity = info.st_dev, info.st_ino
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BackupValidationError("BACKUP_PRIVATE_FILE_INVALID")
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
        _regular_file(path, identity)
        complete = True
        return identity
    finally:
        os.close(descriptor)
        if not complete and identity is not None:
            try:
                _regular_file(path, identity)
                path.unlink()
            except OSError, BackupValidationError:
                pass  # Do not unlink a substituted or externally linked file.


def _header(content: bytes) -> None:
    if not isinstance(content, bytes) or not 100 <= len(content) <= MAX_BACKUP_BYTES:
        raise BackupValidationError("BACKUP_SIZE_INVALID")
    page_size = int.from_bytes(content[16:18], "big")
    if page_size == 1:
        page_size = 65536
    if (
        content[:16] != b"SQLite format 3\x00"
        or page_size < 512
        or page_size > 65536
        or page_size & (page_size - 1)
        or len(content) % page_size
        or content[18] not in (1, 2)
        or content[19] not in (1, 2)
        or content[21:24] != bytes((64, 32, 32))
        or int.from_bytes(content[44:48], "big") not in (1, 2, 3, 4)
        or int.from_bytes(content[56:60], "big") != 1
        or content[72:92] != bytes(20)
    ):
        raise BackupValidationError("BACKUP_HEADER_INVALID")


def _harden(connection: sqlite3.Connection, deadline: float, *, readonly: bool) -> None:
    limits = {
        sqlite3.SQLITE_LIMIT_LENGTH: MAX_BACKUP_BYTES,
        sqlite3.SQLITE_LIMIT_SQL_LENGTH: 64 * 1024,
        sqlite3.SQLITE_LIMIT_COLUMN: 128,
        sqlite3.SQLITE_LIMIT_EXPR_DEPTH: 64,
        sqlite3.SQLITE_LIMIT_COMPOUND_SELECT: 16,
        sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER: 128,
        sqlite3.SQLITE_LIMIT_ATTACHED: 0,
        # SQLite's trusted FK cascade actions also use the trigger depth budget.
        sqlite3.SQLITE_LIMIT_TRIGGER_DEPTH: 0 if readonly else 16,
        sqlite3.SQLITE_LIMIT_LIKE_PATTERN_LENGTH: 4096,
        sqlite3.SQLITE_LIMIT_VDBE_OP: 100_000,
        sqlite3.SQLITE_LIMIT_WORKER_THREADS: 0,
    }
    for category, limit in limits.items():
        connection.setlimit(category, limit)
    connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    if hasattr(connection, "enable_load_extension"):
        connection.enable_load_extension(False)
    connection.execute("PRAGMA trusted_schema = OFF")
    if connection.execute("PRAGMA trusted_schema").fetchone()[0] != 0:
        raise BackupValidationError("BACKUP_SQLITE_CONFIGURATION_INVALID")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute("PRAGMA busy_timeout = 100")
    if readonly:
        connection.execute("PRAGMA query_only = ON")
    else:
        connection.execute("PRAGMA secure_delete = ON")


class _PrivateRuntimeDatabase(RuntimeDatabase):
    """Apply the shared trusted migrations with the same normalization deadline."""

    def __init__(self, directory: Path, identity: tuple[int, int], deadline: float) -> None:
        super().__init__(directory, busy_timeout_ms=100)
        self._identity = identity
        self._deadline = deadline

    def _open(self, *, configure_journal_mode: bool = False) -> sqlite3.Connection:
        _check_time(self._deadline)
        _check_directory(self.database_path.parent)
        _regular_file(self.database_path, self._identity)
        for suffix in ("-wal", "-shm", "-journal"):
            sibling = self.database_path.with_name(self.database_path.name + suffix)
            if sibling.exists() or sibling.is_symlink():
                _regular_file(sibling)
        connection = super()._open(configure_journal_mode=configure_journal_mode)
        try:
            _harden(connection, self._deadline, readonly=False)
            return connection
        except Exception:
            connection.close()
            raise


def _schema(connection: sqlite3.Connection) -> list[tuple[str, str, str, str | None]]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name LIMIT ?",
        (_MAX_SCHEMA_OBJECTS + 1,),
    ).fetchall()
    if len(rows) > _MAX_SCHEMA_OBJECTS or any(row[0] not in {"table", "index"} for row in rows):
        raise BackupValidationError("BACKUP_SCHEMA_INVALID")
    return [tuple(row) for row in rows]


def _migration_rows(connection: sqlite3.Connection) -> list[tuple[int, str]]:
    rows = connection.execute(
        "SELECT version, name FROM runtime_schema_migrations ORDER BY version LIMIT ?",
        (len(MIGRATIONS) + 1,),
    ).fetchall()
    return [tuple(row) for row in rows]


def _integrity(connection: sqlite3.Connection) -> None:
    if tuple(connection.execute("PRAGMA integrity_check(1)").fetchone() or ()) != ("ok",):
        raise BackupValidationError("BACKUP_INTEGRITY_INVALID")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise BackupValidationError("BACKUP_FOREIGN_KEYS_INVALID")


def _quote(identifier: str) -> str:
    # Identifiers come exclusively from a schema created by trusted migrations.
    return '"' + identifier.replace('"', '""') + '"'


def _copy_rows(source: sqlite3.Connection, target: sqlite3.Connection, deadline: float) -> None:
    tables = [row[1] for row in _schema(target) if row[0] == "table" and row[1] != _MIGRATION_TABLE]
    target.execute("PRAGMA foreign_keys = OFF")
    target.execute("BEGIN IMMEDIATE")
    try:
        for table in tables:
            target.execute(f"DELETE FROM {_quote(table)}")
        for table in tables:
            columns = [row[1] for row in target.execute(f"PRAGMA table_info({_quote(table)})")]
            names = ", ".join(_quote(column) for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            cursor = source.execute(f"SELECT {names} FROM {_quote(table)}")
            while True:
                _check_time(deadline)
                rows = cursor.fetchmany(128)
                if not rows:
                    break
                target.executemany(
                    f"INSERT INTO {_quote(table)} ({names}) VALUES ({placeholders})", rows
                )
        target.execute("COMMIT")
    except Exception:
        if target.in_transaction:
            target.execute("ROLLBACK")
        raise
    finally:
        target.execute("PRAGMA foreign_keys = ON")
    _integrity(target)


def _revoke_authority(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT state_key, session_epoch FROM admin_state").fetchall()
    if (
        len(rows) != 1
        or rows[0][0] != "current"
        or not isinstance(rows[0][1], int)
        or not 0 <= rows[0][1] < 2**63 - 1
    ):
        raise BackupValidationError("BACKUP_AUTH_STATE_INVALID")
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("UPDATE admin_audit SET session_hash = NULL")
        for table in (
            "admin_oauth_transactions",
            "scene_background_drafts",
            "admin_sessions",
            "admin_setup",
            "admin_local_launch_grants",
        ):
            connection.execute(f"DELETE FROM {_quote(table)}")
        connection.execute(
            "UPDATE admin_state SET session_epoch = ? WHERE state_key = 'current'",
            (rows[0][1] + 1,),
        )
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def _cleanup(
    source_path: Path,
    source_identity: tuple[int, int] | None,
    output: Path,
    output_identity: tuple[int, int] | None,
    *,
    keep_output: bool,
    owned_directory: bool,
) -> None:
    if source_identity is not None:
        _regular_file(source_path, source_identity)
        source_path.unlink()
    if not keep_output and output_identity is not None:
        for suffix in ("-wal", "-shm", "-journal", ""):
            path = output.with_name(output.name + suffix)
            if path.exists() or path.is_symlink():
                _regular_file(path, output_identity if not suffix else None)
                path.unlink()
    if not keep_output and owned_directory:
        output.parent.rmdir()


def validate_backup(sqlite_bytes: bytes, working_directory: Path) -> ValidatedBackup:
    """Validate raw SQLite and produce current trusted-schema, session-free storage.

    The caller supplies a fresh private local directory, keeps it inaccessible to
    concurrent writers, and owns its eventual cleanup. Windows directory ACLs are
    the caller's responsibility. The returned version describes the source;
    the returned database has all current migrations. No live runtime is opened.
    """
    _header(sqlite_bytes)
    deadline = time.monotonic() + VALIDATION_SECONDS
    source_path = working_directory / "uploaded.sqlite"
    output = working_directory / "normalized/runtime.sqlite"
    source_identity: tuple[int, int] | None = None
    output_identity: tuple[int, int] | None = None
    complete = False
    owned_directory = False
    try:
        _check_directory(working_directory, fresh=True)
        source_identity = _create_file(source_path, sqlite_bytes)
        output.parent.mkdir(mode=0o700)
        owned_directory = True
        output_identity = _create_file(output, b"")
        database = _PrivateRuntimeDatabase(output.parent, output_identity, deadline)
        database.initialize(migrations=MIGRATIONS[:1])
        _regular_file(source_path, source_identity)
        source = sqlite3.connect(
            source_path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=0.1
        )
        try:
            _harden(source, deadline, readonly=True)
            source_schema = _schema(source)
            with database.connection() as target:
                expected_metadata = next(
                    row for row in _schema(target) if row[1] == _MIGRATION_TABLE
                )
            if expected_metadata not in source_schema:
                raise BackupValidationError("BACKUP_SCHEMA_INVALID")
            applied = _migration_rows(source)
            expected = [(item.version, item.name) for item in MIGRATIONS[: len(applied)]]
            if not applied or applied != expected:
                raise BackupValidationError("BACKUP_MIGRATIONS_INVALID")
            source_version = applied[-1][0]
            database.initialize(migrations=MIGRATIONS[: len(applied)])
            with database.connection() as target:
                if source_schema != _schema(target):
                    raise BackupValidationError("BACKUP_SCHEMA_INVALID")
                _integrity(source)
                _copy_rows(source, target, deadline)
        finally:
            source.close()
        database.initialize()
        with database.connection() as target:
            _revoke_authority(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.execute("PRAGMA journal_mode = DELETE")
            # VACUUM internally attaches its own temporary database. Only the
            # trusted output connection receives this one-operation allowance.
            target.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 1)
            try:
                target.execute("VACUUM")
            finally:
                target.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
            _integrity(target)
            if _migration_rows(target) != [(item.version, item.name) for item in MIGRATIONS]:
                raise BackupValidationError("BACKUP_MIGRATIONS_INVALID")
        _check_time(deadline)
        _regular_file(source_path, source_identity)
        _regular_file(output, output_identity)
        complete = True
        return ValidatedBackup(output, source_version)
    except BackupValidationError:
        raise
    except sqlite3.Error, RuntimeDatabaseError, OSError, MemoryError:
        if time.monotonic() >= deadline:
            raise BackupValidationError("BACKUP_VALIDATION_TIMEOUT") from None
        raise BackupValidationError("BACKUP_SQLITE_INVALID") from None
    finally:
        try:
            _cleanup(
                source_path,
                source_identity,
                output,
                output_identity,
                keep_output=complete,
                owned_directory=owned_directory,
            )
        except OSError, BackupValidationError:
            raise BackupValidationError("BACKUP_PRIVATE_FILE_INVALID") from None
