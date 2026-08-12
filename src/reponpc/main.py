"""Production FastAPI entrypoint for RepoNPC."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.github import GitHubAdminClient, UrllibGitHubAdminTransport
from reponpc.admin.operations import AdminOperations
from reponpc.api.admin import create_admin_router
from reponpc.api.public import SetupState, create_public_router, error_response
from reponpc.bundles.manager import BundleManager
from reponpc.bundles.updater import BundleUpdater, UrllibBundleTransport
from reponpc.chat.limits import ChatLimits
from reponpc.chat.service import GroundedChatService
from reponpc.config.environment import (
    EnvironmentSettings,
    EnvironmentValidationError,
    load_environment,
)
from reponpc.i18n.catalog import translate
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.providers import (
    ChatProvider,
    OllamaChatProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    ProviderCapabilities,
    RuntimeEmbeddingProvider,
)
from reponpc.providers.local_sentence_transformers import (
    LocalSentenceTransformersEmbeddingProvider,
)
from reponpc.providers.runtime import LocalRuntimeEmbeddingProvider, ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError


class PublicBoundaryMiddleware:
    """Attach safe public response headers without buffering ASGI disconnects."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request_headers = Headers(scope=scope)
        scope.setdefault("state", {})["request_id"] = _request_id(
            request_headers.get("X-Request-ID")
        )

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = scope["state"]["request_id"]
                response_headers["Cache-Control"] = "no-store"
                for header, value in _SECURITY_HEADERS.items():
                    if header not in response_headers:
                        response_headers[header] = value
            await send(message)

        await self._app(scope, receive, send_with_headers)


