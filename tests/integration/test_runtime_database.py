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


def _seed_analysis_batch(database: RuntimeDatabase) -> None:
    selection_hash = "a" * 64
    idempotency_hash = "b" * 64
    commit_sha = "c" * 40
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO analysis_batches(
              batch_id, plan_id, selection_hash, idempotency_key_hash, state,
              maximum_generation_attempts, created_at, updated_at
            ) VALUES ('batch-migration', 'plan-migration', ?, ?, 'completed', 2, 'now', 'now')
            """,
            (selection_hash, idempotency_hash),
        )
        connection.execute(
            """
            INSERT INTO analysis_batch_items(
              item_id, batch_id, position, repository_slug, requested_ref,
              selection_hash, resolved_commit_sha, selection_json, state,
              result_json, error_reason, created_at, updated_at
            ) VALUES (
              'item-migration', 'batch-migration', 0, 'octocat/demo', 'main', ?, ?,
              '{"include":["src/**"],"exclude":[]}', 'complete',
              '{"repository":{"slug":"octocat/demo"},"inferences":[],"skipped_summary":{"count":0,"reasons":[]}}',
              'PROVIDER_OUTPUT_SCHEMA_INVALID', 'now', 'now'
            )
            """,
            (selection_hash, commit_sha),
        )
        connection.execute(
            """
            INSERT INTO analysis_batch_events(
              event_id, batch_id, item_id, event_type, payload_json, occurred_at
            ) VALUES (
              17, 'batch-migration', 'item-migration', 'item_completed', '{"ok":true}', 'now'
            )
            """
        )


def test_runtime_database_is_idempotent_and_separate_from_index_data(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "runtime-data")

    database.initialize()
    database.initialize()

    assert database.database_path == tmp_path / "runtime-data" / "runtime.sqlite"
    assert database.database_path.exists()
    assert database.schema_version() == 25
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
        "host_managed_connection_overrides",
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
    assert database.schema_version() == 25


def test_host_connection_override_migration_is_atomic(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "host-override-rollback")
    previous = tuple(m for m in MIGRATIONS if m.version < 21)
    database.initialize(migrations=previous)
    migration = next(m for m in MIGRATIONS if m.version == 21)
    broken = Migration(
        version=21,
        name=migration.name,
        statements=(*migration.statements, "INVALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))

    assert database.schema_version() == 20
    assert "host_managed_connection_overrides" not in table_names(database)
    database.initialize()
    assert database.schema_version() == 25


def test_connection_revision_rebinding_migration_repairs_safe_candidates(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "connection-rebinding")
    previous = tuple(m for m in MIGRATIONS if m.version < 22)
    database.initialize(migrations=previous)
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO model_connections(
              connection_id, display_name, provider, source, revision, secret_ref,
              endpoint_configured, key_configured, status, created_at, updated_at
            ) VALUES (
              'environment-embedding', 'Environment embedding', 'ollama', 'managed', 2,
              'model-connection:environment-embedding:2', 1, 0, 'configured', 'now', 'now'
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO model_connection_secrets(
              secret_ref, connection_id, revision, ciphertext, created_at
            ) VALUES (?, 'environment-embedding', ?, X'01', 'now')
            """,
            (
                ("model-connection:environment-embedding:1", 1),
                ("model-connection:environment-embedding:2", 2),
            ),
        )
        connection.execute(
            """
            INSERT INTO chat_profiles(
              profile_id, connection_id, connection_revision, model_id, status, active,
              observed_model_id, last_error_code, last_error_message, created_at,
              updated_at, last_probed_at
            ) VALUES (
              'chat-safe', 'environment-embedding', 1, 'chat-model', 'probe_failed', 0,
              'chat-model', 'PROVIDER_TIMEOUT', 'old error', 'now', 'now', 'now'
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO embedding_profiles(
              profile_id, provider, model_id, dimension, normalized, query_prefix,
              passage_prefix, connection_reference, connection_revision, status, active,
              observed_adapter, observed_model_id, observed_dimension, last_error_code,
              last_error_message, created_at, updated_at, last_probed_at
            ) VALUES (?, 'ollama', ?, 4096, 1, '', '', 'environment-embedding', 1, ?, ?,
                      'ollama', ?, 4096, ?, ?, 'now', 'now', 'now')
            """,
            (
                (
                    "embedding-safe",
                    "qwen3-embedding:8b",
                    "probe_failed",
                    0,
                    "qwen3-embedding:8b",
                    "EMBEDDING_CONNECTION_REQUIRED",
                    "old error",
                ),
                (
                    "embedding-active",
                    "active-model",
                    "ready",
                    1,
                    "active-model",
                    None,
                    None,
                ),
                (
                    "embedding-building",
                    "building-model",
                    "reindexing",
                    0,
                    "building-model",
                    None,
                    None,
                ),
            ),
        )
        connection.execute(
            """
            UPDATE analysis_model_selection SET
              chat_profile_id = 'chat-safe', chat_connection_revision = 1,
              embedding_profile_id = 'embedding-safe', embedding_connection_revision = 1,
              selection_generation = 4, updated_at = 'now'
            WHERE selection_key = 'current'
            """
        )

    database.initialize()

    assert database.schema_version() == 25
    with database.connection() as connection:
        revisions = connection.execute(
            "SELECT revision, provider FROM model_connection_secrets ORDER BY revision"
        ).fetchall()
        chat = connection.execute(
            "SELECT * FROM chat_profiles WHERE profile_id = 'chat-safe'"
        ).fetchone()
        embedding = connection.execute(
            "SELECT * FROM embedding_profiles WHERE profile_id = 'embedding-safe'"
        ).fetchone()
        protected = connection.execute(
            "SELECT profile_id, connection_revision FROM embedding_profiles "
            "WHERE profile_id <> 'embedding-safe' ORDER BY profile_id"
        ).fetchall()
        selection = connection.execute(
            "SELECT * FROM analysis_model_selection WHERE selection_key = 'current'"
        ).fetchone()
    assert [(row["revision"], row["provider"]) for row in revisions] == [
        (1, "ollama"),
        (2, "ollama"),
    ]
    assert chat is not None
    assert (chat["connection_revision"], chat["status"], chat["last_probed_at"]) == (
        2,
        "probe",
        None,
    )
    assert embedding is not None
    assert (
        embedding["connection_revision"],
        embedding["status"],
        embedding["last_error_code"],
        embedding["last_probed_at"],
    ) == (2, "reindex_required", None, None)
    assert [(row["profile_id"], row["connection_revision"]) for row in protected] == [
        ("embedding-active", 1),
        ("embedding-building", 1),
    ]
    assert selection is not None
    assert selection["selection_generation"] == 5
    assert selection["chat_connection_revision"] == 1
    assert selection["embedding_connection_revision"] == 1


