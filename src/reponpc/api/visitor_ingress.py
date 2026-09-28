"""Closed visitor ingress sharing the existing public serializers and grounded chat."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.datastructures import MutableHeaders
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from reponpc.api.public import (
    PublicChatRequest,
    SetupState,
    _DisconnectedResponse,
    _public_chat_message,
    _public_index_version,
    create_public_router,
    error_response,
    request_id,
)
from reponpc.bundles.manager import BundleActivationError
from reponpc.chat.limits import ChatLimitError
from reponpc.chat.service import ChatCancelledError, ChatHistoryMessage, delivery_events
from reponpc.domain.evidence import COMMIT_RE, EVIDENCE_ID_RE
from reponpc.providers import ProviderError, ProviderFailureCode

_BODY_BYTES = 65536
_CHAT_PATH = "/api/public/chat/stream"
_PUBLIC_READS = frozenset(
    {
        "/healthz",
        "/readyz",
        "/api/public/status",
        "/api/public/profile",
        "/api/public/faq",
        "/api/public/character.png",
        "/api/public/card.svg",
        "/api/public/card.gif",
        "/api/public/card.png",
    }
)


class VisitorChatWorkers:
    """Retain admissions until the synchronous worker actually exits, across restarts."""

    def __init__(self, capacity: int) -> None:
        if isinstance(capacity, bool) or capacity < 1:
            raise ValueError("visitor worker capacity must be positive")
        self._capacity = capacity
        self._lock = threading.Lock()
        self._active: set[threading.Event] = set()

    def reserve(self) -> threading.Event | None:
        with self._lock:
            if len(self._active) >= self._capacity:
                return None
            cancelled = threading.Event()
            self._active.add(cancelled)
            return cancelled

    def release(self, cancelled: threading.Event) -> None:
        with self._lock:
            self._active.discard(cancelled)

    def cancel_all(self) -> None:
        with self._lock:
            for cancelled in self._active:
                cancelled.set()

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)


class _VisitorStream(StreamingResponse):
    cancelled: threading.Event

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.cancelled.set()


def _regular_build_file(root: Path, name: str) -> Path:
    if (
        not name
        or any(ord(char) < 33 or ord(char) == 127 for char in name)
        or any(char in name for char in "\\%?#:")
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError("invalid visitor build")
    candidate = root.joinpath(*PurePosixPath(name).parts)
    if root.is_symlink() or any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise ValueError("invalid visitor build")
    candidate.resolve().relative_to(root.resolve())
    if not candidate.is_file():
        raise ValueError("invalid visitor build")
    return candidate


def _visitor_files(root: Path | None) -> dict[str, Path]:
    if root is None:
        return {}
    try:
        manifest_path = _regular_build_file(root, ".vite/manifest.json")
        if manifest_path.stat().st_size > 1024 * 1024:
            return {}
        manifest = json.loads(manifest_path.read_bytes())
        if not isinstance(manifest, dict) or len(manifest) > 1024:
            return {}
        entry = manifest.get("index.html")
        if not isinstance(entry, dict) or entry.get("isEntry") is not True:
            return {}
        files = {"/": _regular_build_file(root, "index.html")}
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visited:
                return
            visited.add(key)
            item = manifest[key]
            if not isinstance(item, dict) or item.get("isDynamicEntry") is True:
                raise ValueError("invalid visitor build")
            name = item.get("file")
            if not isinstance(name, str) or name == ".vite/manifest.json":
                raise ValueError("invalid visitor build")
            files["/" + name] = _regular_build_file(root, name)
            for field in ("css", "assets"):
                values = item.get(field, [])
                if not isinstance(values, list) or len(values) > 1024:
                    raise ValueError("invalid visitor build")
                for name in values:
                    if not isinstance(name, str) or name == ".vite/manifest.json":
                        raise ValueError("invalid visitor build")
                    files["/" + name] = _regular_build_file(root, name)
            imports = item.get("imports", [])
            if not isinstance(imports, list) or len(imports) > 1024:
                raise ValueError("invalid visitor build")
            for dependency in imports:
                if not isinstance(dependency, str):
                    raise ValueError("invalid visitor build")
                visit(dependency)

        visit("index.html")
        return files
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {}


def _owner_statement(path: str) -> bool:
    parts = path.split("/")
    return (
        len(parts) == 6
        and parts[:4] == ["", "api", "public", "owner-statements"]
        and COMMIT_RE.fullmatch(parts[4]) is not None
        and EVIDENCE_ID_RE.fullmatch(parts[5]) is not None
    )


def _message(locale: str, code: str) -> str:
    if code in {"RATE_LIMITED", "DAILY_BUDGET_EXHAUSTED", "CONCURRENCY_LIMIT"}:
        return _public_chat_message(locale, code.casefold())
    copy = {
        "SERVICE_NOT_READY": (
            "服務目前休息中。請稍後再試。",
            "The service is resting. Please try later.",
        ),
        "REQUEST_TIMEOUT": ("請求逾時。請稍後再試。", "The request timed out. Please try later."),
        "REQUEST_FAILED": (
            "請求暫時無法完成。請稍後再試。",
            "The request could not be completed. Please try later.",
        ),
        "VALIDATION_ERROR": ("請求格式不正確。", "The request is invalid."),
        "PAYLOAD_TOO_LARGE": ("請求內容過大。", "The request is too large."),
        "GATEWAY_IDENTITY_INVALID": (
            "無法驗證請求來源。",
            "The request source could not be verified.",
        ),
    }
    return copy[code][0 if locale == "zh-TW" else 1]


class _VisitorBoundary:
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings_supplier: Callable[[], Mapping[str, Any]],
        paths: frozenset[str],
        gateway_port: int,
    ) -> None:
        self._app = app
        self._settings = settings_supplier
        self._paths = paths
        self._port = gateway_port

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        scope.setdefault("state", {})["gateway_started_at"] = time.monotonic()
        request = Request(scope, receive)
        headers = request.headers
        path = scope["path"]
        raw = scope.get("raw_path", path.encode("utf-8"))
        try:
            settings = self._settings()
        except Exception:
            response = error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message=_message("en", "SERVICE_NOT_READY"),
            )
            if scope["method"] == "HEAD":
                response.body = b""
            await response(scope, receive, send)
            return
        origin = settings.get("gateway_origin")
        hosts = headers.getlist("host")
        allowed_hosts = {f"127.0.0.1:{self._port}"}
        if isinstance(origin, str):
            allowed_hosts.add(urlsplit(origin).netloc.casefold())
        public_read = path in _PUBLIC_READS or _owner_statement(path)
        public_api = (public_read and path.startswith("/api/public/")) or path == _CHAT_PATH
        allowed_methods = {"GET", "HEAD"} if public_read or path in self._paths else set()
        if path == _CHAT_PATH:
            allowed_methods = {"POST"}
        if public_api:
            allowed_methods.add("OPTIONS")
        if (
            raw != path.encode("utf-8")
            or b"%" in raw
            or "\\" in path
            or any(part in {".", ".."} for part in path.split("/"))
            or "//" in path
            or len(hosts) != 1
            or hosts[0].casefold() not in allowed_hosts
            or any(name in headers for name in ("cookie", "authorization", "x-csrf-token"))
            or scope["method"] not in allowed_methods
        ):
            await Response(status_code=404)(scope, receive, send)
            return
        origins = headers.getlist("origin")
        cors = public_api and len(origins) == 1 and origins[0] == settings.get("pages_origin")
        started = False

        async def safe_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message["headers"] = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() not in {b"set-cookie", b"access-control-allow-credentials"}
                ]
                response_headers = MutableHeaders(scope=message)
                if public_api:
                    response_headers.add_vary_header("Origin")
                if cors:
                    response_headers["Access-Control-Allow-Origin"] = origins[0]
            if scope["method"] == "HEAD" and message["type"] == "http.response.body":
                message = {**message, "body": b""}
            await send(message)

        if not settings.get("enabled") or not settings.get("listener_ready"):
            await error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message=_message("en", "SERVICE_NOT_READY"),
            )(scope, receive, safe_send)
            return
        if scope["method"] == "OPTIONS":
            requested = headers.getlist("access-control-request-method")
            requested_headers = headers.getlist("access-control-request-headers")
            valid_headers = len(requested_headers) <= 1 and (
                not requested_headers or requested_headers[0].strip().casefold() == "content-type"
            )
            if (
                not cors
                or len(requested) != 1
                or requested[0] not in allowed_methods - {"OPTIONS"}
                or not valid_headers
            ):
                await Response(status_code=404)(scope, receive, send)
                return
            await Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": origins[0],
                    "Vary": "Origin",
                    "Access-Control-Allow-Methods": requested[0],
                    "Access-Control-Allow-Headers": "Content-Type",
                },
            )(scope, receive, send)
            return

        try:
            await self._app(scope, receive, safe_send)
        except Exception:
            if started:
                raise
            await error_response(
                request,
                status_code=502,
                code="REQUEST_FAILED",
                message=_message("en", "REQUEST_FAILED"),
            )(scope, receive, safe_send)


def create_visitor_gateway_app(
    *,
    state_supplier: Callable[[], SetupState],
    bundle_manager_supplier: Callable[[], Any],
    chat_service_supplier: Callable[[], Any],
    faq_supplier: Callable[[], Any],
    settings_supplier: Callable[[], Mapping[str, Any]],
    web_dist: Path | None,
    gateway_port: int,
    admin_origins: tuple[str, ...],
    trusted_proxy_cidrs: tuple[str, ...],
    max_message_characters: int,
    max_history_messages: int,
    max_history_characters: int,
    global_concurrency: int,
    keepalive_seconds: float,
    workers: VisitorChatWorkers | None = None,
) -> FastAPI:
    """Build a closed subapp; no private routes, SPA mount or second service lifespan."""
    from reponpc.main import PublicBoundaryMiddleware

    del admin_origins  # The owner configuration boundary validates hostname separation.
    if keepalive_seconds <= 0:
        raise ValueError("visitor keepalive must be positive")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)
    active_workers = workers or VisitorChatWorkers(global_concurrency)
    app.state.visitor_workers = active_workers
    networks = tuple(ipaddress.ip_network(value) for value in trusted_proxy_cidrs)
    files = _visitor_files(web_dist)
    router = create_public_router(
        state_supplier(),
        state_supplier=state_supplier,
        bundle_manager_supplier=bundle_manager_supplier,
        faq_supplier=faq_supplier,
    )
    router.routes = [
        route
        for route in router.routes
        if getattr(route, "path", None) not in {_CHAT_PATH, "/api/public/status"}
    ]
    app.include_router(router)
    for route in list(router.routes):
        if isinstance(route, APIRoute) and "GET" in (route.methods or set()):
            app.add_api_route(
                route.path, route.endpoint, methods=["HEAD"], response_model=route.response_model
            )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _error: RequestValidationError) -> Response:
        return error_response(
            request,
            status_code=400,
            code="VALIDATION_ERROR",
            message=_message("en", "VALIDATION_ERROR"),
        )

    @app.api_route("/api/public/status", methods=["GET", "HEAD"])
    async def status() -> dict[str, Any]:
        current = state_supplier()
        return {
            "status": "ready" if current.ready else "resting",
            "chat_available": current.ready,
            "index": {
                "ready": current.index_ready,
                "version": _public_index_version(current.index_version),
            },
        }

    def bind_file(file: Path) -> Callable[[], Response]:
        # Bind without a query parameter that could override the selected file.
        def serve() -> Response:
            try:
                assert web_dist is not None
                checked = _regular_build_file(web_dist, file.relative_to(web_dist).as_posix())
            except (OSError, ValueError):
                return Response(status_code=404)
            return FileResponse(checked)

        return serve

    for path, file in files.items():
        app.add_api_route(path, bind_file(file), methods=["GET", "HEAD"], response_model=None)

    def public_identity(request: Request) -> str | None:
        if not networks:
            return None
        addresses = request.headers.getlist("x-forwarded-for")
        try:
            peer = ipaddress.ip_address(request.client.host if request.client else "")
            if len(addresses) != 1 or "%" in addresses[0]:
                raise ValueError
            identity = ipaddress.ip_address(addresses[0])
            if not any(peer in network for network in networks):
                raise ValueError
            return str(identity)
        except ValueError:
            raise ChatLimitError("GATEWAY_IDENTITY_INVALID") from None

    @app.post(_CHAT_PATH)
    async def chat(request: Request) -> Response:
        service = chat_service_supplier()
        deadline = request.state.gateway_started_at + getattr(service, "timeout_seconds", 45.0)
        try:
            identity = public_identity(request)
        except ChatLimitError:
            return error_response(
                request,
                status_code=400,
                code="GATEWAY_IDENTITY_INVALID",
                message=_message("en", "GATEWAY_IDENTITY_INVALID"),
            )
        try:
            payload = bytearray()
            async with asyncio.timeout_at(deadline):
                async for chunk in request.stream():
                    if len(payload) + len(chunk) > _BODY_BYTES:
                        return error_response(
                            request,
                            status_code=413,
                            code="PAYLOAD_TOO_LARGE",
                            message=_message("en", "PAYLOAD_TOO_LARGE"),
                        )
                    payload.extend(chunk)
            body = PublicChatRequest.model_validate_json(payload)
        except TimeoutError:
            return error_response(
                request,
                status_code=504,
                code="REQUEST_TIMEOUT",
                message=_message("en", "REQUEST_TIMEOUT"),
            )
        except ClientDisconnect:
            return _DisconnectedResponse()
        except (ValidationError, ValueError):
            return error_response(
                request,
                status_code=400,
                code="VALIDATION_ERROR",
                message=_message("en", "VALIDATION_ERROR"),
            )
        if (
            len(body.message) > max_message_characters
            or len(body.history) > max_history_messages
            or sum(len(item.content) for item in body.history) > max_history_characters
        ):
            return error_response(
                request,
                status_code=413,
                code="PAYLOAD_TOO_LARGE",
                message=_message(body.locale, "PAYLOAD_TOO_LARGE"),
            )
        current = settings_supplier()
        if (
            not current.get("enabled")
            or not current.get("listener_ready")
            or not state_supplier().ready
            or service is None
        ):
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message=_message(body.locale, "SERVICE_NOT_READY"),
            )
        if time.monotonic() >= deadline:
            return error_response(
                request,
                status_code=504,
                code="REQUEST_TIMEOUT",
                message=_message(body.locale, "REQUEST_TIMEOUT"),
            )
        cancelled = active_workers.reserve()
        if cancelled is None:
            return error_response(
                request,
                status_code=429,
                code="CONCURRENCY_LIMIT",
                message=_message(body.locale, "CONCURRENCY_LIMIT"),
                retry_after_seconds=1,
            )

        def answer() -> Any:
            try:
                return service.answer(
                    message=body.message,
                    locale=body.locale,
                    history=tuple(
                        ChatHistoryMessage(item.role, item.content) for item in body.history
                    ),
                    client_ip=identity,
                    cancel_requested=cancelled,
                    timeout_seconds=deadline - time.monotonic(),
                    allow_retry=False,
                )
            finally:
                active_workers.release(cancelled)

        task = asyncio.create_task(asyncio.to_thread(answer))
        task.add_done_callback(
            lambda finished: None if finished.cancelled() else finished.exception()
        )

        async def stream():
            next_heartbeat = time.monotonic() + keepalive_seconds
            try:
                yield ": connected\n\n"
                while not task.done():
                    if await request.is_disconnected():
                        return
                    if cancelled.is_set():
                        raise ChatCancelledError("visitor work cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    await asyncio.wait(
                        {task},
                        timeout=min(0.05, remaining, max(0, next_heartbeat - time.monotonic())),
                    )
                    if time.monotonic() >= next_heartbeat and not task.done():
                        yield ": keepalive\n\n"
                        next_heartbeat = time.monotonic() + keepalive_seconds
                if time.monotonic() >= deadline:
                    raise TimeoutError
                for event, event_payload in delivery_events(task.result(), request_id(request)):
                    if cancelled.is_set():
                        raise ChatCancelledError("visitor work cancelled")
                    if event == "complete":
                        event_payload = {
                            **event_payload,
                            "usage": None,
                            "finish_reason": event_payload["finish_reason"]
                            if event_payload["finish_reason"]
                            in {"stop", "length", "insufficient_context"}
                            else "stop",
                        }
                    serialized = json.dumps(
                        event_payload, ensure_ascii=False, separators=(",", ":")
                    )
                    yield f"event: {event}\ndata: {serialized}\n\n"
            except (Exception, asyncio.CancelledError) as exc:
                if isinstance(exc, asyncio.CancelledError):
                    raise
                if isinstance(exc, ChatLimitError) and exc.code in {
                    "RATE_LIMITED",
                    "DAILY_BUDGET_EXHAUSTED",
                    "CONCURRENCY_LIMIT",
                }:
                    code = exc.code
                    retry = exc.retry_after_seconds
                else:
                    retry = None
                    if isinstance(exc, TimeoutError) or (
                        isinstance(exc, ProviderError) and exc.code is ProviderFailureCode.TIMEOUT
                    ):
                        code = "REQUEST_TIMEOUT"
                    elif isinstance(exc, (BundleActivationError, ChatCancelledError)) or (
                        isinstance(exc, ProviderError)
                        and exc.code is ProviderFailureCode.UNAVAILABLE
                    ):
                        code = "SERVICE_NOT_READY"
                    else:
                        code = "REQUEST_FAILED"
                envelope = json.loads(
                    error_response(
                        request,
                        status_code=200,
                        code=code,
                        message=_message(body.locale, code),
                        retry_after_seconds=retry,
                    ).body
                )
                serialized = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
                yield f"event: error\ndata: {serialized}\n\n"
            finally:
                cancelled.set()

        response = _VisitorStream(
            stream(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
        )
        response.cancelled = cancelled
        return response

    app.add_middleware(
        _VisitorBoundary,
        settings_supplier=settings_supplier,
        paths=frozenset(files),
        gateway_port=gateway_port,
    )
    app.add_middleware(PublicBoundaryMiddleware)
    return app
