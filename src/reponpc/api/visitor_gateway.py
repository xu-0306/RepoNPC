"""Owner-controlled lifecycle for the loopback-only visitor listener."""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn

from reponpc.api.visitor_ingress import VisitorChatWorkers, create_visitor_gateway_app
from reponpc.config.environment import EnvironmentSettings, _canonical_origin
from reponpc.runtime.database import RuntimeDatabase
from reponpc.runtime.visitor_gateway import (
    VisitorGatewaySettings,
    VisitorGatewayStore,
    VisitorGatewayStoreError,
)


class VisitorGatewayError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("visitor gateway operation failed")


class _LoopbackServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        # The private listener shares the primary server's process and signals.
        yield


class VisitorGateway:
    """Persist owner intent while keeping listener and verification facts live."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        environment: EnvironmentSettings,
        state_supplier: Callable[[], Any],
        bundle_manager_supplier: Callable[[], Any],
        chat_service_supplier: Callable[[], Any],
        faq_supplier: Callable[[], Any],
        web_dist: Path,
    ) -> None:
        self._store = VisitorGatewayStore(database)
        self._environment = environment
        self._state_supplier = state_supplier
        self._bundles = bundle_manager_supplier
        self._chat = chat_service_supplier
        self._faq = faq_supplier
        self._web_dist = web_dist
        self.workers = VisitorChatWorkers(environment.global_chat_concurrency)
        self._server: _LoopbackServer | None = None
        self._server_task: asyncio.Task[None] | None = None
        self._socket: socket.socket | None = None
        self._accepting = False
        self._starting = False
        self._error_code: str | None = None
        self._start_generation = 0
        self._verified_generation: int | None = None
        self._verified_bundle: str | None = None
        self._observed_ready: bool | None = None
        self._observed_bundle: str | None = None
        self._observation_epoch = 0
        self._operation_lock = asyncio.Lock()

    def snapshot(self) -> dict[str, Any]:
        local_ready, bundle_id = self._read_local_state()
        listener_ready = self._listener_ready()
        self._observe(local_ready, bundle_id, listener_ready)
        try:
            settings = self._store.get()
        except Exception:
            self._accepting = False
            self._error_code = "GATEWAY_UNAVAILABLE"
            return {
                "revision": 1,
                "gateway_origin": None,
                "pages_origin": None,
                "enabled": False,
                "listener_ready": False,
                "error_code": self._error_code,
                "local_ready": local_ready,
                "entry_configured": False,
                "external_verified": False,
                "verified_at": None,
                "verification_method": None,
                "active_bundle_id": bundle_id,
                "client_identity_mode": (
                    "trusted_proxy"
                    if self._environment.visitor_trusted_proxy_cidrs
                    else "aggregate"
                ),
            }
        matching_report = (
            settings.verification_gateway_origin == settings.gateway_origin
            and settings.verification_pages_origin == settings.pages_origin
            and settings.verification_bundle_id == bundle_id
            and settings.verification_method == "owner_reported"
            and settings.verified_at is not None
        )
        external_verified = bool(
            matching_report
            and settings.enabled
            and listener_ready
            and local_ready
            and self._verified_generation == self._start_generation
            and self._verified_bundle == bundle_id
        )
        return {
            "revision": settings.revision,
            "gateway_origin": settings.gateway_origin,
            "pages_origin": settings.pages_origin,
            "enabled": settings.enabled,
            "listener_ready": listener_ready,
            "error_code": self._error_code,
            "local_ready": local_ready,
            "entry_configured": bool(
                settings.gateway_origin and settings.pages_origin and listener_ready
            ),
            "external_verified": external_verified,
            "verified_at": settings.verified_at,
            "verification_method": settings.verification_method,
            "active_bundle_id": bundle_id,
            "client_identity_mode": (
                "trusted_proxy" if self._environment.visitor_trusted_proxy_cidrs else "aggregate"
            ),
        }

    def observe_state(self) -> None:
        """Invalidate an owner report when a primary readiness poll sees a change."""

        local_ready, bundle_id = self._read_local_state()
        self._observe(local_ready, bundle_id, self._listener_ready())

    async def resume(self) -> dict[str, Any]:
        """Resume only persisted owner intent after the primary lifespan is ready."""

        async with self._operation_lock:
            try:
                settings = self._store.get()
                if not settings.enabled:
                    return self.snapshot()
                self._validate_configuration(settings.gateway_origin, settings.pages_origin)
                await self._listen(settings)
            except (VisitorGatewayError, VisitorGatewayStoreError):
                self._error_code = "GATEWAY_UNAVAILABLE"
            return self.snapshot()

    async def configure(
        self, *, revision: int, gateway_origin: str | None, pages_origin: str | None
    ) -> dict[str, Any]:
        async with self._operation_lock:
            return await self._configure(
                revision=revision,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
            )

    async def _configure(
        self, *, revision: int, gateway_origin: str | None, pages_origin: str | None
    ) -> dict[str, Any]:
        settings = self._store.get()
        self._expect_revision(settings, revision)
        if self._listener_ready() or self._starting:
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        if gateway_origin is None and pages_origin is None:
            pass
        elif gateway_origin is None or pages_origin is None:
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        else:
            normalized_gateway, normalized_pages = self._validate_configuration(
                gateway_origin, pages_origin
            )
            if normalized_gateway != gateway_origin or normalized_pages != pages_origin:
                raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        try:
            self._store.configure(
                revision=revision,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
            )
        except VisitorGatewayStoreError as exc:
            raise VisitorGatewayError(exc.code) from None
        self._invalidate_verification()
        self._error_code = None
        return self.snapshot()

    async def start(self, *, revision: int) -> dict[str, Any]:
        async with self._operation_lock:
            return await self._start(revision=revision)

    async def _start(self, *, revision: int) -> dict[str, Any]:
        settings = self._store.get()
        self._expect_revision(settings, revision)
        self._validate_configuration(settings.gateway_origin, settings.pages_origin)
        if self._listener_ready() and self._started_origins() == (
            settings.gateway_origin,
            settings.pages_origin,
        ):
            return self.snapshot()
        if self._starting:
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
        try:
            settings = self._store.set_enabled(revision=revision, enabled=True)
        except VisitorGatewayStoreError as exc:
            raise VisitorGatewayError(exc.code) from None
        self._invalidate_verification()
        try:
            await self._listen(settings)
        except VisitorGatewayError:
            raise
        return self.snapshot()

    async def stop(self, *, revision: int) -> dict[str, Any]:
        async with self._operation_lock:
            return await self._stop(revision=revision)

    async def _stop(self, *, revision: int) -> dict[str, Any]:
        settings = self._store.get()
        self._expect_revision(settings, revision)
        try:
            self._store.set_enabled(revision=revision, enabled=False)
        except VisitorGatewayStoreError as exc:
            raise VisitorGatewayError(exc.code) from None
        self._invalidate_verification()
        stopped = await self._stop_listener()
        if not stopped:
            self._error_code = "GATEWAY_UNAVAILABLE"
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
        self._error_code = None
        return self.snapshot()

    async def verify(
        self,
        *,
        revision: int,
        gateway_origin: str,
        pages_origin: str,
        bundle_id: str,
        external_checks_confirmed: bool,
    ) -> dict[str, Any]:
        async with self._operation_lock:
            return await self._verify(
                revision=revision,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
                bundle_id=bundle_id,
                external_checks_confirmed=external_checks_confirmed,
            )

    async def _verify(
        self,
        *,
        revision: int,
        gateway_origin: str,
        pages_origin: str,
        bundle_id: str,
        external_checks_confirmed: bool,
    ) -> dict[str, Any]:
        settings_before = self._store.get()
        self._expect_revision(settings_before, revision)
        current = self.snapshot()
        if (
            external_checks_confirmed is not True
            or not current["enabled"]
            or not current["listener_ready"]
            or not current["local_ready"]
            or not bundle_id
            or bundle_id != current["active_bundle_id"]
            or gateway_origin != current["gateway_origin"]
            or pages_origin != current["pages_origin"]
        ):
            raise VisitorGatewayError("GATEWAY_VERIFICATION_STALE")
        observation_epoch = self._observation_epoch
        timestamp = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            settings = self._store.verify(
                revision=revision,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
                bundle_id=bundle_id,
                verified_at=timestamp,
            )
        except VisitorGatewayStoreError as exc:
            raise VisitorGatewayError(exc.code) from None
        self.observe_state()
        if observation_epoch != self._observation_epoch:
            self._invalidate_verification()
            raise VisitorGatewayError("GATEWAY_VERIFICATION_STALE")
        self._verified_generation = self._start_generation
        self._verified_bundle = settings.verification_bundle_id
        return self.snapshot()

    async def shutdown(self) -> None:
        async with self._operation_lock:
            self._invalidate_verification()
            await self._stop_listener()

    async def _listen(self, settings: VisitorGatewaySettings) -> None:
        self._starting = True
        listener: socket.socket | None = None
        server: _LoopbackServer | None = None
        task: asyncio.Task[None] | None = None
        try:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            exclusive_address = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if exclusive_address is None:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            else:
                listener.setsockopt(socket.SOL_SOCKET, exclusive_address, 1)
            listener.bind(("127.0.0.1", self._environment.visitor_gateway_port))
            listener.listen(socket.SOMAXCONN)
            listener.setblocking(False)
            listener.set_inheritable(False)
            app = create_visitor_gateway_app(
                state_supplier=self._state_supplier,
                bundle_manager_supplier=self._bundles,
                chat_service_supplier=self._chat,
                faq_supplier=self._faq,
                settings_supplier=self.snapshot,
                web_dist=self._web_dist,
                gateway_port=self._environment.visitor_gateway_port,
                admin_origins=self._environment.admin_origins,
                trusted_proxy_cidrs=self._environment.visitor_trusted_proxy_cidrs,
                max_message_characters=self._environment.max_message_characters,
                max_history_messages=self._environment.max_history_messages,
                max_history_characters=self._environment.max_history_characters,
                global_concurrency=self._environment.global_chat_concurrency,
                keepalive_seconds=self._environment.sse_keepalive_seconds,
                workers=self.workers,
            )
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self._environment.visitor_gateway_port,
                lifespan="off",
                proxy_headers=False,
                log_config=None,
                access_log=False,
                timeout_graceful_shutdown=self._environment.shutdown_grace_seconds,
            )
            server = _LoopbackServer(config)
            self._server = server
            self._socket = listener
            self._server_task = task = asyncio.create_task(server.serve(sockets=[listener]))
            deadline = time.monotonic() + 5.0
            while not server.started and not task.done() and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            if not server.started:
                raise VisitorGatewayError("GATEWAY_UNAVAILABLE")
            self._server = server
            self._socket = listener
            self._server_task = task
            self._accepting = True
            self._error_code = None
            self._start_generation += 1
            self._started_gateway_origin = settings.gateway_origin
            self._started_pages_origin = settings.pages_origin
        except VisitorGatewayError:
            self._error_code = "GATEWAY_UNAVAILABLE"
            await self._cleanup_start_failure(server, task, listener)
            raise
        except (OSError, RuntimeError, SystemExit):
            self._error_code = "GATEWAY_UNAVAILABLE"
            await self._cleanup_start_failure(server, task, listener)
            raise VisitorGatewayError("GATEWAY_UNAVAILABLE") from None
        finally:
            self._starting = False

    async def _cleanup_start_failure(
        self,
        server: _LoopbackServer | None,
        task: asyncio.Task[None] | None,
        listener: socket.socket | None,
    ) -> None:
        self._accepting = False
        if server is not None:
            server.should_exit = True
            server.force_exit = True
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception, SystemExit):
                await task
        if listener is not None:
            with suppress(OSError):
                listener.close()
        self._server = None
        self._server_task = None
        self._socket = None

    async def _stop_listener(self) -> bool:
        self._accepting = False
        self.workers.cancel_all()
        deadline = time.monotonic() + self._environment.shutdown_grace_seconds
        server, task, listener = self._server, self._server_task, self._socket
        if server is None and task is None:
            if listener is not None:
                with suppress(OSError):
                    listener.close()
            self._socket = None
            return True
        if server is not None:
            server.should_exit = True
        stopped = True
        listener_servers = tuple(getattr(server, "servers", ())) if server is not None else ()
        for listener_server in listener_servers:
            listener_server.close()
        if listener_servers:
            with suppress(Exception):
                await asyncio.wait_for(
                    asyncio.gather(*(item.wait_closed() for item in listener_servers)),
                    timeout=max(0.0, min(0.5, deadline - time.monotonic())),
                )
        if task is not None:
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=max(0.0, deadline - time.monotonic()),
                )
            except TimeoutError:
                stopped = False
                if server is not None:
                    server.force_exit = True
                task.cancel()
                with suppress(asyncio.CancelledError, Exception, SystemExit, TimeoutError):
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        timeout=max(0.0, deadline - time.monotonic()),
                    )
            except (Exception, SystemExit):
                stopped = False
        if listener is not None:
            with suppress(OSError):
                listener.close()
        self._server = None
        self._server_task = None
        self._socket = None
        self._started_gateway_origin = None
        self._started_pages_origin = None
        return stopped

    def _listener_ready(self) -> bool:
        task = self._server_task
        server = self._server
        if task is not None and task.done() and self._accepting:
            self._accepting = False
            self._error_code = "GATEWAY_UNAVAILABLE"
            self._invalidate_verification()
        return bool(
            self._accepting
            and server is not None
            and server.started
            and task is not None
            and not task.done()
        )

    def _read_local_state(self) -> tuple[bool, str | None]:
        state = self._state_supplier()
        bundle_manager = self._bundles()
        if bundle_manager is not None:
            try:
                bundle_id = bundle_manager.status().active_bundle_id
            except Exception:
                return False, None
            if not bundle_id:
                return False, None
            return bool(getattr(state, "ready", False)), str(bundle_id)
        bundle_id = getattr(state, "index_version", None)
        return bool(getattr(state, "ready", False)), bundle_id

    def _observe(self, local_ready: bool, bundle_id: str | None, listener_ready: bool) -> None:
        invalidating_observation = (
            not local_ready
            or not listener_ready
            or (self._observed_ready is False and local_ready)
            or (self._observed_bundle is not None and bundle_id != self._observed_bundle)
        )
        if invalidating_observation:
            self._observation_epoch += 1
        if self._verified_generation is not None and invalidating_observation:
            self._invalidate_verification()
        self._observed_ready = local_ready
        self._observed_bundle = bundle_id

    def _invalidate_verification(self) -> None:
        self._verified_generation = None
        self._verified_bundle = None

    def _started_origins(self) -> tuple[str | None, str | None]:
        return (
            getattr(self, "_started_gateway_origin", None),
            getattr(self, "_started_pages_origin", None),
        )

    def _validate_configuration(
        self, gateway_origin: str | None, pages_origin: str | None
    ) -> tuple[str, str]:
        if (
            self._environment.deployment_profile != "production"
            or not self._environment.admin_origins_explicit
            or gateway_origin is None
            or pages_origin is None
        ):
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        gateway = _https_origin(gateway_origin)
        pages = _pages_origin(pages_origin)
        if gateway is None or pages is None:
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        admin_hosts = {_host(origin) for origin in self._environment.admin_origins}
        if (
            _host(gateway) == _host(pages)
            or _host(gateway) in admin_hosts
            or _host(pages) in admin_hosts
        ):
            raise VisitorGatewayError("GATEWAY_CONFIGURATION_INVALID")
        return gateway, pages

    @staticmethod
    def _expect_revision(settings: VisitorGatewaySettings, revision: int) -> None:
        if settings.revision != revision:
            raise VisitorGatewayError("GATEWAY_CONFLICT")


def _host(origin: str) -> str:
    return (urlsplit(origin).hostname or "").casefold()


def _https_origin(value: str) -> str | None:
    parsed = _strict_url_origin(value)
    return parsed if parsed is not None and parsed.startswith("https://") else None


def _pages_origin(value: str) -> str | None:
    try:
        if urlsplit(value).port is not None:
            return None
    except (TypeError, ValueError):
        return None
    parsed = _strict_url_origin(value)
    if parsed is None or not parsed.startswith("https://"):
        return None
    host = urlsplit(parsed).hostname or ""
    labels = host.split(".")
    if (
        len(labels) != 3
        or labels[1:] != ["github", "io"]
        or not labels[0]
        or len(labels[0]) > 63
        or labels[0][0] == "-"
        or labels[0][-1] == "-"
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in labels[0])
    ):
        return None
    return parsed


def _strict_url_origin(value: str) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    origin = _canonical_origin(value)
    return origin if origin is not None and origin.startswith("https://") else None
