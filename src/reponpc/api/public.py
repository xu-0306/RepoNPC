"""Public setup-state HTTP contract for the Phase 1 RepoNPC application."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from reponpc.admin.faq import FaqError, ReviewedFaq
from reponpc.admin.scene import AdminSceneService, SceneServiceError
from reponpc.bundles.archive import BundleError
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.bundles.manifest import ManifestError, parse_bundle_manifest
from reponpc.cards.assets import SpriteValidationError, validate_sprite
from reponpc.chat.service import (
    GroundedChatService,
    delivery_events,
)
from reponpc.i18n.catalog import SUPPORTED_LOCALES, translate
from reponpc.indexing.public_profile import (
    BilingualPublicProfile,
    PublicProfileError,
    localized_public_profile_bytes,
    normalize_public_profile_scene,
    parse_public_profile_bytes,
    validate_public_profile_metadata,
)
from reponpc.observability import get_safe_logger
from reponpc.scene.images import SceneImageError, validate_scene_image
from reponpc.scene.resolve import SceneResolutionError

if TYPE_CHECKING:
    from reponpc.api.visitor_ingress import VisitorChatWorkers

DEFAULT_LOCALE = "zh-TW"
_PUBLIC_INDEX_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_PUBLIC_MODEL_PROVIDERS = frozenset({"ollama", "openai_compatible"})
SVG_ASSET_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
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
    if "rev" in values and (not re.fullmatch(r"(?:0|[1-9][0-9]{0,8})", values["rev"])):
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
    bundle_manager_supplier: Callable[[], object | None] | None = None,
    chat_service: GroundedChatService | None = None,
    chat_service_supplier: Callable[[], GroundedChatService | None] | None = None,
    max_message_characters: int = 2000,
    max_history_messages: int = 6,
    max_history_characters: int = 6000,
    chat_request_limits_supplier: Callable[[], tuple[int, int, int]] | None = None,
    chat_workers: VisitorChatWorkers | None = None,
    keepalive_seconds_supplier: Callable[[], float] = lambda: 15,
    faq_supplier: Callable[[], ReviewedFaq | None] = lambda: None,
    scene_supplier: Callable[[], object | None] = lambda: None,
) -> APIRouter:
    """Create routes bound to one immutable setup/readiness snapshot."""

    router = APIRouter()
    current_state = state_supplier or (lambda: state)
    current_chat_service = chat_service_supplier or (lambda: chat_service)

    def current_bundle_manager() -> BundleManager | None:
        candidate = bundle_manager_supplier() if bundle_manager_supplier is not None else None
        return candidate if isinstance(candidate, BundleManager) else None

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

    @router.get("/api/public/faq")
    async def approved_faq(request: Request, locale: Literal["zh-TW", "en"] = "zh-TW") -> Response:
        faq = faq_supplier()
        if faq is None:
            return unavailable(request, locale)
        try:
            return JSONResponse(
                await asyncio.to_thread(faq.public_payload, locale),
                headers={"Cache-Control": "no-store"},
            )
        except BundleActivationError, FaqError:
            return unavailable(request, locale)

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
                details={
                    "max_message_characters": message_limit,
                    "max_history_messages": history_count_limit,
                    "max_history_characters": history_character_limit,
                },
            )
        import time

        from reponpc.api.visitor_ingress import _chat_response, _message, _stream_error

        service = current_chat_service()
        if not current_state().ready or service is None:
            return error_response(
                request,
                status_code=503,
                code="SERVICE_NOT_READY",
                message=_message(body.locale, "SERVICE_NOT_READY"),
            )
        return await _chat_response(
            request,
            body,
            service,
            identity=request.client.host if request.client is not None else "unknown",
            active_workers=chat_workers,
            deadline=time.monotonic() + getattr(service, "timeout_seconds", 180.0),
            keepalive_seconds=keepalive_seconds_supplier(),
            project_event=lambda _event, payload: payload,
            stream_error=_stream_error,
            events=delivery_events,
            allow_retry=True,
        )

    @router.get("/api/public/owner-statements/{revision}/{evidence_id}")
    async def owner_statement(request: Request, revision: str, evidence_id: str) -> Response:
        from reponpc.bundles.manager import BundleActivationError, BundleManager
        from reponpc.domain.evidence import COMMIT_RE, EVIDENCE_ID_RE

        manager = bundle_manager_supplier() if bundle_manager_supplier is not None else None
        if (
            not COMMIT_RE.fullmatch(revision)
            or not EVIDENCE_ID_RE.fullmatch(evidence_id)
            or not isinstance(manager, BundleManager)
        ):
            return Response(status_code=404)
        try:
            with manager.acquire() as index:
                evidence = index.evidence(evidence_id)
                if (
                    evidence is None
                    or evidence.evidence_class != "OWNER_ASSERTION"
                    or evidence.repository_slug != "local/portfolio"
                    or evidence.commit_sha != revision
                    or evidence.metadata.get("origin") != "local"
                ):
                    return Response(status_code=404)
                return Response(
                    content="Owner-confirmed statement / 本人確認的陳述\n\n" + evidence.content,
                    media_type="text/plain",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                )
        except BundleActivationError:
            return Response(status_code=404)

    @router.get("/api/public/profile")
    async def profile(request: Request) -> Response:
        query = _validated_query(request, {"locale"})
        if isinstance(query, JSONResponse):
            return query
        locale = query.get("locale", DEFAULT_LOCALE)
        scene_service = scene_supplier()
        if scene_service is not None:
            try:
                with scene_service.published_profile() as snapshot:  # type: ignore[attr-defined]
                    body = localized_public_profile_bytes(snapshot.document, locale)
                    selected_version = snapshot.bundle_id
            except SceneServiceError, BundleActivationError:
                return unavailable(request, locale)
            return Response(
                content=body,
                media_type="application/json",
                headers={"ETag": _etag(selected_version, f"profile:{locale}", body)},
            )
        manager = current_bundle_manager()
        if manager is not None:
            try:
                with _leased_public_profile(manager) as snapshot:
                    body = localized_public_profile_bytes(snapshot["document"], locale)
                    selected_version = snapshot["bundle_id"]
            except (
                OSError,
                BundleActivationError,
                BundleError,
                ManifestError,
                PublicProfileError,
                SpriteValidationError,
                SceneResolutionError,
                ValueError,
            ):
                return unavailable(request, locale)
            return Response(
                content=body,
                media_type="application/json",
                headers={"ETag": _etag(selected_version, f"profile:{locale}", body)},
            )
        directory = public_directory()
        if directory is None:
            return unavailable(request, locale)
        try:
            payload = _public_profile_from_directory(
                directory, index_version=version(), built_at=None, repository_count=None
            )
            body = localized_public_profile_bytes(payload, locale)
        except OSError, PublicProfileError, SpriteValidationError, SceneResolutionError:
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
        requested_revision = int(query["rev"]) if "rev" in query else None
        scene_service = scene_supplier()
        if scene_service is not None:
            try:
                with scene_service.published_profile() as snapshot:  # type: ignore[attr-defined]
                    if (
                        requested_revision is not None
                        and requested_revision != snapshot.character_revision
                    ):
                        return Response(status_code=404)
                    payload = snapshot.sprite_content
                    selected_version = snapshot.bundle_id
            except SceneServiceError, BundleActivationError:
                return unavailable(request, DEFAULT_LOCALE)
            return Response(
                payload,
                media_type="image/png",
                headers={
                    "ETag": _etag(
                        selected_version, f"character:{snapshot.character_revision}", payload
                    )
                },
            )
        manager = current_bundle_manager()
        if manager is not None:
            try:
                with _leased_public_profile(manager) as snapshot:
                    document = snapshot["document"]
                    revision = document.character.revision
                    if requested_revision is not None and requested_revision != revision:
                        return Response(status_code=404)
                    payload = snapshot["sprite_content"]
                    selected_version = snapshot["bundle_id"]
            except (
                OSError,
                BundleActivationError,
                BundleError,
                ManifestError,
                PublicProfileError,
                SpriteValidationError,
                SceneResolutionError,
                ValueError,
            ):
                return unavailable(request, DEFAULT_LOCALE)
            return Response(
                payload,
                media_type="image/png",
                headers={"ETag": _etag(selected_version, f"character:{revision}", payload)},
            )
        directory = public_directory()
        if directory is None:
            return unavailable(request, DEFAULT_LOCALE)
        try:
            profile = _public_profile_from_directory(
                directory, index_version=version(), built_at=None, repository_count=None
            )
            revision = profile.character.revision
            if requested_revision is not None and requested_revision != revision:
                return Response(status_code=404)
            payload = (directory / "character.png").read_bytes()
            canonical = validate_sprite(payload)
            if canonical.content != payload:
                return Response(status_code=404)
            return Response(
                payload,
                media_type="image/png",
                headers={"ETag": _etag(version(), f"character:{revision}", payload)},
            )
        except OSError, PublicProfileError, SpriteValidationError, SceneResolutionError:
            return unavailable(request, DEFAULT_LOCALE)

    @router.api_route("/api/public/scene-background", methods=["GET", "HEAD", "OPTIONS"])
    async def scene_background(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers={"Allow": "GET, HEAD, OPTIONS"})
        query = _validated_query(request, {"rev"})
        if isinstance(query, JSONResponse) or "rev" not in query:
            return query if isinstance(query, JSONResponse) else Response(status_code=404)
        revision = int(query["rev"])
        scene_service = scene_supplier()
        manager = current_bundle_manager()
        if scene_service is None and manager is not None:
            scene_service = AdminSceneService(
                manager=manager,
                database=None,
                data_directory=manager.data_directory,
            )
        if scene_service is not None:
            try:
                result = scene_service.background_for_revision(revision)  # type: ignore[attr-defined]
            except SceneServiceError, BundleActivationError:
                return Response(status_code=404)
            if result is None:
                return Response(status_code=404)
            payload, extension, bundle_id = result
            media_type = "image/webp" if extension == "webp" else "image/png"
            return Response(
                b"" if request.method == "HEAD" else payload,
                media_type=media_type,
                headers={
                    "ETag": _etag(bundle_id, f"scene-background:{revision}", payload),
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                    "Content-Length": str(len(payload)),
                },
            )
        if manager is None:
            return Response(status_code=404)
        return Response(status_code=404)

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


@contextmanager
def _leased_public_profile(manager: BundleManager) -> Iterator[dict[str, Any]]:
    """Read a validated public profile and its canonical sheet under one lease."""

    with manager.acquire_snapshot() as (_index, bundle_id, public_directory):
        yield _bundle_profile_snapshot(bundle_id, public_directory)


def _bundle_profile_snapshot(bundle_id: str, public_directory: Path) -> dict[str, Any]:
    manifest = parse_bundle_manifest((public_directory.parent / "manifest.json").read_bytes())
    if manifest.bundle_id != bundle_id:
        raise ManifestError("bundle identity does not match its active lease")
    sprite_content = (public_directory / "character.png").read_bytes()
    canonical = validate_sprite(sprite_content)
    if canonical.content != sprite_content:
        raise SpriteValidationError("SPRITE_NOT_CANONICAL")
    document = parse_public_profile_bytes((public_directory / "profile.json").read_bytes())
    validate_public_profile_metadata(
        document,
        index_version=bundle_id,
        built_at=manifest.built_at,
        repository_count=dict(manifest.statistics)["repositories"],
    )
    background_content = _bundle_scene_background(public_directory, manifest, document)
    document = normalize_public_profile_scene(
        document,
        sprite_content=sprite_content,
        background_content=background_content,
    )
    return {
        "bundle_id": bundle_id,
        "document": document,
        "sprite_content": sprite_content,
        "background_content": background_content,
    }


def _public_profile_from_directory(
    public_directory: Path,
    *,
    index_version: str,
    built_at: str | None,
    repository_count: int | None,
) -> BilingualPublicProfile:
    sprite_content = (public_directory / "character.png").read_bytes()
    canonical = validate_sprite(sprite_content)
    if canonical.content != sprite_content:
        raise SpriteValidationError("SPRITE_NOT_CANONICAL")
    document = parse_public_profile_bytes((public_directory / "profile.json").read_bytes())
    validate_public_profile_metadata(
        document,
        index_version=index_version,
        built_at=built_at,
        repository_count=repository_count,
    )
    background_content: bytes | None = None
    manifest_path = public_directory.parent / "manifest.json"
    if manifest_path.is_file():
        manifest = parse_bundle_manifest(manifest_path.read_bytes())
        if manifest.bundle_id != index_version:
            raise ManifestError("bundle identity does not match its profile")
        background_content = _bundle_scene_background(public_directory, manifest, document)
    return normalize_public_profile_scene(
        document, sprite_content=sprite_content, background_content=background_content
    )


def _bundle_scene_background(
    public_directory: Path, manifest: Any, document: BilingualPublicProfile
) -> bytes | None:
    scene = document.character.scene
    paths = [item.path for item in manifest.files if item.path.startswith("public/scene/")]
    if scene is None or scene.background_url is None:
        if paths:
            raise ManifestError("scene background is not declared by the public profile")
        return None
    if len(paths) != 1:
        raise ManifestError("scene background manifest entry is missing")
    match = re.fullmatch(r"public/scene/([0-9a-f]{64})\.(png|webp)", paths[0])
    if match is None:
        raise ManifestError("scene background manifest entry is invalid")
    content = (public_directory / paths[0].removeprefix("public/")).read_bytes()
    image = validate_scene_image(content, filename=f"background.{match.group(2)}")
    if image.content != content or image.sha256 != match.group(1):
        raise SceneImageError("SCENE_IMAGE_NOT_CANONICAL")
    return content


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
        headers.update(
            {
                "Content-Security-Policy": SVG_ASSET_CSP,
                "X-Content-Type-Options": "nosniff",
            }
        )
    return Response(content=payload, media_type=content_type, headers=headers)
