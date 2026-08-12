"""Public setup-state HTTP contract for the Phase 1 RepoNPC application."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from reponpc.bundles.manager import BundleActivationError
from reponpc.chat.limits import ChatLimitError
from reponpc.chat.service import (
    ChatHistoryMessage,
    GroundedChatService,
    delivery_events,
)
from reponpc.i18n.catalog import SUPPORTED_LOCALES, translate
from reponpc.indexing.public_profile import (
    PublicProfileError,
    localized_public_profile_bytes,
    parse_public_profile_bytes,
    validate_public_profile_metadata,
)
from reponpc.observability import get_safe_logger
from reponpc.providers import ProviderError, ProviderFailureCode

DEFAULT_LOCALE = "zh-TW"
_PUBLIC_INDEX_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_PUBLIC_MODEL_PROVIDERS = frozenset({"ollama", "openai_compatible"})
_LOGGER = get_safe_logger(__name__)


class _DisconnectedResponse(Response):
    """Finish an already-disconnected ASGI request without writing a response."""

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        del scope, receive, send


def _public_index_version(value: str | None) -> str | None:
    if isinstance(value, str) and _PUBLIC_INDEX_VERSION_RE.fullmatch(value):
        return value
    return None


def _public_model_provider(value: str | None) -> str | None:
    if isinstance(value, str) and value in _PUBLIC_MODEL_PROVIDERS:
        return value
    return None


def _public_timestamp(value: str | None) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if parsed.tzinfo is not None else None


class StrictResponseModel(BaseModel):
    """Response model base that rejects accidental contract expansion."""

    model_config = ConfigDict(extra="forbid")


class IndexStatus(StrictResponseModel):
    ready: bool
    version: str | None
    last_checked_at: str | None
    update_error: str | None


class ModelStatus(StrictResponseModel):
    ready: bool
    provider: str | None
    last_checked_at: str | None


class PublicStatus(StrictResponseModel):
    status: Literal["ready", "setup_required", "degraded", "offline"]
    index: IndexStatus
    model: ModelStatus
    chat_available: bool


class ErrorDetail(StrictResponseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any]
    retry_after_seconds: int | None = None


class ErrorEnvelope(StrictResponseModel):
    error: ErrorDetail


class PublicChatHistory(StrictResponseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class PublicChatRequest(StrictResponseModel):
    message: str = Field(min_length=1, max_length=4000)
    locale: Literal["zh-TW", "en"]
    history: tuple[PublicChatHistory, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def validate_history(self) -> PublicChatRequest:
        if sum(len(item.content) for item in self.history) > 12000:
            raise ValueError("history is too large")
        for position, item in enumerate(self.history):
            expected = "user" if position % 2 == 0 else "assistant"
            if item.role != expected:
                raise ValueError("history roles must alternate starting with user")
        return self


@dataclass(frozen=True, slots=True)
class SetupState:
    """Immutable first-boot state before a validated bundle is active."""

    index_ready: bool = False
    index_version: str | None = None
    index_last_checked_at: str | None = None
    index_update_error: str | None = None
    model_ready: bool = False
    model_provider: str | None = None
    model_last_checked_at: str | None = None
    runtime_storage_usable: bool = True
    public_directory: Path | None = None

    @property
    def ready(self) -> bool:
        return self.index_ready and self.model_ready and self.runtime_storage_usable

    def public_status(self) -> PublicStatus:
        status: Literal["ready", "setup_required", "degraded", "offline"]
        if not self.index_ready:
            status = "setup_required"
        elif self.ready:
            status = "ready"
        else:
            status = "degraded"
        return PublicStatus(
            status=status,
            index=IndexStatus(
                ready=self.index_ready,
                version=_public_index_version(self.index_version),
                last_checked_at=_public_timestamp(self.index_last_checked_at),
                update_error=_public_index_version(self.index_update_error),
            ),
            model=ModelStatus(
                ready=self.model_ready,
                provider=_public_model_provider(self.model_provider),
                last_checked_at=_public_timestamp(self.model_last_checked_at),
            ),
            chat_available=self.ready,
        )


def request_id(request: Request) -> str:
    """Return the request identifier installed by the application middleware."""

    return str(request.state.request_id)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    """Build the stable safe error envelope without internal diagnostics."""

    body = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id(request),
            details=details or {},
            retry_after_seconds=retry_after_seconds,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def validated_locale(request: Request) -> str | JSONResponse:
    """Validate the public locale query before any bundle-dependent work."""

    locale = request.query_params.get("locale", DEFAULT_LOCALE)
    if locale in SUPPORTED_LOCALES:
        return locale
    return error_response(
        request,
        status_code=400,
        code="VALIDATION_ERROR",
        message=translate(
            DEFAULT_LOCALE,
            "validation_error",
            field="locale",
            reason="不支援的語系",
        ),
        details={"fields": [{"path": "locale", "code": "unsupported_locale"}]},
    )


def _validated_query(request: Request, allowed: set[str]) -> dict[str, str] | JSONResponse:
    items = list(request.query_params.multi_items())
    supplied_locale = next((value for key, value in items if key == "locale"), DEFAULT_LOCALE)
    error_locale = supplied_locale if supplied_locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    if any(key not in allowed for key, _ in items) or len({key for key, _ in items}) != len(items):
        return _validation_error(request, error_locale)
    values = dict(items)
    locale = validated_locale(request)
    if isinstance(locale, JSONResponse):
        return locale
    if "rev" in values and (not re.fullmatch(r"[1-9][0-9]{0,8}", values["rev"])):
        return _validation_error(request, error_locale)
    return values


def _validation_error(request: Request, locale: str = DEFAULT_LOCALE) -> JSONResponse:
    return error_response(
        request,
        status_code=400,
        code="VALIDATION_ERROR",
        message=translate(locale, "validation_error", field="query", reason="invalid"),
        details={"fields": [{"path": "query", "code": "invalid_query"}]},
    )


def create_public_router(
    state: SetupState,
    *,
    state_supplier: Callable[[], SetupState] | None = None,
    chat_service: GroundedChatService | None = None,
    chat_service_supplier: Callable[[], GroundedChatService | None] | None = None,
    max_message_characters: int = 2000,
    max_history_messages: int = 6,
    max_history_characters: int = 6000,
    chat_request_limits_supplier: Callable[[], tuple[int, int, int]] | None = None,
) -> APIRouter:
    """Create routes bound to one immutable setup/readiness snapshot."""

    router = APIRouter()
    current_state = state_supplier or (lambda: state)
    current_chat_service = chat_service_supplier or (lambda: chat_service)

    def public_directory() -> Path | None:
        directory = current_state().public_directory
        return directory if directory is not None and directory.is_dir() else None

    def unavailable(request: Request, locale: str) -> JSONResponse:
        return error_response(
            request,
            status_code=503,
            code="INDEX_UNAVAILABLE",
            message=translate(locale, "index_unavailable"),
        )

    def version() -> str:
        return _public_index_version(current_state().index_version) or "unversioned"

    @router.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "alive"}

    @router.get("/readyz")
    async def readyz(request: Request) -> JSONResponse:
        if current_state().ready:
            return JSONResponse(status_code=200, content={"status": "ready"})
        return error_response(
            request,
            status_code=503,
            code="SERVICE_NOT_READY",
            message=translate("en", "service_not_ready", service="RepoNPC"),
        )

    @router.get("/api/public/status", response_model=PublicStatus)
    async def status() -> PublicStatus:
        return current_state().public_status()

    @router.post("/api/public/chat/stream")
    async def chat_stream(request: Request, body: PublicChatRequest) -> Response:
        message_limit, history_count_limit, history_character_limit = (
            chat_request_limits_supplier()
            if chat_request_limits_supplier is not None
            else (max_message_characters, max_history_messages, max_history_characters)
        )
        if (
            len(body.message) > message_limit
            or len(body.history) > history_count_limit
            or sum(len(item.content) for item in body.history) > history_character_limit
        ):
            return error_response(
                request,
                status_code=413,
                code="PAYLOAD_TOO_LARGE",
                message=translate(
                    body.locale,
                    "validation_error",
                    field="request",
                    reason="too large",
                ),
            )
        current = current_state()
        service = current_chat_service()
        if not current.index_ready:
            return error_response(
                request,
                status_code=503,
                code="INDEX_UNAVAILABLE",
                message=translate(body.locale, "index_unavailable"),
            )
        if not current.model_ready or service is None:
            return error_response(
                request,
                status_code=503,
                code="MODEL_UNAVAILABLE",
                message=_public_chat_message(body.locale, "model_unavailable"),
            )
        client_ip = request.client.host if request.client is not None else "unknown"
        cancel_requested = threading.Event()
        try:
            import asyncio

            answer_task = asyncio.create_task(
                asyncio.to_thread(
                    service.answer,
                    message=body.message,
                    locale=body.locale,
                    history=tuple(
                        ChatHistoryMessage(item.role, item.content) for item in body.history
                    ),
                    client_ip=client_ip,
                    cancel_requested=cancel_requested,
                )
            )
            disconnect_task = asyncio.create_task(_wait_for_disconnect(request))
            done, _pending = await asyncio.wait(
                {answer_task, disconnect_task},
                timeout=getattr(service, "timeout_seconds", 45.0),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if disconnect_task in done and disconnect_task.result():
                cancel_requested.set()
                answer_task.cancel()
                return _DisconnectedResponse()
            disconnect_task.cancel()
            if answer_task not in done:
                cancel_requested.set()
                answer_task.cancel()
                raise TimeoutError
            delivery = answer_task.result()
        except TimeoutError:
            return error_response(
                request,
                status_code=504,
                code="PROVIDER_TIMEOUT",
                message=_public_chat_message(body.locale, "provider_timeout"),
            )
        except ChatLimitError as exc:
            return error_response(
                request,
                status_code=429,
                code=exc.code,
                message=_public_chat_message(body.locale, exc.code.casefold()),
                retry_after_seconds=exc.retry_after_seconds,
            )
        except BundleActivationError:
            return error_response(
                request,
                status_code=503,
                code="INDEX_UNAVAILABLE",
                message=translate(body.locale, "index_unavailable"),
            )
        except ProviderError as exc:
            status_code, code = _provider_public_error(exc.code)
            return error_response(
                request,
                status_code=status_code,
                code=code,
                message=_public_chat_message(body.locale, code.casefold()),
            )
        except Exception:
            return error_response(
                request,
                status_code=502,
                code="PROVIDER_ERROR",
                message=_public_chat_message(body.locale, "provider_error"),
            )

        async def stream() -> Any:
            correlation_id = request_id(request)
            terminal_emitted = False
            try:
                for event, payload in delivery_events(delivery, correlation_id):
                    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    yield f"event: {event}\ndata: {serialized}\n\n"
                    if event == "complete":
                        terminal_emitted = True
                        _LOGGER.emit(
                            logging.INFO,
                            "chat.stream.complete",
                            request_id=correlation_id,
                            route_template="/api/public/chat/stream",
                            status=200,
                            retrieval_count=delivery.evidence_count,
                        )
                        return
            except Exception:
                if not terminal_emitted:
                    error = ErrorEnvelope(
                        error=ErrorDetail(
                            code="PROVIDER_ERROR",
                            message=_public_chat_message(body.locale, "provider_error"),
                            request_id=correlation_id,
                            details={},
                        )
                    ).model_dump(mode="json")
                    serialized = json.dumps(error, ensure_ascii=False, separators=(",", ":"))
                    yield f"event: error\ndata: {serialized}\n\n"
                    _LOGGER.emit(
                        logging.ERROR,
                        "chat.stream.error",
                        request_id=correlation_id,
                        route_template="/api/public/chat/stream",
                        status=502,
                        error_category="internal",
                    )

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/api/public/profile")
    async def profile(request: Request) -> Response:
        query = _validated_query(request, {"locale"})
        if isinstance(query, JSONResponse):
            return query
        locale = query.get("locale", DEFAULT_LOCALE)
        directory = public_directory()
        if directory is None:
            return unavailable(request, locale)
        try:
            payload = parse_public_profile_bytes((directory / "profile.json").read_bytes())
            validate_public_profile_metadata(payload, index_version=version())
            body = localized_public_profile_bytes(payload, locale)
        except (OSError, PublicProfileError):
            return unavailable(request, locale)
        return Response(
            content=body,
            media_type="application/json",
            headers={"ETag": _etag(version(), f"profile:{locale}", body)},
        )

    @router.get("/api/public/character.png")
    async def character(request: Request) -> Response:
        query = _validated_query(request, {"rev"})
        if isinstance(query, JSONResponse):
            return query
        directory = public_directory()
        if directory is None:
            return unavailable(request, DEFAULT_LOCALE)
        return _asset_response(
            directory / "character.png", "image/png", version(), f"character:{query.get('rev', '')}"
        ) or unavailable(request, DEFAULT_LOCALE)

    @router.get("/api/public/card.{extension}")
    async def card(request: Request, extension: str) -> Response:
        query = _validated_query(request, {"locale", "theme", "rev"})
        if isinstance(query, JSONResponse):
            return query
        locale = query.get("locale", DEFAULT_LOCALE)
        theme = query.get("theme", "light")
        content_type = {"svg": "image/svg+xml", "gif": "image/gif", "png": "image/png"}.get(
            extension
        )
        if theme not in {"light", "dark"} or content_type is None:
            return _validation_error(request, locale)
        directory = public_directory()
        if directory is None:
            return unavailable(request, locale)
        return _asset_response(
            directory / f"card-{theme}-{locale}.{extension}",
            content_type,
            version(),
            f"card:{theme}:{locale}:{extension}:{query.get('rev', '')}",
        ) or unavailable(request, locale)

    return router


async def _wait_for_disconnect(request: Request) -> bool:
    import asyncio

    while not await request.is_disconnected():
        await asyncio.sleep(0.01)
    return True


def _provider_public_error(code: ProviderFailureCode) -> tuple[int, str]:
    if code is ProviderFailureCode.TIMEOUT:
        return 504, "PROVIDER_TIMEOUT"
    if code is ProviderFailureCode.UNAVAILABLE:
        return 503, "MODEL_UNAVAILABLE"
    return 502, "PROVIDER_ERROR"


def _public_chat_message(locale: str, code: str) -> str:
    messages = {
        "zh-TW": {
            "model_unavailable": "模型目前無法使用。",
            "provider_timeout": "模型回應逾時。",
            "provider_error": "模型服務暫時失敗。",
            "rate_limited": "請稍後再試。",
            "daily_budget_exhausted": "今日聊天額度已用完。",
            "concurrency_limit": "目前聊天使用量已滿。請稍後再試。",
        },
        "en": {
            "model_unavailable": "The model is currently unavailable.",
            "provider_timeout": "The model response timed out.",
            "provider_error": "The model service failed safely.",
            "rate_limited": "Please try again later.",
            "daily_budget_exhausted": "Today's chat budget is exhausted.",
            "concurrency_limit": "Chat capacity is currently full. Please try again later.",
        },
    }
    locale_messages = messages.get(locale, messages["en"])
    return locale_messages.get(code, locale_messages["provider_error"])


def _etag(version: str, variant: str, payload: bytes) -> str:
    return (
        '"'
        + hashlib.sha256(version.encode() + b"\0" + variant.encode() + b"\0" + payload).hexdigest()
        + '"'
    )


def _asset_response(path: Path, content_type: str, version: str, variant: str) -> Response | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None
    if not payload:
        return None
    headers = {"ETag": _etag(version, variant, payload)}
    if content_type == "image/svg+xml":
        svg_csp = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        headers.update(
            {
                "Content-Security-Policy": svg_csp,
                "X-Content-Type-Options": "nosniff",
            }
        )
    return Response(content=payload, media_type=content_type, headers=headers)
