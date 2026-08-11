from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from reponpc.runtime.database import Migration, RuntimeDatabase, RuntimeDatabaseError


def table_names(database: RuntimeDatabase) -> set[str]:
    with database.connection() as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def test_runtime_database_is_idempotent_and_separate_from_index_data(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime-data")

    database.initialize()
    database.initialize()

    assert database.database_path == tmp_path / "runtime-data" / "runtime.sqlite"
    assert database.database_path.exists()
    assert database.schema_version() == 1
    assert {
        "runtime_schema_migrations",
        "admin_sessions",
        "rate_buckets",
        "daily_usage",
        "bundle_state",
        "admin_audit",
    } <= table_names(database)
    with pytest.raises(RuntimeDatabaseError, match="runtime storage is unavailable"):
        RuntimeDatabase(tmp_path / "index.sqlite")


def test_failed_migration_rolls_back_every_statement(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "rollback")
    broken = Migration(
        version=1,
        name="broken",
        statements=(
            "CREATE TABLE partial_runtime_change (value TEXT)",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(RuntimeDatabaseError) as raised:
        database.initialize(migrations=(broken,))

    assert raised.value.code == "runtime_migration_failed"
    assert "partial_runtime_change" not in table_names(database)
    assert database.schema_version() == 0


def test_concurrent_initialization_creates_one_versioned_schema(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "concurrent", busy_timeout_ms=10_000)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _unused: database.initialize(), range(2)))

    assert database.schema_version() == 1
    with database.connection() as connection:
        versions = connection.execute("SELECT version FROM runtime_schema_migrations").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
    assert [row[0] for row in versions] == [1]
    assert foreign_keys is not None and foreign_keys[0] == 1


def test_concurrent_initialization_across_database_owners_is_safe(tmp_path: Path) -> None:
    for attempt in range(5):
        data_dir = tmp_path / f"concurrent-owners-{attempt}"

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(
                executor.map(
                    lambda _unused, current_data_dir=data_dir: RuntimeDatabase(
                        current_data_dir, busy_timeout_ms=10_000
                    ).initialize(),
                    range(4),
                )
            )

        database = RuntimeDatabase(data_dir)
        database.initialize()
        assert database.schema_version() == 1
        with database.connection() as connection:
            versions = connection.execute(
                "SELECT version FROM runtime_schema_migrations"
            ).fetchall()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
        assert [row[0] for row in versions] == [1]
        assert journal_mode is not None and journal_mode[0] == "wal"


def test_failed_journal_mode_configuration_closes_connection_and_stays_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingConnection:
        closed = False
        row_factory: object | None = None

        def execute(self, statement: str) -> None:
            if statement == "PRAGMA journal_mode = WAL":
                raise sqlite3.OperationalError("injected journal failure")
            return None

        def close(self) -> None:
            self.closed = True

    connection = FailingConnection()
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connection)

    with pytest.raises(RuntimeDatabaseError) as error:
        RuntimeDatabase(tmp_path / "runtime").initialize()

    assert error.value.code == "runtime_configuration_failed"
    assert connection.closed is True


def test_runtime_schema_rejects_raw_session_csrf_and_ip_values(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "privacy")
    database.initialize()

    with database.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO admin_sessions(
                    session_hash, csrf_hash, created_at, last_seen_at, idle_expires_at,
                    absolute_expires_at, session_epoch
                ) VALUES (?, ?, 'now', 'now', 'later', 'later', 1)
                """,
                ("RAW_SESSION_CANARY", "RAW_CSRF_CANARY"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO rate_buckets(
                    ip_hmac, bucket_started_at, capacity, remaining_tokens, expires_at
                ) VALUES (?, 'now', 10, 10, 'later')
                """,
                ("192.0.2.99",),
            )


def test_runtime_database_reports_integrity_failure_without_exposing_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "corrupt"
    data_dir.mkdir()
    (data_dir / "runtime.sqlite").write_bytes(b"not a sqlite database")

    with pytest.raises(RuntimeDatabaseError) as raised:
        RuntimeDatabase(data_dir).initialize()

    assert raised.value.code in {"runtime_configuration_failed", "runtime_migration_failed"}
    assert str(data_dir) not in str(raised.value)
