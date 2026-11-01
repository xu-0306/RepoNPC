"""Same-origin HTTP boundary for the single-owner admin session."""

from __future__ import annotations

import asyncio
import base64
import inspect
import ipaddress
import json
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import replace
from pathlib import Path as FilePath
from threading import Event
from typing import Annotated, Any, Literal, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, File, Form, Header, Path, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, model_validator
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Message

from reponpc.admin.analysis_selection import AnalysisSelectionError
from reponpc.admin.auth import (
    MAX_ADMIN_PASSWORD_LENGTH,
    MIN_ADMIN_PASSWORD_LENGTH,
    SESSION_COOKIE,
    AdminAuthError,
    AdminSession,
    AdminSessionService,
)
from reponpc.admin.backup_encryption import MAX_SQLITE_BYTES, BackupEncryptionError
from reponpc.admin.backup_resources import BackupResourceError
from reponpc.admin.backup_validation import BackupValidationError
from reponpc.admin.batch_resolver import (
    BatchPreflightPlan,
    BatchResolverError,
    RateBudget,
    RepositorySelection,
    normalize_repository_slug,
)
from reponpc.admin.batch_runtime import BatchRuntimeError, BatchSnapshot
from reponpc.admin.chat_profiles import ChatProfileError, ChatProfileInput
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileInput,
    embedding_model_catalog,
)
from reponpc.admin.faq import FaqError, ReviewedFaq
from reponpc.admin.local_portfolio import LocalPortfolioError, apply_character
from reponpc.admin.maintenance import MaintenanceError, MaintenanceService
from reponpc.admin.maintenance_host import MaintenanceHostError
from reponpc.admin.model_connections import (
    ModelConnectionError,
    ModelConnectionInput,
)
from reponpc.admin.model_operations import OllamaModelOperation
from reponpc.admin.onboarding import (
    GuidedOnboardingError,
    GuidedProfileDraft,
    GuidedRepositoryDraft,
)
from reponpc.admin.operations import AdminOperations
from reponpc.admin.preview_assets import PreviewAssetError, PreviewAssetStore
from reponpc.admin.scene import AdminSceneService, SceneServiceError
from reponpc.api.public import SVG_ASSET_CSP, error_response
from reponpc.api.visitor_gateway import (
    KEEP_VISITOR_PORT,
    VisitorGateway,
    VisitorGatewayError,
)
from reponpc.bundles.manager import BundleActivationError
from reponpc.cards.assets import CanonicalSprite, SpriteValidationError
from reponpc.cards.conversion import (
    MAX_PACK_ENTRIES,
    MAX_SOURCE_BYTES,
    MAX_SOURCE_MEMBER_BYTES,
    MAX_SOURCE_UNCOMPRESSED_BYTES,
    ConversionStrategy,
    MaterialEntry,
    SpriteConversion,
    SpriteConversionError,
    SpriteSelection,
)
from reponpc.cards.render import CardRenderError
from reponpc.chat.limits import ChatLimitError
from reponpc.config.environment import _canonical_origin
from reponpc.config.models import ConfigValidationError, PublicConfig, SceneFocusConfig
from reponpc.providers import ProviderError
from reponpc.runtime.database import RuntimeDatabaseError
from reponpc.scene.registry import DEFAULT_SCHEME_ID
from reponpc.sharing.export import build_visitor_site_export
from reponpc.sharing.manifest import SiteExportError
from reponpc.sharing.pages import PagesSharingService


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _mounted_web_directory(request: Request) -> FilePath | None:
    for route in request.app.routes:
        if getattr(route, "name", None) != "web":
            continue
        directory = getattr(getattr(route, "app", None), "directory", None)
        if isinstance(directory, str):
            return FilePath(directory)
        if isinstance(directory, FilePath):
            return directory
    return None


class LoginRequest(_StrictRequest):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class LocalLaunchRequest(_StrictRequest):
    grant: str = Field(min_length=1, max_length=1024)


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
    password: str | None = Field(default=None, min_length=1, max_length=1024)
    local_launch_grant: str | None = Field(default=None, min_length=1, max_length=1024)


class EmbeddingProfileRequest(_StrictRequest):
    provider: Literal["ollama", "openai_compatible", "vllm", "builtin_onnx"]
    model_id: str = Field(min_length=1, max_length=256)
    dimension: int | None = Field(default=None, ge=1, le=65536)
    normalized: bool = True
    query_prefix: str = Field(default="query: ", max_length=128)
    passage_prefix: str = Field(default="passage: ", max_length=128)
    connection_reference: str | None = Field(
        default="environment", pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
    )
    connection_revision: int = Field(default=0, ge=0)

    def profile_input(self) -> EmbeddingProfileInput:
        return EmbeddingProfileInput(**self.model_dump())


class ConfirmedBuiltinDownloadRequest(_StrictRequest):
    confirmed: StrictBool

    @model_validator(mode="after")
    def require_consent(self) -> ConfirmedBuiltinDownloadRequest:
        if self.confirmed is not True:
            raise ValueError("download consent is required")
        return self


class DeviceCheckRequest(_StrictRequest):
    pass


class BackupRequest(_StrictRequest):
    password: SecretStr = Field(min_length=12, max_length=1024)


class RestoreRequest(ConfirmedBuiltinDownloadRequest):
    preview_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class PinRequest(ConfirmedBuiltinDownloadRequest):
    bundle_id: str = Field(min_length=1, max_length=128)


class ModelConnectionRequest(_StrictRequest):
    display_name: str = Field(min_length=1, max_length=120)
    provider: Literal["ollama", "openai_compatible", "vllm"]
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: str | None = Field(default=None, max_length=4096)
    credential_action: Literal["retain", "replace", "remove"] = "retain"
    endpoint_action: Literal["retain", "replace"] = "replace"
    chat_api: Literal["chat_completions", "responses"] | None = None

    def connection_input(self) -> ModelConnectionInput:
        return ModelConnectionInput(**self.model_dump())


class ChatProfileRequest(_StrictRequest):
    connection_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    model_id: str = Field(min_length=1, max_length=256)

    def profile_input(self) -> ChatProfileInput:
        return ChatProfileInput(**self.model_dump())


class AnalysisSelectionRequest(_StrictRequest):
    chat_profile_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    embedding_profile_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    expected_generation: int | None = Field(default=None, ge=0)


class ConfirmedModelActionRequest(_StrictRequest):
    profile_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    confirmed: Literal[True]


class ConfigContentRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=1024 * 1024)


class PortfolioRequest(ConfigContentRequest):
    sprite_base64: str | None = Field(default=None, max_length=3 * 1024 * 1024)
    expected_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class PreparePortfolioRequest(_StrictRequest):
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    selection_generation: int = Field(ge=0)
    confirmed: Literal[True]


class SceneProposalRequest(_StrictRequest):
    color_scheme: str = Field(default=DEFAULT_SCHEME_ID, min_length=1, max_length=64)
    color_mode: Literal["system", "light", "dark"] = "system"
    visitor_mode_toggle: StrictBool = True
    visitor_scheme_choice: StrictBool = True
    accent: str | None = Field(default=None, max_length=7)
    background: str = Field(
        default="current",
        max_length=80,
        pattern=r"^(?:current|none|draft:[A-Za-z0-9_-]{32,64})$",
    )
    focus: SceneFocusConfig = Field(default_factory=SceneFocusConfig)
    dim: Literal["auto", "none", "low", "medium", "high"] = "auto"
    scaling: Literal["smooth", "pixelated"] = "smooth"

    def proposal(self) -> dict[str, object]:
        result = self.model_dump()
        result["focus"] = self.focus.model_dump()
        return result


class SceneExpectedRequest(_StrictRequest):
    source_bundle_id: str = Field(min_length=1, max_length=128)
    source_character_revision: int = Field(strict=True, ge=0)
    character_revision: int = Field(strict=True, ge=0)
    appearance_revision: int = Field(strict=True, ge=0)
    draft_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sprite_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SceneApplyRequest(_StrictRequest):
    proposal: SceneProposalRequest
    expected: SceneExpectedRequest


class ShareProfileRequest(_StrictRequest):
    account: str = Field(
        min_length=1, max_length=39, pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"
    )
    filename: Literal["reponpc-card.gif"] = "reponpc-card.gif"


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


class AnalysisBatchReanalyzeRequest(_StrictRequest):
    item_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=16, max_length=512)
    model_selection: Literal["frozen", "current"] = "frozen"
    confirm_model_change: bool = False
    expected_selection_generation: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def unique_items(self) -> AnalysisBatchReanalyzeRequest:
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("analysis item IDs must be unique")
        if any(not 1 <= len(item_id) <= 64 for item_id in self.item_ids):
            raise ValueError("invalid analysis item ID")
        return self


