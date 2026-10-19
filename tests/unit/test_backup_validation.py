"""Disposable, offline fixtures exercise the SQLite restore trust boundary."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

import pytest

from reponpc.admin import backup_validation as validation
from reponpc.runtime.database import MIGRATIONS, RuntimeDatabase

STAMP = "2026-10-03T00:00:00Z"
SESSION = hashlib.sha256(b"synthetic session authority").hexdigest()
GRANT = hashlib.sha256(b"synthetic launch authority").hexdigest()
SETUP = hashlib.sha256(b"synthetic setup authority").hexdigest()
OWNER_HASH = "$argon2id$synthetic-owner-hash"


def _source(
    tmp_path: Path,
    *,
    version: int = MIGRATIONS[-1].version,
    mutate: Callable[[sqlite3.Connection], object] | None = None,
) -> bytes:
    directory = tmp_path / "source"
    directory.mkdir(mode=0o700)
    database = RuntimeDatabase(directory)
    database.initialize(migrations=MIGRATIONS[:version])
    with database.connection() as connection:
        if mutate:
            mutate(connection)
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")
    return database.database_path.read_bytes()


def _work(tmp_path: Path) -> Path:
    path = tmp_path / "work"
    path.mkdir(mode=0o700)
    return path


def _seed_owner(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO admin_owner VALUES ('current', ?, ?, ?)",
        ("fixture'; DROP TABLE admin_owner; --", OWNER_HASH, STAMP),
    )


def _seed_current(connection: sqlite3.Connection) -> None:
    _seed_owner(connection)
    connection.execute("INSERT INTO admin_auth_methods VALUES ('local_password', ?)", (STAMP,))
    connection.execute("UPDATE admin_state SET session_epoch = 12")
    connection.execute(
        "INSERT INTO admin_sessions(session_hash,csrf_hash,created_at,last_seen_at,"
        "idle_expires_at,absolute_expires_at,session_epoch,authenticated_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (SESSION, "c" * 64, STAMP, STAMP, STAMP, STAMP, 12, STAMP),
    )
    connection.execute("INSERT INTO admin_setup VALUES ('current', ?, ?, ?)", (SETUP, STAMP, STAMP))
    connection.execute(
        "INSERT INTO admin_local_launch_grants VALUES ('current', ?, ?, ?, NULL)",
        (GRANT, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO admin_audit(occurred_at,action,request_id,outcome,session_hash) "
        "VALUES (?, 'fixture-audit', 'fixture-request', 'ok', ?)",
        (STAMP, SESSION),
    )
    connection.execute(
        "INSERT INTO admin_oauth_transactions VALUES "
        "(?, 'connection', ?, ?, ?, ?, ?, NULL, '/admin')",
        ("d" * 64, b"fixture-nonce", b"fixture-ciphertext", SESSION, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO scene_background_drafts VALUES (?, ?, ?, 'png', ?, ?)",
        ("e" * 64, SESSION, "f" * 64, STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO model_connections(connection_id,display_name,provider,source,revision,"
        "secret_ref,endpoint_configured,key_configured,status,created_at,updated_at) VALUES "
        "('fixture-connection', 'Fixture service', 'ollama', 'managed', 2, 'secret-2',"
        " 1, 0, 'available', ?, ?)",
        (STAMP, STAMP),
    )
    for revision in (1, 2):
        connection.execute(
            "INSERT INTO model_connection_secrets"
            "(secret_ref,connection_id,revision,ciphertext,created_at,provider) "
            "VALUES (?, 'fixture-connection', ?, ?, ?, 'ollama')",
            (f"secret-{revision}", revision, f"synthetic-encrypted-{revision}".encode(), STAMP),
        )
    connection.execute(
        "INSERT INTO embedding_profiles"
        "(profile_id,provider,model_id,dimension,normalized,query_prefix,passage_prefix,"
        "connection_reference,status,active,created_at,updated_at,connection_revision,bundle_id) "
        "VALUES ('fixture-embed','ollama','unseen-model',1024,1,'','',"
        "'fixture-connection','last_known_good',1,?,?,2,'fixture-bundle')",
        (STAMP, STAMP),
    )
    connection.execute(
        "INSERT INTO chat_profiles"
        "(profile_id,connection_id,connection_revision,model_id,status,active,"
        "created_at,updated_at) "
        "VALUES ('fixture-chat','fixture-connection',2,'unseen-chat','last_known_good',1,?,?)",
        (STAMP, STAMP),
    )
    connection.execute(
        "UPDATE analysis_model_selection SET chat_profile_id='fixture-chat', "
        "chat_connection_revision=2, embedding_profile_id='fixture-embed', "
        "embedding_connection_revision=2"
    )
    connection.execute(
        "INSERT INTO bundle_state(state_key,active_bundle_id,previous_bundle_id,pinned_bundle_id) "
        "VALUES ('current','fixture-bundle','fixture-previous','fixture-bundle')"
    )
    connection.execute(
        "INSERT INTO analysis_batches(batch_id,plan_id,selection_hash,idempotency_key_hash,state,"
        "maximum_generation_attempts,created_at,updated_at) "
        "VALUES ('fixture-batch','fixture-plan',?,?,'running',3,?,?)",
        ("1" * 64, "2" * 64, STAMP, STAMP),
    )


@pytest.mark.parametrize("version", [33, 34, 36, 37])
def test_current_round_trip_preserves_owner_encrypted_revisions_selection_and_bundle(
    tmp_path: Path,
    version: int,
) -> None:
    blob = _source(tmp_path, version=version, mutate=_seed_current)
    original = hashlib.sha256(blob).hexdigest()
    result = validation.validate_backup(blob, _work(tmp_path))

    assert result.schema_version == version
    assert set(asdict(result)) == {"path", "schema_version"}
    assert hashlib.sha256(blob).hexdigest() == original
    assert result.path != tmp_path / "source/runtime.sqlite"
    with closing(sqlite3.connect(result.path)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT password_hash FROM admin_owner").fetchone() == (
            OWNER_HASH,
        )
        assert connection.execute("SELECT method FROM admin_auth_methods").fetchone() == (
            "local_password",
        )
        assert connection.execute(
            "SELECT revision,ciphertext FROM model_connection_secrets ORDER BY revision"
        ).fetchall() == [(1, b"synthetic-encrypted-1"), (2, b"synthetic-encrypted-2")]
        assert connection.execute("SELECT active_bundle_id FROM bundle_state").fetchone() == (
            "fixture-bundle",
        )
        assert connection.execute("SELECT state FROM analysis_batches").fetchone() == ("running",)
        assert connection.execute("SELECT active FROM embedding_profiles").fetchone() == (1,)
        assert connection.execute(
            "SELECT embedding_connection_revision FROM analysis_model_selection"
        ).fetchone() == (2,)
    assert not (tmp_path / "work/uploaded.sqlite").exists()
    assert sorted(path.name for path in result.path.parent.iterdir()) == ["runtime.sqlite"]


def test_authority_and_preview_rows_are_removed_without_deleting_audit_or_owner(
    tmp_path: Path,
) -> None:
    blob = _source(tmp_path, mutate=_seed_current)
    result = validation.validate_backup(blob, _work(tmp_path))

    with closing(sqlite3.connect(result.path)) as connection:
        for table in (
            "admin_sessions",
            "admin_local_launch_grants",
            "admin_setup",
            "admin_oauth_transactions",
            "scene_background_drafts",
        ):
            assert connection.execute(f'SELECT count(*) FROM "{table}"').fetchone() == (0,)
        assert connection.execute("SELECT session_epoch FROM admin_state").fetchone() == (13,)
        assert connection.execute("SELECT action,session_hash FROM admin_audit").fetchone() == (
            "fixture-audit",
            None,
        )
        assert connection.execute("SELECT count(*) FROM admin_owner").fetchone() == (1,)
    output = result.path.read_bytes()
    assert all(value.encode() not in output for value in (SESSION, GRANT, SETUP))
    assert (
        OWNER_HASH.encode() in output
    )  # Private encrypted-artifact input, never browser metadata.


@pytest.mark.parametrize("version", [1, 3, 5, 12, 16, 29, 33])
def test_older_source_version_matches_artifact_metadata_while_output_is_current(
    tmp_path: Path,
    version: int,
) -> None:
    blob = _source(tmp_path, version=version, mutate=_seed_owner if version >= 3 else None)
    artifact_metadata = {"schema_version": version}
    result = validation.validate_backup(blob, _work(tmp_path))

    assert result.schema_version == artifact_metadata["schema_version"]
    assert result.schema_version != MIGRATIONS[-1].version
    with closing(sqlite3.connect(result.path)) as connection:
        assert connection.execute(
            "SELECT max(version) FROM runtime_schema_migrations"
        ).fetchone() == (MIGRATIONS[-1].version,)
        assert connection.execute("SELECT session_epoch FROM admin_state").fetchone() == (1,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        if version >= 3:
            assert connection.execute("SELECT password_hash FROM admin_owner").fetchone() == (
                OWNER_HASH,
            )


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE unexpected(secret TEXT)",
        "CREATE VIEW owner_view AS SELECT * FROM admin_owner",
        "CREATE TRIGGER owner_trigger AFTER INSERT ON admin_owner "
        "BEGIN DELETE FROM admin_owner; END",
        "CREATE INDEX extra_index ON admin_owner(username)",
        "DROP INDEX admin_audit_occurred_at_idx",
        "ALTER TABLE admin_owner ADD COLUMN unexpected TEXT",
    ],
)
def test_extra_or_changed_schema_is_rejected_before_application_rows(
    tmp_path: Path, sql: str
) -> None:
    blob = _source(tmp_path, mutate=lambda connection: connection.execute(sql))
    work = _work(tmp_path)

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_SCHEMA_INVALID"
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM runtime_schema_migrations WHERE version=2",
        "UPDATE runtime_schema_migrations SET name='forged' WHERE version=3",
        "INSERT INTO runtime_schema_migrations(version,name) VALUES (999,'future')",
        "DELETE FROM runtime_schema_migrations",
    ],
)
def test_missing_tampered_or_future_migrations_fail_closed(tmp_path: Path, sql: str) -> None:
    blob = _source(tmp_path, mutate=lambda connection: connection.execute(sql))
    work = _work(tmp_path)

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_MIGRATIONS_INVALID"
    assert list(work.iterdir()) == []


def test_foreign_key_violation_is_rejected_and_discarded(tmp_path: Path) -> None:
    def violate(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO admin_audit(occurred_at,action,request_id,outcome,session_hash) "
            "VALUES (?, 'fixture', 'fixture', 'ok', ?)",
            (STAMP, SESSION),
        )

    work = _work(tmp_path)
    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(_source(tmp_path, mutate=violate), work)
    assert failure.value.code == "BACKUP_FOREIGN_KEYS_INVALID"
    assert list(work.iterdir()) == []


def test_malicious_check_cannot_invoke_registered_function(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def forge(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_schema SET sql=replace(sql,'length(username)','hostile(username)') "
            "WHERE name='admin_owner'"
        )
        connection.execute("PRAGMA writable_schema=OFF")

    blob = _source(tmp_path, mutate=forge)
    called: list[object] = []
    original: Callable[..., sqlite3.Connection] = sqlite3.connect

    def hostile(value: object) -> int:
        called.append(value)
        return 1

    def connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = original(*args, **kwargs)
        if kwargs.get("uri"):
            connection.create_function("hostile", 1, hostile)
        return connection

    monkeypatch.setattr(validation.sqlite3, "connect", connect)
    with pytest.raises(validation.BackupValidationError):
        validation.validate_backup(blob, _work(tmp_path))
    assert called == []


def test_invalid_stored_check_data_fails_integrity(tmp_path: Path) -> None:
    def violate(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "INSERT INTO admin_owner VALUES ('current','fixture','invalid-hash',?)", (STAMP,)
        )

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(_source(tmp_path, mutate=violate), _work(tmp_path))
    # SQLite CHECK coverage varies; trusted parameterized insertion is also a
    # required constraint gate and must reject this row before returning output.
    assert failure.value.code in {"BACKUP_INTEGRITY_INVALID", "BACKUP_SQLITE_INVALID"}


@pytest.mark.parametrize(
    "invalid", [b"PK\x03\x04" + bytes(4092), b"BEGIN; CREATE TABLE fake(x);", bytes(4096)]
)
def test_only_raw_sqlite_is_accepted_without_creating_files(tmp_path: Path, invalid: bytes) -> None:
    work = _work(tmp_path)
    with pytest.raises(validation.BackupValidationError):
        validation.validate_backup(invalid, work)
    assert list(work.iterdir()) == []


def test_size_and_header_constraints_are_checked_before_disk_writes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert validation.MAX_BACKUP_BYTES == 128 * 1024 * 1024
    blob = _source(tmp_path)
    work = _work(tmp_path)
    monkeypatch.setattr(validation, "MAX_BACKUP_BYTES", len(blob) - 1)
    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_SIZE_INVALID"
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    "offset,value", [(16, b"\x00\x21"), (18, b"\x09"), (56, b"\x00\x00\x00\x02"), (72, b"\x01")]
)
def test_malformed_sqlite_header_is_rejected(tmp_path: Path, offset: int, value: bytes) -> None:
    blob = bytearray(_source(tmp_path))
    blob[offset : offset + len(value)] = value
    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(bytes(blob), _work(tmp_path))
    assert failure.value.code == "BACKUP_HEADER_INVALID"


def test_corrupt_database_pages_fail_closed(tmp_path: Path) -> None:
    blob = bytearray(_source(tmp_path))
    blob[100] = 0  # Invalid sqlite_schema b-tree page type; the raw header remains valid.
    with pytest.raises(validation.BackupValidationError):
        validation.validate_backup(bytes(blob), _work(tmp_path))


def test_nonfresh_directory_and_hardlinked_sibling_are_never_overwritten(tmp_path: Path) -> None:
    blob = _source(tmp_path)
    work = _work(tmp_path)
    outside = tmp_path / "outside"
    outside.write_bytes(b"disposable outside content")
    os.link(outside, work / "uploaded.sqlite")

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_WORKING_DIRECTORY_NOT_FRESH"
    assert outside.read_bytes() == b"disposable outside content"
    assert (work / "uploaded.sqlite").read_bytes() == outside.read_bytes()


def test_symlinked_ancestor_is_rejected(tmp_path: Path) -> None:
    blob = _source(tmp_path)
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    (real / "work").mkdir(mode=0o700)
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("this host cannot create disposable directory symlinks")

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, linked / "work")
    assert failure.value.code == "BACKUP_WORKING_DIRECTORY_INVALID"
    assert list((real / "work").iterdir()) == []


def test_descriptor_creation_is_exclusive_and_private(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blob = _source(tmp_path)
    work = _work(tmp_path)
    original = os.open
    observed: list[tuple[int, int]] = []

    def open_file(path: Path, flags: int, mode: int = 0o777) -> int:
        observed.append((flags, mode))
        return original(path, flags, mode)

    monkeypatch.setattr(validation.os, "open", open_file)
    validation.validate_backup(blob, work)

    assert len(observed) == 2
    for flags, mode in observed:
        assert flags & os.O_EXCL and flags & os.O_CREAT
        assert mode == 0o600
        if hasattr(os, "O_NOFOLLOW"):
            assert flags & os.O_NOFOLLOW


def test_deadline_failure_leaves_no_normalized_or_raw_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blob = _source(tmp_path)
    work = _work(tmp_path)
    monkeypatch.setattr(validation, "VALIDATION_SECONDS", 0)

    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_VALIDATION_TIMEOUT"
    assert list(work.iterdir()) == []


def test_hardened_readonly_connection_disables_extensions_and_bounds_sql(tmp_path: Path) -> None:
    _source(tmp_path)
    path = tmp_path / "source/runtime.sqlite"
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        validation._harden(connection, time.monotonic() + 30, readonly=True)
        assert connection.execute("PRAGMA trusted_schema").fetchone() == (0,)
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED) == 0
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_COLUMN) == 128
        assert connection.getlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH) == 64 * 1024
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("INSERT INTO admin_state VALUES ('forbidden',1)")
        with pytest.raises(sqlite3.OperationalError, match="not authorized"):
            connection.execute("SELECT load_extension('forbidden-fixture-extension')")


def test_progress_deadline_interrupts_expensive_sql(tmp_path: Path) -> None:
    _source(tmp_path)
    path = tmp_path / "source/runtime.sqlite"
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        validation._harden(connection, time.monotonic() - 1, readonly=True)
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            connection.execute(
                "WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<1000000) "
                "SELECT sum(n) FROM x"
            ).fetchone()


def test_errors_do_not_expose_uploaded_values_or_database_path(tmp_path: Path) -> None:
    blob = _source(
        tmp_path, mutate=lambda connection: connection.execute("CREATE TABLE private_secret(x)")
    )
    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, _work(tmp_path))

    assert str(failure.value) == "backup validation failed"
    assert "private_secret" not in repr(failure.value)
    assert str(tmp_path) not in repr(failure.value)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM admin_state",
        "UPDATE admin_state SET session_epoch=9223372036854775807",
        "UPDATE admin_state SET session_epoch=0.5",
    ],
)
def test_missing_or_unsafe_auth_epoch_cannot_produce_restorable_authority(
    tmp_path: Path,
    sql: str,
) -> None:
    blob = _source(tmp_path, mutate=lambda connection: connection.execute(sql))
    work = _work(tmp_path)
    with pytest.raises(validation.BackupValidationError) as failure:
        validation.validate_backup(blob, work)
    assert failure.value.code == "BACKUP_AUTH_STATE_INVALID"
    assert list(work.iterdir()) == []


def test_output_creation_failure_removes_only_our_private_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blob = _source(tmp_path)
    work = _work(tmp_path)
    original = validation._create_file

    def fail_output(path: Path, content: bytes) -> tuple[int, int]:
        if path.name == "runtime.sqlite":
            raise OSError("disposable fixture write failure")
        return original(path, content)

    monkeypatch.setattr(validation, "_create_file", fail_output)
    with pytest.raises(validation.BackupValidationError):
        validation.validate_backup(blob, work)
    assert list(work.iterdir()) == []


@pytest.mark.parametrize("version", [36, 37])
def test_faq_reason_backup_normalization_preserves_current_and_upgrades_old(tmp_path, version):
    def seed(connection):
        connection.execute(
            "INSERT INTO faq_entries(entry_id,question_key,bundle_id,locale,question,claim_kind,"
            "review_state,answer_markdown) VALUES ('fixture','q','bundle','en','Question',"
            "'context','approved','Reviewed answer')"
        )
        if version == 37:
            connection.execute("UPDATE faq_entries SET no_match_reason='SOURCE_ID_UNKNOWN'")

    blob = _source(tmp_path, version=version, mutate=seed)
    result = validation.validate_backup(blob, _work(tmp_path))
    assert result.schema_version == version
    with closing(sqlite3.connect(result.path)) as connection:
        assert (
            connection.execute("SELECT max(version) FROM runtime_schema_migrations").fetchone()[0]
            == 37
        )
        assert connection.execute(
            "SELECT answer_markdown,review_state,no_match_reason FROM faq_entries"
        ).fetchone() == (
            "Reviewed answer",
            "approved",
            "SOURCE_ID_UNKNOWN" if version == 37 else None,
        )
