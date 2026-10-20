"""Disposable SQLite and real-thread regressions for maintenance failure boundaries."""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO, cast

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import StreamingResponse

import reponpc.admin.maintenance as maintenance_module
from reponpc.admin.maintenance import MaintenanceError, MaintenanceService
from reponpc.admin.maintenance_host import MaintenanceHost
from reponpc.api.public import PublicChatRequest
from reponpc.api.visitor_gateway import VisitorGatewayError
from reponpc.api.visitor_ingress import VisitorChatWorkers, _chat_response
from reponpc.main import create_app
from reponpc.runtime.database import BundleRuntimeState, RuntimeDatabase
from tests.integration.test_visitor_gateway_lifecycle import make_gateway

PASSWORD = "SYNTHETIC_BACKUP_PASSWORD_ONLY"
SESSION = "synthetic-session-hash"


class ManualTimer:
    """Run the actual expiry callback deterministically without a ten-minute sleep."""

    def __init__(
        self, interval: float, function: Callable[..., object], args: Sequence[object] = ()
    ) -> None:
        self.interval = interval
        self.function = function
        self.args = args
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        assert self.started and not self.cancelled
        self.function(*self.args)


@pytest.fixture
def database(tmp_path: Path) -> RuntimeDatabase:
    database = RuntimeDatabase(tmp_path / "data")
    database.initialize()
    database.save_bundle_state(BundleRuntimeState(None, None, None, "BEFORE", None))
    return database


@pytest.fixture
def service(
    database: RuntimeDatabase, monkeypatch: pytest.MonkeyPatch
) -> Iterator[MaintenanceService]:
    monkeypatch.setattr(maintenance_module.threading, "Timer", ManualTimer)
    service = MaintenanceService(
        database,
        resource_check=lambda _: None,
        application_factory=FastAPI,
        idle_check=lambda: None,
    )
    try:
        yield service
    finally:
        service.close(abort_restore=True)


def inspect(service: MaintenanceService) -> str:
    return str(service.inspect(service.backup(PASSWORD), PASSWORD, SESSION)["preview_id"])


def test_idle_expiry_removes_owned_plaintext_and_clears_password(
    service: MaintenanceService,
) -> None:
    inspect(service)
    preview = service._preview
    timer = service._preview_timer
    assert preview is not None and isinstance(timer, ManualTimer)
    assert timer.interval <= 600 and timer.started and timer.daemon
    assert preview.database_path.read_bytes().startswith(b"SQLite format 3\x00")
    timer.fire()
    assert preview.password == ""
    assert service._preview is None
    assert not preview.directory.exists()
    assert timer.cancelled
    # The independently encrypted recovery artifact survives private-preview cleanup.
    assert service.last_backup_at() is not None


@pytest.mark.parametrize("terminal", ["abort", "failed-host"])
def test_near_expiry_restore_terminal_cleanup_preserves_current(
    service: MaintenanceService, database: RuntimeDatabase, terminal: str
) -> None:
    inspect(service)
    preview = service._preview
    timer = service._preview_timer
    assert preview is not None and isinstance(timer, ManualTimer)
    service._restoring = True
    preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    timer.fire()
    assert preview.password == ""
    if terminal == "abort":
        service.close(abort_restore=True)
    else:
        host = MaintenanceHost(FastAPI())
        host._busy = False
        host._last_error = "MAINTENANCE_DRAIN_TIMEOUT"
        service.reconcile_host(host)
    assert service._preview is None and not service._restoring
    assert not preview.directory.exists()
    assert database.bundle_state().manifest_etag == "BEFORE"