class ContributionSuggestRequest(_StrictRequest):
    slug: str = Field(min_length=3, max_length=201)
    owner_statement: str = Field(min_length=1, max_length=4000)


class OnboardingDraftRequest(_StrictRequest):
    profile: GuidedProfileDraft
    repositories: tuple[GuidedRepositoryDraft, ...] = Field(min_length=1, max_length=50)
    base_config: PublicConfig | None = None
    confirmed_assertions: Literal[True]


class FaqQueueRequest(_StrictRequest):
    locale: Literal["zh-TW", "en"]


class FaqGenerateRequest(_StrictRequest):
    revision: Annotated[int, Field(strict=True, ge=1)]


class FaqReviewRequest(FaqGenerateRequest):
    action: Literal["approve", "reject"]


class FaqVariantsRequest(_StrictRequest):
    bundle_id: Annotated[str, Field(min_length=1, max_length=128)]
    revision: Annotated[int, Field(strict=True, ge=1)]
    variants: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=200)]],
        Field(max_length=8),
    ]


class PagesUrlRequest(_StrictRequest):
    pages_url: Annotated[str, Field(min_length=1, max_length=2048)]


class GatewayRevisionRequest(_StrictRequest):
    revision: int = Field(gt=0, strict=True)


class GatewayConfigurationRequest(GatewayRevisionRequest):
    gateway_origin: Annotated[str | None, Field(max_length=2048)]
    pages_origin: Annotated[str | None, Field(max_length=2048)]
    # Tri-state: omitted keeps the stored port, null clears it to the environment default.
    visitor_port: Annotated[int | None, Field(ge=1024, le=65535, strict=True)] = None


class GatewayVerificationRequest(GatewayRevisionRequest):
    external_checks_confirmed: bool = Field(strict=True)


class GatewaySnapshot(_StrictRequest):
    revision: int
    gateway_origin: str | None
    pages_origin: str | None
    enabled: bool
    listener_ready: bool
    error_code: Literal["GATEWAY_CONFIGURATION_INVALID", "GATEWAY_UNAVAILABLE"] | None
    local_ready: bool
    entry_configured: bool
    external_verified: bool
    verified_at: str | None
    verification_method: Literal["owner_reported"] | None
    active_bundle_id: str | None
    client_identity_mode: Literal["aggregate", "trusted_proxy"]
    visitor_port: int
    visitor_port_source: Literal["owner", "environment"]


