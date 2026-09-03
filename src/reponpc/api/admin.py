"""Same-origin HTTP boundary for the single-owner admin session."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Callable
from contextlib import suppress
from threading import Event
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, File, Form, Header, Path, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from reponpc.admin.auth import (
    MAX_ADMIN_PASSWORD_LENGTH,
    MIN_ADMIN_PASSWORD_LENGTH,
    SESSION_COOKIE,
    AdminAuthError,
    AdminSession,
    AdminSessionService,
)
from reponpc.admin.batch_resolver import (
    BatchPreflightPlan,
    RateBudget,
    RepositorySelection,
    normalize_repository_slug,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchSnapshot
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    embedding_model_catalog,
)
from reponpc.admin.github import GitHubAdminError
from reponpc.admin.model_operations import OllamaModelOperation
from reponpc.admin.oauth import GitHubIdentityService, GitHubOAuthError
from reponpc.admin.onboarding import (
    GuidedOnboardingError,
    GuidedProfileDraft,
    GuidedRepositoryDraft,
)
from reponpc.admin.operations import AdminOperations
from reponpc.api.public import error_response
from reponpc.cards.assets import CanonicalSprite, SpriteValidationError
from reponpc.cards.render import CardRenderError
from reponpc.config.models import ConfigValidationError, PublicConfig

OAUTH_TRANSACTION_COOKIE_TTL_SECONDS = 10 * 60
GITHUB_OAUTH_SETUP_DOCUMENTATION_URL = (
    "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app"
)
GITHUB_OAUTH_CALLBACK_PATH = "/api/admin/github/callback"


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_StrictRequest):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class SetupRequest(_StrictRequest):
    setup_code: str = Field(min_length=1, max_length=256)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(
        min_length=MIN_ADMIN_PASSWORD_LENGTH,
        max_length=MAX_ADMIN_PASSWORD_LENGTH,
    )
    password_confirmation: str = Field(
        min_length=MIN_ADMIN_PASSWORD_LENGTH,
        max_length=MAX_ADMIN_PASSWORD_LENGTH,
    )


class LogoutAllRequest(_StrictRequest):
    # A GitHub-only owner has no local password.  Its fresh GitHub session is
    # the second factor for this operation; local-password owners still must
    # supply their current password.
    password: str | None = Field(default=None, min_length=1, max_length=1024)


class GitHubPatRequest(_StrictRequest):
    token: str = Field(min_length=1, max_length=1024)


class EmbeddingProfileRequest(_StrictRequest):
    provider: Literal["ollama", "openai_compatible", "vllm"]
    model_id: str = Field(min_length=1, max_length=256)
    dimension: int = Field(ge=1, le=65536)
    normalized: bool = True
    query_prefix: str = Field(default="query: ", max_length=128)
    passage_prefix: str = Field(default="passage: ", max_length=128)
    connection_reference: str = Field(
        default="environment", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
    )

    def profile_input(self) -> EmbeddingProfileInput:
        return EmbeddingProfileInput(**self.model_dump())


class ConfirmedModelActionRequest(_StrictRequest):
    profile_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    confirmed: Literal[True]


class ConfigContentRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=1024 * 1024)


class ConfigWriteRequest(ConfigContentRequest):
    expected_blob_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    commit_message: str = Field(default="Update RepoNPC configuration", max_length=120)


class RepositoryDiscoverRequest(_StrictRequest):
    account: str = Field(min_length=1, max_length=200)
    page: int = Field(default=1, ge=1, le=5)


class RepositoryResolveRequest(_StrictRequest):
    repository: str = Field(min_length=1, max_length=300)
    ref: str | None = Field(default=None, min_length=1, max_length=255)


class RepositoryAnalyzeRequest(_StrictRequest):
    slug: str = Field(min_length=3, max_length=201)
    ref: str | None = Field(default=None, min_length=1, max_length=255)
    include: tuple[str, ...] = Field(default=(), max_length=100)
    exclude: tuple[str, ...] = Field(default=(), max_length=100)


class AnalysisBatchSelectionRequest(_StrictRequest):
    slug: str = Field(min_length=3, max_length=201)
    ref: str | None = Field(default=None, min_length=1, max_length=255)
    include: tuple[str, ...] = Field(default=(), max_length=100)
    exclude: tuple[str, ...] = Field(default=(), max_length=100)
    confirmed: Literal[True]

    def selection(self) -> RepositorySelection:
        try:
            return RepositorySelection(
                slug=normalize_repository_slug(self.slug),
                ref=self.ref,
                include=self.include,
                exclude=self.exclude,
                confirmed=self.confirmed,
            )
        except ValueError as exc:
            raise ValueError("invalid repository selection") from exc


class AnalysisBatchPreflightRequest(_StrictRequest):
    selections: tuple[AnalysisBatchSelectionRequest, ...] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_repositories(self) -> AnalysisBatchPreflightRequest:
        try:
            slugs = [selection.selection().slug.casefold() for selection in self.selections]
        except ValueError as exc:
            raise ValueError("invalid repository selection") from exc
        if len(slugs) != len(set(slugs)):
            raise ValueError("repository selections must be unique")
        return self

    def resolved_selections(self) -> tuple[RepositorySelection, ...]:
        return tuple(selection.selection() for selection in self.selections)


class AnalysisBatchCreateRequest(AnalysisBatchPreflightRequest):
    plan_id: str = Field(min_length=16, max_length=256)
    idempotency_key: str = Field(min_length=16, max_length=512)


class ContributionSuggestRequest(_StrictRequest):
    slug: str = Field(min_length=3, max_length=201)
    owner_statement: str = Field(min_length=1, max_length=4000)


class OnboardingDraftRequest(_StrictRequest):
    profile: GuidedProfileDraft
    repositories: tuple[GuidedRepositoryDraft, ...] = Field(min_length=1, max_length=50)
    base_config: PublicConfig | None = None
    confirmed_assertions: Literal[True]


def create_admin_router(
    *,
    service_supplier: Callable[[], AdminSessionService | None],
    origins_supplier: Callable[[], tuple[str, ...]],
    operations_supplier: Callable[[], AdminOperations | None] = lambda: None,
    github_identity_supplier: Callable[[], GitHubIdentityService | None] = lambda: None,
    github_oauth_callback_supplier: Callable[[], str | None] = lambda: None,
) -> APIRouter:
    """Create auth routes whose production dependencies may attach after startup."""

    router = APIRouter(prefix="/api/admin")
    oauth_cookie = "__Secure-reponpc_oauth_transaction"
    oauth_handoff_cookie = "__Secure-reponpc_oauth_handoff"

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

    def github_identity(request: Request) -> GitHubIdentityService | JSONResponse:
        configured = github_identity_supplier()
        if configured is not None:
            return configured
        return error_response(
            request,
            status_code=503,
            code="GITHUB_LOGIN_UNAVAILABLE",
            message="GitHub sign-in is not configured.",
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

    @router.get("/setup")
    async def setup_status(request: Request) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        status = configured.setup_status()
        return JSONResponse(
            {
                "setup_required": status.setup_required,
                "setup_code_available": status.setup_code_available,
            }
        )

    @router.post("/setup")
    async def setup_owner(request: Request, body: SetupRequest) -> Response:
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        try:
            session = configured.setup_owner(
                setup_code=body.setup_code,
                username=body.username,
                password=body.password,
                password_confirmation=body.password_confirmation,
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        response = JSONResponse(_session_body(session))
        _set_session_cookie(response, session.session_token)
        return response

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
        response = JSONResponse(_session_body(session))
        _set_session_cookie(response, session.session_token)
        return response

    @router.get("/auth/methods")
    async def auth_methods(request: Request) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        github_service = github_identity_supplier()
        status = configured.auth_methods(
            github_configured=(github_service is not None and github_service.oauth_available)
        )
        return JSONResponse(
            {
                "password": {"available": status.password_available},
                "github": {"available": status.github_available},
                "setup_required": status.setup_required,
            }
        )

    @router.get("/embedding-profiles")
    async def list_embedding_profiles(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profiles = await asyncio.to_thread(configured.list_embedding_profiles)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(
            {"profiles": [_embedding_profile_payload(profile) for profile in profiles]}
        )

    @router.get("/embedding-models/catalog")
    async def list_embedding_model_catalog(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        return _embedding_profile_response({"models": embedding_model_catalog()})

    @router.get("/embedding-models/installed")
    async def list_installed_embedding_models(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            models = await asyncio.to_thread(configured.installed_ollama_embedding_models)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response({"provider": "ollama", "models": models})

    @router.post("/embedding-profiles")
    async def create_embedding_profile(
        request: Request,
        body: EmbeddingProfileRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(
                configured.create_embedding_profile, body.profile_input()
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile), status_code=201)

    @router.get("/embedding-profiles/{profile_id}")
    async def get_embedding_profile(
        request: Request,
        profile_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(configured.get_embedding_profile, profile_id)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile))

    @router.put("/embedding-profiles/{profile_id}")
    async def update_embedding_profile(
        request: Request,
        body: EmbeddingProfileRequest,
        profile_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(
                configured.update_embedding_profile, profile_id, body.profile_input()
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile))

    @router.delete("/embedding-profiles/{profile_id}")
    async def delete_embedding_profile(
        request: Request,
        profile_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            await asyncio.to_thread(configured.delete_embedding_profile, profile_id)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return Response(status_code=204)

    @router.post("/embedding-profiles/{profile_id}/probe")
    async def probe_embedding_profile(
        request: Request,
        profile_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(configured.probe_embedding_profile, profile_id)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile))

    @router.post("/embedding-profiles/{profile_id}/activate")
    async def activate_embedding_profile(
        request: Request,
        profile_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(configured.activate_embedding_profile, profile_id)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile))

    @router.post("/embedding-models/ollama/pull")
    async def pull_ollama_embedding_model(
        request: Request,
        body: ConfirmedModelActionRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            operation = await asyncio.to_thread(
                configured.start_ollama_embedding_model_pull,
                body.profile_id,
                confirmed=body.confirmed,
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        if operation is None:
            profile = await asyncio.to_thread(configured.get_embedding_profile, body.profile_id)
            return _embedding_profile_response(_embedding_profile_payload(profile))
        return JSONResponse(
            _ollama_model_operation_payload(operation),
            status_code=202,
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/embedding-model-operations/{operation_id}")
    async def get_ollama_embedding_model_operation(
        request: Request,
        operation_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            operation = await asyncio.to_thread(
                configured.get_ollama_embedding_model_operation, operation_id
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_ollama_model_operation_payload(operation))

    @router.delete("/embedding-model-operations/{operation_id}")
    async def cancel_ollama_embedding_model_operation(
        request: Request,
        operation_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            operation = await asyncio.to_thread(
                configured.cancel_ollama_embedding_model_operation, operation_id
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_ollama_model_operation_payload(operation))

    @router.delete("/embedding-models/ollama/{model_id}")
    async def delete_ollama_embedding_model(
        request: Request,
        body: ConfirmedModelActionRequest,
        model_id: str = Path(min_length=1, max_length=256),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            profile = await asyncio.to_thread(configured.get_embedding_profile, body.profile_id)
            if profile.model_id != model_id:
                raise EmbeddingProfileError("VALIDATION_ERROR")
            profile = await asyncio.to_thread(
                configured.ollama_embedding_model_action,
                body.profile_id,
                action="delete",
                confirmed=body.confirmed,
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(_embedding_profile_payload(profile))

    @router.get("/github/oauth/setup-guide")
    async def github_oauth_setup_guide(request: Request) -> Response:
        callback_url = _setup_guide_callback_url(
            github_oauth_callback_supplier(), origins_supplier()
        )
        if callback_url is None:
            response = error_response(
                request,
                status_code=503,
                code="GITHUB_SETUP_GUIDE_UNAVAILABLE",
                message="GitHub OAuth setup guidance is unavailable.",
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        github_service = github_identity_supplier()
        response = JSONResponse(
            {
                "configured": bool(github_service is not None and github_service.oauth_available),
                "callback_url": callback_url,
                "documentation_url": GITHUB_OAUTH_SETUP_DOCUMENTATION_URL,
                "next_step": (
                    "continue_with_github"
                    if github_service is not None and github_service.oauth_available
                    else "configure_host_secrets_restart_then_recheck"
                ),
            },
            headers={"Cache-Control": "no-store"},
        )
        return response

    @router.post("/session/github/start")
    async def start_github_login(request: Request) -> Response:
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        try:
            started = identity.start(intent="login")
        except GitHubOAuthError as exc:
            return _oauth_error(request, exc)
        return _oauth_redirect(started.authorization_url, started.state, oauth_cookie)

    @router.post("/setup/github/start")
    async def reject_legacy_github_setup(request: Request) -> Response:
        """Preserve the legacy route without creating GitHub-only ownership."""

        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        status = configured.setup_status()
        code = "SETUP_DENIED" if status.setup_required else "SETUP_ALREADY_COMPLETE"
        return error_response(
            request,
            status_code=403 if status.setup_required else 409,
            code=code,
            message="GitHub-only owner setup is not available.",
        )

    @router.post("/identity/github/link/start")
    async def start_github_link(
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
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        try:
            started = identity.start(intent="link", session_token=session_token)
        except (AdminAuthError, GitHubOAuthError) as exc:
            return _oauth_or_auth_error(request, exc)
        if "application/json" in request.headers.get("accept", ""):
            response = JSONResponse({"authorization_url": started.authorization_url})
            _set_oauth_transaction_cookie(response, started.state, oauth_cookie)
            return response
        return _oauth_redirect(started.authorization_url, started.state, oauth_cookie)

    @router.get("/github/callback")
    async def github_callback(
        request: Request,
        state: Annotated[str | None, Query(max_length=512)] = None,
        code: Annotated[str | None, Query(max_length=2048)] = None,
        error: Annotated[str | None, Query(max_length=128)] = None,
    ) -> Response:
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return _oauth_callback_failure("GITHUB_LOGIN_UNAVAILABLE", oauth_cookie)
        if error is not None or code is None:
            return _oauth_callback_failure("OAUTH_AUTHORIZATION_DENIED", oauth_cookie)
        try:
            completion = identity.complete(
                state=state or "",
                cookie_state=request.cookies.get(oauth_cookie, ""),
                code=code,
            )
        except AdminAuthError as exc:
            callback_code = (
                "INVALID_CREDENTIALS"
                if exc.code == "INVALID_CREDENTIALS"
                else "OAUTH_AUTHORIZATION_DENIED"
            )
            return _oauth_callback_failure(callback_code, oauth_cookie)
        except GitHubOAuthError:
            return _oauth_callback_failure("OAUTH_AUTHORIZATION_DENIED", oauth_cookie)
        response = RedirectResponse("/admin?github_oauth=success", status_code=303)
        response.delete_cookie(oauth_cookie, path="/api/admin/github", secure=True, httponly=True)
        if completion.session is not None and completion.handoff is not None:
            _set_session_cookie(response, completion.session.session_token)
            response.set_cookie(
                oauth_handoff_cookie,
                completion.handoff,
                max_age=120,
                secure=True,
                httponly=True,
                samesite="strict",
                path="/api/admin/session/github/result",
            )
        return response

    @router.get("/session/github/result")
    async def github_oauth_result(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        try:
            csrf_token = identity.consume_handoff(
                handoff=request.cookies.get(oauth_handoff_cookie, ""),
                session_token=session_token or "",
            )
        except GitHubOAuthError as exc:
            return _oauth_error(request, exc)
        response = JSONResponse({"csrf_token": csrf_token})
        response.delete_cookie(
            oauth_handoff_cookie,
            path="/api/admin/session/github/result",
            secure=True,
            httponly=True,
            samesite="strict",
        )
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
        response = JSONResponse(_session_body(session))
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

    def authenticated_session(
        request: Request,
        session_token: str | None,
        csrf_token: str | None = None,
    ) -> tuple[AdminSessionService, str] | JSONResponse:
        configured_service = service(request)
        if isinstance(configured_service, JSONResponse):
            return configured_service
        if csrf_token is not None:
            denied = authorize(request, configured_service, session_token, csrf_token)
            if denied is not None:
                return denied
        else:
            try:
                authority = configured_service.authorize(session_token=session_token or "")
            except AdminAuthError as exc:
                return _auth_error(request, exc)
            return configured_service, authority.session_hash
        try:
            authority = configured_service.authorize(session_token=session_token or "")
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        return configured_service, authority.session_hash

    @router.get("/github/connections")
    async def github_connections(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        return JSONResponse({"connections": identity.connections()})

    @router.put("/github/connections/pat")
    async def save_github_pat(
        request: Request,
        body: GitHubPatRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        try:
            result = identity.save_pat(body.token)
        except GitHubOAuthError as exc:
            return _oauth_error(request, exc)
        return JSONResponse(result, status_code=201)

    @router.post("/github/connections/{credential_id}/check")
    async def check_github_connection(
        request: Request,
        credential_id: Annotated[int, Path(ge=1)],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        try:
            result = identity.check_credential(credential_id)
        except GitHubOAuthError as exc:
            return _oauth_error(request, exc)
        return JSONResponse(result)

    @router.delete("/github/connections/{credential_id}", status_code=204)
    async def delete_github_connection(
        request: Request,
        credential_id: Annotated[int, Path(ge=1)],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        identity = github_identity(request)
        if isinstance(identity, JSONResponse):
            return identity
        identity.delete_credential(credential_id)
        return Response(status_code=204)

    @router.delete("/identity/github", status_code=204)
    async def unlink_github_identity(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            configured.unlink_github(session_token=session_token or "")
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        return Response(status_code=204)

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
        except GitHubAdminError as exc:
            return _github_error(request, exc)
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

    @router.post("/onboarding/repositories/discover")
    async def discover_repositories(
        request: Request,
        body: RepositoryDiscoverRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            result = await asyncio.to_thread(
                configured.discover_repositories,
                account=body.account,
                page=body.page,
            )
        except GuidedOnboardingError as exc:
            return _onboarding_error(request, exc)
        return JSONResponse(result)

    @router.post("/onboarding/repositories/resolve")
    async def resolve_repository(
        request: Request,
        body: RepositoryResolveRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            result = await asyncio.to_thread(
                configured.resolve_repository,
                repository=body.repository,
                ref=body.ref,
            )
        except GuidedOnboardingError as exc:
            return _onboarding_error(request, exc)
        return JSONResponse(result)

    @router.post("/onboarding/repositories/analyze")
    async def analyze_repository(
        request: Request,
        body: RepositoryAnalyzeRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, session_hash = boundary
        cancelled = Event()
        task = asyncio.create_task(
            asyncio.to_thread(
                configured.analyze_repository,
                session_hash=session_hash,
                slug=body.slug,
                ref=body.ref,
                include=body.include,
                exclude=body.exclude,
                cancel_requested=cancelled,
            )
        )
        try:
            while not task.done():
                done, _pending = await asyncio.wait({task}, timeout=0.1)
                if done:
                    break
                if await request.is_disconnected():
                    cancelled.set()
                    with suppress(Exception):
                        await task
                    return Response(status_code=499)
            result = await task
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        except GuidedOnboardingError as exc:
            return _onboarding_error(request, exc)
        return JSONResponse(result)

    @router.post("/onboarding/analysis-batches/preflight")
    async def preflight_analysis_batch(
        request: Request,
        body: AnalysisBatchPreflightRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            plan = await asyncio.to_thread(
                configured.preflight_analysis_batch,
                selections=body.resolved_selections(),
            )
        except (BatchRuntimeError, ValueError) as exc:
            return _batch_error(request, exc)
        return _batch_response(_preflight_payload(plan))

    @router.post("/onboarding/analysis-batches")
    async def create_analysis_batch(
        request: Request,
        body: AnalysisBatchCreateRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            snapshot, created = await asyncio.to_thread(
                configured.create_analysis_batch,
                plan_id=body.plan_id,
                selections=body.resolved_selections(),
                idempotency_key=body.idempotency_key,
            )
        except (BatchRuntimeError, ValueError) as exc:
            return _batch_error(request, exc)
        return _batch_response({"batch": _batch_snapshot_payload(snapshot), "created": created})

    @router.get("/onboarding/analysis-batches/active")
    async def active_analysis_batch(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            snapshot = await asyncio.to_thread(configured.active_analysis_batch)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response(_batch_snapshot_payload(snapshot))

    @router.get("/onboarding/analysis-batches/{batch_id}")
    async def get_analysis_batch(
        request: Request,
        batch_id: str = Path(min_length=1, max_length=64),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            snapshot = await asyncio.to_thread(configured.analysis_batch, batch_id=batch_id)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response(_batch_snapshot_payload(snapshot))

    @router.get("/onboarding/analysis-batches/{batch_id}/events")
    async def stream_analysis_batch_events(
        request: Request,
        batch_id: str = Path(min_length=1, max_length=64),
        last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    ) -> Response:
        boundary = protected(request, request.cookies.get(SESSION_COOKIE))
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        try:
            cursor = _last_event_id(last_event_id)
        except ValueError:
            return _batch_error(request, BatchRuntimeError("VALIDATION_ERROR"))
        configured, _session_hash = boundary
        try:
            await asyncio.to_thread(configured.analysis_batch, batch_id=batch_id)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)

        async def events():
            event_cursor = cursor
            while not await request.is_disconnected():
                try:
                    pending = await asyncio.to_thread(
                        configured.analysis_batch_events,
                        batch_id=batch_id,
                        after_event_id=event_cursor,
                    )
                except BatchRuntimeError:
                    return
                for event in pending:
                    event_cursor = event.event_id
                    payload = {
                        "event_id": event.event_id,
                        "batch_id": event.batch_id,
                        "item_id": event.item_id,
                        "event_type": event.event_type,
                        "payload": event.payload,
                        "occurred_at": event.occurred_at,
                    }
                    encoded = json.dumps(payload, separators=(",", ":"))
                    yield (f"id: {event.event_id}\nevent: {event.event_type}\ndata: {encoded}\n\n")
                try:
                    snapshot = await asyncio.to_thread(configured.analysis_batch, batch_id=batch_id)
                except BatchRuntimeError:
                    return
                if snapshot.state in {"cancelled", "completed", "completed_with_errors", "failed"}:
                    return
                if not pending:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @router.post("/onboarding/analysis-batches/{batch_id}/{action}")
    async def action_analysis_batch(
        request: Request,
        batch_id: str = Path(min_length=1, max_length=64),
        action: Literal["pause", "resume", "cancel", "retry"] = Path(),
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            snapshot = await asyncio.to_thread(
                configured.analysis_batch_action, batch_id=batch_id, action=action
            )
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response(_batch_snapshot_payload(snapshot))

    @router.post("/onboarding/contributions/suggest")
    async def suggest_contributions(
        request: Request,
        body: ContributionSuggestRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, session_hash = boundary
        try:
            result = await asyncio.to_thread(
                configured.suggest_contributions,
                session_hash=session_hash,
                slug=body.slug,
                owner_statement=body.owner_statement,
            )
        except GuidedOnboardingError as exc:
            return _onboarding_error(request, exc)
        return JSONResponse(result)

    @router.post("/onboarding/draft")
    async def create_onboarding_draft(
        request: Request,
        body: OnboardingDraftRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            result = configured.create_onboarding_draft(
                profile=body.profile,
                repositories=body.repositories,
                base_config=body.base_config,
                confirmed_assertions=body.confirmed_assertions,
            )
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except GuidedOnboardingError as exc:
            return _onboarding_error(request, exc)
        return JSONResponse(result)

    return router


def _auth_error(request: Request, error: AdminAuthError) -> JSONResponse:
    statuses = {
        "CSRF_FAILED": 403,
        "SETUP_ALREADY_COMPLETE": 409,
        "SETUP_DENIED": 401,
    }
    return error_response(
        request,
        status_code=statuses.get(error.code, 401),
        code=error.code,
        message="Authentication failed.",
        retry_after_seconds=error.retry_after_seconds,
    )


def _oauth_error(request: Request, error: GitHubOAuthError) -> JSONResponse:
    statuses = {
        "GITHUB_LOGIN_UNAVAILABLE": 503,
        "GITHUB_CONNECTION_REQUIRED": 401,
        "GITHUB_CREDENTIAL_INVALID": 401,
        "GITHUB_SCOPE_UNSAFE": 403,
        "OAUTH_TRANSACTION_INVALID": 401,
        "OAUTH_TRANSACTION_EXPIRED": 401,
        "OAUTH_AUTHORIZATION_DENIED": 401,
    }
    return error_response(
        request,
        status_code=statuses.get(error.code, 502),
        code=error.code,
        message="GitHub sign-in failed.",
    )


def _oauth_or_auth_error(
    request: Request, error: AdminAuthError | GitHubOAuthError
) -> JSONResponse:
    if isinstance(error, AdminAuthError):
        return _auth_error(request, error)
    return _oauth_error(request, error)


def _oauth_redirect(authorization_url: str, state: str, cookie_name: str) -> RedirectResponse:
    response = RedirectResponse(authorization_url, status_code=303)
    _set_oauth_transaction_cookie(response, state, cookie_name)
    return response


def _set_oauth_transaction_cookie(response: Response, state: str, cookie_name: str) -> None:
    response.set_cookie(
        cookie_name,
        state,
        max_age=int(OAUTH_TRANSACTION_COOKIE_TTL_SECONDS),
        secure=True,
        httponly=True,
        samesite="lax",
        path="/api/admin/github",
    )


def _oauth_callback_failure(code: str, cookie_name: str) -> RedirectResponse:
    response = RedirectResponse(f"/admin?github_oauth={code.casefold()}", status_code=303)
    response.delete_cookie(cookie_name, path="/api/admin/github", secure=True, httponly=True)
    return response


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
    statuses = {
        "CONFIG_CONFLICT": 409,
        "WRITE_NOT_ALLOWED": 403,
        "NOT_FOUND": 404,
        "SERVICE_NOT_READY": 503,
    }
    details = {"current_blob_sha": error.current_blob_sha} if error.current_blob_sha else {}
    return error_response(
        request,
        status_code=statuses.get(error.code, 502),
        code=error.code,
        message="GitHub operation failed.",
        details=details,
    )


def _onboarding_error(request: Request, error: GuidedOnboardingError) -> JSONResponse:
    statuses = {
        "VALIDATION_ERROR": 400,
        "AUTHENTICATION_REQUIRED": 401,
        "NOT_FOUND": 404,
        "CONFIG_INVALID": 422,
        "RATE_LIMITED": 429,
        "CONCURRENCY_LIMIT": 429,
        "GITHUB_ERROR": 502,
        "PROVIDER_ERROR": 502,
        "MODEL_UNAVAILABLE": 503,
        "SERVICE_NOT_READY": 503,
        "PROVIDER_TIMEOUT": 504,
        "CANCELLED": 499,
    }
    details = {"reason": error.reason} if error.reason else {}
    return error_response(
        request,
        status_code=statuses.get(error.code, 502),
        code=error.code,
        message="Guided onboarding operation failed.",
        details=details,
        retry_after_seconds=error.retry_after_seconds,
    )


def _batch_response(payload: dict[str, object]) -> JSONResponse:
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


def _embedding_profile_response(
    payload: dict[str, object], *, status_code: int = 200
) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _embedding_profile_error(request: Request, error: EmbeddingProfileError) -> JSONResponse:
    status_code = {
        "NOT_FOUND": 404,
        "SERVICE_NOT_READY": 503,
        "EMBEDDING_CONNECTION_REQUIRED": 409,
        "EMBEDDING_PROFILE_ACTIVE_IMMUTABLE": 409,
        "EMBEDDING_PROFILE_ACTIVE_REQUIRED": 409,
        "EMBEDDING_REINDEX_REQUIRED": 409,
        "EMBEDDING_PROBE_REQUIRED": 409,
        "EMBEDDING_REINDEX_ACTIVE": 409,
        "EMBEDDING_REINDEX_STALE": 409,
        "EMBEDDING_MODEL_OPERATION_ACTIVE": 409,
        "EMBEDDING_MODEL_OPERATION_FAILED": 502,
    }.get(error.code, 400)
    response = error_response(
        request,
        status_code=status_code,
        code=error.code,
        message="Embedding profile operation failed.",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _batch_error(request: Request, error: Exception) -> JSONResponse:
    code = error.code if isinstance(error, BatchRuntimeError) else "VALIDATION_ERROR"
    statuses = {
        "VALIDATION_ERROR": 400,
        "NOT_FOUND": 404,
        "ANALYSIS_BATCH_ACTIVE": 409,
        "ANALYSIS_PLAN_STALE": 409,
        "GITHUB_RATE_LIMITED": 429,
        "RATE_LIMITED": 429,
        "GITHUB_CONNECTION_REQUIRED": 503,
        "MODEL_UNAVAILABLE": 503,
        "SERVICE_NOT_READY": 503,
    }
    return error_response(
        request,
        status_code=statuses.get(code, 502),
        code=code,
        message="Analysis batch operation failed.",
    )


def _last_event_id(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    if not value.isdigit():
        raise ValueError("event cursor is invalid")
    parsed = int(value)
    if parsed < 0:
        raise ValueError("event cursor is invalid")
    return parsed


def _preflight_payload(plan: BatchPreflightPlan) -> dict[str, object]:
    graphql, core, secondary = plan.graphql_budget, plan.core_budget, plan.secondary_retry_at
    return {
        "plan_id": plan.plan_id,
        "expires_at": plan.expires_at.isoformat(),
        "selection_hash": plan.selection_hash,
        "selected_credential": (
            {
                "credential_id": plan.selected_credential.credential_id,
                "purpose": plan.selected_credential.purpose,
                "github_login": plan.selected_credential.github_login,
            }
            if plan.selected_credential is not None
            else None
        ),
        "repositories": [
            {
                "slug": repository.slug,
                "commit_sha": repository.commit_sha,
                "default_branch": repository.default_branch,
                "is_archived": repository.is_archived,
            }
            for repository in plan.repositories
        ],
        "cache_predictions": {
            key: {
                "derived_index_hit": prediction.derived_index_hit,
                "validated_analysis_hit": prediction.validated_analysis_hit,
            }
            for key, prediction in plan.cache_predictions.items()
        },
        "graphql_budget": _rate_budget_payload(graphql),
        "core_budget": _rate_budget_payload(core),
        "secondary_retry_at": secondary.isoformat() if secondary is not None else None,
        "provider_ready": plan.provider_ready,
        "capacity": {
            "github_requests": plan.server_capacity.github_requests,
            "archive_staging": plan.server_capacity.archive_staging,
            "index_work": plan.server_capacity.index_work,
            "generation": plan.server_capacity.generation,
            "whole_job_items": plan.server_capacity.whole_job_items,
        },
        "maximum_generation_attempts": plan.maximum_generation_attempts,
        "duration": (
            {
                "minimum_seconds": plan.duration.minimum_seconds,
                "maximum_seconds": plan.duration.maximum_seconds,
                "confidence": plan.duration.confidence,
            }
            if plan.duration is not None
            else None
        ),
        "blockers": [{"slug": item.slug, "code": item.code} for item in plan.blockers],
        "warnings": list(plan.warnings),
    }


def _rate_budget_payload(budget: RateBudget) -> dict[str, object]:
    return {
        "remaining": budget.remaining,
        "limit": budget.limit,
        "reset_at": budget.reset_at.isoformat() if budget.reset_at is not None else None,
    }


def _batch_snapshot_payload(snapshot: BatchSnapshot) -> dict[str, object]:
    return {
        "batch_id": snapshot.batch_id,
        "state": snapshot.state,
        "plan_id": snapshot.plan_id,
        "selection_hash": snapshot.selection_hash,
        "maximum_generation_attempts": snapshot.maximum_generation_attempts,
        "created_at": snapshot.created_at,
        "started_at": snapshot.started_at,
        "completed_at": snapshot.completed_at,
        "expires_at": snapshot.expires_at,
        "error_code": snapshot.error_code,
        "progress": snapshot.progress,
        "items": [
            {
                "item_id": item.item_id,
                "slug": item.slug,
                "requested_ref": item.requested_ref,
                "commit_sha": item.commit_sha,
                "state": item.state,
                "retryable": item.retryable,
                "error_code": item.error_code,
                "retry_at": item.retry_at,
                "result": item.result,
            }
            for item in snapshot.items
        ],
    }


def _embedding_profile_payload(profile: EmbeddingProfile) -> dict[str, object]:
    return {
        "profile_id": profile.profile_id,
        "provider": profile.provider,
        "model_id": profile.model_id,
        "dimension": profile.dimension,
        "normalized": profile.normalized,
        "query_prefix": profile.query_prefix,
        "passage_prefix": profile.passage_prefix,
        "connection_reference": profile.connection_reference,
        "status": profile.status,
        "active": profile.active,
        "observed_identity": (
            {
                "adapter": profile.observed_adapter,
                "model_id": profile.observed_model_id,
                "dimension": profile.observed_dimension,
            }
            if profile.observed_adapter is not None
            else None
        ),
        "last_error_code": profile.last_error_code,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "last_probed_at": profile.last_probed_at,
        "reindex_generation": profile.reindex_generation,
        "reindex_started_at": profile.reindex_started_at,
        "reindex_completed_at": profile.reindex_completed_at,
        "bundle_id": profile.bundle_id,
    }


def _ollama_model_operation_payload(operation: OllamaModelOperation) -> dict[str, object]:
    return {
        "operation_id": operation.operation_id,
        "profile_id": operation.profile_id,
        "model_id": operation.model_id,
        "status": operation.status,
        "completed": operation.completed,
        "total": operation.total,
        "error_code": operation.error_code,
        "updated_at": operation.updated_at,
    }


def _asset_result(canonical: CanonicalSprite) -> dict[str, object]:
    return {
        "sha256": canonical.sha256,
        "width": canonical.width,
        "height": canonical.height,
        "png_base64": base64.b64encode(canonical.content).decode("ascii"),
    }


def _session_body(session: AdminSession) -> dict[str, str]:
    return {
        "csrf_token": session.csrf_token,
        "expires_at": session.expires_at,
        "absolute_expires_at": session.absolute_expires_at,
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
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return ""
    return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}"


def _setup_guide_callback_url(
    configured_callback: str | None,
    origins: tuple[str, ...],
) -> str | None:
    """Return the validated fixed callback without trusting request headers."""

    allowed_origins = tuple(
        dict.fromkeys(
            normalized for origin in origins if (normalized := _normalized_origin(origin))
        )
    )
    if configured_callback:
        try:
            parsed = urlsplit(configured_callback)
            callback_origin = _normalized_origin(configured_callback)
            allowed_scheme = parsed.scheme == "https" or (
                parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
            )
        except ValueError:
            callback_origin = ""
            allowed_scheme = False
            parsed = None
        if (
            parsed is not None
            and allowed_scheme
            and callback_origin in allowed_origins
            and parsed.path == GITHUB_OAUTH_CALLBACK_PATH
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
            and not parsed.password
        ):
            return configured_callback
    for normalized in allowed_origins:
        if normalized:
            return f"{normalized}{GITHUB_OAUTH_CALLBACK_PATH}"
    return None


def _origin_from_referer(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
