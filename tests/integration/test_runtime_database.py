from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from reponpc.runtime.database import MIGRATIONS, Migration, RuntimeDatabase, RuntimeDatabaseError


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
    assert database.schema_version() == 20
    assert {
        "runtime_schema_migrations",
        "admin_sessions",
        "rate_buckets",
        "daily_usage",
        "bundle_state",
        "analysis_batches",
        "analysis_batch_items",
        "analysis_batch_events",
        "analysis_cache_entries",
        "github_rate_state",
        "embedding_profiles",
        "embedding_switch_intent",
        "admin_audit",
        "admin_owner",
        "admin_setup",
        "admin_auth_methods",
        "admin_oauth_transactions",
        "admin_github_credentials",
        "admin_local_launch_grants",
        "github_public_resolution_cache",
        "model_connections",
        "model_connection_secrets",
        "chat_profiles",
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


def test_provider_message_migration_is_atomic(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "provider-message-rollback")
    previous = tuple(m for m in MIGRATIONS if m.version < 20)
    database.initialize(migrations=previous)
    migration = next(m for m in MIGRATIONS if m.version == 20)
    broken = Migration(
        version=20, name=migration.name, statements=(migration.statements[0], "INVALID SQL")
    )
    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))
    assert database.schema_version() == 19
    with database.connection() as connection:
        for table in ("chat_profiles", "embedding_profiles"):
            assert "last_error_message" not in {
                row[1] for row in connection.execute(f"PRAGMA table_info({table})")
            }
    database.initialize()
    assert database.schema_version() == 20


def test_concurrent_initialization_creates_one_versioned_schema(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "concurrent", busy_timeout_ms=10_000)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _unused: database.initialize(), range(2)))

    assert database.schema_version() == 20
    with database.connection() as connection:
        versions = connection.execute("SELECT version FROM runtime_schema_migrations").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        assert [row[0] for row in versions] == list(range(1, 21))
    assert foreign_keys is not None and foreign_keys[0] == 1