def create_admin_router(
    *,
    service_supplier: Callable[[], AdminSessionService | None],
    origins_supplier: Callable[[], tuple[str, ...]],
    operations_supplier: Callable[[], AdminOperations | None] = lambda: None,
    faq_supplier: Callable[[], ReviewedFaq | None] = lambda: None,
    gateway_supplier: Callable[[], VisitorGateway | None] = lambda: None,
    scene_supplier: Callable[[], AdminSceneService | None] = lambda: None,
    preview_assets_supplier: Callable[[], PreviewAssetStore] | None = None,
) -> APIRouter:
    """Create auth routes whose production dependencies may attach after startup."""

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
        allowed = frozenset(filter(None, map(_canonical_origin, origins_supplier())))
        hosts = request.headers.getlist("host")
        origins = request.headers.getlist("origin")
        referers = request.headers.getlist("referer")
        candidate = origins[0] if len(origins) == 1 else None
        if not origins and len(referers) == 1:
            candidate = _origin_from_referer(referers[0])
        authority = (
            _canonical_origin(f"{request.scope['scheme']}://{hosts[0]}") if len(hosts) == 1 else ""
        )
        origin = _canonical_origin(candidate) if candidate is not None else ""
        if (
            len(origins) > 1
            or len(referers) > 1
            or not origin
            or origin != authority
            or authority not in allowed
        ):
            return error_response(
                request,
                status_code=403,
                code="CSRF_FAILED",
                message="The request origin could not be verified.",
            )
        return None

    class PrivateOriginRoute(APIRoute):
        def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def guarded(request: Request) -> Response:
                configured = service_supplier()
                if request.url.path.startswith("/api/admin/maintenance"):
                    rejected = same_origin(request)
                    if rejected is not None:
                        return rejected
                    if configured is None:
                        return error_response(
                            request,
                            status_code=503,
                            code="SERVICE_NOT_READY",
                            message="The admin service is not configured.",
                        )
                    try:
                        await asyncio.to_thread(
                            configured.authorize,
                            session_token=request.cookies.get(SESSION_COOKIE, ""),
                            csrf_token=(
                                request.headers.get("X-CSRF-Token", "")
                                if request.method not in {"GET", "HEAD"}
                                else None
                            ),
                        )
                    except AdminAuthError as exc:
                        return _auth_error(request, exc)
                    if (
                        request.method == "POST"
                        and request.url.path != "/api/admin/maintenance/restore/inspect"
                    ):
                        lengths = request.headers.getlist("content-length")
                        if (
                            len(lengths) != 1
                            or len(lengths[0]) > 10
                            or not lengths[0].isascii()
                            or not lengths[0].isdigit()
                            or int(lengths[0]) > 8192
                            or request.headers.getlist("transfer-encoding")
                        ):
                            return error_response(
                                request,
                                status_code=413,
                                code="BACKUP_TOO_LARGE",
                                message="The maintenance request is too large.",
                            )
                        body = bytearray()
                        async for chunk in request.stream():
                            if len(body) + len(chunk) > 8192:
                                return error_response(
                                    request,
                                    status_code=413,
                                    code="BACKUP_TOO_LARGE",
                                    message="The maintenance request is too large.",
                                )
                            body.extend(chunk)
                        # Reuse Starlette's request body cache for the bounded FastAPI parser.
                        request._body = bytes(body)
                profile = getattr(request.app.state, "deployment_profile", None)
                if profile is None and configured is not None:
                    profile = configured.deployment_profile
                if profile == "production":
                    rejected = same_origin(request)
                    if rejected is not None:
                        return rejected
                return await handler(request)

            return guarded

    router = APIRouter(prefix="/api/admin", route_class=PrivateOriginRoute)
    local_preview_assets = PreviewAssetStore()

    def maintenance(request: Request) -> MaintenanceService:
        configured = getattr(request.app.state, "maintenance_service", None)
        if not isinstance(configured, MaintenanceService):
            raise MaintenanceError("SERVICE_NOT_READY")
        host = getattr(request.app.state, "maintenance_host", None)
        if host is not None:
            configured.reconcile_host(host)
        return configured

    def maintenance_failure(request: Request, exc: Exception) -> JSONResponse:
        code = getattr(exc, "code", "RESTORE_FAILED")
        status = 409 if code in {"MAINTENANCE_BUSY", "RESTORE_WORK_PENDING"} else 400
        if code in {"SERVICE_NOT_READY", "BACKUP_STORAGE_UNAVAILABLE", "RESTORE_FAILED"}:
            status = 503
        if code == "BACKUP_DOWNLOAD_UNAVAILABLE":
            status = 404
        return error_response(
            request,
            status_code=status,
            code=code,
            message="The maintenance operation could not be completed.",
        )

    def maintenance_status(request: Request) -> dict[str, object]:
        configured = maintenance(request)
        state = configured.database.bundle_state()
        gateway = gateway_supplier()
        snapshot = gateway.snapshot() if gateway is not None else {}
        return {
            "active_bundle_id": state.active_bundle_id,
            "previous_bundle_id": state.previous_bundle_id,
            "pinned_bundle_id": state.pinned_bundle_id,
            "last_backup_at": configured.last_backup_at(),
            "local_ready": bool(snapshot.get("local_ready", False)),
            "gateway_configured": bool(
                snapshot.get("gateway_origin") and snapshot.get("pages_origin")
            ),
            "externally_verified": bool(snapshot.get("external_verified", False)),
        }

    maintenance_errors = (
        MaintenanceError,
        BackupEncryptionError,
        BackupValidationError,
        BackupResourceError,
        MaintenanceHostError,
        RuntimeDatabaseError,
        OSError,
    )

    @router.get("/maintenance/status")
    async def read_maintenance_status(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        rejected = same_origin(request)
        if rejected is not None:
            return rejected
        try:
            result = await asyncio.to_thread(maintenance_status, request)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)

    @router.post("/maintenance/backup")
    async def download_runtime_backup(
        request: Request,
        body: BackupRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        try:
            artifact, backup_id = await asyncio.to_thread(
                maintenance(request).backup_for_download, body.password.get_secret_value()
            )
            return Response(
                artifact,
                media_type="application/octet-stream",
                headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": 'attachment; filename="reponpc-backup.reponpc-backup"',
                    "Content-Location": f"/api/admin/maintenance/backup/{backup_id}",
                },
            )
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)

    @router.get("/maintenance/backup/{backup_id}")
    async def read_encrypted_backup(
        request: Request,
        backup_id: Annotated[str, Path(pattern=r"^[0-9]{8}T[0-9]{6}-[0-9a-f]{16}$")],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = protected(request, session_token, None)
        if isinstance(boundary, JSONResponse):
            return boundary
        try:
            artifact = await asyncio.to_thread(maintenance(request).read_backup, backup_id)
            return Response(
                artifact,
                media_type="application/octet-stream",
                headers={
                    "Cache-Control": "no-store",
                    "Content-Disposition": 'attachment; filename="reponpc-backup.reponpc-backup"',
                },
            )
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)

    @router.post("/maintenance/restore/inspect")
    async def inspect_runtime_backup(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        lengths = request.headers.getlist("content-length")
        if (
            len(lengths) != 1
            or len(lengths[0]) > 10
            or not lengths[0].isascii()
            or not lengths[0].isdigit()
            or int(lengths[0]) > MAX_SQLITE_BYTES + 24576
            or request.headers.getlist("transfer-encoding")
        ):
            return maintenance_failure(request, MaintenanceError("BACKUP_TOO_LARGE"))
        receive = request._receive
        received = 0
        declared = int(lengths[0])

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_SQLITE_BYTES + 24576 or received > declared:
                    raise MaintenanceError("BACKUP_TOO_LARGE")
                if not message.get("more_body", False) and received != declared:
                    raise MaintenanceError("BACKUP_FORMAT_INVALID")
            return message

        request._receive = bounded_receive
        try:
            async with request.form(max_files=1, max_fields=1, max_part_size=8192) as form:
                upload, password = form.get("backup"), form.get("password")
                if (
                    set(form) != {"backup", "password"}
                    or len(form.multi_items()) != 2
                    or not isinstance(upload, StarletteUploadFile)
                    or not isinstance(password, str)
                ):
                    raise MaintenanceError("BACKUP_FORMAT_INVALID")
                content = await upload.read(MAX_SQLITE_BYTES + 8193)
                if len(content) > MAX_SQLITE_BYTES + 8192:
                    raise MaintenanceError("BACKUP_TOO_LARGE")
                result = await asyncio.to_thread(
                    maintenance(request).inspect,
                    content,
                    password,
                    boundary[1],
                )
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)
        except ValueError, StarletteHTTPException:
            return maintenance_failure(request, MaintenanceError("BACKUP_FORMAT_INVALID"))

    @router.post("/maintenance/restore")
    async def restore_runtime_backup(
        request: Request,
        body: RestoreRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        try:
            host = getattr(request.app.state, "maintenance_host", None)
            if host is None:
                raise MaintenanceError("SERVICE_NOT_READY")
            # schedule executes on the ASGI loop, then lets this 202 drain before replacement.
            configured = maintenance(request)
            await asyncio.to_thread(configured.verify_restore, body.preview_id, boundary[1])
            configured.restore(body.preview_id, boundary[1], host)
            return JSONResponse(
                {"status": "restoring"}, status_code=202, headers={"Cache-Control": "no-store"}
            )
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)

    @router.delete("/maintenance/restore/{preview_id}")
    async def cancel_runtime_restore(
        request: Request,
        preview_id: str,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        try:
            await asyncio.to_thread(maintenance(request).cancel, preview_id, boundary[1])
            return Response(status_code=204, headers={"Cache-Control": "no-store"})
        except maintenance_errors as exc:
            return maintenance_failure(request, exc)

    @router.post("/maintenance/pin")
    async def pin_previous_bundle(
        request: Request,
        body: PinRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        manager = getattr(request.app.state, "bundle_manager", None)
        try:
            if manager is None or manager.status().previous_bundle_id != body.bundle_id:
                raise MaintenanceError("RESTORE_RESOURCE_MISSING")
            pinned = await asyncio.to_thread(manager.pin, body.bundle_id, require_previous=True)
            current = request.app.state.reponpc
            request.app.state.reponpc = replace(
                current,
                index_ready=pinned.active_bundle_id is not None,
                index_version=pinned.active_bundle_id,
                public_directory=manager.active_public_directory(),
            )
            return JSONResponse(maintenance_status(request), headers={"Cache-Control": "no-store"})
        except (*maintenance_errors, BundleActivationError) as exc:
            return maintenance_failure(request, exc)

    @router.post("/maintenance/gateway/stop")
    async def maintenance_stop_gateway(
        request: Request,
        body: DeviceCheckRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        try:
            gateway = gateway_supplier()
            if gateway is not None:
                await gateway.stop(revision=gateway.snapshot()["revision"])
            return JSONResponse(maintenance_status(request), headers={"Cache-Control": "no-store"})
        except (*maintenance_errors, VisitorGatewayError) as exc:
            return maintenance_failure(request, exc)

    def scene_service(request: Request) -> AdminSceneService | JSONResponse:
        configured = scene_supplier()
        if configured is not None:
            return configured
        return error_response(
            request,
            status_code=503,
            code="SERVICE_NOT_READY",
            message="The scene service is not configured.",
        )

    def preview_assets() -> PreviewAssetStore:
        return (
            preview_assets_supplier()
            if preview_assets_supplier is not None
            else local_preview_assets
        )

    def attach_preview_urls(payload: object, session_hash: str) -> object:
        return _attach_preview_urls(
            payload, owner_session_hash=session_hash, store=preview_assets()
        )

    def local_launch_boundary(request: Request, configured: AdminSessionService) -> bool:
        if configured.deployment_profile != "loopback_evaluation":
            return False
        if request.client is None or not _is_loopback_host(request.client.host):
            return False
        if any(
            name.lower() == b"forwarded" or name.lower().startswith(b"x-forwarded-")
            for name, _value in request.headers.raw
        ):
            return False
        allowed_origins = frozenset(
            normalized
            for value in origins_supplier()
            if (normalized := _canonical_origin(value)) and _origin_is_loopback(normalized)
        )
        origin = request.headers.get("origin")
        if origin is None or _canonical_origin(origin) not in allowed_origins:
            return False
        host = request.headers.get("host")
        return host is not None and _host_is_allowed_loopback(host, allowed_origins)

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

    @router.post("/session/local-launch")
    async def local_launch(request: Request) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        remote_identity = request.client.host if request.client is not None else "unknown"
        body: LocalLaunchRequest | None = None
        try:
            body = LocalLaunchRequest.model_validate(await request.json())
        except TypeError, ValueError:
            body = None
        grant = (
            body.grant if body is not None and local_launch_boundary(request, configured) else ""
        )
        try:
            session = configured.consume_local_launch(grant=grant, remote_identity=remote_identity)
        except AdminAuthError as exc:
            return _local_launch_error(request, exc)
        response = JSONResponse(_session_body(session))
        _set_session_cookie(response, session.session_token)
        return response

    @router.get("/auth/methods")
    async def auth_methods(request: Request) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        status = configured.auth_methods()
        return JSONResponse(
            {
                "mode": status.mode,
                "password": {"available": status.password_available},
                "setup_required": status.setup_required,
            }
        )

    @router.post("/session/resume")
    async def resume_session(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        configured = service(request)
        if isinstance(configured, JSONResponse):
            return configured
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        if await request.body():
            return _auth_error(request, AdminAuthError("AUTHENTICATION_REQUIRED"))
        if configured.deployment_profile == "loopback_evaluation" and not local_launch_boundary(
            request, configured
        ):
            return _auth_error(request, AdminAuthError("AUTHENTICATION_REQUIRED"))
        try:
            session = configured.resume(session_token=session_token or "")
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        return JSONResponse(
            _session_body(session),
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/model-connections")
    async def list_model_connections(
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
            connections = await asyncio.to_thread(configured.list_model_connections)
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return _model_connection_response(
            {"connections": [connection.safe_dict() for connection in connections]}
        )

    @router.post("/model-connections")
    async def create_model_connection(
        request: Request,
        body: ModelConnectionRequest,
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
            connection = await asyncio.to_thread(
                configured.create_model_connection, body.connection_input()
            )
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return _model_connection_response(connection.safe_dict(), status_code=201)

    @router.get("/model-connections/{connection_id}")
    async def get_model_connection(
        request: Request,
        connection_id: str = Path(min_length=1, max_length=64),
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
            connection = await asyncio.to_thread(configured.get_model_connection, connection_id)
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return _model_connection_response(connection.safe_dict())

    @router.post("/model-connections/{connection_id}/edit-endpoint")
    async def read_model_connection_edit_endpoint(
        request: Request,
        connection_id: str = Path(min_length=1, max_length=64),
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
            endpoint = await asyncio.to_thread(
                configured.model_connection_edit_endpoint, connection_id
            )
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return _model_connection_response(endpoint)

    @router.put("/model-connections/{connection_id}")
    async def update_model_connection(
        request: Request,
        body: ModelConnectionRequest,
        connection_id: str = Path(min_length=1, max_length=64),
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
            connection = await asyncio.to_thread(
                configured.update_model_connection, connection_id, body.connection_input()
            )
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return _model_connection_response(connection.safe_dict())

    @router.delete("/model-connections/{connection_id}")
    async def delete_model_connection(
        request: Request,
        connection_id: str = Path(min_length=1, max_length=64),
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
            await asyncio.to_thread(configured.delete_model_connection, connection_id)
        except ModelConnectionError as exc:
            return _model_connection_error(request, exc)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/chat-profiles")
    async def list_chat_profiles(
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
            profiles = await asyncio.to_thread(configured.list_chat_profiles)
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response({"profiles": [profile.safe_dict() for profile in profiles]})

    @router.post("/chat-profiles")
    async def create_chat_profile(
        request: Request,
        body: ChatProfileRequest,
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
            profile = await asyncio.to_thread(configured.create_chat_profile, body.profile_input())
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response(profile.safe_dict(), status_code=201)

    @router.get("/chat-profiles/{profile_id}")
    async def get_chat_profile(
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
            profile = await asyncio.to_thread(configured.get_chat_profile, profile_id)
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response(profile.safe_dict())

    @router.put("/chat-profiles/{profile_id}")
    async def update_chat_profile(
        request: Request,
        body: ChatProfileRequest,
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
                configured.update_chat_profile, profile_id, body.profile_input()
            )
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response(profile.safe_dict())

    @router.delete("/chat-profiles/{profile_id}")
    async def delete_chat_profile(
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
            await asyncio.to_thread(configured.delete_chat_profile, profile_id)
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.post("/chat-profiles/{profile_id}/probe")
    async def probe_chat_profile(
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
            profile = await asyncio.to_thread(configured.probe_chat_profile, profile_id)
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response(profile.safe_dict())

    @router.post("/chat-profiles/{profile_id}/activate")
    async def activate_chat_profile(
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
            profile = await asyncio.to_thread(configured.activate_chat_profile, profile_id)
        except ChatProfileError as exc:
            return _chat_profile_error(request, exc)
        return _chat_profile_response(profile.safe_dict())

    @router.get("/analysis-selection")
    async def get_analysis_selection(
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
            view = await asyncio.to_thread(configured.analysis_selection_view)
        except AnalysisSelectionError as exc:
            return _analysis_selection_error(request, exc)
        return _analysis_selection_response(view.safe_dict())

    @router.put("/analysis-selection")
    @router.post("/analysis-selection")
    async def select_analysis_models(
        request: Request,
        body: AnalysisSelectionRequest,
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
            view = await asyncio.to_thread(
                configured.select_analysis_models,
                chat_profile_id=body.chat_profile_id,
                embedding_profile_id=body.embedding_profile_id,
                expected_generation=body.expected_generation,
            )
        except AnalysisSelectionError as exc:
            return _analysis_selection_error(request, exc)
        return _analysis_selection_response(view.safe_dict())

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

    @router.get("/embedding-models/builtin")
    async def builtin_model_info(
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
            info = await asyncio.to_thread(configured.builtin_model_info)
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(info)

    @router.post("/embedding-models/builtin/download")
    async def download_builtin_model(
        request: Request,
        body: ConfirmedBuiltinDownloadRequest,
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
                configured.start_builtin_download, confirmed=body.confirmed
            )
        except EmbeddingProfileError as exc:
            return _embedding_profile_error(request, exc)
        return _embedding_profile_response(
            _ollama_model_operation_payload(operation), status_code=202
        )

    @router.post("/model-guidance/device-check")
    async def check_model_device(
        request: Request,
        body: DeviceCheckRequest,
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
        return _embedding_profile_response(await asyncio.to_thread(configured.check_model_device))

    @router.get("/embedding-models/installed")
    async def list_installed_embedding_models(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        connection_id: str | None = Query(
            default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"
        ),
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _session_hash = boundary
        try:
            models = await asyncio.to_thread(
                configured.installed_ollama_embedding_models, connection_id
            )
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
        try:
            session_hash = configured.authorize(session_token=session_token or "").session_hash
            configured.logout(session_token=session_token or "", csrf_token=csrf_token or "")
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        preview_assets().delete_session(session_hash)
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
                local_launch_grant=body.local_launch_grant,
            )
        except AdminAuthError as exc:
            return _auth_error(request, exc)
        preview_assets().clear()
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

    async def gateway_operation(
        request: Request,
        session_token: str | None,
        csrf_token: str | None,
        action: Callable[[VisitorGateway], Any],
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        rejected = same_origin(request)
        if rejected is not None:
            return rejected
        gateway = gateway_supplier()
        code = "GATEWAY_UNAVAILABLE"
        if gateway is not None:
            try:
                result = action(gateway)
                if inspect.isawaitable(result):
                    result = await result
                payload = GatewaySnapshot.model_validate(result).model_dump(mode="json")
                return JSONResponse(payload, headers={"Cache-Control": "no-store"})
            except VisitorGatewayError as exc:
                code = (
                    exc.code
                    if exc.code
                    in {
                        "GATEWAY_CONFLICT",
                        "GATEWAY_CONFIGURATION_INVALID",
                        "GATEWAY_UNAVAILABLE",
                    }
                    else "GATEWAY_UNAVAILABLE"
                )
            except Exception:
                pass
        return error_response(
            request,
            status_code=409
            if code == "GATEWAY_CONFLICT"
            else 422
            if code == "GATEWAY_CONFIGURATION_INVALID"
            else 503,
            code=code,
            message="The visitor gateway operation could not be completed.",
        )

    @router.get("/visitor-gateway")
    async def visitor_gateway_status(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        return await gateway_operation(
            request, session_token, None, lambda gateway: gateway.snapshot()
        )

    @router.put("/visitor-gateway")
    async def configure_visitor_gateway(
        request: Request,
        body: GatewayConfigurationRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        return await gateway_operation(
            request,
            session_token,
            csrf_token or "",
            lambda gateway: gateway.configure(
                revision=body.revision,
                gateway_origin=body.gateway_origin,
                pages_origin=body.pages_origin,
                visitor_port=(
                    body.visitor_port
                    if "visitor_port" in body.model_fields_set
                    else KEEP_VISITOR_PORT
                ),
            ),
        )

    @router.post("/visitor-gateway/start")
    async def start_visitor_gateway(
        request: Request,
        body: GatewayRevisionRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        return await gateway_operation(
            request,
            session_token,
            csrf_token or "",
            lambda gateway: gateway.start(revision=body.revision),
        )

    @router.post("/visitor-gateway/stop")
    async def stop_visitor_gateway(
        request: Request,
        body: GatewayRevisionRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        return await gateway_operation(
            request,
            session_token,
            csrf_token or "",
            lambda gateway: gateway.stop(revision=body.revision),
        )

    @router.post("/visitor-gateway/verify")
    async def verify_visitor_gateway(
        request: Request,
        body: GatewayVerificationRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        return await gateway_operation(
            request,
            session_token,
            csrf_token or "",
            lambda gateway: gateway.verify(**body.model_dump()),
        )

    def local_error(request: Request, exc: Exception) -> Response:
        code = getattr(exc, "code", "PORTFOLIO_INVALID")
        return error_response(
            request,
            status_code=409
            if code in {"PORTFOLIO_CONFLICT", "PORTFOLIO_BUSY", "EMBEDDING_REINDEX_ACTIVE"}
            else 422,
            code=code,
            message="Local portfolio operation could not be completed.",
        )

    async def faq_operation(request: Request, operation: Callable[[], Any]) -> Response:
        try:
            result = await asyncio.to_thread(operation)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except (FaqError, BundleActivationError, LocalPortfolioError) as exc:
            return error_response(
                request,
                status_code=503
                if exc.code in {"SERVICE_NOT_READY", "FAQ_GENERATION_FAILED"}
                else 409
                if exc.code
                in {
                    "FAQ_CONFLICT",
                    "FAQ_STALE",
                    "FAQ_NOT_READY",
                    "PORTFOLIO_CONFLICT",
                }
                else 422,
                code=exc.code,
                message="FAQ operation could not be completed.",
            )
        except ProviderError, ChatLimitError:
            return error_response(
                request,
                status_code=503,
                code="FAQ_GENERATION_FAILED",
                message="FAQ generation could not be completed.",
            )
        except ConfigValidationError as exc:
            return _config_error(request, exc)

    def faq_boundary(request: Request, session_token: str | None, csrf_token: str | None = None):
        boundary = protected(request, session_token, csrf_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        denied = same_origin(request)
        if denied is not None:
            return denied
        faq = faq_supplier()
        return (
            faq
            if faq is not None
            else error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="FAQ service is unavailable.",
            )
        )

    def pages_sharing_service(
        request: Request, faq: ReviewedFaq
    ) -> PagesSharingService | JSONResponse:
        configured_operations = operations(request)
        configured_scene = scene_supplier()
        if isinstance(configured_operations, JSONResponse):
            return configured_operations
        if configured_scene is None or gateway_supplier() is None:
            return error_response(
                request,
                status_code=503,
                code="SHARING_EXPORT_UNAVAILABLE",
                message="Pages sharing is unavailable.",
            )
        try:
            return PagesSharingService(
                database=configured_operations.database,
                faq=faq,
                scene_service=configured_scene,
                gateway_supplier=gateway_supplier,
            )
        except ValueError:
            return error_response(
                request,
                status_code=503,
                code="SHARING_EXPORT_UNAVAILABLE",
                message="Pages sharing is unavailable.",
            )

    def pages_sharing_error(request: Request, exc: SiteExportError) -> JSONResponse:
        status_code = (
            409
            if exc.code == "SHARING_CONFLICT"
            else 413
            if exc.code == "SHARING_EXPORT_TOO_LARGE"
            else 422
            if exc.code
            in {
                "SHARING_CONFIGURATION_INVALID",
                "SHARING_EXPORT_INVALID",
                "SHARING_VERIFICATION_FAILED",
            }
            else 503
        )
        message = (
            "The saved Pages configuration is invalid."
            if exc.code == "SHARING_CONFIGURATION_INVALID"
            else "The Pages site did not match the saved export."
            if exc.code == "SHARING_VERIFICATION_FAILED"
            else "The Pages operation could not be completed."
        )
        return error_response(
            request,
            status_code=status_code,
            code=exc.code,
            message=message,
        )

    @router.get("/portfolio/faq")
    @router.get("/portfolio/faq/export")
    async def read_faq(
        request: Request,
        locale: Literal["zh-TW", "en"] = "zh-TW",
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token)
        if isinstance(faq, JSONResponse):
            return faq
        response = await faq_operation(
            request,
            lambda: (
                faq.public_payload(locale)
                if request.url.path.endswith("/export")
                else faq.view(locale)
            ),
        )
        if request.url.path.endswith("/export") and response.status_code == 200:
            response.headers["Content-Disposition"] = f'attachment; filename="faq-{locale}.json"'
        return response

    @router.post("/portfolio/faq/check")
    async def initialize_faq(
        request: Request,
        body: FaqQueueRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        return await faq_operation(request, lambda: faq.initialize_queue(body.locale))

    @router.post("/portfolio/faq/{entry_id}/regenerate")
    async def generate_faq(
        entry_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")],
        request: Request,
        body: FaqGenerateRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        return await faq_operation(request, lambda: faq.regenerate(entry_id, body.revision))

    @router.post("/portfolio/faq/{entry_id}/review")
    async def review_faq(
        entry_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")],
        request: Request,
        body: FaqReviewRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        return await faq_operation(
            request, lambda: faq.review(entry_id, body.revision, body.action)
        )

    @router.put("/portfolio/faq/{entry_id}/variants")
    async def replace_faq_variants(
        entry_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")],
        request: Request,
        body: FaqVariantsRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        return await faq_operation(
            request,
            lambda: faq.replace_variants(
                entry_id,
                body.revision,
                body.bundle_id,
                body.variants,
            ),
        )

    @router.get("/sharing/export")
    async def export_visitor_site(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token)
        if isinstance(faq, JSONResponse):
            return faq
        sharing = pages_sharing_service(request, faq)
        if isinstance(sharing, JSONResponse):
            return sharing
        web_dist = _mounted_web_directory(request)
        if web_dist is None:
            return error_response(
                request,
                status_code=503,
                code="SHARING_EXPORT_UNAVAILABLE",
                message="The visitor export could not be created.",
            )
        artifact = None
        try:
            state = await asyncio.to_thread(sharing.state)
            pages_url = state.get("pages_url")
            if not isinstance(pages_url, str):
                raise SiteExportError("SHARING_CONFIGURATION_INVALID")
            gateway_origin, pages_origin = await asyncio.to_thread(sharing.current_origins)
            artifact = await asyncio.to_thread(
                build_visitor_site_export,
                faq=faq,
                scene_service=sharing.scene_service,
                web_dist=web_dist,
                pages_url=pages_url,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
                origins_supplier=sharing.current_origins,
            )
        except SiteExportError as exc:
            if artifact is not None:
                artifact.cleanup()
            return pages_sharing_error(request, exc)
        except BundleActivationError, SceneServiceError, FaqError:
            if artifact is not None:
                artifact.cleanup()
            return error_response(
                request,
                status_code=409,
                code="SHARING_CONFLICT",
                message="The visitor export could not be created.",
            )
        return FileResponse(
            artifact.path,
            media_type="application/zip",
            filename="reponpc-site.zip",
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
            background=BackgroundTask(artifact.cleanup),
        )

    @router.get("/sharing/readme")
    async def export_profile_readme(
        request: Request,
        locale: Literal["zh-TW", "en"] = "zh-TW",
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token)
        if isinstance(faq, JSONResponse):
            return faq
        sharing = pages_sharing_service(request, faq)
        if isinstance(sharing, JSONResponse):
            return sharing
        web_dist = _mounted_web_directory(request)
        if web_dist is None:
            return error_response(
                request,
                status_code=503,
                code="SHARING_EXPORT_UNAVAILABLE",
                message="The profile README could not be created.",
            )
        try:
            content = await asyncio.to_thread(sharing.readme, web_dist=web_dist, locale=locale)
        except SiteExportError as exc:
            return pages_sharing_error(request, exc)
        except BundleActivationError, SceneServiceError, FaqError:
            return pages_sharing_error(request, SiteExportError("SHARING_CONFLICT"))
        return Response(
            content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="README.md"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.get("/sharing/state")
    async def read_pages_sharing_state(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token)
        if isinstance(faq, JSONResponse):
            return faq
        sharing = pages_sharing_service(request, faq)
        if isinstance(sharing, JSONResponse):
            return sharing
        try:
            state = await asyncio.to_thread(sharing.state)
        except SiteExportError as exc:
            return pages_sharing_error(request, exc)
        return JSONResponse(state, headers={"Cache-Control": "no-store"})

    @router.put("/sharing/pages")
    async def configure_pages_url(
        request: Request,
        body: PagesUrlRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        sharing = pages_sharing_service(request, faq)
        if isinstance(sharing, JSONResponse):
            return sharing
        try:
            state = await asyncio.to_thread(
                sharing.configure_pages,
                pages_url=body.pages_url,
            )
        except SiteExportError as exc:
            return pages_sharing_error(request, exc)
        return JSONResponse(state, headers={"Cache-Control": "no-store"})

    @router.post("/sharing/verify")
    async def verify_pages_export(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        faq = faq_boundary(request, session_token, csrf_token or "")
        if isinstance(faq, JSONResponse):
            return faq
        sharing = pages_sharing_service(request, faq)
        if isinstance(sharing, JSONResponse):
            return sharing
        web_dist = _mounted_web_directory(request)
        if web_dist is None:
            return error_response(
                request,
                status_code=503,
                code="SHARING_EXPORT_UNAVAILABLE",
                message="The visitor export could not be created.",
            )
        try:
            state = await asyncio.to_thread(
                sharing.verify,
                web_dist=web_dist,
            )
        except SiteExportError as exc:
            return pages_sharing_error(request, exc)
        return JSONResponse(state, headers={"Cache-Control": "no-store"})

    @router.get("/portfolio")
    async def read_portfolio(
        request: Request, session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
    ) -> Response:
        boundary = protected(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        origin_error = same_origin(request)
        if origin_error is not None:
            return origin_error
        configured, _ = boundary
        if configured.local_portfolio is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="Local storage is unavailable.",
            )
        try:
            draft = await asyncio.to_thread(configured.local_portfolio.read)
            return JSONResponse(
                draft.as_dict()
                if draft
                else {"content": "", "sprite_base64": None, "revision": None},
                headers={"Cache-Control": "no-store"},
            )
        except LocalPortfolioError as exc:
            return local_error(request, exc)

    @router.put("/portfolio")
    async def save_portfolio(
        request: Request,
        body: PortfolioRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _ = boundary
        if configured.local_portfolio is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="Local storage is unavailable.",
            )
        try:
            draft = await asyncio.to_thread(
                configured.local_portfolio.save,
                content=body.content,
                sprite_base64=body.sprite_base64,
                expected_revision=body.expected_revision,
            )
            return JSONResponse(draft.as_dict(), headers={"Cache-Control": "no-store"})
        except LocalPortfolioError as exc:
            return local_error(request, exc)
        except ConfigValidationError as exc:
            return _config_error(request, exc)

    @router.post("/portfolio/character")
    @router.post("/portfolio/preview")
    async def preview_portfolio(
        request: Request,
        body: PortfolioRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _ = boundary
        try:
            if request.url.path.endswith("/character"):
                draft = await asyncio.to_thread(
                    apply_character, body.content, body.sprite_base64 or ""
                )
                return JSONResponse(draft.as_dict(), headers={"Cache-Control": "no-store"})
            parsed = configured.validate_config(body.content.encode("utf-8"))
            sprite = (
                base64.b64decode(body.sprite_base64, validate=True) if body.sprite_base64 else None
            )
            if parsed.character.mode == "custom" and sprite is None:
                raise LocalPortfolioError("PORTFOLIO_ASSET_REQUIRED")
            if parsed.character.mode == "builtin" and sprite is not None:
                raise LocalPortfolioError("PORTFOLIO_INVALID")
            preview = await asyncio.to_thread(
                configured.preview_config, body.content.encode("utf-8"), sprite_content=sprite
            )
            return JSONResponse(
                attach_preview_urls(preview, boundary[1]),
                headers={"Cache-Control": "no-store"},
            )
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except (LocalPortfolioError, ValueError, SpriteValidationError, CardRenderError) as exc:
            return local_error(request, exc)

    @router.get("/portfolio/status")
    @router.delete("/portfolio/prepare")
    async def portfolio_status(
        request: Request,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(
            request, session_token, (csrf_token or "") if request.method == "DELETE" else None
        )
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _ = boundary
        if request.method == "DELETE" and configured.local_publication is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="Local preparation is unavailable.",
            )
        try:
            operation = None
            if configured.local_publication is not None:
                operation = (
                    configured.local_publication.cancel
                    if request.method == "DELETE"
                    else configured.local_publication.status
                )
            if request.method == "DELETE" and operation is None:
                return error_response(
                    request,
                    status_code=503,
                    code="SERVICE_NOT_READY",
                    message="Local preparation is unavailable.",
                )
            result = (
                await asyncio.to_thread(operation) if operation is not None else {"retry_at": None}
            )
            if request.method == "GET":
                configured_scene = scene_supplier()
                if configured_scene is not None:
                    scene_state = (
                        await asyncio.to_thread(configured_scene.scene_state)
                        if configured_scene.manager.status().active_bundle_id is not None
                        else None
                    )
                    result = {**result, "scene_state": scene_state}
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except SceneServiceError as exc:
            return _scene_error(request, exc)
        except LocalPortfolioError as exc:
            return local_error(request, exc)

    @router.post("/assets/scene/background-drafts")
    async def create_scene_background_draft(
        request: Request,
        file: Annotated[UploadFile, File()],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        service_configured = scene_service(request)
        if isinstance(service_configured, JSONResponse):
            return service_configured
        _auth, session_hash = boundary
        content = await file.read(2 * 1024 * 1024 + 1)
        try:
            result = await asyncio.to_thread(
                service_configured.create_background_draft,
                session_hash=session_hash,
                content=content,
                filename=file.filename or "",
            )
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except SceneServiceError as exc:
            return _scene_error(request, exc)

    @router.get("/assets/scene/background-drafts/{draft_id}")
    async def read_scene_background_draft(
        request: Request,
        draft_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{32,64}$")],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        service_configured = scene_service(request)
        if isinstance(service_configured, JSONResponse):
            return service_configured
        _auth, session_hash = boundary
        try:
            draft = await asyncio.to_thread(
                service_configured.get_background_draft,
                session_hash=session_hash,
                draft_id=draft_id,
            )
            return Response(
                draft.image.content,
                media_type=draft.image.media_type,
                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
            )
        except SceneServiceError as exc:
            return _scene_error(request, exc)

    @router.delete("/assets/scene/background-drafts/{draft_id}", status_code=204)
    async def delete_scene_background_draft(
        request: Request,
        draft_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{32,64}$")],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        service_configured = scene_service(request)
        if isinstance(service_configured, JSONResponse):
            return service_configured
        _auth, session_hash = boundary
        try:
            await asyncio.to_thread(
                service_configured.delete_background_draft,
                session_hash=session_hash,
                draft_id=draft_id,
            )
            return Response(status_code=204)
        except SceneServiceError as exc:
            return _scene_error(request, exc)

    @router.post("/scene/preview")
    async def preview_scene(
        request: Request,
        body: SceneProposalRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        service_configured = scene_service(request)
        if isinstance(service_configured, JSONResponse):
            return service_configured
        _auth, session_hash = boundary
        try:
            result = await asyncio.to_thread(
                service_configured.preview,
                session_hash=session_hash,
                proposal=body.proposal(),
            )
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except SceneServiceError as exc:
            return _scene_error(request, exc)

    @router.put("/scene")
    async def apply_scene(
        request: Request,
        body: SceneApplyRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        service_configured = scene_service(request)
        if isinstance(service_configured, JSONResponse):
            return service_configured
        _auth, session_hash = boundary
        try:
            result = await asyncio.to_thread(
                service_configured.apply,
                session_hash=session_hash,
                proposal=body.proposal.proposal(),
                expected=body.expected.model_dump(),
            )
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except SceneServiceError as exc:
            return _scene_error(request, exc)

    @router.get("/assets/previews/{asset_id}")
    async def read_preview_asset(
        request: Request,
        asset_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{32,64}$")],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        boundary = authenticated_session(request, session_token)
        if isinstance(boundary, JSONResponse):
            return boundary
        _auth, session_hash = boundary
        try:
            asset = preview_assets().get(asset_id=asset_id, owner_session_hash=session_hash)
        except PreviewAssetError:
            return Response(status_code=404, headers={"Cache-Control": "no-store"})
        headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        if asset.media_type == "image/svg+xml":
            headers["Content-Security-Policy"] = SVG_ASSET_CSP
        return Response(
            asset.content,
            media_type=asset.media_type,
            headers=headers,
        )

    @router.post("/portfolio/prepare")
    async def prepare_portfolio(
        request: Request,
        body: PreparePortfolioRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _ = boundary
        if configured.local_publication is None or configured.analysis_selection is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="Local preparation is unavailable.",
            )
        view = configured.analysis_selection.view()
        if not view.eligible or view.selection.generation != body.selection_generation:
            return local_error(request, LocalPortfolioError("PORTFOLIO_MODEL_CHANGED"))
        try:
            result = await asyncio.to_thread(
                configured.local_publication.prepare,
                expected_revision=body.expected_revision,
                embedding_profile_id=view.selection.embedding_profile_id or "",
                chat_profile_id=view.selection.chat_profile_id or "",
            )
            return JSONResponse(result, status_code=202, headers={"Cache-Control": "no-store"})
        except (LocalPortfolioError, EmbeddingProfileError, ChatProfileError) as exc:
            return local_error(request, exc)

    @router.post("/portfolio/github-profile")
    async def share_profile(
        request: Request,
        body: ShareProfileRequest,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _ = boundary
        if configured.local_publication is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message="Public metadata is unavailable.",
            )
        result = await asyncio.to_thread(
            configured.local_publication.resolver.profile_card_metadata,
            account=body.account,
            filename=body.filename,
        )
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

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
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            preview = configured.preview_config(body.content.encode("utf-8"))
        except ConfigValidationError as exc:
            return _config_error(request, exc)
        except SpriteValidationError, CardRenderError:
            return error_response(
                request,
                status_code=422,
                code="CONFIG_INVALID",
                message="Configuration preview failed.",
            )
        return JSONResponse(
            attach_preview_urls(preview, boundary[1]),
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/assets/character/validate")
    async def validate_asset(
        request: Request,
        file: Annotated[UploadFile, File()],
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        content = await file.read(2 * 1024 * 1024 + 1)
        try:
            canonical = configured.validate_asset(filename=file.filename or "", content=content)
        except SpriteValidationError as exc:
            return _asset_error(request, exc)
        return JSONResponse(
            attach_preview_urls(_asset_result(canonical), boundary[1]),
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/assets/character/convert")
    async def convert_asset(
        request: Request,
        file: Annotated[UploadFile | None, File()] = None,
        files: Annotated[list[UploadFile] | None, File()] = None,
        paths_json: Annotated[str | None, Form(max_length=32_768)] = None,
        strategy: Annotated[Literal["pixel_exact", "pixelize"], Form()] = "pixelize",
        candidate_id: Annotated[
            str | None, Form(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
        ] = None,
        session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
    ) -> Response:
        boundary = protected(request, session_token, csrf_token or "")
        if isinstance(boundary, JSONResponse):
            return boundary
        configured, _session_hash = boundary
        try:
            folder_uploads = files or []
            if file is not None and folder_uploads:
                raise SpriteConversionError("SOURCE_SELECTION_INVALID")
            if file is not None:
                if paths_json is not None:
                    raise SpriteConversionError("SOURCE_SELECTION_INVALID")
                content: bytes | None = await file.read(MAX_SOURCE_BYTES + 1)
                entries: tuple[MaterialEntry, ...] = ()
            else:
                if (
                    not folder_uploads
                    or len(folder_uploads) > MAX_PACK_ENTRIES
                    or paths_json is None
                ):
                    raise SpriteConversionError("SOURCE_SELECTION_INVALID")
                try:
                    relative_paths = json.loads(paths_json)
                except json.JSONDecodeError as exc:
                    raise SpriteConversionError("SOURCE_SELECTION_INVALID") from exc
                if (
                    not isinstance(relative_paths, list)
                    or len(relative_paths) != len(folder_uploads)
                    or any(not isinstance(path, str) for path in relative_paths)
                ):
                    raise SpriteConversionError("SOURCE_SELECTION_INVALID")
                material_entries: list[MaterialEntry] = []
                total_size = 0
                for upload, relative_path in zip(folder_uploads, relative_paths, strict=True):
                    member_content = await upload.read(MAX_SOURCE_MEMBER_BYTES + 1)
                    total_size += len(member_content)
                    if total_size > MAX_SOURCE_UNCOMPRESSED_BYTES:
                        raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
                    material_entries.append(
                        MaterialEntry(path=relative_path, content=member_content)
                    )
                content = None
                entries = tuple(material_entries)
            preparation = configured.convert_asset(
                content=content,
                entries=entries,
                strategy=cast(ConversionStrategy, strategy),
                candidate_id=candidate_id,
            )
        except SpriteConversionError as exc:
            return _conversion_error(request, exc)
        return JSONResponse(
            attach_preview_urls(_preparation_result(preparation), boundary[1]),
            headers={"Cache-Control": "no-store"},
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
        except (BatchRuntimeError, BatchResolverError, ValueError) as exc:
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
            snapshot, recovery = await asyncio.to_thread(configured.recoverable_analysis_batch)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response({**_batch_snapshot_payload(snapshot), "recovery": recovery})

    @router.post("/onboarding/analysis-batches/{batch_id}/dismiss")
    async def dismiss_analysis_batch(
        request: Request,
        batch_id: str = Path(min_length=1, max_length=64),
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
            await asyncio.to_thread(configured.dismiss_analysis_batch, batch_id=batch_id)
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response({"dismissed": True})

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

    @router.post("/onboarding/analysis-batches/{batch_id}/reanalyze")
    async def reanalyze_batch_items(
        request: Request,
        body: AnalysisBatchReanalyzeRequest,
        batch_id: str = Path(min_length=1, max_length=64),
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
                configured.reanalyze_batch_items,
                batch_id=batch_id,
                item_ids=body.item_ids,
                idempotency_key=body.idempotency_key,
                model_selection=body.model_selection,
                confirm_model_change=body.confirm_model_change,
                expected_selection_generation=body.expected_selection_generation,
            )
        except BatchRuntimeError as exc:
            return _batch_error(request, exc)
        return _batch_response({"batch": _batch_snapshot_payload(snapshot), "created": created})

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


def _local_launch_error(request: Request, error: AdminAuthError | None = None) -> JSONResponse:
    return error_response(
        request,
        status_code=401,
        code="LOCAL_LAUNCH_DENIED",
        message="Authentication failed.",
        retry_after_seconds=error.retry_after_seconds if error is not None else None,
    )


def _config_error(request: Request, error: ConfigValidationError) -> JSONResponse:
    return error_response(
        request,
        status_code=422,
        code="CONFIG_INVALID",
        message="Configuration is invalid.",
        details={"fields": [issue.model_dump(mode="json") for issue in error.issues[:20]]},
    )


def _scene_error(request: Request, error: SceneServiceError) -> JSONResponse:
    status_code = {
        "SCENE_CONFLICT": 409,
        "NOT_FOUND": 404,
        "IMAGE_TOO_LARGE": 413,
        "SCENE_SETTINGS_INVALID": 422,
        "SCENE_ASSET_INVALID": 422,
        "IMAGE_INVALID": 422,
        "IMAGE_FORMAT_INVALID": 422,
        "IMAGE_FORMAT_MISMATCH": 422,
        "IMAGE_DIMENSIONS_INVALID": 422,
        "IMAGE_ANIMATED": 422,
        "IMAGE_FILENAME_INVALID": 422,
        "IMAGE_EXTENSION_INVALID": 422,
        "IMAGE_CONTAINER_INVALID": 422,
        "SERVICE_NOT_READY": 503,
        "PUBLIC_SCENE_UNAVAILABLE": 503,
        "SCENE_DRAFT_WRITE_FAILED": 503,
        "SCENE_ASSET_WRITE_FAILED": 503,
        "SCENE_PUBLISH_FAILED": 503,
        "SCENE_RECOVERY_FAILED": 503,
    }.get(error.code, 422)
    response = error_response(
        request,
        status_code=status_code,
        code=error.code,
        message="Scene operation failed.",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _attach_preview_urls(
    payload: object, *, owner_session_hash: str, store: PreviewAssetStore
) -> object:
    if isinstance(payload, list):
        return [
            _attach_preview_urls(item, owner_session_hash=owner_session_hash, store=store)
            for item in payload
        ]
    if not isinstance(payload, dict):
        return payload
    result = {
        key: _attach_preview_urls(value, owner_session_hash=owner_session_hash, store=store)
        for key, value in payload.items()
    }
    media_types = {
        "png_base64": ("png_url", "image/png"),
        "gif_base64": ("gif_url", "image/gif"),
        "svg_base64": ("svg_url", "image/svg+xml"),
        "webp_base64": ("webp_url", "image/webp"),
    }
    for key, (url_key, media_type) in media_types.items():
        encoded = payload.get(key)
        if not isinstance(encoded, str):
            continue
        try:
            content = base64.b64decode(encoded, validate=True)
            asset_id = store.put(
                owner_session_hash=owner_session_hash,
                content=content,
                media_type=cast(Any, media_type),
            )
        except ValueError, PreviewAssetError:
            continue
        result[url_key] = f"/api/admin/assets/previews/{asset_id}"
    return result


def _asset_error(request: Request, error: SpriteValidationError) -> JSONResponse:
    status = 413 if error.code == "FILE_TOO_LARGE" else 422
    return error_response(
        request,
        status_code=status,
        code="ASSET_INVALID",
        message="Character asset is invalid.",
        details={"reason": error.code},
    )


def _conversion_error(request: Request, error: SpriteConversionError) -> JSONResponse:
    status = (
        413
        if error.code
        in {"SOURCE_FILE_TOO_LARGE", "PACK_LIMIT_EXCEEDED", "SOURCE_DIMENSIONS_UNSAFE"}
        else 422
    )
    return error_response(
        request,
        status_code=status,
        code="ASSET_CONVERSION_FAILED",
        message="Character material could not be converted.",
        details={"reason": error.code},
    )


def _onboarding_error(request: Request, error: GuidedOnboardingError) -> JSONResponse:
    statuses = {
        "VALIDATION_ERROR": 400,
        "AUTHENTICATION_REQUIRED": 401,
        "NOT_FOUND": 404,
        "CONFIG_INVALID": 422,
        "EMPTY_REPOSITORY": 422,
        "RATE_LIMITED": 429,
        "CONCURRENCY_LIMIT": 429,
        "GITHUB_ERROR": 502,
        "PROVIDER_ERROR": 502,
        "MODEL_UNAVAILABLE": 503,
        "SERVICE_NOT_READY": 503,
        "PROVIDER_TIMEOUT": 504,
        "ANALYSIS_TIMEOUT": 504,
        "GITHUB_TIMEOUT": 504,
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


def _model_connection_response(
    payload: dict[str, object], *, status_code: int = 200
) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _model_connection_error(request: Request, error: ModelConnectionError) -> JSONResponse:
    status_code = {
        "NOT_FOUND": 404,
        "CREDENTIAL_REPLACE_REQUIRED": 409,
        "HOST_CONNECTION_REPLACEMENT_REQUIRED": 409,
        "MODEL_CONNECTION_IN_USE": 409,
        "MODEL_SECRET_STORAGE_UNAVAILABLE": 503,
        "SERVICE_NOT_READY": 503,
        "MODEL_CONNECTION_SAVE_FAILED": 503,
        "MODEL_CONNECTION_DELETE_FAILED": 503,
        "PROVIDER_NETWORK_BLOCKED": 422,
        "PROVIDER_NETWORK_UNAVAILABLE": 503,
        "INSECURE_PROVIDER_URL": 422,
        "INVALID_PROVIDER_URL": 422,
    }.get(error.code, 400)
    response = error_response(
        request,
        status_code=status_code,
        code=error.code,
        message="Model connection operation failed.",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _chat_profile_response(payload: dict[str, object], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store"})


def _chat_profile_error(request: Request, error: ChatProfileError) -> JSONResponse:
    status_code = {
        "NOT_FOUND": 404,
        "SERVICE_NOT_READY": 503,
        "CHAT_CONNECTION_REQUIRED": 409,
        "CHAT_PROFILE_ACTIVE_IMMUTABLE": 409,
        "CHAT_PROBE_REQUIRED": 409,
        "CHAT_PROFILE_STALE": 409,
        "CHAT_PROBE_FAILED": 502,
        "CHAT_PROBE_INVALID_RESPONSE": 502,
    }.get(error.code, 400)
    response = error_response(
        request,
        status_code=status_code,
        code=error.code,
        message="Chat profile operation failed.",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _analysis_selection_response(
    payload: dict[str, object], *, status_code: int = 200
) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store"})


def _analysis_selection_error(request: Request, error: AnalysisSelectionError) -> JSONResponse:
    status_code = {
        "SERVICE_NOT_READY": 503,
        "CHAT_PROFILE_NOT_FOUND": 404,
        "EMBEDDING_PROFILE_NOT_FOUND": 404,
        "CHAT_PROBE_REQUIRED": 409,
        "EMBEDDING_PROBE_REQUIRED": 409,
        "ANALYSIS_SELECTION_STALE": 409,
    }.get(error.code, 400)
    response = error_response(
        request,
        status_code=status_code,
        code=error.code,
        message="Analysis model selection failed.",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _embedding_profile_error(request: Request, error: EmbeddingProfileError) -> JSONResponse:
    status_code = {
        "NOT_FOUND": 404,
        "EMPTY_REPOSITORY": 422,
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
    code = (
        error.code
        if isinstance(error, (BatchRuntimeError, BatchResolverError))
        else "VALIDATION_ERROR"
    )
    statuses = {
        "VALIDATION_ERROR": 400,
        "NOT_FOUND": 404,
        "EMPTY_REPOSITORY": 422,
        "ANALYSIS_BATCH_ACTIVE": 409,
        "ANALYSIS_PLAN_STALE": 409,
        "ANALYSIS_RETRY_NOT_AVAILABLE": 409,
        "ANALYSIS_RECOVERY_NOT_AVAILABLE": 409,
        "ANALYSIS_REANALYZE_NOT_AVAILABLE": 409,
        "ANALYSIS_SOURCE_BATCH_NOT_TERMINAL": 409,
        "ANALYSIS_REANALYZE_ITEM_INVALID": 409,
        "ANALYSIS_SUCCESSOR_CONFLICT": 409,
        "ANALYSIS_IDEMPOTENCY_CONFLICT": 409,
        "ANALYSIS_SOURCE_STATE_CHANGED": 409,
        "ANALYSIS_MODEL_SELECTION_STALE": 409,
        "ANALYSIS_MODEL_CHANGE_CONFIRMATION_REQUIRED": 409,
        "ANALYSIS_GENERATION_ATTEMPTS_EXHAUSTED": 409,
        "ANALYSIS_EXECUTION_BUDGET_EXHAUSTED": 409,
        "GITHUB_RATE_LIMITED": 429,
        "RATE_LIMITED": 429,
        "MODEL_UNAVAILABLE": 503,
        "SERVICE_NOT_READY": 503,
    }
    retry_after = error.retry_after_seconds if isinstance(error, BatchResolverError) else None
    return error_response(
        request,
        status_code=statuses.get(code, 502),
        code=code,
        message="Analysis batch operation failed.",
        retry_after_seconds=retry_after,
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
    core, secondary = plan.core_budget, plan.secondary_retry_at
    return {
        "plan_id": plan.plan_id,
        "expires_at": plan.expires_at.isoformat(),
        "selection_hash": plan.selection_hash,
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
        "recovery_maximum_generation_attempts": (snapshot.recovery_maximum_generation_attempts),
        "source_batch_id": snapshot.source_batch_id,
        "analysis_round": snapshot.analysis_round,
        "analysis_model_pair": snapshot.analysis_model_pair,
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
                "reanalyzable": item.reanalyzable,
                "retry_blocker": item.retry_blocker,
                "error_code": item.error_code,
                "error_reason": item.error_reason,
                "failure_stage": item.failure_stage,
                "retry_at": item.retry_at,
                "execution_elapsed_seconds": item.execution_elapsed_seconds,
                "execution_budget_seconds": item.execution_budget_seconds,
                "recovery_execution_budget_seconds": (item.recovery_execution_budget_seconds),
                "generation_attempt_count": item.generation_attempt_count,
                "source_item_id": item.source_item_id,
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
        "connection_revision": profile.connection_revision,
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
        "last_error_message": profile.last_error_message,
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


def _conversion_result(conversion: SpriteConversion) -> dict[str, object]:
    return {
        "status": "converted",
        "asset": _asset_result(conversion.sprite),
        "edge_cleanup": (
            {
                "asset": _asset_result(conversion.cleanup.sprite),
                "affected_frames": [
                    {"state": state, "frame": frame}
                    for state, frame in conversion.cleanup.affected_frames
                ],
                "removed_source_pixels": conversion.cleanup.removed_source_pixels,
            }
            if conversion.cleanup is not None
            else None
        ),
        "conversion": {
            "source_kind": conversion.source_kind,
            "strategy": conversion.strategy,
            "source_frame_sizes": [list(size) for size in conversion.source_frame_sizes],
            "candidate_id": conversion.candidate_id,
            "source_path": conversion.source_path,
            "warnings": [
                {"code": warning.code, "items": list(warning.items)}
                for warning in conversion.warnings
            ],
        },
    }


def _preparation_result(
    preparation: SpriteConversion | SpriteSelection,
) -> dict[str, object]:
    if isinstance(preparation, SpriteConversion):
        return _conversion_result(preparation)
    return {
        "status": "selection_required",
        "discovery": {
            "source_kind": "bundle",
            "strategy": preparation.strategy,
            "ignored_count": preparation.ignored_count,
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "source_path": candidate.source_path,
                    "asset": _asset_result(candidate.conversion.sprite),
                    "conversion": {
                        "source_frame_sizes": [
                            list(size) for size in candidate.conversion.source_frame_sizes
                        ],
                        "warnings": [
                            {"code": warning.code, "items": list(warning.items)}
                            for warning in candidate.conversion.warnings
                        ],
                    },
                }
                for candidate in preparation.candidates
            ],
        },
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


def _is_loopback_host(value: str) -> bool:
    candidate = value.strip().removesuffix(".").casefold()
    if candidate == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def _origin_is_loopback(value: str) -> bool:
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return False
    return host is not None and _is_loopback_host(host)


def _host_is_allowed_loopback(host: str, allowed_origins: frozenset[str]) -> bool:
    try:
        parsed_host = urlsplit(f"//{host}")
    except ValueError:
        return False
    if parsed_host.hostname is None or not _is_loopback_host(parsed_host.hostname):
        return False
    candidate = parsed_host.netloc.casefold()
    return any(urlsplit(origin).netloc.casefold() == candidate for origin in allowed_origins)


def _origin_from_referer(value: str) -> str | None:
    if any(ord(character) <= 32 or ord(character) == 127 for character in value):
        return None
    if "\\" in value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