def test_expired_after_admission_never_seals_or_swaps_current(
    service: MaintenanceService, database: RuntimeDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspect(service)
    preview = service._preview
    assert preview is not None
    preview.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    service._restoring = True
    pointer = database.database_path.parent / "bundles/active.json"
    pointer.parent.mkdir()
    pointer.write_bytes(b'{"bundle_id":"SYNTHETIC_LKG"}')
    receipts = set(service._root.glob("*.reponpc-backup"))

    def forbidden_seal(*_args: object, **_kwargs: object) -> None:
        pytest.fail("an expired restore must fail before encrypting a snapshot")

    monkeypatch.setattr(maintenance_module, "seal", forbidden_seal)
    with pytest.raises(MaintenanceError) as failure:
        service._replace(preview)
    assert failure.value.code == "RESTORE_FAILED"
    assert database.bundle_state().manifest_etag == "BEFORE"
    assert pointer.read_bytes() == b'{"bundle_id":"SYNTHETIC_LKG"}'
    assert set(service._root.glob("*.reponpc-backup")) == receipts
    assert service._preview is None and preview.password == ""
    assert not preview.directory.exists()


@pytest.mark.parametrize("failure", ["write", "fsync"])
def test_failed_backup_save_has_no_final_receipt_or_timestamp(
    service: MaintenanceService, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    # This tests ciphertext publication only; no plaintext enters the saved-file primitive.
    sentinel = service._working_directory() / "unrelated-owner-file"
    sentinel.write_bytes(b"keep unrelated fixture")
    original_fdopen = os.fdopen

    class PartialWriter:
        def __init__(self, stream: BinaryIO) -> None:
            self.stream = stream

        def write(self, data: bytes) -> int:
            self.stream.write(data[:8])
            raise OSError("SYNTHETIC_DISK_FULL")

    @contextmanager
    def partial_fdopen(descriptor: int, mode: str) -> Iterator[PartialWriter]:
        with original_fdopen(descriptor, mode) as stream:
            yield PartialWriter(cast(BinaryIO, stream))

    def failed_fsync(_descriptor: int) -> None:
        raise OSError("SYNTHETIC_FSYNC_FAILURE")

    if failure == "write":
        monkeypatch.setattr(maintenance_module.os, "fdopen", partial_fdopen)
    else:
        monkeypatch.setattr(maintenance_module.os, "fsync", failed_fsync)
    with pytest.raises(OSError):
        service._save_encrypted(b"synthetic-ciphertext-not-a-real-backup")
    assert not list(service._root.glob("*.reponpc-backup"))
    assert not list(service._root.glob("*.tmp"))
    assert service.last_backup_at() is None
    assert sentinel.read_bytes() == b"keep unrelated fixture"


def test_real_lifespan_failed_gateway_stop_cleans_preview_and_stays_closed(
    service: MaintenanceService, database: RuntimeDatabase
) -> None:
    preview_id = inspect(service)
    preview = service._preview
    assert preview is not None
    database.save_bundle_state(BundleRuntimeState(None, None, None, "CURRENT_LKG", None))
    app = create_app(runtime_database=database)

    class FailedGateway:
        async def resume(self) -> None:
            pass

        async def shutdown(self) -> None:
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")

    app.state.visitor_gateway = FailedGateway()
    app.state.maintenance_service = service

    async def scenario() -> None:
        host = MaintenanceHost(app)
        await host._enter(app)
        host._busy = False
        try:
            service.restore(preview_id, SESSION, host)
            assert host._maintenance is not None
            await asyncio.wait_for(asyncio.shield(host._maintenance), 3)
            assert host.busy and host.current is app
            assert host.last_error == "MAINTENANCE_STOP_FAILED"
            assert service._preview is None and not service._restoring
            assert preview.password == "" and not preview.directory.exists()
            assert database.bundle_state().manifest_etag == "CURRENT_LKG"
        finally:
            await host._exit()

    asyncio.run(scenario())


class BlockedAnswer:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.cancel_requested: threading.Event | None = None

    def answer(self, **kwargs: object) -> None:
        cancelled = kwargs["cancel_requested"]
        assert isinstance(cancelled, threading.Event)
        self.cancel_requested = cancelled
        self.started.set()
        try:
            assert self.release.wait(5), "synthetic worker was not released"
        finally:
            self.finished.set()


async def wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(0.001)


async def detach(workers: VisitorChatWorkers, answer: BlockedAnswer) -> None:
    async def receive() -> dict[str, str]:
        return {"type": "http.disconnect"}

    request = Request(
        {"type": "http", "method": "POST", "path": "/api/public/chat/stream", "headers": []},
        receive,
    )
    response = await _chat_response(
        request,
        PublicChatRequest(message="synthetic fixture", locale="en"),
        answer,
        identity="synthetic-fixture",
        active_workers=workers,
        deadline=time.monotonic() + 4,
        keepalive_seconds=0.05,
        project_event=lambda _event, payload: payload,
        stream_error=lambda _: ("REQUEST_FAILED", None),
    )
    assert isinstance(response, StreamingResponse)
    stream = aiter(response.body_iterator)
    await anext(stream)
    await wait_until(answer.started.is_set)
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


def test_public_disconnect_retains_worker_until_actual_thread_exit() -> None:
    async def scenario() -> None:
        workers = VisitorChatWorkers(None)
        answer = BlockedAnswer()
        try:
            await detach(workers, answer)
            assert answer.cancel_requested is not None and answer.cancel_requested.is_set()
            assert workers.active_count == 1 and not answer.finished.is_set()
        finally:
            answer.release.set()
            await wait_until(lambda: workers.active_count == 0)
        assert answer.finished.is_set()

    asyncio.run(scenario())


@pytest.mark.parametrize("release_before_deadline", [True, False])
def test_gateway_shutdown_waits_detached_worker_and_fails_closed_on_timeout(
    tmp_path: Path, release_before_deadline: bool
) -> None:
    gateway, _database, _port, _state, _manager = make_gateway(tmp_path)

    async def scenario() -> None:
        answer = BlockedAnswer()
        stopping: asyncio.Task[None] | None = None
        try:
            await detach(gateway.workers, answer)
            stopping = asyncio.create_task(gateway.shutdown())
            if release_before_deadline:
                await asyncio.sleep(0.02)
                assert not stopping.done() and gateway.workers.active_count == 1
                answer.release.set()
                await asyncio.wait_for(stopping, 3)
                assert gateway.workers.active_count == 0
            else:
                with pytest.raises(VisitorGatewayError) as failure:
                    await asyncio.wait_for(stopping, 3)
                assert failure.value.code == "GATEWAY_UNAVAILABLE"
                assert gateway.workers.active_count == 1 and not answer.finished.is_set()
        finally:
            answer.release.set()
            await wait_until(lambda: gateway.workers.active_count == 0)
            if stopping is not None and not stopping.done():
                await asyncio.wait_for(stopping, 3)

    asyncio.run(scenario())