def test_connection_revision_rebinding_migration_is_atomic(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "connection-rebinding-rollback")
    previous = tuple(m for m in MIGRATIONS if m.version < 22)
    database.initialize(migrations=previous)
    migration = next(m for m in MIGRATIONS if m.version == 22)
    broken = Migration(
        version=22,
        name=migration.name,
        statements=(*migration.statements, "INVALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))

    assert database.schema_version() == 21
    with database.connection() as connection:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(model_connection_secrets)")
        }
    assert "provider" not in columns
    database.initialize()
    assert database.schema_version() == 25


def test_analysis_batch_error_reason_migration_is_atomic(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "analysis-error-reason-rollback")
    previous = tuple(m for m in MIGRATIONS if m.version < 23)
    database.initialize(migrations=previous)
    migration = next(m for m in MIGRATIONS if m.version == 23)
    broken = Migration(
        version=23,
        name=migration.name,
        statements=(*migration.statements, "INVALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))

    assert database.schema_version() == 22
    with database.connection() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_batch_items)")}
    assert "error_reason" not in columns
    database.initialize()
    assert database.schema_version() == 25


def test_analysis_output_limit_reason_migration_preserves_results_events_and_foreign_keys(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "analysis-output-limit")
    database.initialize(migrations=tuple(m for m in MIGRATIONS if m.version < 24))
    _seed_analysis_batch(database)
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO analysis_batch_events(
              event_id, batch_id, item_id, event_type, payload_json, occurred_at
            ) VALUES (9000, 'batch-migration', 'item-migration', 'pruned', '{}', 'now')
            """
        )
        connection.execute("DELETE FROM analysis_batch_events WHERE event_id = 9000")

    database.initialize()

    assert database.schema_version() == 25
    with database.connection() as connection:
        item = connection.execute(
            "SELECT * FROM analysis_batch_items WHERE item_id = 'item-migration'"
        ).fetchone()
        event = connection.execute(
            "SELECT * FROM analysis_batch_events WHERE event_id = 17"
        ).fetchone()
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(analysis_batch_events)"
        ).fetchall()
        sequence = connection.execute(
            "SELECT COUNT(*), MAX(seq) FROM sqlite_sequence WHERE name = 'analysis_batch_events'"
        ).fetchone()
        connection.execute(
            "UPDATE analysis_batch_items SET error_reason = 'PROVIDER_OUTPUT_LIMIT_REACHED' "
            "WHERE item_id = 'item-migration'"
        )
        updated_reason = connection.execute(
            "SELECT error_reason FROM analysis_batch_items WHERE item_id = 'item-migration'"
        ).fetchone()[0]
        inserted = connection.execute(
            """
            INSERT INTO analysis_batch_events(
              batch_id, item_id, event_type, payload_json, occurred_at
            ) VALUES ('batch-migration', 'item-migration', 'post-migration', '{}', 'now')
            """
        )

    assert item is not None
    assert item["result_json"] == (
        '{"repository":{"slug":"octocat/demo"},"inferences":[],'
        '"skipped_summary":{"count":0,"reasons":[]}}'
    )
    assert item["selection_json"] == '{"include":["src/**"],"exclude":[]}'
    assert event is not None and event["event_id"] == 17
    assert {row[2] for row in foreign_keys} == {"analysis_batches", "analysis_batch_items"}
    assert tuple(sequence) == (1, 9000)
    assert updated_reason == "PROVIDER_OUTPUT_LIMIT_REACHED"
    assert inserted.lastrowid == 9001


def test_analysis_output_limit_reason_migration_preserves_event_watermark_when_all_events_pruned(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "analysis-output-limit-all-pruned")
    previous = tuple(m for m in MIGRATIONS if m.version < 24)
    database.initialize(migrations=previous)
    _seed_analysis_batch(database)
    with database.connection() as connection:
        connection.execute("DELETE FROM analysis_batch_events")

    database.initialize()

    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM analysis_batch_events").fetchone()[0] == 0
        sequence = connection.execute(
            "SELECT COUNT(*), MAX(seq) FROM sqlite_sequence WHERE name = 'analysis_batch_events'"
        ).fetchone()
        inserted = connection.execute(
            """
            INSERT INTO analysis_batch_events(
              batch_id, item_id, event_type, payload_json, occurred_at
            ) VALUES ('batch-migration', 'item-migration', 'post-migration', '{}', 'now')
            """
        )

    assert tuple(sequence) == (1, 17)
    assert inserted.lastrowid == 18


def test_analysis_output_limit_reason_migration_rolls_back_without_losing_old_schema(
    tmp_path: Path,
) -> None:
    database = RuntimeDatabase(tmp_path / "analysis-output-limit-rollback")
    previous = tuple(m for m in MIGRATIONS if m.version < 24)
    database.initialize(migrations=previous)
    _seed_analysis_batch(database)
    migration = next(m for m in MIGRATIONS if m.version == 24)
    broken = Migration(
        version=24,
        name=migration.name,
        statements=(*migration.statements, "INVALID SQL"),
    )

    with pytest.raises(RuntimeDatabaseError):
        database.initialize(migrations=(*previous, broken))

    assert database.schema_version() == 23
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT result_json FROM analysis_batch_items WHERE item_id = 'item-migration'"
            )
            .fetchone()[0]
            .startswith('{"repository"')
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM analysis_batch_events WHERE event_id = 17"
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%_v24'"
            ).fetchone()[0]
            == 0
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE analysis_batch_items SET error_reason = 'PROVIDER_OUTPUT_LIMIT_REACHED' "
                "WHERE item_id = 'item-migration'"
            )

    database.initialize()
    assert database.schema_version() == 25


def test_flexible_analysis_budget_migration_preserves_existing_value(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "analysis-budget-v25")
    previous = tuple(m for m in MIGRATIONS if m.version < 25)
    database.initialize(migrations=previous)
    _seed_analysis_batch(database)
    with database.connection() as connection:
        connection.execute(
            "UPDATE analysis_batch_items SET execution_budget_seconds = 600 "
            "WHERE item_id = 'item-migration'"
        )

    database.initialize()

    assert database.schema_version() == 25
    with database.connection() as connection:
        row = connection.execute(
            "SELECT legacy_execution_budget_seconds, execution_budget_seconds "
            "FROM analysis_batch_items WHERE item_id = 'item-migration'"
        ).fetchone()
    assert tuple(row) == (600, 600)


def test_concurrent_initialization_creates_one_versioned_schema(tmp_path: Path) -> None:
    database = RuntimeDatabase(tmp_path / "concurrent", busy_timeout_ms=10_000)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda _unused: database.initialize(), range(2)))

    assert database.schema_version() == 25
    with database.connection() as connection:
        versions = connection.execute("SELECT version FROM runtime_schema_migrations").fetchall()
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        assert [row[0] for row in versions] == list(range(1, 26))
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
        assert database.schema_version() == 25
        with database.connection() as connection:
            versions = connection.execute(
                "SELECT version FROM runtime_schema_migrations"
            ).fetchall()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            assert [row[0] for row in versions] == list(range(1, 26))
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
