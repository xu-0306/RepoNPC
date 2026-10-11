"""Disposable encrypted maintenance exercises the real normalizer and lifecycle."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reponpc.admin.backup_encryption import BackupEncryptionError, BackupMetadata, seal, unseal
from reponpc.admin.maintenance import MaintenanceError, MaintenanceService
from reponpc.admin.maintenance_host import MaintenanceHost
from reponpc.runtime.database import BundleRuntimeState, RuntimeDatabase

PASSWORD = "SYNTHETIC_BACKUP_PASSWORD_ONLY"
SESSION = "synthetic-session-hash"


def _state(database: RuntimeDatabase, value: str) -> None:
    database.save_bundle_state(BundleRuntimeState(None, None, None, None, None, value))


@pytest.fixture
def database(tmp_path: Path) -> RuntimeDatabase:
    result = RuntimeDatabase(tmp_path / "data")
    result.initialize()
    _state(result, "BEFORE")
    return result


def _service(database: RuntimeDatabase) -> MaintenanceService:
    return MaintenanceService(
        database,
        resource_check=lambda _: None,
        application_factory=lambda: FastAPI(),
        idle_check=lambda: None,
    )


def test_backup_ciphertext_only_and_online_snapshot(database: RuntimeDatabase) -> None:
    service = _service(database)
    artifact = service.backup(PASSWORD)
    assert b"SQLite format 3" not in artifact
    metadata, raw = unseal(artifact, PASSWORD)
    assert metadata.schema_version == database.schema_version()
    assert raw.startswith(b"SQLite format 3\x00")
    assert service.last_backup_at() is not None
    assert list((database.database_path.parent / "private/maintenance").glob("*.reponpc-backup"))
    assert not list((database.database_path.parent / "private/maintenance").glob("preview-*"))


def test_preview_is_bound_to_session_expires_and_cancel_removes_plaintext(
    database: RuntimeDatabase,
) -> None:
    service = _service(database)
    preview = service.inspect(service.backup(PASSWORD), PASSWORD, SESSION)
    assert set(preview) == {
        "preview_id",
        "created_at",
        "schema_version",
        "application_version",
        "expires_at",
    }
    with pytest.raises(MaintenanceError, match="maintenance operation failed") as wrong:
        service.cancel(str(preview["preview_id"]), "another-session")
    assert wrong.value.code == "RESTORE_PREVIEW_EXPIRED"
    assert service._preview is not None
    service._preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(MaintenanceError) as expired:
        service.verify_restore(str(preview["preview_id"]), SESSION)
    assert expired.value.code == "RESTORE_PREVIEW_EXPIRED"
    service.close()
    assert service._preview is None
    assert not list(service._root.glob("preview-*"))


@pytest.mark.parametrize("kind", ["password", "tamper", "metadata", "future-version"])
def test_invalid_backup_keeps_current_data(database: RuntimeDatabase, kind: str) -> None:
    service = _service(database)
    artifact = service.backup(PASSWORD)
    password = PASSWORD
    if kind == "password":
        password += "wrong"
    elif kind == "tamper":
        artifact = artifact[:-1] + bytes([artifact[-1] ^ 1])
    else:
        metadata, raw = unseal(artifact, PASSWORD)
        metadata = BackupMetadata(
            metadata.created_at,
            metadata.schema_version + 1 if kind == "metadata" else metadata.schema_version,
            "999.0.0" if kind == "future-version" else metadata.application_version,
        )
        artifact = seal(raw, PASSWORD, metadata)
    with pytest.raises((MaintenanceError, BackupEncryptionError)):
        service.inspect(artifact, password, SESSION)
    assert database.bundle_state().safe_update_error == "BEFORE"
    assert not list(service._root.glob("preview-*"))


def test_candidate_change_after_preview_is_rejected(database: RuntimeDatabase) -> None:
    service = _service(database)
    preview = service.inspect(service.backup(PASSWORD), PASSWORD, SESSION)
    assert service._preview is not None
    with service._preview.database_path.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(MaintenanceError) as error:
        service.verify_restore(str(preview["preview_id"]), SESSION)
    assert error.value.code == "BACKUP_SQLITE_INVALID"
    assert database.bundle_state().safe_update_error == "BEFORE"
    service.close()


def test_busy_crypto_lane_rejects_without_creating_storage(database: RuntimeDatabase) -> None:
    service = _service(database)
    service._lock.acquire()
    try:
        with pytest.raises(MaintenanceError) as error:
            service.backup(PASSWORD)
        assert error.value.code == "MAINTENANCE_BUSY"
        assert not service._root.exists()
    finally:
        service._lock.release()


@pytest.mark.parametrize("failure", [None, "pointer", "fresh-start"])
def test_real_host_restore_or_rollback_preserves_snapshot(
    database: RuntimeDatabase,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    events: list[str] = []
    starts = 0
    service: MaintenanceService

    def application_factory() -> FastAPI:
        nonlocal starts
        starts += 1
        generation = starts

        @asynccontextmanager
        async def lifespan(application: FastAPI):
            if failure == "fresh-start" and generation == 2:
                raise RuntimeError("SYNTHETIC_START_FAILURE")
            events.append(f"start-{generation}")
            yield
            events.append(f"stop-{generation}")

        application = FastAPI(lifespan=lifespan)

        @application.get("/value")
        def read_value():
            return {"value": database.bundle_state().safe_update_error}

        @application.post("/restore")
        async def restore():
            service.restore(preview_id, SESSION, host)
            return {"status": "restoring"}

        return application

    service = MaintenanceService(
        database,
        resource_check=lambda _: None,
        application_factory=application_factory,
        idle_check=lambda: None,
    )
    preview = service.inspect(service.backup(PASSWORD), PASSWORD, SESSION)
    preview_id = str(preview["preview_id"])
    _state(database, "AFTER")
    pointer = database.database_path.parent / "bundles/active.json"
    pointer.parent.mkdir()
    pointer.write_bytes(b'{"bundle_id":"SYNTHETIC_PREVIOUS"}')
    if failure == "pointer":
        original = service._write_pointer
        once = True

        def fail_pointer(path: Path, payload: bytes | None) -> None:
            nonlocal once
            if once:
                once = False
                raise OSError("SYNTHETIC_POINTER_FAILURE")
            original(path, payload)

        monkeypatch.setattr(service, "_write_pointer", fail_pointer)
    host = MaintenanceHost(application_factory(), restart_old=application_factory)
    with TestClient(host) as client:
        response = client.post("/restore")
        assert response.status_code == 200
        deadline = time.monotonic() + 10
        while host.busy and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not host.busy
        expected = "BEFORE" if failure is None else "AFTER"
        assert client.get("/value").json() == {"value": expected}
        assert events[0:2] == ["start-1", "stop-1"]
        assert len(list(service._root.glob("*.reponpc-backup"))) == 2
        # Automatic current backup is encrypted using the uploaded backup's password.
        snapshots = [
            unseal(item.read_bytes(), PASSWORD)[1]
            for item in service._root.glob("*.reponpc-backup")
        ]
        assert all(item.startswith(b"SQLite format 3\x00") for item in snapshots)
        if failure is None:
            assert service._preview is None
            assert not pointer.exists()
        else:
            assert pointer.read_bytes() == b'{"bundle_id":"SYNTHETIC_PREVIOUS"}'
            assert host.last_error is not None
    service.close()
