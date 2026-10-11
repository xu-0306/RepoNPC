"""Own a single application lifespan while draining and replacing its runtime."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from starlette.types import Receive, Scope, Send

_DRAIN_SECONDS = 30.0


def _nothing() -> None:
    pass


@dataclass(frozen=True, slots=True)
class Replacement:
    application: FastAPI
    rollback: Callable[[], FastAPI]
    commit: Callable[[], None] = _nothing


class MaintenanceHostError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = (
            code
            if type(code) is str and code in {"MAINTENANCE_BUSY", "MAINTENANCE_NOT_STARTED"}
            else "MAINTENANCE_BUSY"
        )
        super().__init__("application maintenance is unavailable")


async def _finish_owned[Result](task: asyncio.Task[Result]) -> Result:
    # Caller cancellation must not abandon a synchronous database writer in to_thread.
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


class MaintenanceHost:
    """One server event loop owns this host and its single ASGI lifespan."""

    def __init__(
        self, application: FastAPI, *, restart_old: Callable[[], FastAPI] | None = None
    ) -> None:
        self._current = application
        self._restart_old = restart_old
        self._busy = True
        self._last_error: str | None = None
        self._active = 0
        self._drained = asyncio.Event()
        self._drained.set()
        self._context: AbstractAsyncContextManager[Any] | None = None
        self._maintenance: asyncio.Task[None] | None = None
        self._shutting_down = False
        self._started = False
        self._state: dict[str, Any] | None = None
        self._state_keys: set[str] = set()
        application.state.maintenance_host = self

    @property
    def current(self) -> FastAPI:
        return self._current

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def schedule(
        self,
        replacement: Callable[[], Replacement],
        *,
        before_stop: Callable[[], None] = _nothing,
    ) -> None:
        if self._context is None or self._shutting_down:
            raise MaintenanceHostError("MAINTENANCE_NOT_STARTED")
        if self._busy:
            raise MaintenanceHostError("MAINTENANCE_BUSY")
        loop = asyncio.get_running_loop()
        self._busy = True
        self._last_error = None
        self._maintenance = loop.create_task(self._replace(replacement, before_stop))

    async def _enter(self, application: FastAPI) -> None:
        application.state.maintenance_host = self
        context = application.router.lifespan_context(application)
        state = await context.__aenter__()
        if state is not None and (self._state is None or not isinstance(state, Mapping)):
            await context.__aexit__(None, None, None)
            raise RuntimeError("application lifespan state is unavailable")
        if self._state is not None:
            for key in self._state_keys:
                self._state.pop(key, None)
            self._state_keys.clear()
            if state is not None:
                self._state.update(state)
                self._state_keys.update(state)
        self._context = context
        self._current = application

    async def _exit(self) -> None:
        context, self._context = self._context, None
        if context is not None:
            await context.__aexit__(None, None, None)

    async def _sync[Result](self, callback: Callable[[], Result]) -> Result:
        task = asyncio.create_task(asyncio.to_thread(callback))
        return await _finish_owned(task)

    async def _replace(
        self, replacement: Callable[[], Replacement], before_stop: Callable[[], None]
    ) -> None:
        try:
            await asyncio.wait_for(self._drained.wait(), timeout=_DRAIN_SECONDS)
        except TimeoutError:
            self._last_error = "MAINTENANCE_DRAIN_TIMEOUT"
            self._busy = self._shutting_down
            return
        try:
            await self._sync(before_stop)
        except Exception:
            self._last_error = "MAINTENANCE_PRECHECK_FAILED"
            self._busy = self._shutting_down
            return
        old = self._current
        try:
            await self._exit()
        except Exception:
            self._last_error = "MAINTENANCE_STOP_FAILED"
            return
        try:
            candidate = await self._sync(replacement)
        except Exception:
            self._last_error = "MAINTENANCE_REPLACEMENT_FAILED"
            try:
                previous = await self._sync(self._restart_old) if self._restart_old else old
                await self._enter(previous)
            except Exception:
                self._last_error = "MAINTENANCE_ROLLBACK_FAILED"
                return
            self._busy = self._shutting_down
            return
        if (
            not isinstance(candidate, Replacement)
            or not isinstance(candidate.application, FastAPI)
            or not callable(candidate.rollback)
            or not callable(candidate.commit)
        ):
            self._last_error = "MAINTENANCE_REPLACEMENT_INVALID"
            return
        try:
            await self._enter(candidate.application)
        except Exception:
            self._last_error = "MAINTENANCE_FRESH_START_FAILED"
            try:
                previous = await self._sync(candidate.rollback)
                await self._enter(previous)
            except Exception:
                self._last_error = "MAINTENANCE_ROLLBACK_FAILED"
                return
        else:
            try:
                await self._sync(candidate.commit)
            except Exception:
                self._last_error = "RESTORE_CLEANUP_FAILED"
        self._busy = self._shutting_down

    async def _lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        if message["type"] != "lifespan.startup" or self._started:
            await send({"type": "lifespan.startup.failed", "message": "application startup failed"})
            return
        self._started = True
        self._state = scope.get("state")
        try:
            await self._enter(self._current)
        except Exception:
            self._last_error = "MAINTENANCE_START_FAILED"
            await send({"type": "lifespan.startup.failed", "message": "application startup failed"})
            return
        self._busy = False
        await send({"type": "lifespan.startup.complete"})
        try:
            await receive()
        finally:
            self._shutting_down = True
            self._busy = True
            if self._maintenance is not None:
                await _finish_owned(self._maintenance)
            await _finish_owned(asyncio.create_task(self._drained.wait()))
            try:
                await self._exit()
            except Exception:
                self._last_error = "MAINTENANCE_SHUTDOWN_FAILED"
                await send(
                    {"type": "lifespan.shutdown.failed", "message": "application shutdown failed"}
                )
            else:
                await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._lifespan(scope, receive, send)
            return
        if scope["type"] not in {"http", "websocket"}:
            raise RuntimeError("unsupported application scope")
        if self._busy:
            await self._unavailable(scope, send)
            return
        # No await between admission and increment: schedule cannot miss an admitted request.
        application = self._current
        self._active += 1
        self._drained.clear()
        delegated = asyncio.create_task(application(scope, receive, send))
        try:
            try:
                await asyncio.shield(delegated)
            except asyncio.CancelledError:
                try:
                    await _finish_owned(delegated)
                finally:
                    raise asyncio.CancelledError from None
        finally:
            self._active -= 1
            if self._active == 0:
                self._drained.set()

    @staticmethod
    async def _unavailable(scope: Scope, send: Send) -> None:
        websocket = scope["type"] == "websocket"
        if websocket and "websocket.http.response" not in scope.get("extensions", {}):
            await send({"type": "websocket.close", "code": 1013})
            return
        prefix = "websocket.http.response" if websocket else "http.response"
        body = b'{"error":{"code":"MAINTENANCE_BUSY","message":"Service temporarily unavailable."}}'
        if scope.get("method") == "HEAD":
            body = b""
        await send(
            {
                "type": prefix + ".start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": prefix + ".body", "body": body})
