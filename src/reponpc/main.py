"""Production FastAPI entrypoint for RepoNPC."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from reponpc.admin.analysis_selection import AnalysisModelPair, AnalysisSelectionRegistry
from reponpc.admin.auth import AdminSessionService
from reponpc.admin.batch_execution import PinnedBatchItemRunner
from reponpc.admin.batch_resolver import (
    ArchiveSafetyLimits,
    BatchCapacity,
    BatchPreflightPlanner,
    GitHubArchiveSource,
    GitHubRateLimiter,
    GitHubRESTMetadataResolver,
    UrllibGitHubArchiveTransport,
    UrllibGitHubRESTTransport,
)
from reponpc.admin.batch_runtime import (
    BatchRuntimeStore,
    SQLiteGitHubRateStateStore,
    SQLiteGitHubResolutionCache,
)
from reponpc.admin.batches import AnalysisBatchService, BatchStageGates
from reponpc.admin.chat_profiles import ChatProfile, ChatProfileRegistry
from reponpc.admin.embedding_profiles import (
    EmbeddingProfile,
    EmbeddingProfileError,
    EmbeddingProfileRegistry,
)
from reponpc.admin.embedding_reindex import (
    EmbeddingReindexCoordinator,
    ProductionFrozenProfileBuilder,
)
from reponpc.admin.github import GitHubAdminClient, UrllibGitHubAdminTransport
from reponpc.admin.model_connections import (
    ModelConnectionError,
    ModelConnectionRegistry,
    ProtectedModelSecretStore,
)
from reponpc.admin.model_operations import OllamaModelOperationCoordinator
from reponpc.admin.onboarding import GuidedOnboardingService
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
from reponpc.indexing.github import GitHubSourceResolver
from reponpc.indexing.sources import EmbeddingIdentity, EmbeddingProvider
from reponpc.providers import (
    ChatProvider,
    OllamaChatProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    ProviderCapabilities,
    ProviderError,
    RuntimeEmbeddingProvider,
)
from reponpc.providers.runtime import ProviderRuntime
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
        request_path = str(scope.get("path", path))
        if request_path == "/api" or request_path.startswith("/api/"):
            return await super().get_response(path, scope)
        if not self._is_spa_route(path):
            return await super().get_response(path, scope)
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return FileResponse(Path(self.directory or "") / "index.html")
        if response.status_code != 404:
            return response
        return FileResponse(Path(self.directory or "") / "index.html")

    @staticmethod
    def _is_spa_route(path: str) -> bool:
        normalized_path = path.lstrip("/")
        path_parts = Path(normalized_path).parts
        return (
            bool(normalized_path)
            and not Path(normalized_path).suffix
            and not normalized_path.startswith(("api/", "assets/"))
            and not any(part in {".", ".."} for part in path_parts)
        )


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
    chat_limits: ChatLimits | None = None,
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
            registry = getattr(application.state, "embedding_profile_registry", None)
            profile_ready = registry is None or registry.active_matches(
                provider.embedding.identity()
            )
            current_state = application.state.reponpc
            application.state.reponpc = replace(
                current_state,
                model_ready=provider_status.ready and profile_ready,
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
            reindex = getattr(application.state, "embedding_reindex_coordinator", None)
            if reindex is not None:
                await asyncio.to_thread(reindex.shutdown)
            model_operations = getattr(application.state, "ollama_model_operations", None)
            if model_operations is not None:
                await asyncio.to_thread(model_operations.shutdown)

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
    application.state.analysis_runtime_supplier = lambda: application.state.provider_runtime
    application.state.provider_adapter = provider_adapter
    application.state.provider_health_seconds = provider_health_seconds
    application.state.chat_service = chat_service
    application.state.chat_limits = chat_limits
    application.state.max_message_characters = max_message_characters
    application.state.max_history_messages = max_history_messages
    application.state.max_history_characters = max_history_characters
    application.state.admin_session_service = admin_session_service
    application.state.admin_origins = admin_origins
    application.state.admin_operations = admin_operations
    application.state.chat_profile_registry = (
        admin_operations.chat_profiles if admin_operations is not None else None
    )
    application.state.github_rate_limiter = None
    application.state.embedding_reindex_coordinator = None
    application.state.ollama_model_operations = (
        admin_operations.ollama_model_operations if admin_operations is not None else None
    )
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
            _configure_embedding_reindex(settings)
        batch_service = getattr(app.state, "analysis_batch_service", None)
        if batch_service is not None:
            batch_service.recover()
    except RuntimeDatabaseError:
        app.state.runtime_database = None
        app.state.runtime_storage_usable = False
    uvicorn.run(
        "reponpc.main:app",
        host=settings.host,
        port=settings.port,
        factory=False,
        proxy_headers=settings.deployment_profile != "loopback_evaluation",
    )


def _configure_admin(settings: EnvironmentSettings, runtime_database: RuntimeDatabase) -> None:
    password_hash = getattr(settings, "admin_password_hash", None)
    secrets = getattr(settings, "secrets", {})
    identity_key = secrets.get("ip_hash_key")
    github_token = secrets.get("github_token")
    if identity_key is None:
        app.state.admin_session_service = None
        app.state.admin_origins = ()
        app.state.admin_operations = None
        app.state.github_rate_limiter = None
        return
    app.state.admin_session_service = AdminSessionService(
        database=runtime_database,
        username=settings.admin_username if password_hash is not None else None,
        password_hash=password_hash.reveal() if password_hash is not None else None,
        identity_hmac_key=hashlib.sha256(identity_key.reveal().encode("utf-8")).digest(),
        idle_minutes=settings.admin_idle_minutes,
        absolute_hours=settings.admin_absolute_hours,
        deployment_profile=settings.deployment_profile,
    )
    app.state.admin_origins = (settings.public_base_url,)
    app.state.chat_limits = ChatLimits(
        runtime_database,
        ip_hash_key=hashlib.sha256(identity_key.reveal().encode()).digest(),
        requests_per_minute=settings.rate_limit_requests_per_minute,
        daily_budget=settings.daily_chat_request_budget,
        global_concurrency=settings.global_chat_concurrency,
    )
    github = None
    if github_token is not None:
        github = GitHubAdminClient(
            repository=settings.config_repository,
            branch=settings.config_branch,
            workflow=settings.index_workflow,
            token=github_token.reveal(),
            transport=UrllibGitHubAdminTransport(),
            api_url=settings.github_api_url,
        )
    rate_limiter = GitHubRateLimiter(
        persistence=SQLiteGitHubRateStateStore(runtime_database),
    )
    app.state.github_rate_limiter = rate_limiter
    resolution_cache = SQLiteGitHubResolutionCache(runtime_database)
    onboarding = GuidedOnboardingService(
        source_resolver=GitHubSourceResolver(
            api_base_url=settings.github_api_url,
            rate_limiter=rate_limiter,
        ),
        providers_supplier=lambda: app.state.analysis_runtime_supplier(),
        limits_supplier=lambda: app.state.chat_limits,
        staging_root=settings.data_dir / "onboarding-staging",
        provider_timeout_seconds=settings.chat_timeout_seconds,
    )
    capacity = BatchCapacity(
        github_requests=1,
        archive_staging=1,
        index_work=2,
        generation=max(1, settings.global_chat_concurrency),
        whole_job_items=4,
    )
    stage_gates = BatchStageGates(capacity)

    archive_source = GitHubArchiveSource(
        transport=UrllibGitHubArchiveTransport(timeout_seconds=20.0),
        limiter=rate_limiter,
        staging_root=settings.data_dir / "analysis-archive-staging",
        limits=ArchiveSafetyLimits(
            max_compressed_bytes=50 * 1024 * 1024,
            max_uncompressed_bytes=200 * 1024 * 1024,
            max_entries=10_000,
            max_single_file_bytes=2 * 1024 * 1024,
        ),
    )
    store = BatchRuntimeStore(runtime_database)
    runner = PinnedBatchItemRunner(
        store=store,
        source=archive_source,
        onboarding=onboarding,
        gates=stage_gates,
        runtime_resolver=lambda pair: app.state.analysis_frozen_runtime_resolver(pair),
    )
    analysis_batches = AnalysisBatchService(
        store=store,
        planner=BatchPreflightPlanner(
            resolver=GitHubRESTMetadataResolver(
                transport=UrllibGitHubRESTTransport(timeout_seconds=20.0),
                limiter=rate_limiter,
                cache=resolution_cache,
            ),
            limiter=rate_limiter,
        ),
        provider_ready_supplier=lambda: (
            app.state.analysis_runtime_supplier() is not None and app.state.chat_limits is not None
        ),
        capacity=capacity,
        stage_gates=stage_gates,
        runner=runner,
        analysis_pair_supplier=lambda: analysis_selection.frozen_pair(),
        embedding_identity=settings.embedding_model,
        chat_model=settings.chat_model,
    )
    app.state.analysis_batch_service = analysis_batches
    embedding_identity = _configured_embedding_identity(settings)

    def resolve_embedding_profile(
        profile: EmbeddingProfile,
    ) -> RuntimeEmbeddingProvider | None:
        environment_provider = _environment_embedding_provider(settings, profile)
        if environment_provider is not None:
            return environment_provider
        if profile.connection_reference == "environment":
            return None
        try:
            revision = model_connections.revision_for(
                profile.connection_reference, profile.connection_revision
            )
            if revision.provider != profile.provider:
                return None
            return _embedding_provider_from_connection(
                revision.provider,
                revision.secret.base_url,
                revision.secret.api_key,
                profile.identity if profile.dimension is not None else None,
                model=profile.model_id,
                query_prefix=profile.query_prefix,
                passage_prefix=profile.passage_prefix,
            )
        except ModelConnectionError:
            return None

    def profile_bundle_compatible(profile: EmbeddingProfile) -> bool:
        manager = app.state.bundle_manager
        return (
            manager is not None
            and manager.status().active_bundle_id is not None
            and manager.active_embedding_identity() == profile.identity
        )

    embedding_profiles = EmbeddingProfileRegistry(
        database=runtime_database,
        provider_resolver=resolve_embedding_profile,
        activation_compatible=profile_bundle_compatible,
    )
    model_connections = ModelConnectionRegistry(
        runtime_database,
        ProtectedModelSecretStore(settings.data_dir / "model-secrets" / "master.key"),
    )
    environment_embedding_connection = None
    for role, provider, base_url, secret_name, model in (
        (
            "chat",
            settings.chat_provider,
            settings.chat_base_url,
            "chat_api_key",
            settings.chat_model,
        ),
        (
            "embedding",
            settings.embedding_provider,
            settings.embedding_base_url,
            "embedding_api_key",
            settings.embedding_model,
        ),
    ):
        if provider not in {"ollama", "openai_compatible", "vllm"} or not base_url or not model:
            continue
        secret = settings.secrets.get(secret_name)
        connection = model_connections.ensure_host_managed(
            f"environment-{role}",
            display_name=f"Environment {role}",
            provider=provider,
            base_url=base_url,
            api_key=secret.reveal() if secret is not None else None,
        )
        if role == "embedding":
            environment_embedding_connection = connection
    if (
        settings.embedding_provider in {"ollama", "openai_compatible", "vllm"}
        and environment_embedding_connection is not None
        and environment_embedding_connection.source == "host-managed"
    ):
        embedding_profiles.ensure_environment_profile(
            provider=settings.embedding_provider,
            identity=embedding_identity,
            connection_reference=environment_embedding_connection.connection_id,
            connection_revision=environment_embedding_connection.revision,
        )

    def resolve_chat_profile(profile: ChatProfile) -> ChatProvider | None:
        try:
            revision = model_connections.revision_for(
                profile.connection_id, profile.connection_revision
            )
            return _chat_provider_from_connection(
                settings,
                revision.provider,
                profile.model_id,
                revision.secret.base_url,
                revision.secret.api_key,
            )
        except ModelConnectionError:
            return None

    chat_profiles = ChatProfileRegistry(
        runtime_database,
        model_connections,
        resolve_chat_profile,
        on_activated=lambda _profile, provider: _replace_runtime_chat(provider),
    )
    analysis_selection = AnalysisSelectionRegistry(
        runtime_database, chat_profiles, embedding_profiles, model_connections
    )

    def analysis_runtime_supplier() -> ProviderRuntime | None:
        """Resolve the explicitly selected pair without mutating public runtime."""

        view = analysis_selection.view()
        if not view.eligible:
            return None
        try:
            chat_profile = chat_profiles.get(view.selection.chat_profile_id or "")
            embedding_profile = embedding_profiles.get(view.selection.embedding_profile_id or "")
            chat_provider = chat_profiles.resolve_provider(chat_profile)
            embedding_provider = embedding_profiles.resolve_provider(embedding_profile)
            if (
                chat_provider is None
                or embedding_provider is None
                or not isinstance(embedding_provider, RuntimeEmbeddingProvider)
            ):
                return None
            return ProviderRuntime(chat=chat_provider, embedding=embedding_provider)
        except Exception:
            return None

    def frozen_analysis_runtime(pair: AnalysisModelPair) -> ProviderRuntime | None:
        """Resolve only the connection revisions captured by a batch."""

        try:
            chat_revision = model_connections.revision_for(
                pair.chat_connection_id, pair.chat_connection_revision
            )
            embedding_revision = model_connections.revision_for(
                pair.embedding_connection_id, pair.embedding_connection_revision
            )
            if (
                chat_revision.provider != pair.chat_provider
                or embedding_revision.provider != pair.embedding_provider
            ):
                return None
            return ProviderRuntime(
                chat=_chat_provider_from_connection(
                    settings,
                    pair.chat_provider,
                    pair.chat_model_id,
                    chat_revision.secret.base_url,
                    chat_revision.secret.api_key,
                ),
                embedding=_embedding_provider_from_connection(
                    pair.embedding_provider,
                    embedding_revision.secret.base_url,
                    embedding_revision.secret.api_key,
                    pair.embedding_identity,
                ),
            )
        except (ModelConnectionError, ValueError):
            return None

    app.state.analysis_runtime_supplier = analysis_runtime_supplier
    app.state.analysis_frozen_runtime_resolver = frozen_analysis_runtime
    app.state.analysis_selection_registry = analysis_selection
    app.state.embedding_profile_registry = embedding_profiles
    app.state.chat_profile_registry = chat_profiles
    model_operations = OllamaModelOperationCoordinator(embedding_profiles)
    app.state.ollama_model_operations = model_operations

    def list_connection_models(connection_id: str) -> tuple[str, ...]:
        try:
            connection = model_connections.get(connection_id)
            if connection.provider != "ollama":
                raise EmbeddingProfileError("VALIDATION_ERROR")
            secret = model_connections.secret_for(connection_id, connection.revision)
            provider = OllamaEmbeddingProvider(
                secret.base_url, "model-list", None, allow_dimension_discovery=True
            )
            return provider.installed_models()
        except ModelConnectionError:
            raise EmbeddingProfileError("EMBEDDING_CONNECTION_REQUIRED") from None
        except ProviderError:
            raise EmbeddingProfileError("EMBEDDING_MODEL_OPERATION_FAILED") from None

    app.state.admin_operations = AdminOperations(
        github=github,
        database=runtime_database,
        public_base_url=settings.public_base_url,
        onboarding=onboarding,
        analysis_batches=analysis_batches,
        embedding_profiles=embedding_profiles,
        model_connections=model_connections,
        chat_profiles=chat_profiles,
        analysis_selection=analysis_selection,
        ollama_model_operations=model_operations,
        connection_model_lister=list_connection_models,
    )


def _configure_bundle_lifecycle(
    settings: EnvironmentSettings,
    runtime_database: RuntimeDatabase,
) -> None:
    """Attach the real polling owner only when immutable discovery is configured."""

    if not hasattr(settings, "embedding_provider"):
        return
    registry = getattr(app.state, "embedding_profile_registry", None)
    active_profile = registry.active() if registry is not None else None
    environment_embedding = (
        EmbeddingIdentity(
            adapter=_provider_contract_adapter(settings.embedding_provider),
            model_id=settings.embedding_model,
            dimension=settings.embedding_dimension,
            normalized=settings.embedding_normalized,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )
        if settings.embedding_provider in {"ollama", "openai_compatible", "vllm"}
        else EmbeddingIdentity("unconfigured", "unconfigured", 1, True, "", "")
    )
    embedding = active_profile.identity if active_profile is not None else environment_embedding
    allowed_hosts = frozenset({"api.github.com", "github.com", "raw.githubusercontent.com"})
    manager = BundleManager(
        data_directory=settings.data_dir,
        runtime_database=runtime_database,
        expected_embedding=embedding,
        keep_valid_bundles=settings.keep_valid_bundles,
    )
    app.state.bundle_manager = manager
    if registry is not None:
        registry.reconcile_active_bundle(
            manager.active_embedding_identity(),
            manager.status().active_bundle_id,
        )
    manifest_url = getattr(settings, "index_manifest_url", None)
    if not manifest_url:
        app.state.bundle_updater = None
        return
    app.state.bundle_updater = BundleUpdater(
        manifest_url=manifest_url,
        transport=UrllibBundleTransport(allowed_hosts=allowed_hosts),
        manager=manager,
        runtime_database=runtime_database,
        expected_embedding=embedding,
        expected_embedding_supplier=lambda: (
            manager.active_embedding_identity() or environment_embedding
        ),
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

    embedding_identity = _configured_embedding_identity(settings)
    capabilities = ProviderCapabilities(
        streaming=False,
        system_role=True,
        structured_output=True,
        usage_reporting=True,
        health_check=True,
        max_context_tokens=settings.chat_max_context_tokens,
        max_output_tokens=settings.chat_max_output_tokens,
    )
    chat: ChatProvider | None = None
    chat_profiles: ChatProfileRegistry | None = (
        app.state.chat_profile_registry
        if isinstance(getattr(app.state, "chat_profile_registry", None), ChatProfileRegistry)
        else None
    )
    active_chat = chat_profiles.active() if isinstance(chat_profiles, ChatProfileRegistry) else None
    if active_chat is not None and chat_profiles is not None:
        chat = chat_profiles.resolve_provider(active_chat)
    elif (
        settings.chat_provider in {"ollama", "openai_compatible", "vllm"}
        and settings.chat_model
        and settings.chat_base_url
    ):
        chat = _chat_provider_from_settings(settings, capabilities)
    registry = getattr(app.state, "embedding_profile_registry", None)
    active_profile = registry.active() if registry is not None else None
    if active_profile is not None:
        embedding = registry.resolve_provider(active_profile) if registry is not None else None
    else:
        embedding = (
            _embedding_provider_from_settings(settings, embedding_identity)
            if settings.embedding_provider in {"ollama", "openai_compatible", "vllm"}
            and settings.embedding_model
            and settings.embedding_base_url
            else None
        )
    if embedding is None or chat is None:
        app.state.provider_runtime = None
        app.state.provider_adapter = (
            _provider_contract_adapter(settings.chat_provider)
            if settings.chat_provider in {"ollama", "openai_compatible", "vllm"}
            else None
        )
        app.state.chat_service = None
        # Admission controls remain available for later authenticated analysis
        # setup even when public providers are not configured at boot.
        if getattr(app.state, "chat_limits", None) is None:
            ip_hash_key = settings.secrets.get("ip_hash_key")
            if ip_hash_key is not None:
                app.state.chat_limits = ChatLimits(
                    runtime_database,
                    ip_hash_key=ip_hash_key.reveal().encode(),
                    requests_per_minute=settings.rate_limit_requests_per_minute,
                    daily_budget=settings.daily_chat_request_budget,
                    global_concurrency=settings.global_chat_concurrency,
                )
        return
    providers = ProviderRuntime(chat=chat, embedding=embedding)
    app.state.provider_runtime = providers
    app.state.provider_adapter = _provider_contract_adapter(settings.chat_provider)
    app.state.provider_health_seconds = settings.provider_health_seconds
    app.state.max_message_characters = settings.max_message_characters
    app.state.max_history_messages = settings.max_history_messages
    app.state.max_history_characters = settings.max_history_characters
    manager = app.state.bundle_manager
    ip_hash_key = settings.secrets.get("ip_hash_key")
    if ip_hash_key is None:
        app.state.chat_service = None
        app.state.chat_limits = None
        return
    limits = ChatLimits(
        runtime_database,
        ip_hash_key=ip_hash_key.reveal().encode(),
        requests_per_minute=settings.rate_limit_requests_per_minute,
        daily_budget=settings.daily_chat_request_budget,
        global_concurrency=settings.global_chat_concurrency,
    )
    app.state.chat_limits = limits
    if manager is None:
        app.state.chat_service = None
        return
    app.state.chat_service = GroundedChatService(
        bundles=manager,
        providers=providers,
        limits=limits,
        max_output_tokens=settings.chat_max_output_tokens,
        timeout_seconds=settings.chat_timeout_seconds,
    )


def _configure_embedding_reindex(settings: EnvironmentSettings) -> None:
    registry: EmbeddingProfileRegistry | None = getattr(
        app.state, "embedding_profile_registry", None
    )
    manager: BundleManager | None = app.state.bundle_manager
    runtime: ProviderRuntime | None = app.state.provider_runtime
    operations: AdminOperations | None = app.state.admin_operations
    rate_limiter: GitHubRateLimiter | None = getattr(app.state, "github_rate_limiter", None)
    if (
        registry is None
        or manager is None
        or runtime is None
        or operations is None
        or rate_limiter is None
    ):
        return

    def provider_transition(
        profile: EmbeddingProfile,
        provider: EmbeddingProvider,
    ):
        if not isinstance(provider, RuntimeEmbeddingProvider):
            raise ValueError("runtime embedding provider is unavailable")
        previous = runtime.replace_embedding(provider)

        def rollback() -> None:
            runtime.replace_embedding(previous)

        return rollback

    def publish_activation(profile: EmbeddingProfile, bundle_id: str) -> None:
        provider_status = runtime.poll_health()
        current = app.state.reponpc
        app.state.reponpc = replace(
            current,
            index_ready=True,
            index_version=bundle_id,
            public_directory=manager.active_public_directory(),
            model_ready=(provider_status.ready and registry.active_matches(profile.identity)),
            model_last_checked_at=provider_status.checked_at,
        )

    coordinator = EmbeddingReindexCoordinator(
        registry=registry,
        manager=manager,
        builder=ProductionFrozenProfileBuilder(
            data_directory=settings.data_dir,
            config_repository=settings.config_repository,
            config_branch=settings.config_branch,
            github_api_url=settings.github_api_url,
            max_bundle_bytes=settings.max_bundle_bytes,
            source_resolver=GitHubSourceResolver(
                api_base_url=settings.github_api_url,
                rate_limiter=rate_limiter,
            ),
        ),
        provider_transition=provider_transition,
        on_activated=publish_activation,
    )
    app.state.embedding_reindex_coordinator = coordinator
    app.state.admin_operations = replace(operations, embedding_reindex=coordinator)


def _environment_embedding_provider(
    settings: EnvironmentSettings,
    profile: EmbeddingProfile,
) -> RuntimeEmbeddingProvider | None:
    if (
        profile.dimension is None
        or profile.connection_reference != "environment"
        or profile.provider != settings.embedding_provider
    ):
        return None
    return _embedding_provider_from_settings(settings, profile.identity)


def _configured_embedding_identity(settings: EnvironmentSettings) -> EmbeddingIdentity:
    if (
        settings.embedding_provider not in {"ollama", "openai_compatible", "vllm"}
        or not settings.embedding_model
    ):
        return EmbeddingIdentity("unconfigured", "unconfigured", 1, True, "", "")
    return EmbeddingIdentity(
        adapter=_provider_contract_adapter(settings.embedding_provider),
        model_id=settings.embedding_model,
        dimension=settings.embedding_dimension,
        normalized=settings.embedding_normalized,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )


def _chat_provider_from_settings(
    settings: EnvironmentSettings, capabilities: ProviderCapabilities
) -> ChatProvider:
    key = settings.secrets.get("chat_api_key")
    return _chat_provider_from_connection(
        settings,
        settings.chat_provider,
        settings.chat_model,
        settings.chat_base_url,
        key.reveal() if key is not None else None,
        capabilities=capabilities,
    )


def _chat_provider_from_connection(
    settings: EnvironmentSettings,
    provider: str,
    model: str,
    base_url: str,
    api_key: str | None,
    *,
    capabilities: ProviderCapabilities | None = None,
) -> ChatProvider:
    selected_capabilities = capabilities or ProviderCapabilities(
        streaming=False,
        system_role=True,
        structured_output=True,
        usage_reporting=True,
        health_check=True,
        max_context_tokens=settings.chat_max_context_tokens,
        max_output_tokens=settings.chat_max_output_tokens,
    )
    if provider == "ollama":
        return OllamaChatProvider(base_url, model, selected_capabilities)
    if provider in {"openai_compatible", "vllm"}:
        return OpenAICompatibleChatProvider(
            base_url,
            model,
            selected_capabilities,
            api_key=api_key,
            allow_private_http=provider == "vllm",
        )
    raise ValueError("unsupported chat provider")


def _embedding_provider_from_connection(
    provider: str,
    base_url: str,
    api_key: str | None,
    identity: EmbeddingIdentity | None,
    *,
    model: str | None = None,
    query_prefix: str = "",
    passage_prefix: str = "",
) -> RuntimeEmbeddingProvider:
    model_id = identity.model_id if identity else model
    if not model_id:
        raise ValueError("embedding model is required")
    if provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url,
            model_id,
            identity,
            allow_dimension_discovery=identity is None,
            query_prefix=query_prefix,
            passage_prefix=passage_prefix,
        )
    if provider in {"openai_compatible", "vllm"}:
        return OpenAICompatibleEmbeddingProvider(
            base_url,
            model_id,
            identity,
            api_key=api_key,
            allow_private_http=provider == "vllm",
            allow_dimension_discovery=identity is None,
            query_prefix=query_prefix,
            passage_prefix=passage_prefix,
        )
    raise ValueError("unsupported embedding provider")


def _embedding_provider_from_settings(
    settings: EnvironmentSettings,
    identity: EmbeddingIdentity,
) -> RuntimeEmbeddingProvider | None:
    if identity.adapter != _provider_contract_adapter(settings.embedding_provider):
        return None
    embedding_key = settings.secrets.get("embedding_api_key")
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            settings.embedding_base_url,
            identity.model_id,
            identity,
        )
    if settings.embedding_provider in {"openai_compatible", "vllm"}:
        return OpenAICompatibleEmbeddingProvider(
            settings.embedding_base_url,
            identity.model_id,
            identity,
            api_key=embedding_key.reveal() if embedding_key is not None else None,
            allow_private_http=settings.embedding_provider == "vllm",
        )
    return None


def _provider_contract_adapter(provider: str) -> str:
    """Map a named transport preset to the stable public/bundle adapter contract."""

    return "openai_compatible" if provider == "vllm" else provider


def _replace_runtime_chat(provider: ChatProvider) -> Callable[[], None] | None:
    runtime = getattr(app.state, "provider_runtime", None)
    if isinstance(runtime, ProviderRuntime):
        previous = runtime.replace_chat(provider)

        def restore() -> None:
            runtime.replace_chat(previous)

        return restore
    return None
