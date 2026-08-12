"""Same-origin HTTP boundary for the single-owner admin session."""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from reponpc.admin.auth import SESSION_COOKIE, AdminAuthError, AdminSessionService
from reponpc.admin.github import GitHubAdminError
from reponpc.admin.operations import AdminOperations
from reponpc.api.public import error_response
from reponpc.cards.assets import CanonicalSprite, SpriteValidationError
from reponpc.cards.render import CardRenderError
from reponpc.config.models import ConfigValidationError


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_StrictRequest):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class LogoutAllRequest(_StrictRequest):
    password: str = Field(min_length=1, max_length=1024)


class ConfigContentRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=1024 * 1024)


class ConfigWriteRequest(ConfigContentRequest):
    expected_blob_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    commit_message: str = Field(default="Update RepoNPC configuration", max_length=120)


def create_admin_router(
    *,
    service_supplier: Callable[[], AdminSessionService | None],
    origins_supplier: Callable[[], tuple[str, ...]],
    operations_supplier: Callable[[], AdminOperations | None] = lambda: None,
) -> APIRouter:
    """Create auth routes whose production dependencies may attach after startup."""

    router = APIRouter(prefix="/api/admin")

    def service(request: Request) -> AdminSessionService | JSONResponse:
        configured = service_supplier()
        if configured is not None:
            return configured
        return error_response(
            request,
            status_code=503,
            code="SERVICE_NOT_READY",
            message="The admin service is not configured.",
        )

    def operations(request: Request) -> AdminOperations | JSONResponse:
        configured = operations_supplier()
        if configured is not None:
            return configured
        return error_response(
            request,
            status_code=503,
            code="SERVICE_NOT_READY",
            message="The admin operation is not configured.",
        )

    def same_origin(request: Request) -> JSONResponse | None:
        allowed = frozenset(_normalized_origin(value) for value in origins_supplier())
        candidate = request.headers.get("origin")
        if candidate is None:
            referer = request.headers.get("referer")
            candidate = _origin_from_referer(referer) if referer is not None else None
        if candidate is None or _normalized_origin(candidate) not in allowed:
            return error_response(
                request,
                status_code=403,
                code="CSRF_FAILED",
                message="The request origin could not be verified.",
            )
        return None

    def authorize(
        request: Request,
        configured: AdminSessionService,
        session_token: str | None,
        csrf_token: str | None,
    ) -> JSONResponse | None:
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        try:
            configured.authorize(
                session_token=session_token or "",
                csrf_token=csrf_token or "",
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        return None

    @router.post("/session")
    async def login(request: Request, body: LoginRequest) -> Response:
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        remote_identity = request.client.host if request.client is not None else "unknown"
        try:
            session = configured.login(
                username=body.username,
                password=body.password,
                remote_identity=remote_identity,
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        response = JSONResponse(
            {
                "csrf_token": session.csrf_token,
                "expires_at": session.expires_at,
                "absolute_expires_at": session.absolute_expires_at,
            }
        )
        _set_session_cookie(response, session.session_token)
        return response

    @router.post("/session/refresh")
    async def refresh(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        try:
            session = configured.refresh(
                session_token=session_token or "",
                csrf_token=csrf_token or "",
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        response = JSONResponse(
            {
                "csrf_token": session.csrf_token,
                "expires_at": session.expires_at,
                "absolute_expires_at": session.absolute_expires_at,
            }
        )
        _set_session_cookie(response, session.session_token)
        return response

    @router.delete("/session", status_code=204)
    async def logout(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        denied = authorize(request, configured, session_token, csrf_token)
        if denied is not None:
            return denied
        configured.logout(session_token=session_token or "", csrf_token=csrf_token or "")
        response = Response(status_code=204)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
        )
        return response

    @router.delete("/sessions", status_code=204)
    async def logout_all(
        request: Request,
        body: LogoutAllRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        denied = authorize(request, configured, session_token, csrf_token)
        if denied is not None:
            return denied
        try:
            configured.logout_all(
                session_token=session_token or "",
                csrf_token=csrf_token or "",
                password=body.password,
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        response = Response(status_code=204)
        response.delete_cookie(
            SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict"
        )
        return response

    def protected(
        request: Request, session_token: str | None, csrf_token: str | None = None
    ) -> tuple[AdminOperations, str] | JSONResponse:
        configured_service = service(request)
        configured_operations = operations(request)
        if isinstance(configured_service, JSONResponse):
            return configured_service
        if isinstance(configured_operations, JSONResponse):
            return configured_operations
        if csrf_token is None:
            try:
                authority = configured_service.authorize(session_token=session_token or "")
            except AdminAuthError as exc:
                return _auth_error(request, exc)
        else:
            denied = authorize(request, configured_service, session_token, csrf_token)
            if denied is not None:
                return denied
            authority = configured_service.authorize(session_token=session_token or "")
        return configured_operations, authority.session_hash

    @router.get("/config")
    async def read_config(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            result = configured.read_config()
        except GitHubAdminError as exc:
            return _github_error(request, exc)
        return JSONResponse(
            {
                "content": result.content.decode("utf-8"),
                "blob_sha": result.blob_sha,
                "commit_sha": result.commit_sha,
                "updated_at": result.updated_at,
            }
        )

    @router.post("/config/validate")
    async def validate_config(
        request: Request,
        body: ConfigContentRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            parsed = configured.validate_config(body.content.encode("utf-8"))
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        return JSONResponse(
            {"valid": True, "errors": [], "warnings": [], "parsed": parsed.model_dump(mode="json")}
        )

    @router.post("/config/preview")
    async def preview_config(
        request: Request,
        body: ConfigContentRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            preview = configured.preview_config(body.content.encode("utf-8"))
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except (SpriteValidationError, CardRenderError):
            return error_response(
                request,
                status_code=422,
                code="CONFIG_INVALID",
                message="Configuration preview failed.",
            )
        return JSONResponse(preview)

    @router.put("/config")
    async def write_config(
        request: Request,
        body: ConfigWriteRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, session_hash = boundary
        try:
            commit = configured.write_config(
                content=body.content.encode("utf-8"),
                expected_blob_sha=body.expected_blob_sha,
                commit_message=body.commit_message,
                request_id=str(request.state.request_id),
                session_hash=session_hash,
            )
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except GitHubAdminError as exc:
            return _github_error(request, exc)
        return JSONResponse(
            {"path": commit.path, "commit_sha": commit.commit_sha, "blob_sha": commit.blob_sha}
        )

    @router.post("/assets/character/validate")
    async def validate_asset(
        request: Request,
        file: Annotated[UploadFile, File()],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        content = await file.read(2 * 1024 * 1024 + 1)
        try:
            canonical = configured.validate_asset(filename=file.filename or "", content=content)
        except SpriteValidationError as exc:
            return _asset_error(request, exc)
        return JSONResponse(_asset_result(canonical))

    @router.put("/assets/character/{filename}")
    async def write_asset(
        request: Request,
        filename: str,
        file: Annotated[UploadFile, File()],
        expected_blob_sha: Annotated[str | None, Form()] = None,
        commit_message: Annotated[str, Form(max_length=120)] = "Update RepoNPC character",
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, session_hash = boundary
        content = await file.read(2 * 1024 * 1024 + 1)
        try:
            commit, canonical = configured.write_asset(
                filename=filename,
                content=content,
                expected_blob_sha=expected_blob_sha or None,
                commit_message=commit_message,
                request_id=str(request.state.request_id),
                session_hash=session_hash,
            )
        except SpriteValidationError as exc:
            return _asset_error(request, exc)
        except GitHubAdminError as exc:
            return _github_error(request, exc)
        return JSONResponse(
            {
                "commit": {
                    "path": commit.path,
                    "commit_sha": commit.commit_sha,
                    "blob_sha": commit.blob_sha,
                },
                "asset": _asset_result(canonical),
            }
        )

    @router.get("/readme-snippet")
    async def readme_snippet(
        request: Request,
        locale: Annotated[str, Query(pattern=r"^(zh-TW|en)$")],
        theme: Annotated[str, Query(pattern=r"^(light|dark)$")],
        extension: Annotated[str, Query(pattern=r"^(svg|gif|png)$")],
        revision: Annotated[int, Query(ge=0)],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            markdown = configured.readme_snippet(
                locale=locale, theme=theme, extension=extension, revision=revision
            )
        except CardRenderError:
            return error_response(
                request,
                status_code=400,
                code="VALIDATION_ERROR",
                message="README snippet parameters are invalid.",
            )
        payload = markdown.removeprefix("[![RepoNPC](")
        asset_url, target = payload.split(")](", 1)
        target_url = target.removesuffix(")")
        return JSONResponse(
            {"markdown": markdown, "asset_url": asset_url, "target_url": target_url}
        )

    @router.post("/index/dispatch")
    async def dispatch_index(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, session_hash = boundary
        try:
            configured.dispatch(request_id=str(request.state.request_id), session_hash=session_hash)
        except GitHubAdminError as exc:
            return _github_error(request, exc)
        return JSONResponse({"accepted": True}, status_code=202)

    @router.get("/index/status")
    async def index_status(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        return JSONResponse(configured.index_status())

    return router


def _auth_error(request: Request, error: AdminAuthError) -> JSONResponse:
    status = 403 if error.code == "CSRF_FAILED" else 401
    return error_response(
        request,
        status_code=status,
        code=error.code,
        message="Authentication failed.",
        retry_after_seconds=error.retry_after_seconds,
    )


def _config_error(request: Request, error: ConfigValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="CONFIG_INVALID",
        message="Configuration is invalid.",
        details={"fields": [issue.model_dump(mode="json") for issue in error.issues[:20]]},
    )


def _asset_error(request: Request, error: SpriteValidationError) -> JSONResponse:
    status = 413 if error.code == "FILE_TOO_LARGE" else 422
    return error_response(
        request,
        status_code=status,
        code="ASSET_INVALID",
        message="Character asset is invalid.",
        details={"reason": error.code},
    )


def _github_error(request: Request, error: GitHubAdminError) -> JSONResponse:
    statuses = {"CONFIG_CONFLICT": 409, "WRITE_NOT_ALLOWED": 403, "NOT_FOUND": 404}
    details = {"current_blob_sha": error.current_blob_sha} if error.current_blob_sha else {}
    return error_response(
        request,
        status_code=statuses.get(error.code, 502),
        code=error.code,
        message="GitHub operation failed.",
        details=details,
    )


def _asset_result(canonical: CanonicalSprite) -> dict[str, object]:
    return {
        "sha256": canonical.sha256,
        "width": canonical.width,
        "height": canonical.height,
        "png_base64": base64.b64encode(canonical.content).decode("ascii"),
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )


def _normalized_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"


def _origin_from_referer(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
