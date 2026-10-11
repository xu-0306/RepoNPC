"""Owned ASGI lifespans and in-memory callbacks; no real runtime state is restored."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response

from reponpc.admin import maintenance_host as module
from reponpc.admin.maintenance_host import MaintenanceHost, MaintenanceHostError, Replacement


class Tracker:
    def __init__(self) -> None:
        self.active: list[str] = []
        self.events: list[str] = []

    def application(
        self, label: str, *, start_fails: bool = False, stop_fails: bool = False
    ) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, str]]:
            assert not self.active, "two application lifespans must never overlap"
            self.active.append(label)
            self.events.append("enter:" + label)
            try:
                if start_fails:
                    raise RuntimeError("example-private-start-error")
                yield {"generation": label}
            finally:
                self.events.append("exit:" + label)
                self.active.remove(label)
                if stop_fails:
                    raise RuntimeError("example-private-stop-error")

        app = FastAPI(lifespan=lifespan)

        @app.get("/healthz")
        async def health() -> dict[str, str]:
            return {"generation": label}

        return app


class Lifespan:
    def __init__(self, host: MaintenanceHost) -> None:
        self.host = host
        self.incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.outgoing: asyncio.Queue[Any] = asyncio.Queue()
        self.state: dict[str, Any] = {}
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> dict[str, Any]:
        scope = {"type": "lifespan", "state": self.state}
        self.task = asyncio.create_task(self.host(scope, self.incoming.get, self.outgoing.put))
        await self.incoming.put({"type": "lifespan.startup"})
        return await asyncio.wait_for(self.outgoing.get(), 2)

    async def stop(self) -> dict[str, Any]:
        assert self.task is not None
        await self.incoming.put({"type": "lifespan.shutdown"})
        response = await asyncio.wait_for(self.outgoing.get(), 2)
        await self.task
        return response


async def request(host: MaintenanceHost, path: str = "/healthz", **extra: Any) -> list[Any]:
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "scheme": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 54321),
        "server": ("127.0.0.1", 8000),
        "state": {},
    }
    scope.update(extra)
    messages: list[Any] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Any) -> None:
        messages.append(message)

    await host(scope, receive, send)
    return messages


async def maintenance_done(host: MaintenanceHost) -> None:
    assert host._maintenance is not None
    await asyncio.wait_for(asyncio.shield(host._maintenance), 2)


def test_initial_start_and_shutdown_own_exactly_one_context() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        host = MaintenanceHost(old)
        assert host.current is old and host.busy
        assert (await request(host))[0]["status"] == 503
        with pytest.raises(MaintenanceHostError) as captured:
            host.schedule(lambda: Replacement(old, lambda: old))
        assert captured.value.code == "MAINTENANCE_NOT_STARTED"
        life = Lifespan(host)
        assert (await life.start())["type"] == "lifespan.startup.complete"
        assert old.state.maintenance_host is host
        assert life.state == {"generation": "old"}
        assert not host.busy and tracker.active == ["old"]
        assert (await request(host))[0]["status"] == 200
        assert (await life.stop())["type"] == "lifespan.shutdown.complete"
        assert tracker.events == ["enter:old", "exit:old"]
        assert host.busy and not tracker.active

    asyncio.run(scenario())


def test_inflight_request_drains_and_busy_response_is_safe() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        entered, release = asyncio.Event(), asyncio.Event()

        @old.get("/hold")
        async def hold() -> Response:
            entered.set()
            await release.wait()
            return Response(status_code=204)

        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        in_flight = asyncio.create_task(request(host, "/hold"))
        await entered.wait()
        callbacks: list[str] = []

        def precheck() -> None:
            assert tracker.active == ["old"] and in_flight.done()
            callbacks.append("precheck")

        def replace() -> Replacement:
            assert not tracker.active
            callbacks.append("replace")
            return Replacement(fresh, lambda: old, lambda: callbacks.append("commit"))

        host.schedule(replace, before_stop=precheck)
        with pytest.raises(MaintenanceHostError) as captured:
            host.schedule(replace)
        assert captured.value.code == "MAINTENANCE_BUSY"
        busy = await request(host)
        assert busy[0]["status"] == 503
        assert (b"cache-control", b"no-store") in busy[0]["headers"]
        assert b"MAINTENANCE_BUSY" in busy[1]["body"]
        await asyncio.sleep(0)
        assert tracker.active == ["old"] and not callbacks
        release.set()
        assert (await in_flight)[0]["status"] == 204
        await maintenance_done(host)
        assert callbacks == ["precheck", "replace", "commit"]
        assert host.current is fresh and fresh.state.maintenance_host is host
        assert life.state == {"generation": "fresh"}
        assert not host.busy and host.last_error is None
        assert (await request(host))[1]["body"] == b'{"generation":"fresh"}'
        await life.stop()
        assert tracker.events == ["enter:old", "exit:old", "enter:fresh", "exit:fresh"]

    asyncio.run(scenario())


def test_schedule_from_request_returns_202_before_replacement() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        response_finished = False

        def replace() -> Replacement:
            assert response_finished and not tracker.active
            return Replacement(fresh, lambda: old)

        @old.post("/restore")
        async def restore() -> Response:
            host.schedule(replace)
            return Response(status_code=202)

        result = await request(host, "/restore", method="POST")
        response_finished = True
        assert result[0]["status"] == 202
        await maintenance_done(host)
        assert host.current is fresh
        await life.stop()

    asyncio.run(scenario())


def test_precheck_failure_retains_live_old_lifespan(capsys: Any) -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()

        def fail() -> None:
            raise RuntimeError("example-private-precheck-error")

        host.schedule(lambda: pytest.fail("replacement must not run"), before_stop=fail)
        await maintenance_done(host)
        assert host.last_error == "MAINTENANCE_PRECHECK_FAILED" and not host.busy
        assert host.current is old and tracker.events == ["enter:old"]
        assert (await request(host))[0]["status"] == 200
        await life.stop()

    asyncio.run(scenario())
    assert "example-private" not in capsys.readouterr().out


def test_drain_timeout_retains_old_context(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        entered, release = asyncio.Event(), asyncio.Event()

        @old.get("/hold")
        async def hold() -> Response:
            entered.set()
            await release.wait()
            return Response()

        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        pending = asyncio.create_task(request(host, "/hold"))
        await entered.wait()
        host.schedule(lambda: pytest.fail("replacement must not run"))
        await maintenance_done(host)
        assert host.last_error == "MAINTENANCE_DRAIN_TIMEOUT"
        assert not host.busy and tracker.events == ["enter:old"]
        release.set()
        await pending
        assert (await request(host))[0]["status"] == 200
        await life.stop()

    monkeypatch.setattr(module, "_DRAIN_SECONDS", 0.01)
    asyncio.run(scenario())


def test_replacement_failure_restarts_old_lifespan() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()

        def fail() -> Replacement:
            assert not tracker.active
            raise RuntimeError("example-private-replacement-error")

        host.schedule(fail)
        await maintenance_done(host)
        assert host.last_error == "MAINTENANCE_REPLACEMENT_FAILED"
        assert not host.busy and host.current is old
        assert tracker.events == ["enter:old", "exit:old", "enter:old"]
        await life.stop()

    asyncio.run(scenario())


def test_replacement_failure_rebuilds_terminal_resources_instead_of_reviving_old() -> None:
    async def scenario() -> None:
        closed = False
        entries = 0

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncIterator[None]:
            nonlocal closed, entries
            assert not closed, "terminally closed service cannot be revived"
            entries += 1
            try:
                yield
            finally:
                closed = True

        old = FastAPI(lifespan=lifespan)
        tracker = Tracker()
        rebuilt = tracker.application("rebuilt")
        loop_thread = threading.get_ident()
        rebuilt_count = 0

        def restart() -> FastAPI:
            nonlocal rebuilt_count
            assert threading.get_ident() != loop_thread and closed
            rebuilt_count += 1
            return rebuilt

        def fail() -> Replacement:
            raise RuntimeError("example-private-replacement-error")

        host = MaintenanceHost(old, restart_old=restart)
        life = Lifespan(host)
        await life.start()
        host.schedule(fail)
        await maintenance_done(host)
        assert entries == 1 and rebuilt_count == 1
        assert host.current is rebuilt and not host.busy
        assert host.last_error == "MAINTENANCE_REPLACEMENT_FAILED"
        assert (await request(host))[0]["status"] == 200
        await life.stop()
        assert tracker.events == ["enter:rebuilt", "exit:rebuilt"]

    asyncio.run(scenario())


@pytest.mark.parametrize("startup_fails", [False, True])
def test_restart_old_factory_failure_fails_closed(startup_fails: bool) -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")

        def fail() -> Replacement:
            raise RuntimeError("example-private-replacement-error")

        def restart() -> FastAPI:
            if not startup_fails:
                raise RuntimeError("example-private-rebuild-error")
            return tracker.application("rebuilt", start_fails=True)

        host = MaintenanceHost(old, restart_old=restart)
        life = Lifespan(host)
        await life.start()
        host.schedule(fail)
        await maintenance_done(host)
        assert host.busy and host.last_error == "MAINTENANCE_ROLLBACK_FAILED"
        assert not tracker.active
        assert (await request(host))[0]["status"] == 503
        await life.stop()

    asyncio.run(scenario())


def test_precheck_runs_off_loop_before_stopping_old_context() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        loop_thread = threading.get_ident()
        entered, release = threading.Event(), threading.Event()

        def precheck() -> None:
            assert threading.get_ident() != loop_thread
            assert tracker.active == ["old"]
            entered.set()
            assert release.wait(2)

        host.schedule(lambda: Replacement(fresh, lambda: old), before_stop=precheck)
        while not entered.is_set():
            await asyncio.sleep(0.001)
        assert (await asyncio.wait_for(request(host), 1))[0]["status"] == 503
        assert tracker.events == ["enter:old"]
        release.set()
        await maintenance_done(host)
        assert host.current is fresh
        await life.stop()

    asyncio.run(scenario())


def test_fresh_entry_failure_rolls_back_before_reentering() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        broken = tracker.application("fresh", start_fails=True)
        rollback_app = tracker.application("rollback")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        restored: list[str] = []

        def rollback() -> FastAPI:
            assert not tracker.active
            restored.append("old-state")
            return rollback_app

        host.schedule(
            lambda: Replacement(broken, rollback, lambda: pytest.fail("must not commit failed app"))
        )
        await maintenance_done(host)
        assert restored == ["old-state"]
        assert host.current is rollback_app and not host.busy
        assert host.last_error == "MAINTENANCE_FRESH_START_FAILED"
        assert tracker.active == ["rollback"]
        assert life.state == {"generation": "rollback"}
        await life.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("factory_fails", [False, True])
def test_rollback_failure_stays_busy_and_never_reports_health(factory_fails: bool) -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()

        def rollback() -> FastAPI:
            if factory_fails:
                raise RuntimeError("example-private-rollback-error")
            return tracker.application("rollback", start_fails=True)

        host.schedule(lambda: Replacement(tracker.application("fresh", start_fails=True), rollback))
        await maintenance_done(host)
        assert host.busy and host.last_error == "MAINTENANCE_ROLLBACK_FAILED"
        assert not tracker.active
        assert (await request(host))[0]["status"] == 503
        await life.stop()
        assert not tracker.active

    asyncio.run(scenario())


def test_commit_cleanup_failure_keeps_successful_fresh_app() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()

        def cleanup() -> None:
            assert tracker.active == ["fresh"]
            raise RuntimeError("example-private-cleanup-error")

        host.schedule(
            lambda: Replacement(
                fresh, lambda: pytest.fail("cleanup failure must not roll back"), cleanup
            )
        )
        await maintenance_done(host)
        assert host.last_error == "RESTORE_CLEANUP_FAILED"
        assert host.current is fresh and not host.busy
        assert (await request(host))[0]["status"] == 200
        await life.stop()

    asyncio.run(scenario())


def test_shutdown_waits_owned_writer_and_closes_only_current_context() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        entered, release = threading.Event(), threading.Event()

        def writer() -> Replacement:
            entered.set()
            assert release.wait(2)
            return Replacement(fresh, lambda: old)

        host.schedule(writer)
        while not entered.is_set():
            await asyncio.sleep(0.001)
        stopping = asyncio.create_task(life.stop())
        await asyncio.sleep(0.01)
        assert not stopping.done() and host.busy
        release.set()
        assert (await stopping)["type"] == "lifespan.shutdown.complete"
        assert tracker.events == ["enter:old", "exit:old", "enter:fresh", "exit:fresh"]
        assert host.busy and not tracker.active

    asyncio.run(scenario())


def test_shutdown_cancellation_does_not_abandon_sync_writer() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def writer() -> Replacement:
            entered.set()
            assert release.wait(2)
            finished.set()
            return Replacement(fresh, lambda: old)

        host.schedule(writer)
        while not entered.is_set():
            await asyncio.sleep(0.001)
        await life.incoming.put({"type": "lifespan.shutdown"})
        await asyncio.sleep(0.01)
        assert life.task is not None
        life.task.cancel()
        await asyncio.sleep(0.01)
        assert not life.task.done() and not finished.is_set()
        release.set()
        message = await asyncio.wait_for(life.outgoing.get(), 2)
        await life.task
        assert message["type"] == "lifespan.shutdown.complete"
        assert finished.is_set() and not tracker.active
        assert tracker.events == ["enter:old", "exit:old", "enter:fresh", "exit:fresh"]

    asyncio.run(scenario())


def test_stopping_old_context_failure_is_fail_closed() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        host = MaintenanceHost(tracker.application("old", stop_fails=True))
        life = Lifespan(host)
        await life.start()
        host.schedule(lambda: pytest.fail("must not replace after incomplete stop"))
        await maintenance_done(host)
        assert host.last_error == "MAINTENANCE_STOP_FAILED" and host.busy
        assert (await request(host))[0]["status"] == 503
        await life.stop()
        assert tracker.events == ["enter:old", "exit:old"]

    asyncio.run(scenario())


def test_cancelled_request_waits_for_owned_thread_writer_before_releasing_drain() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()

        def writer() -> None:
            entered.set()
            assert release.wait(2)
            completed.set()

        @old.get("/hold")
        async def hold() -> None:
            await asyncio.to_thread(writer)

        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        pending = asyncio.create_task(request(host, "/hold"))
        while not entered.is_set():
            await asyncio.sleep(0.001)
        pending.cancel()
        await asyncio.sleep(0.01)
        assert not pending.done() and not completed.is_set()
        host.schedule(lambda: Replacement(fresh, lambda: old))
        await asyncio.sleep(0.01)
        assert host.busy and host.current is old
        assert tracker.active == ["old"]
        assert (await request(host))[0]["status"] == 503
        assert host._active == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await maintenance_done(host)
        assert completed.is_set() and not host.busy and host.current is fresh
        await life.stop()

    asyncio.run(scenario())


def test_ordinary_shutdown_waits_for_cancelled_request_thread_writer() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old = tracker.application("old")
        entered, release, completed = threading.Event(), threading.Event(), threading.Event()

        def writer() -> None:
            entered.set()
            assert release.wait(2)
            completed.set()

        @old.get("/hold")
        async def hold() -> None:
            await asyncio.to_thread(writer)

        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        pending = asyncio.create_task(request(host, "/hold"))
        while not entered.is_set():
            await asyncio.sleep(0.001)
        pending.cancel()
        stopping = asyncio.create_task(life.stop())
        await asyncio.sleep(0.01)
        assert not pending.done() and not stopping.done() and not completed.is_set()
        assert tracker.events == ["enter:old"] and host.busy
        assert (await request(host))[0]["status"] == 503
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert (await stopping)["type"] == "lifespan.shutdown.complete"
        assert completed.is_set() and tracker.events == ["enter:old", "exit:old"]

    asyncio.run(scenario())


def test_invalid_replacement_fails_closed() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        host = MaintenanceHost(tracker.application("old"))
        life = Lifespan(host)
        await life.start()
        host.schedule(lambda: None)  # type: ignore[arg-type,return-value]
        await maintenance_done(host)
        assert host.busy and host.last_error == "MAINTENANCE_REPLACEMENT_INVALID"
        assert not tracker.active
        await life.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("extensions", [{}, {"websocket.http.response": {}}])
def test_busy_websocket_denied_without_dispatch(extensions: dict[str, Any]) -> None:
    async def scenario() -> None:
        host = MaintenanceHost(FastAPI())
        messages = await request(host, type="websocket", extensions=extensions)
        if extensions:
            assert messages[0]["type"] == "websocket.http.response.start"
            assert messages[0]["status"] == 503
            assert (b"cache-control", b"no-store") in messages[0]["headers"]
        else:
            assert messages == [{"type": "websocket.close", "code": 1013}]

    asyncio.run(scenario())


def test_inflight_websocket_also_drains() -> None:
    async def scenario() -> None:
        tracker = Tracker()
        old, fresh = tracker.application("old"), tracker.application("fresh")
        accepted, release = asyncio.Event(), asyncio.Event()

        @old.websocket("/socket")
        async def websocket(connection: WebSocket) -> None:
            await connection.accept()
            accepted.set()
            await release.wait()
            await connection.close()

        host = MaintenanceHost(old)
        life = Lifespan(host)
        await life.start()
        scope = {
            "type": "websocket",
            "path": "/socket",
            "scheme": "ws",
            "query_string": b"",
            "headers": [],
            "root_path": "",
            "subprotocols": [],
        }

        async def receive() -> dict[str, Any]:
            return {"type": "websocket.connect"}

        async def send(message: Any) -> None:
            pass

        pending = asyncio.create_task(host(scope, receive, send))
        await accepted.wait()
        host.schedule(lambda: Replacement(fresh, lambda: old))
        await asyncio.sleep(0)
        assert tracker.active == ["old"]
        release.set()
        await pending
        await maintenance_done(host)
        assert host.current is fresh
        await life.stop()

    asyncio.run(scenario())


def test_start_and_stop_errors_have_only_safe_lifespan_messages(capsys: Any) -> None:
    async def scenario() -> None:
        tracker = Tracker()
        start_host = MaintenanceHost(tracker.application("bad-start", start_fails=True))
        startup = await Lifespan(start_host).start()
        assert startup == {
            "type": "lifespan.startup.failed",
            "message": "application startup failed",
        }
        assert start_host.busy and not tracker.active
        host = MaintenanceHost(tracker.application("bad-stop", stop_fails=True))
        life = Lifespan(host)
        await life.start()
        shutdown = await life.stop()
        assert shutdown == {
            "type": "lifespan.shutdown.failed",
            "message": "application shutdown failed",
        }
        assert host.last_error == "MAINTENANCE_SHUTDOWN_FAILED"
        assert host.busy and not tracker.active

    asyncio.run(scenario())
    captured = capsys.readouterr()
    assert not captured.out and not captured.err
