"""Transactional SQLite owner for mutable RepoNPC runtime state."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final

DEFAULT_BUSY_TIMEOUT_MS: Final = 5_000


class RuntimeDatabaseError(RuntimeError):
    """A safe runtime-storage failure without database internals in its text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("runtime storage is unavailable")


@dataclass(frozen=True, slots=True)
class Migration:
    """One all-or-nothing runtime schema revision."""

    version: int
    name: str
    statements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BundleRuntimeState:
    """Safe mutable activation state; IDs and ETags are never secret values."""

    active_bundle_id: str | None
    previous_bundle_id: str | None
    pinned_bundle_id: str | None
    manifest_etag: str | None
    last_checked_at: str | None
    safe_update_error: str | None


MIGRATIONS: Final[tuple[Migration, ...]] = (
    Migration(
        version=1,
        name="runtime-foundation",
        statements=(
            """
            CREATE TABLE admin_sessions (
                session_hash TEXT PRIMARY KEY
                    CHECK(length(session_hash) = 64 AND session_hash NOT GLOB '*[^0-9a-f]*'),
                csrf_hash TEXT NOT NULL
                    CHECK(length(csrf_hash) = 64 AND csrf_hash NOT GLOB '*[^0-9a-f]*'),
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                idle_expires_at TEXT NOT NULL,
                absolute_expires_at TEXT NOT NULL,
                session_epoch INTEGER NOT NULL,
                revoked_at TEXT
            )
            """,
            """
            CREATE TABLE rate_buckets (
                ip_hmac TEXT NOT NULL
                    CHECK(length(ip_hmac) = 64 AND ip_hmac NOT GLOB '*[^0-9a-f]*'),
                bucket_started_at TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                remaining_tokens REAL NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (ip_hmac, bucket_started_at)
            )
            """,
            """
            CREATE TABLE daily_usage (
                usage_date TEXT PRIMARY KEY,
                accepted_count INTEGER NOT NULL,
                input_token_count INTEGER,
                output_token_count INTEGER,
                estimated_cost_micros INTEGER
            )
            """,
            """
            CREATE TABLE bundle_state (
                state_key TEXT PRIMARY KEY,
                active_bundle_id TEXT,
                previous_bundle_id TEXT,
                pinned_bundle_id TEXT,
                manifest_etag TEXT,
                last_checked_at TEXT,
                safe_update_error TEXT
            )
            """,
            """
            CREATE TABLE admin_audit (
                audit_id INTEGER PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                action TEXT NOT NULL,
                target_path TEXT,
                result_commit_sha TEXT,
                request_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                session_hash TEXT REFERENCES admin_sessions(session_hash)
            )
            """,
            "CREATE INDEX admin_audit_occurred_at_idx ON admin_audit(occurred_at)",
            "CREATE INDEX rate_buckets_expiry_idx ON rate_buckets(expires_at)",
        ),
    ),
    Migration(
        version=2,
        name="admin-auth-state",
        statements=(
            """
            CREATE TABLE admin_state (
                state_key TEXT PRIMARY KEY,
                session_epoch INTEGER NOT NULL CHECK(session_epoch >= 0)
            )
            """,
            "INSERT INTO admin_state(state_key, session_epoch) VALUES ('current', 0)",
            """
            CREATE TABLE admin_login_backoff (
                identity_hmac TEXT PRIMARY KEY
                    CHECK(length(identity_hmac) = 64
                          AND identity_hmac NOT GLOB '*[^0-9a-f]*'),
                failure_count INTEGER NOT NULL CHECK(failure_count >= 0),
                next_allowed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX admin_login_backoff_expiry_idx ON admin_login_backoff(expires_at)",
        ),
    ),
)


class RuntimeDatabase:
    """Create and migrate only ``REPONPC_DATA_DIR/runtime.sqlite``."""

    # A WAL transition takes an exclusive SQLite lock.  SQLite's WAL negotiation
    # can race with another startup connection before either owner has applied
    # migrations, so process-wide startup negotiation is serialized alongside
    # the per-database migration lock. Normal connections remain concurrent.
    _initialization_locks: ClassVar[dict[Path, threading.RLock]] = {}
    _initialization_locks_guard: ClassVar[threading.Lock] = threading.Lock()
    _journal_mode_lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, data_dir: Path, *, busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS) -> None:
        if data_dir.name.casefold() == "index.sqlite":
            raise RuntimeDatabaseError("runtime_data_dir_invalid")
        if busy_timeout_ms <= 0:
            raise ValueError("busy_timeout_ms must be positive")
        self._data_dir = data_dir
        self._busy_timeout_ms = busy_timeout_ms

    @property
    def database_path(self) -> Path:
        """Return the sole mutable database location without opening it."""

        return self._data_dir / "runtime.sqlite"

    def initialize(self, *, migrations: Sequence[Migration] = MIGRATIONS) -> None:
        """Apply schema revisions and validate integrity before runtime use."""

        with (
            self._journal_mode_lock,
            self._initialization_lock(),
            self._configured_initialization_connection() as connection,
        ):
            self._apply_migrations(connection, migrations)
            self._check_integrity(connection)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open a configured connection and reliably close it after use."""

        connection = self._open()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _configured_initialization_connection(self) -> Iterator[sqlite3.Connection]:
        """Open the one connection allowed to change the persistent WAL mode."""

        connection = self._open(configure_journal_mode=True)
        try:
            yield connection
        finally:
            connection.close()

    def schema_version(self) -> int:
        """Return the most recently committed migration version, or zero."""

        with self.connection() as connection:
            if not self._has_migration_table(connection):
                return 0
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM runtime_schema_migrations"
            ).fetchone()
            return int(row[0])

    def bundle_state(self) -> BundleRuntimeState:
        """Return the one safe runtime bundle-state row, creating no index data."""

        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT active_bundle_id, previous_bundle_id, pinned_bundle_id,
                       manifest_etag, last_checked_at, safe_update_error
                FROM bundle_state WHERE state_key = 'current'
                """
            ).fetchone()
        if row is None:
            return BundleRuntimeState(None, None, None, None, None, None)
        return BundleRuntimeState(
            active_bundle_id=str(row["active_bundle_id"]) if row["active_bundle_id"] else None,
            previous_bundle_id=str(row["previous_bundle_id"])
            if row["previous_bundle_id"]
            else None,
            pinned_bundle_id=str(row["pinned_bundle_id"]) if row["pinned_bundle_id"] else None,
            manifest_etag=str(row["manifest_etag"]) if row["manifest_etag"] else None,
            last_checked_at=str(row["last_checked_at"]) if row["last_checked_at"] else None,
            safe_update_error=str(row["safe_update_error"]) if row["safe_update_error"] else None,
        )

    def save_bundle_state(self, state: BundleRuntimeState) -> None:
        """Atomically persist safe activation metadata in mutable runtime.sqlite."""

        with self.connection() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO bundle_state(
                      state_key, active_bundle_id, previous_bundle_id, pinned_bundle_id,
                      manifest_etag, last_checked_at, safe_update_error
                    ) VALUES ('current', ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(state_key) DO UPDATE SET
                      active_bundle_id = excluded.active_bundle_id,
                      previous_bundle_id = excluded.previous_bundle_id,
                      pinned_bundle_id = excluded.pinned_bundle_id,
                      manifest_etag = excluded.manifest_etag,
                      last_checked_at = excluded.last_checked_at,
                      safe_update_error = excluded.safe_update_error
                    """,
                    (
                        state.active_bundle_id,
                        state.previous_bundle_id,
                        state.pinned_bundle_id,
                        state.manifest_etag,
                        state.last_checked_at,
                        state.safe_update_error,
                    ),
                )
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                self._rollback(connection)
                raise RuntimeDatabaseError("runtime_bundle_state_failed") from exc

    def _initialization_lock(self) -> threading.RLock:
        """Return the process-local startup lock for this exact runtime database."""

        key = self.database_path.resolve(strict=False)
        with self._initialization_locks_guard:
            return self._initialization_locks.setdefault(key, threading.RLock())

    def _open(self, *, configure_journal_mode: bool = False) -> sqlite3.Connection:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                self.database_path,
                timeout=self._busy_timeout_ms / 1_000,
                isolation_level=None,
            )
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeDatabaseError("runtime_open_failed") from exc
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
            if configure_journal_mode:
                connection.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as exc:
            connection.close()
            raise RuntimeDatabaseError("runtime_configuration_failed") from exc
        return connection

    @staticmethod
    def _has_migration_table(connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'runtime_schema_migrations'"
        ).fetchone()
        return row is not None

    @staticmethod
    def _validate_migrations(migrations: Sequence[Migration]) -> tuple[Migration, ...]:
        ordered = tuple(sorted(migrations, key=lambda migration: migration.version))
        versions = [migration.version for migration in ordered]
        if (
            not ordered
            or any(version <= 0 for version in versions)
            or len(versions) != len(set(versions))
        ):
            raise ValueError("migrations must have unique positive versions")
        return ordered

    def _apply_migrations(
        self,
        connection: sqlite3.Connection,
        migrations: Sequence[Migration],
    ) -> None:
        ordered = self._validate_migrations(migrations)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                int(row["version"]): str(row["name"])
                for row in connection.execute(
                    "SELECT version, name FROM runtime_schema_migrations"
                ).fetchall()
            }
            for migration in ordered:
                applied_name = applied.get(migration.version)
                if applied_name is not None:
                    if applied_name != migration.name:
                        raise RuntimeDatabaseError("runtime_migration_mismatch")
                    continue
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO runtime_schema_migrations(version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
            connection.execute("COMMIT")
        except RuntimeDatabaseError:
            self._rollback(connection)
            raise
        except sqlite3.Error as exc:
            self._rollback(connection)
            raise RuntimeDatabaseError("runtime_migration_failed") from exc

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")

    @staticmethod
    def _check_integrity(connection: sqlite3.Connection) -> None:
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.Error as exc:
            raise RuntimeDatabaseError("runtime_integrity_failed") from exc
        if row is None or str(row[0]).casefold() != "ok":
            raise RuntimeDatabaseError("runtime_integrity_failed")
