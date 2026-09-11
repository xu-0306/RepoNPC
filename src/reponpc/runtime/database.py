"""Transactional SQLite owner for mutable RepoNPC runtime state."""

from __future__ import annotations

import sqlite3
import threading
import uuid
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
    Migration(
        version=3,
        name="first-owner-onboarding",
        statements=(
            """
            CREATE TABLE admin_owner (
                state_key TEXT PRIMARY KEY CHECK(state_key = 'current'),
                username TEXT NOT NULL CHECK(length(username) BETWEEN 1 AND 64),
                password_hash TEXT NOT NULL CHECK(password_hash LIKE '$argon2id$%'),
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE admin_setup (
                state_key TEXT PRIMARY KEY CHECK(state_key = 'current'),
                code_hash TEXT NOT NULL
                    CHECK(length(code_hash) = 64
                          AND code_hash NOT GLOB '*[^0-9a-f]*'),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=4,
        name="github-oauth-identity",
        statements=(
            "ALTER TABLE admin_sessions ADD COLUMN authenticated_at TEXT",
            (
                "UPDATE admin_sessions SET authenticated_at = created_at "
                "WHERE authenticated_at IS NULL"
            ),
            """
            CREATE TABLE admin_auth_methods (
                method TEXT PRIMARY KEY CHECK(method IN ('local_password', 'github')),
                github_user_id TEXT UNIQUE,
                github_login TEXT,
                created_at TEXT NOT NULL,
                CHECK(
                    (method = 'local_password' AND github_user_id IS NULL)
                    OR (method = 'github' AND github_user_id IS NOT NULL)
                )
            )
            """,
            """
            INSERT INTO admin_auth_methods(method, github_user_id, github_login, created_at)
            SELECT 'local_password', NULL, NULL, created_at FROM admin_owner
            WHERE state_key = 'current'
            """,
            """
            CREATE TABLE admin_oauth_transactions (
                state_hash TEXT PRIMARY KEY
                    CHECK(length(state_hash) = 64 AND state_hash NOT GLOB '*[^0-9a-f]*'),
                intent TEXT NOT NULL CHECK(intent IN ('login', 'setup', 'link')),
                verifier_nonce BLOB NOT NULL,
                verifier_ciphertext BLOB NOT NULL,
                setup_code_hash TEXT
                    CHECK(setup_code_hash IS NULL OR (
                        length(setup_code_hash) = 64
                        AND setup_code_hash NOT GLOB '*[^0-9a-f]*'
                    )),
                session_hash TEXT REFERENCES admin_sessions(session_hash),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                return_path TEXT NOT NULL CHECK(return_path = '/admin')
            )
            """,
            (
                "CREATE INDEX admin_oauth_transactions_expiry_idx "
                "ON admin_oauth_transactions(expires_at)"
            ),
            """
            CREATE TABLE admin_github_credentials (
                credential_id INTEGER PRIMARY KEY,
                purpose TEXT NOT NULL CHECK(purpose IN ('identity_public_read', 'public_read')),
                token_nonce BLOB NOT NULL,
                token_ciphertext BLOB NOT NULL,
                key_version INTEGER NOT NULL CHECK(key_version >= 1),
                github_user_id TEXT,
                github_login TEXT,
                expires_at TEXT,
                last_validated_at TEXT,
                status TEXT NOT NULL CHECK(status IN ('ready', 'connection_required', 'invalid')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(purpose, github_user_id)
            )
            """,
        ),
    ),
    Migration(
        version=5,
        name="github-oauth-csrf-handoff",
        statements=(
            """
            CREATE TABLE admin_oauth_handoffs (
                handoff_hash TEXT PRIMARY KEY
                    CHECK(length(handoff_hash) = 64 AND handoff_hash NOT GLOB '*[^0-9a-f]*'),
                session_hash TEXT NOT NULL REFERENCES admin_sessions(session_hash),
                csrf_nonce BLOB NOT NULL,
                csrf_ciphertext BLOB NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            )
            """,
            "CREATE INDEX admin_oauth_handoffs_expiry_idx ON admin_oauth_handoffs(expires_at)",
        ),
    ),
    Migration(
        version=6,
        name="bounded-analysis-batch-runtime",
        statements=(
            """
            CREATE TABLE analysis_batches (
                batch_id TEXT PRIMARY KEY
                    CHECK(length(batch_id) BETWEEN 1 AND 64),
                owner_scope TEXT NOT NULL DEFAULT 'singleton'
                    CHECK(owner_scope = 'singleton'),
                plan_id TEXT NOT NULL CHECK(length(plan_id) BETWEEN 1 AND 128),
                selection_hash TEXT NOT NULL
                    CHECK(length(selection_hash) = 64
                          AND selection_hash NOT GLOB '*[^0-9a-f]*'),
                idempotency_key_hash TEXT NOT NULL UNIQUE
                    CHECK(length(idempotency_key_hash) = 64
                          AND idempotency_key_hash NOT GLOB '*[^0-9a-f]*'),
                state TEXT NOT NULL CHECK(state IN (
                    'queued', 'running', 'paused', 'cancelling', 'cancelled',
                    'completed', 'completed_with_errors', 'failed'
                )),
                maximum_generation_attempts INTEGER NOT NULL
                    CHECK(maximum_generation_attempts BETWEEN 1 AND 10),
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                expires_at TEXT,
                error_code TEXT,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE UNIQUE INDEX analysis_batches_one_active_idx
            ON analysis_batches(owner_scope)
            WHERE state IN ('queued', 'running', 'paused', 'cancelling')
            """,
            "CREATE INDEX analysis_batches_expiry_idx ON analysis_batches(expires_at)",
            """
            CREATE TABLE analysis_batch_items (
                item_id TEXT PRIMARY KEY
                    CHECK(length(item_id) BETWEEN 1 AND 64),
                batch_id TEXT NOT NULL REFERENCES analysis_batches(batch_id)
                    ON DELETE CASCADE,
                position INTEGER NOT NULL CHECK(position >= 0),
                repository_slug TEXT NOT NULL CHECK(length(repository_slug) BETWEEN 3 AND 200),
                requested_ref TEXT CHECK(requested_ref IS NULL OR length(requested_ref) <= 256),
                selection_hash TEXT NOT NULL
                    CHECK(length(selection_hash) = 64
                          AND selection_hash NOT GLOB '*[^0-9a-f]*'),
                resolved_commit_sha TEXT
                    CHECK(resolved_commit_sha IS NULL OR (
                        length(resolved_commit_sha) = 40
                        AND resolved_commit_sha NOT GLOB '*[^0-9a-f]*'
                    )),
                state TEXT NOT NULL CHECK(state IN (
                    'queued', 'resolving_commit', 'fetching_source', 'filtering',
                    'indexing', 'embedding', 'generating', 'validating', 'cleaning_up',
                    'complete', 'waiting_rate_limit', 'waiting_reconnection',
                    'needs_retry_confirmation', 'failed', 'cancelled'
                )),
                resume_state TEXT CHECK(resume_state IS NULL OR resume_state IN (
                    'resolving_commit', 'fetching_source', 'filtering', 'indexing',
                    'embedding', 'generating', 'validating', 'cleaning_up'
                )),
                lease_id TEXT,
                execution_started_at TEXT,
                execution_elapsed_seconds INTEGER NOT NULL DEFAULT 0
                    CHECK(execution_elapsed_seconds >= 0),
                execution_budget_seconds INTEGER NOT NULL DEFAULT 120
                    CHECK(execution_budget_seconds BETWEEN 1 AND 600),
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
                generation_attempt_count INTEGER NOT NULL DEFAULT 0
                    CHECK(generation_attempt_count >= 0),
                result_json TEXT,
                error_code TEXT,
                retry_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(batch_id, position),
                UNIQUE(batch_id, repository_slug)
            )
            """,
            """
            CREATE INDEX analysis_batch_items_schedule_idx
            ON analysis_batch_items(batch_id, state, retry_at, position)
            """,
            """
            CREATE TABLE analysis_batch_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL REFERENCES analysis_batches(batch_id)
                    ON DELETE CASCADE,
                item_id TEXT REFERENCES analysis_batch_items(item_id)
                    ON DELETE CASCADE,
                event_type TEXT NOT NULL CHECK(length(event_type) BETWEEN 1 AND 64),
                payload_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX analysis_batch_events_replay_idx
            ON analysis_batch_events(batch_id, event_id)
            """,
            """
            CREATE TABLE analysis_cache_entries (
                cache_key TEXT PRIMARY KEY
                    CHECK(length(cache_key) = 64
                          AND cache_key NOT GLOB '*[^0-9a-f]*'),
                cache_kind TEXT NOT NULL CHECK(cache_kind IN (
                    'derived_index', 'validated_analysis'
                )),
                derived_index_key TEXT NOT NULL
                    CHECK(length(derived_index_key) = 64
                          AND derived_index_key NOT GLOB '*[^0-9a-f]*'),
                metadata_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
                    CHECK(length(payload_sha256) = 64
                          AND payload_sha256 NOT GLOB '*[^0-9a-f]*'),
                size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX analysis_cache_entries_expiry_idx ON analysis_cache_entries(expires_at)",
            """
            CREATE INDEX analysis_cache_entries_lru_idx
            ON analysis_cache_entries(last_accessed_at)
            """,
        ),
    ),
    Migration(
        version=7,
        name="analysis-batch-selection-policy",
        statements=(
            """
            ALTER TABLE analysis_batch_items
            ADD COLUMN selection_json TEXT NOT NULL DEFAULT '{}'
            """,
        ),
    ),
    Migration(
        version=8,
        name="analysis-batch-selected-credential",
        statements=("ALTER TABLE analysis_batches ADD COLUMN selected_credential_id INTEGER",),
    ),
    Migration(
        version=9,
        name="github-rate-state",
        statements=(
            """
            CREATE TABLE github_rate_state (
                resource TEXT PRIMARY KEY CHECK(resource IN ('graphql', 'core', 'secondary')),
                remaining INTEGER,
                limit_value INTEGER,
                reset_at TEXT,
                retry_at TEXT,
                updated_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=10,
        name="embedding-profile-registry",
        statements=(
            """
            CREATE TABLE embedding_profiles (
                profile_id TEXT PRIMARY KEY
                    CHECK(length(profile_id) BETWEEN 1 AND 64),
                provider TEXT NOT NULL
                    CHECK(provider IN ('ollama', 'openai_compatible', 'vllm')),
                model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
                dimension INTEGER NOT NULL CHECK(dimension BETWEEN 1 AND 65536),
                normalized INTEGER NOT NULL CHECK(normalized IN (0, 1)),
                query_prefix TEXT NOT NULL CHECK(length(query_prefix) <= 128),
                passage_prefix TEXT NOT NULL CHECK(length(passage_prefix) <= 128),
                connection_reference TEXT NOT NULL
                    CHECK(length(connection_reference) BETWEEN 1 AND 64),
                status TEXT NOT NULL CHECK(status IN (
                    'probe', 'reindex_required', 'reindexing', 'ready',
                    'last_known_good', 'probe_failed'
                )),
                active INTEGER NOT NULL CHECK(active IN (0, 1)),
                observed_adapter TEXT,
                observed_model_id TEXT,
                observed_dimension INTEGER,
                last_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_probed_at TEXT
            )
            """,
            """
            CREATE UNIQUE INDEX embedding_profiles_one_active_idx
            ON embedding_profiles(active) WHERE active = 1
            """,
        ),
    ),
    Migration(
        version=11,
        name="embedding-profile-reindex-lifecycle",
        statements=(
            (
                "ALTER TABLE embedding_profiles ADD COLUMN "
                "reindex_generation INTEGER NOT NULL DEFAULT 0"
            ),
            "ALTER TABLE embedding_profiles ADD COLUMN reindex_started_at TEXT",
            "ALTER TABLE embedding_profiles ADD COLUMN reindex_completed_at TEXT",
            "ALTER TABLE embedding_profiles ADD COLUMN bundle_id TEXT",
        ),
    ),
    Migration(
        version=12,
        name="embedding-switch-intent",
        statements=(
            """
            CREATE TABLE embedding_switch_intent (
                state_key TEXT PRIMARY KEY CHECK(state_key = 'current'),
                generation INTEGER NOT NULL CHECK(generation >= 1),
                from_profile_id TEXT REFERENCES embedding_profiles(profile_id),
                from_bundle_id TEXT,
                to_profile_id TEXT NOT NULL REFERENCES embedding_profiles(profile_id),
                to_bundle_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=13,
        name="passwordless-loopback-and-connection-only-github",
        statements=(
            "ALTER TABLE admin_owner RENAME TO admin_owner_v12",
            """
            CREATE TABLE admin_owner (
                state_key TEXT PRIMARY KEY CHECK(state_key = 'current'),
                username TEXT NOT NULL CHECK(length(username) BETWEEN 1 AND 64),
                password_hash TEXT
                    CHECK(password_hash IS NULL OR password_hash LIKE '$argon2id$%'),
                created_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO admin_owner(state_key, username, password_hash, created_at)
            SELECT state_key, username, password_hash, created_at FROM admin_owner_v12
            """,
            "DROP TABLE admin_owner_v12",
            "ALTER TABLE admin_auth_methods RENAME TO admin_auth_methods_v12",
            """
            CREATE TABLE admin_auth_methods (
                method TEXT PRIMARY KEY CHECK(method = 'local_password'),
                created_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO admin_auth_methods(method, created_at)
            SELECT method, created_at FROM admin_auth_methods_v12
            WHERE method = 'local_password'
            """,
            "DROP TABLE admin_auth_methods_v12",
            "ALTER TABLE admin_oauth_transactions RENAME TO admin_oauth_transactions_v12",
            """
            CREATE TABLE admin_oauth_transactions (
                state_hash TEXT PRIMARY KEY
                    CHECK(length(state_hash) = 64 AND state_hash NOT GLOB '*[^0-9a-f]*'),
                intent TEXT NOT NULL CHECK(intent = 'connection'),
                verifier_nonce BLOB NOT NULL,
                verifier_ciphertext BLOB NOT NULL,
                session_hash TEXT NOT NULL REFERENCES admin_sessions(session_hash),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                return_path TEXT NOT NULL CHECK(return_path = '/admin')
            )
            """,
            """
            INSERT INTO admin_oauth_transactions(
                state_hash, intent, verifier_nonce, verifier_ciphertext, session_hash,
                created_at, expires_at, consumed_at, return_path
            )
            SELECT
                state_hash, 'connection', verifier_nonce, verifier_ciphertext, session_hash,
                created_at, expires_at, consumed_at, return_path
            FROM admin_oauth_transactions_v12
            WHERE intent = 'link' AND session_hash IS NOT NULL
            """,
            "DROP TABLE admin_oauth_transactions_v12",
            (
                "CREATE INDEX admin_oauth_transactions_expiry_idx "
                "ON admin_oauth_transactions(expires_at)"
            ),
            "DROP TABLE admin_oauth_handoffs",
            """
            CREATE TABLE admin_local_launch_grants (
                state_key TEXT PRIMARY KEY CHECK(state_key = 'current'),
                grant_hash TEXT NOT NULL
                    CHECK(length(grant_hash) = 64
                          AND grant_hash NOT GLOB '*[^0-9a-f]*'),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            )
            """,
        ),
    ),
    Migration(
        version=14,
        name="retire-github-oauth-public-read-credentials",
        statements=(
            "DELETE FROM admin_oauth_transactions",
            (
                "DELETE FROM admin_github_credentials "
                "WHERE purpose IN ('identity_public_read', 'public_read')"
            ),
        ),
    ),
    Migration(
        version=15,
        name="anonymous-github-resolution-cache",
        statements=(
            """
            CREATE TABLE github_public_resolution_cache (
                cache_key TEXT PRIMARY KEY
                    CHECK(length(cache_key) = 64
                          AND cache_key NOT GLOB '*[^0-9a-f]*'),
                entry_kind TEXT NOT NULL CHECK(entry_kind IN ('metadata', 'resolved')),
                repository_slug TEXT NOT NULL,
                requested_ref TEXT,
                node_id TEXT NOT NULL,
                default_branch TEXT NOT NULL,
                commit_sha TEXT
                    CHECK(commit_sha IS NULL OR (length(commit_sha) = 40
                          AND commit_sha NOT GLOB '*[^0-9a-f]*')),
                is_archived INTEGER NOT NULL CHECK(is_archived IN (0, 1)),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                CHECK((entry_kind = 'metadata' AND commit_sha IS NULL)
                   OR (entry_kind = 'resolved' AND commit_sha IS NOT NULL))
            )
            """,
            (
                "CREATE INDEX github_public_resolution_cache_expiry_idx "
                "ON github_public_resolution_cache(expires_at)"
            ),
        ),
    ),
    Migration(
        version=16,
        name="protected-model-connections",
        statements=(
            (
                "ALTER TABLE embedding_profiles ADD COLUMN connection_revision INTEGER "
                "NOT NULL DEFAULT 0 CHECK(connection_revision >= 0)"
            ),
            """
            CREATE TABLE model_connections (
                connection_id TEXT PRIMARY KEY
                    CHECK(length(connection_id) BETWEEN 1 AND 64),
                display_name TEXT NOT NULL
                    CHECK(length(display_name) BETWEEN 1 AND 120),
                provider TEXT NOT NULL
                    CHECK(provider IN ('ollama', 'openai_compatible', 'vllm')),
                source TEXT NOT NULL
                    CHECK(source IN ('host-managed', 'managed')),
                revision INTEGER NOT NULL CHECK(revision >= 1),
                secret_ref TEXT NOT NULL UNIQUE,
                endpoint_configured INTEGER NOT NULL CHECK(endpoint_configured IN (0, 1)),
                key_configured INTEGER NOT NULL CHECK(key_configured IN (0, 1)),
                status TEXT NOT NULL CHECK(status IN (
                    'configured', 'testing', 'available', 'failed', 'unavailable'
                )),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE model_connection_secrets (
                secret_ref TEXT PRIMARY KEY
                    CHECK(length(secret_ref) BETWEEN 1 AND 128),
                connection_id TEXT NOT NULL
                    REFERENCES model_connections(connection_id) ON DELETE CASCADE,
                revision INTEGER NOT NULL CHECK(revision >= 1),
                ciphertext BLOB NOT NULL CHECK(length(ciphertext) > 0),
                created_at TEXT NOT NULL,
                UNIQUE(connection_id, revision),
                UNIQUE(connection_id, secret_ref)
            )
            """,
            (
                "CREATE INDEX model_connection_secrets_connection_idx "
                "ON model_connection_secrets(connection_id, revision)"
            ),
            """
            CREATE TABLE chat_profiles (
                profile_id TEXT PRIMARY KEY
                    CHECK(length(profile_id) BETWEEN 1 AND 64),
                connection_id TEXT NOT NULL
                    REFERENCES model_connections(connection_id) ON DELETE RESTRICT,
                connection_revision INTEGER NOT NULL CHECK(connection_revision >= 1),
                model_id TEXT NOT NULL CHECK(length(model_id) BETWEEN 1 AND 256),
                status TEXT NOT NULL CHECK(status IN (
                    'probe', 'ready', 'last_known_good', 'probe_failed'
                )),
                active INTEGER NOT NULL CHECK(active IN (0, 1)),
                observed_model_id TEXT,
                last_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_probed_at TEXT
            )
            """,
            (
                "CREATE UNIQUE INDEX chat_profiles_one_active_idx "
                "ON chat_profiles(active) WHERE active = 1"
            ),
            (
                "CREATE INDEX chat_profiles_connection_idx "
                "ON chat_profiles(connection_id, connection_revision)"
            ),
        ),
    ),
    Migration(
        version=17,
        name="analysis-model-selection",
        statements=(
            """
            CREATE TABLE analysis_model_selection (
                selection_key TEXT PRIMARY KEY CHECK(selection_key = 'current'),
                chat_profile_id TEXT REFERENCES chat_profiles(profile_id) ON DELETE SET NULL,
                chat_connection_revision INTEGER
                    CHECK(chat_connection_revision IS NULL OR chat_connection_revision >= 1),
                embedding_profile_id TEXT
                    REFERENCES embedding_profiles(profile_id) ON DELETE SET NULL,
                embedding_connection_revision INTEGER
                    CHECK(embedding_connection_revision IS NULL
                          OR embedding_connection_revision >= 0),
                selection_generation INTEGER NOT NULL DEFAULT 0 CHECK(selection_generation >= 0),
                updated_at TEXT NOT NULL
            )
            """,
            """
            INSERT INTO analysis_model_selection(selection_key, selection_generation, updated_at)
            VALUES ('current', 0, '1970-01-01T00:00:00Z')
            """,
        ),
    ),
    Migration(
        version=18,
        name="analysis-batch-model-pair",
        statements=("ALTER TABLE analysis_batches ADD COLUMN analysis_model_pair_json TEXT",),
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

    def check_integrity(self) -> None:
        """Run the same bounded SQLite integrity check used at startup."""

        if not self.database_path.is_file():
            raise RuntimeDatabaseError("runtime_database_missing")
        with self.connection() as connection:
            self._check_integrity(connection)

    def backup_to(self, destination: Path) -> Path:
        """Create and verify one online SQLite backup without overwriting files."""

        target = destination.resolve()
        source = self.database_path.resolve()
        if not source.is_file():
            raise RuntimeDatabaseError("runtime_database_missing")
        if target == source or target.exists() or not target.parent.is_dir():
            raise RuntimeDatabaseError("runtime_backup_target_invalid")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with self.connection() as connection:
                backup = sqlite3.connect(temporary)
                try:
                    connection.backup(backup)
                    self._check_integrity(backup)
                finally:
                    backup.close()
            temporary.replace(target)
        except RuntimeDatabaseError:
            temporary.unlink(missing_ok=True)
            raise
        except (OSError, sqlite3.Error) as exc:
            temporary.unlink(missing_ok=True)
            raise RuntimeDatabaseError("runtime_backup_failed") from exc
        return target

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