def test_model_setup_migration_rolls_back_as_one_unit(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "model-setup-rollback")
    database.initialize(migrations=MIGRATIONS[:15])
    migration = MIGRATIONS[15]
    broken = Migration(
        version=migration.version,
        name=migration.name,
        statements=(*migration.statements[:2], "THIS IS NOT VALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError) as raised:
        database.initialize(migrations=(*MIGRATIONS[:15], broken))

    assert raised.value.code == "runtime_migration_failed"
    assert database.schema_version() == 15
    with database.connection() as connection:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(embedding_profiles)").fetchall()
        }
    assert "model_connections" not in tables
    assert "model_connection_secrets" not in tables
    assert "connection_revision" not in columns


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
        assert database.schema_version() == 20
        with database.connection() as connection:
            versions = connection.execute(
                "SELECT version FROM runtime_schema_migrations"
            ).fetchall()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            assert [row[0] for row in versions] == list(range(1, 21))
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
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO admin_setup VALUES ('current', ?, 'now', 'later')",
                ("RAW_SETUP_CODE",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO admin_owner VALUES ('current', 'owner', ?, 'now')",
                ("plaintext-password",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO admin_local_launch_grants VALUES ('current', ?, 'now', 'later', NULL)",
                ("RAW_LOCAL_LAUNCH_GRANT",),
            )


def test_local_launch_migration_preserves_durable_state_and_retires_login_identity(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "local-launch-migration")
    database.initialize(migrations=MIGRATIONS[:12])
    session_hash = "a" * 64
    csrf_hash = "b" * 64
    credential_nonce = b"preserved-nonce"
    credential_ciphertext = b"preserved-ciphertext"
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner(state_key, username, password_hash, created_at) "
            "VALUES ('current', 'owner', '$argon2id$preserved', 'created')"
        )
        connection.execute(
            "INSERT INTO admin_auth_methods(method, github_user_id, github_login, created_at) "
            "VALUES ('local_password', NULL, NULL, 'created')"
        )
        connection.execute(
            "INSERT INTO admin_auth_methods(method, github_user_id, github_login, created_at) "
            "VALUES ('github', '42', 'owner', 'created')"
        )
        connection.execute("UPDATE admin_state SET session_epoch = 7 WHERE state_key = 'current'")
        connection.execute(
            """
            INSERT INTO admin_sessions(
                session_hash, csrf_hash, created_at, last_seen_at, idle_expires_at,
                absolute_expires_at, session_epoch, authenticated_at
            ) VALUES (?, ?, 'created', 'seen', 'idle', 'absolute', 7, 'authenticated')
            """,
            (session_hash, csrf_hash),
        )
        connection.execute(
            """
            INSERT INTO admin_github_credentials(
                purpose, token_nonce, token_ciphertext, key_version, github_user_id,
                github_login, status, created_at, updated_at
            ) VALUES (
                'identity_public_read', ?, ?, 1, '42', 'owner', 'ready', 'created', 'updated'
            )
            """,
            (credential_nonce, credential_ciphertext),
        )
        connection.execute(
            """
            INSERT INTO admin_oauth_transactions(
                state_hash, intent, verifier_nonce, verifier_ciphertext, session_hash,
                created_at, expires_at, return_path
            ) VALUES (?, 'link', X'01', X'02', ?, 'created', 'expires', '/admin')
            """,
            ("c" * 64, session_hash),
        )
        connection.commit()

    database.initialize()

    with database.connection() as connection:
        owner = connection.execute(
            "SELECT username, password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()
        epoch = connection.execute(
            "SELECT session_epoch FROM admin_state WHERE state_key = 'current'"
        ).fetchone()
        session = connection.execute(
            "SELECT session_epoch, authenticated_at FROM admin_sessions WHERE session_hash = ?",
            (session_hash,),
        ).fetchone()
        methods = connection.execute(
            "SELECT method FROM admin_auth_methods ORDER BY method"
        ).fetchall()
        method_columns = [
            row["name"] for row in connection.execute("PRAGMA table_info(admin_auth_methods)")
        ]
        credential = connection.execute(
            """
            SELECT purpose, token_nonce, token_ciphertext, github_user_id
            FROM admin_github_credentials
            """
        ).fetchone()
        transaction = connection.execute(
            "SELECT intent, session_hash FROM admin_oauth_transactions"
        ).fetchone()
        connection.execute(
            "UPDATE admin_owner SET password_hash = NULL WHERE state_key = 'current'"
        )
        passwordless = connection.execute(
            "SELECT password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()

    assert owner is not None and tuple(owner) == ("owner", "$argon2id$preserved")
    assert epoch is not None and epoch[0] == 7
    assert session is not None and tuple(session) == (7, "authenticated")
    assert [row[0] for row in methods] == ["local_password"]
    assert method_columns == ["method", "created_at"]
    assert "admin_oauth_handoffs" not in table_names(database)
    assert credential is None
    assert transaction is None
    assert passwordless is not None and passwordless[0] is None


def test_local_launch_migration_failure_rolls_back_schema_and_rows(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "local-launch-rollback")
    database.initialize(migrations=MIGRATIONS[:12])
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner(state_key, username, password_hash, created_at) "
            "VALUES ('current', 'owner', '$argon2id$preserved', 'created')"
        )
        connection.commit()

    migration = next(item for item in MIGRATIONS if item.version == 13)
    broken = Migration(
        version=13,
        name=migration.name,
        statements=(*migration.statements, "THIS IS NOT VALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError) as raised:
        database.initialize(migrations=(*MIGRATIONS[:12], broken))

    with database.connection() as connection:
        owner = connection.execute(
            "SELECT password_hash FROM admin_owner WHERE state_key = 'current'"
        ).fetchone()
        columns = {
            str(row["name"]): int(row["notnull"])
            for row in connection.execute("PRAGMA table_info(admin_owner)").fetchall()
        }

    assert raised.value.code == "runtime_migration_failed"
    assert database.schema_version() == 12
    assert owner is not None and owner[0] == "$argon2id$preserved"
    assert columns["password_hash"] == 1
    assert "admin_local_launch_grants" not in table_names(database)


def test_public_read_retirement_preserves_unrelated_runtime_state(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "public-read-retirement")
    database.initialize(migrations=MIGRATIONS[:13])
    session_hash, csrf_hash = "a" * 64, "b" * 64
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner VALUES ('current', 'owner', '$argon2id$preserved', 'created')"
        )
        connection.execute("INSERT INTO admin_auth_methods VALUES ('local_password', 'created')")
        connection.execute(
            "INSERT INTO admin_sessions(session_hash, csrf_hash, created_at, last_seen_at, "
            "idle_expires_at, absolute_expires_at, session_epoch, authenticated_at) "
            "VALUES (?, ?, 'created', 'seen', 'idle', 'absolute', 0, 'authenticated')",
            (session_hash, csrf_hash),
        )
        connection.execute(
            "INSERT INTO admin_local_launch_grants "
            "VALUES ('current', ?, 'created', 'expires', NULL)",
            ("c" * 64,),
        )
        connection.execute(
            "INSERT INTO bundle_state(state_key, active_bundle_id, previous_bundle_id, "
            "pinned_bundle_id) VALUES ('current', 'active', 'previous', 'pinned')"
        )
        connection.execute(
            "INSERT INTO analysis_batches(batch_id, plan_id, selection_hash, "
            "idempotency_key_hash, state, maximum_generation_attempts, created_at, updated_at) "
            "VALUES ('batch', 'plan', ?, ?, 'completed', 1, 'created', 'updated')",
            ("d" * 64, "e" * 64),
        )
        connection.execute(
            "INSERT INTO embedding_profiles(profile_id, provider, model_id, dimension, normalized, "
            "query_prefix, passage_prefix, connection_reference, status, active, "
            "created_at, updated_at) "
            "VALUES ('profile', 'ollama', 'model', 768, 1, '', '', 'local', 'ready', 1, "
            "'created', 'updated')"
        )
        connection.execute(
            "INSERT INTO admin_oauth_transactions(state_hash, intent, verifier_nonce, "
            "verifier_ciphertext, session_hash, created_at, expires_at, return_path) "
            "VALUES (?, 'connection', X'01', X'02', ?, 'created', 'expires', '/admin')",
            ("f" * 64, session_hash),
        )
        connection.execute(
            "INSERT INTO admin_github_credentials(purpose, token_nonce, token_ciphertext, "
            "key_version, status, created_at, updated_at) "
            "VALUES ('public_read', X'03', X'04', 1, 'ready', 'created', 'updated')"
        )
        connection.commit()

    database.initialize(migrations=MIGRATIONS[:14])

    with database.connection() as connection:
        preserved = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "admin_owner",
                "admin_auth_methods",
                "admin_sessions",
                "admin_local_launch_grants",
                "bundle_state",
                "analysis_batches",
                "embedding_profiles",
            )
        }
        retired = (
            connection.execute("SELECT count(*) FROM admin_oauth_transactions").fetchone()[0],
            connection.execute("SELECT count(*) FROM admin_github_credentials").fetchone()[0],
        )

    assert database.schema_version() == 14
    assert set(preserved.values()) == {1}
    assert retired == (0, 0)


def test_public_read_retirement_failure_restores_legacy_rows_without_secret_output(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "public-read-retirement-rollback")
    database.initialize(migrations=MIGRATIONS[:13])
    secret_canary = b"LEGACY_CIPHERTEXT_CANARY"
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO admin_owner VALUES ('current', 'owner', '$argon2id$preserved', 'created')"
        )
        connection.execute(
            "INSERT INTO admin_github_credentials(purpose, token_nonce, token_ciphertext, "
            "key_version, status, created_at, updated_at) "
            "VALUES ('identity_public_read', X'01', ?, 1, 'ready', 'created', 'updated')",
            (secret_canary,),
        )
        connection.commit()
    migration = MIGRATIONS[13]
    broken = Migration(
        version=14,
        name=migration.name,
        statements=(*migration.statements, "THIS IS NOT VALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError) as raised:
        database.initialize(migrations=(*MIGRATIONS[:13], broken))

    with database.connection() as connection:
        owner = connection.execute("SELECT password_hash FROM admin_owner").fetchone()
        credential = connection.execute(
            "SELECT token_ciphertext FROM admin_github_credentials"
        ).fetchone()
    assert raised.value.code == "runtime_migration_failed"
    assert secret_canary.decode() not in str(raised.value)
    assert database.schema_version() == 13
    assert owner is not None and owner[0] == "$argon2id$preserved"
    assert credential is not None and bytes(credential[0]) == secret_canary


def test_runtime_database_reports_integrity_failure_without_exposing_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "corrupt"
    data_dir.mkdir()
    (data_dir / "runtime.sqlite").write_bytes(b"not a sqlite database")

    with pytest.raises(RuntimeDatabaseError) as raised:
        RuntimeDatabase(data_dir).initialize()

    assert raised.value.code in {"runtime_configuration_failed", "runtime_migration_failed"}
    assert str(data_dir) not in str(raised.value)
