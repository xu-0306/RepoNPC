"""Public setup-state HTTP contract for the Phase 1 RepoNPC application."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from reponpc.i18n.catalog import SUPPORTED_LOCALES, translate

DEFAULT_LOCALE = "zh-TW"
_PUBLIC_INDEX_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_PUBLIC_MODEL_PROVIDERS = frozenset({"ollama", "openai_compatible"})


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
) -> APIRouter:
    """Create routes bound to one immutable setup/readiness snapshot."""

    router = APIRouter()
    current_state = state_supplier or (lambda: state)

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
            payload = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return unavailable(request, locale)
        if not isinstance(payload, dict):
            return unavailable(request, locale)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
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