_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; connect-src 'self'; font-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; img-src 'self'; script-src 'self'; "
        "style-src 'self'"
    ),
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class _BuiltWebFiles(StaticFiles):
    """Serve only bundled files and use index.html for extensionless SPA routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code != 404:
            return response
        path_parts = Path(path).parts
        is_extensionless_route = (
            bool(path) and not Path(path).suffix and not path.startswith("assets/")
        )
        if not is_extensionless_route or any(part in {".", ".."} for part in path_parts):
            return response
        index_file = Path(self.directory or "") / "index.html"
        return FileResponse(index_file)


def _default_web_dist() -> Path:
    return Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"


def _request_id(candidate: str | None) -> str:
    if candidate is not None:
        try:
            return str(uuid.UUID(candidate))
        except (ValueError, AttributeError):
            pass
    return str(uuid.uuid4())


def create_app(
    *,
    setup_state: SetupState | None = None,
    runtime_database: RuntimeDatabase | None = None,
    bundle_manager: BundleManager | None = None,
    bundle_updater: BundleUpdater | None = None,
    bundle_poll_seconds: int = 300,
    provider_runtime: ProviderRuntime | None = None,
    provider_adapter: str | None = None,
    provider_health_seconds: int = 60,
    chat_service: GroundedChatService | None = None,
    max_message_characters: int = 2000,
    max_history_messages: int = 6,
    max_history_characters: int = 6000,
    web_dist: Path | None = None,
    admin_session_service: AdminSessionService | None = None,
    admin_origins: tuple[str, ...] = (),
    admin_operations: AdminOperations | None = None,
) -> FastAPI:
    """Construct the real application and its optional immutable-bundle lifecycle."""

    state = setup_state or SetupState()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime_storage_usable = bool(
            getattr(application.state, "runtime_storage_usable", state.runtime_storage_usable)
        )
        configured_database = getattr(application.state, "runtime_database", None)
        if configured_database is not None:
            try:
                configured_database.initialize()
            except RuntimeDatabaseError:
                runtime_storage_usable = False
        application.state.reponpc = replace(
            state,
            runtime_storage_usable=runtime_storage_usable,
        )
        stopped = asyncio.Event()

        provider = application.state.provider_runtime

        def poll_and_publish_provider_state() -> None:
            provider_status = provider.poll_health()
            current_state = application.state.reponpc
            application.state.reponpc = replace(
                current_state,
                model_ready=provider_status.ready,
                model_provider=application.state.provider_adapter,
                model_last_checked_at=provider_status.checked_at,
            )

        async def provider_lifecycle() -> None:
            while not stopped.is_set():
                try:
                    await asyncio.wait_for(
                        stopped.wait(),
                        timeout=getattr(
                            application.state,
                            "provider_health_seconds",
                            provider_health_seconds,
                        ),
                    )
                except TimeoutError:
                    await asyncio.to_thread(poll_and_publish_provider_state)

        polling_tasks: list[asyncio.Task[None]] = []
        if provider is not None:
            await asyncio.to_thread(poll_and_publish_provider_state)
            polling_tasks.append(asyncio.create_task(provider_lifecycle()))

        updater = application.state.bundle_updater
        manager = application.state.bundle_manager

        def poll_and_publish_state() -> None:
            updater.poll_once()
            runtime_state = configured_database.bundle_state() if configured_database else None
            bundle_status = manager.status()
            current_state = application.state.reponpc
            application.state.reponpc = replace(
                current_state,
                index_ready=bundle_status.active_bundle_id is not None,
                index_version=bundle_status.active_bundle_id,
                index_last_checked_at=(
                    runtime_state.last_checked_at if runtime_state is not None else None
                ),
                index_update_error=(
                    runtime_state.safe_update_error if runtime_state is not None else None
                ),
                public_directory=getattr(manager, "active_public_directory", lambda: None)(),
            )

        async def polling_lifecycle() -> None:
            while not stopped.is_set():
                try:
                    await asyncio.wait_for(
                        stopped.wait(),
                        timeout=getattr(
                            application.state, "bundle_poll_seconds", bundle_poll_seconds
                        ),
                    )
                except TimeoutError:
                    await asyncio.to_thread(poll_and_publish_state)

        if updater is not None and manager is not None:
            await asyncio.to_thread(poll_and_publish_state)
            polling_tasks.append(asyncio.create_task(polling_lifecycle()))
        try:
            yield
        finally:
            stopped.set()
            for polling_task in polling_tasks:
                polling_task.cancel()
            for polling_task in polling_tasks:
                with suppress(asyncio.CancelledError):
                    await polling_task

    application = FastAPI(
        title="RepoNPC",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @application.exception_handler(RequestValidationError)
    async def public_validation_error(request: Request, exc: RequestValidationError) -> Response:
        locale = "en"
        if isinstance(exc.body, dict) and exc.body.get("locale") in {"zh-TW", "en"}:
            locale = str(exc.body["locale"])
        fields: list[dict[str, str]] = []
        for error in exc.errors():
            location = error.get("loc", ())
            safe_path = ".".join(str(part) for part in location if isinstance(part, (str, int)))[
                :200
            ]
            fields.append({"path": safe_path or "request", "code": "invalid"})
        return error_response(
            request,
            status_code=400,
            code="VALIDATION_ERROR",
            message=translate(locale, "validation_error", field="request", reason="invalid"),
            details={"fields": fields[:20]},
        )

    application.add_middleware(PublicBoundaryMiddleware)

    application.state.reponpc = state
    application.state.runtime_storage_usable = state.runtime_storage_usable
    application.state.runtime_database = runtime_database
    application.state.bundle_manager = bundle_manager
    application.state.bundle_updater = bundle_updater
    application.state.bundle_poll_seconds = bundle_poll_seconds
    application.state.provider_runtime = provider_runtime
    application.state.provider_adapter = provider_adapter
    application.state.provider_health_seconds = provider_health_seconds
    application.state.chat_service = chat_service
    application.state.max_message_characters = max_message_characters
    application.state.max_history_messages = max_history_messages
    application.state.max_history_characters = max_history_characters
    application.state.admin_session_service = admin_session_service
    application.state.admin_origins = admin_origins
    application.state.admin_operations = admin_operations
    application.include_router(
        create_public_router(
            state,
            state_supplier=lambda: application.state.reponpc,
            chat_service_supplier=lambda: application.state.chat_service,
            max_message_characters=max_message_characters,
            max_history_messages=max_history_messages,
            max_history_characters=max_history_characters,
            chat_request_limits_supplier=lambda: (
                application.state.max_message_characters,
                application.state.max_history_messages,
                application.state.max_history_characters,
            ),
        )
    )
    application.include_router(
        create_admin_router(
            service_supplier=lambda: application.state.admin_session_service,
            origins_supplier=lambda: application.state.admin_origins,
            operations_supplier=lambda: application.state.admin_operations,
        )
    )
    build_dir = web_dist or _default_web_dist()
    if build_dir.is_dir() and (build_dir / "index.html").is_file():
        application.mount("/", _BuiltWebFiles(directory=build_dir, html=True), name="web")
    return application


app = create_app()


def run() -> None:
    """Run the production ASGI entrypoint using validated host settings."""

    try:
        settings = load_environment()
    except EnvironmentValidationError as exc:
        raise SystemExit("deployment environment is invalid") from exc
    try:
        runtime_database = RuntimeDatabase(
            settings.data_dir,
            busy_timeout_ms=settings.sqlite_busy_timeout_ms,
        )
        runtime_database.initialize()
        app.state.runtime_database = runtime_database
        app.state.runtime_storage_usable = True
        _configure_admin(settings, runtime_database)
        _configure_bundle_lifecycle(settings, runtime_database)
        if hasattr(settings, "chat_provider"):
            _configure_provider_lifecycle(settings, runtime_database)
    except RuntimeDatabaseError:
        app.state.runtime_database = None
        app.state.runtime_storage_usable = False
    uvicorn.run("reponpc.main:app", host=settings.host, port=settings.port, factory=False)


def _configure_admin(settings: EnvironmentSettings, runtime_database: RuntimeDatabase) -> None:
    password_hash = getattr(settings, "admin_password_hash", None)
    secrets = getattr(settings, "secrets", {})
    identity_key = secrets.get("ip_hash_key")
    github_token = secrets.get("github_token")
    if password_hash is None or identity_key is None or github_token is None:
        app.state.admin_session_service = None
        app.state.admin_origins = ()
        app.state.admin_operations = None
        return
    app.state.admin_session_service = AdminSessionService(
        database=runtime_database,
        username=settings.admin_username,
        password_hash=password_hash.reveal(),
        identity_hmac_key=hashlib.sha256(identity_key.reveal().encode("utf-8")).digest(),
        idle_minutes=settings.admin_idle_minutes,
        absolute_hours=settings.admin_absolute_hours,
    )
    app.state.admin_origins = (settings.public_base_url,)
    app.state.admin_operations = AdminOperations(
        github=GitHubAdminClient(
            repository=settings.config_repository,
            branch=settings.config_branch,
            workflow=settings.index_workflow,
            token=github_token.reveal(),
            transport=UrllibGitHubAdminTransport(),
            api_url=settings.github_api_url,
        ),
        database=runtime_database,
        public_base_url=settings.public_base_url,
    )


def _configure_bundle_lifecycle(
    settings: EnvironmentSettings,
    runtime_database: RuntimeDatabase,
) -> None:
    """Attach the real polling owner only when immutable discovery is configured."""

    # Keep the production startup path compatible with the smallest validated
    # settings surface used when immutable bundle discovery is not configured.
    manifest_url = getattr(settings, "index_manifest_url", None)
    if not manifest_url:
        return
    embedding = EmbeddingIdentity(
        adapter=settings.embedding_provider,
        model_id=settings.embedding_model,
        dimension=settings.embedding_dimension,
        normalized=settings.embedding_normalized,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )
    allowed_hosts = frozenset({"api.github.com", "github.com", "raw.githubusercontent.com"})
    manager = BundleManager(
        data_directory=settings.data_dir,
        runtime_database=runtime_database,
        expected_embedding=embedding,
        keep_valid_bundles=settings.keep_valid_bundles,
    )
    app.state.bundle_manager = manager
    app.state.bundle_updater = BundleUpdater(
        manifest_url=manifest_url,
        transport=UrllibBundleTransport(allowed_hosts=allowed_hosts),
        manager=manager,
        runtime_database=runtime_database,
        expected_embedding=embedding,
        max_bundle_bytes=settings.max_bundle_bytes,
        allowed_hosts=allowed_hosts,
        data_directory=settings.data_dir,
    )
    app.state.bundle_poll_seconds = settings.index_poll_seconds


def _configure_provider_lifecycle(
    settings: EnvironmentSettings,
    runtime_database: RuntimeDatabase,
) -> None:
    """Attach exactly the selected chat/embedding adapters without fallback."""

    embedding_identity = EmbeddingIdentity(
        adapter=settings.embedding_provider,
        model_id=settings.embedding_model,
        dimension=settings.embedding_dimension,
        normalized=settings.embedding_normalized,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )
    capabilities = ProviderCapabilities(
        streaming=False,
        system_role=True,
        structured_output=True,
        usage_reporting=True,
        health_check=True,
        max_context_tokens=settings.chat_max_context_tokens,
        max_output_tokens=settings.chat_max_output_tokens,
    )
    chat_key = settings.secrets.get("chat_api_key")
    embedding_key = settings.secrets.get("embedding_api_key")
    if settings.chat_provider == "ollama":
        chat: ChatProvider = OllamaChatProvider(
            settings.chat_base_url,
            settings.chat_model,
            capabilities,
        )
    else:
        chat = OpenAICompatibleChatProvider(
            settings.chat_base_url,
            settings.chat_model,
            capabilities,
            api_key=chat_key.reveal() if chat_key is not None else None,
        )
    if settings.embedding_provider == "ollama":
        embedding: RuntimeEmbeddingProvider = OllamaEmbeddingProvider(
            settings.embedding_base_url,
            settings.embedding_model,
            embedding_identity,
        )
    elif settings.embedding_provider == "openai_compatible":
        embedding = OpenAICompatibleEmbeddingProvider(
            settings.embedding_base_url,
            settings.embedding_model,
            embedding_identity,
            api_key=embedding_key.reveal() if embedding_key is not None else None,
        )
    else:
        local = LocalSentenceTransformersEmbeddingProvider(
            model_id=settings.embedding_model,
            dimension=settings.embedding_dimension,
            normalized=settings.embedding_normalized,
            query_prefix=embedding_identity.query_prefix,
            passage_prefix=embedding_identity.passage_prefix,
        )
        embedding = LocalRuntimeEmbeddingProvider(local)
    providers = ProviderRuntime(chat=chat, embedding=embedding)
    app.state.provider_runtime = providers
    app.state.provider_adapter = settings.chat_provider
    app.state.provider_health_seconds = settings.provider_health_seconds
    app.state.max_message_characters = settings.max_message_characters
    app.state.max_history_messages = settings.max_history_messages
    app.state.max_history_characters = settings.max_history_characters
    manager = app.state.bundle_manager
    ip_hash_key = settings.secrets.get("ip_hash_key")
    if manager is None or ip_hash_key is None:
        app.state.chat_service = None
        return
    limits = ChatLimits(
        runtime_database,
        ip_hash_key=ip_hash_key.reveal().encode(),
        requests_per_minute=settings.rate_limit_requests_per_minute,
        daily_budget=settings.daily_chat_request_budget,
        global_concurrency=settings.global_chat_concurrency,
    )
    app.state.chat_service = GroundedChatService(
        bundles=manager,
        providers=providers,
        limits=limits,
        max_output_tokens=settings.chat_max_output_tokens,
        timeout_seconds=settings.chat_timeout_seconds,
    )
