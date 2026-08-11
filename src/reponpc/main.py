"""Production FastAPI entrypoint for RepoNPC."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from reponpc.api.public import SetupState, create_public_router
from reponpc.bundles.manager import BundleManager
from reponpc.bundles.updater import BundleUpdater, UrllibBundleTransport
from reponpc.config.environment import (
    EnvironmentSettings,
    EnvironmentValidationError,
    load_environment,
)
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError

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
    web_dist: Path | None = None,
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
        updater = application.state.bundle_updater
        manager = application.state.bundle_manager
        if updater is None or manager is None:
            yield
            return

        stopped = asyncio.Event()

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

        await asyncio.to_thread(poll_and_publish_state)
        polling_task = asyncio.create_task(polling_lifecycle())
        yield
        stopped.set()
        polling_task.cancel()
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

    @application.middleware("http")
    async def public_boundary(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = _request_id(request.headers.get("X-Request-ID"))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        for header, value in _SECURITY_HEADERS.items():
            if header not in response.headers:
                response.headers[header] = value
        return response

    application.state.reponpc = state
    application.state.runtime_storage_usable = state.runtime_storage_usable
    application.state.runtime_database = runtime_database
    application.state.bundle_manager = bundle_manager
    application.state.bundle_updater = bundle_updater
    application.state.bundle_poll_seconds = bundle_poll_seconds
    application.include_router(
        create_public_router(state, state_supplier=lambda: application.state.reponpc)
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
        _configure_bundle_lifecycle(settings, runtime_database)
    except RuntimeDatabaseError:
        app.state.runtime_database = None
        app.state.runtime_storage_usable = False
    uvicorn.run("reponpc.main:app", host=settings.host, port=settings.port, factory=False)


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
