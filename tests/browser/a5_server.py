"""Disposable A5 browser host using the production API, build and runtime stores.

Only GitHub/model transports use existing deterministic fixtures. No production
data, external service, public listener or stored credentials are used.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import math
import secrets
import socket
import threading
import time
import zipfile
from contextlib import nullcontext, suppress
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

import uvicorn
from argon2 import PasswordHasher
from argon2.low_level import Type
from starlette.responses import FileResponse, JSONResponse

from reponpc.admin.auth import AdminSessionService
from reponpc.admin.embedding_reindex import EmbeddingReindexCoordinator
from reponpc.admin.faq import ReviewedFaq
from reponpc.admin.local_portfolio import LocalPortfolioStore
from reponpc.admin.local_publication import LocalPortfolioBuilder, LocalPublication
from reponpc.admin.operations import AdminOperations
from reponpc.api.public import SetupState
from reponpc.api.visitor_gateway import VisitorGateway
from reponpc.chat.service import GroundedChatService
from reponpc.config.environment import load_environment
from reponpc.main import create_app
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.visitor_gateway import VisitorGatewayStore
from reponpc.sharing.export import build_visitor_site_export
from reponpc.sharing.manifest import (
    SiteExportError,
    pages_target,
    parse_manifest,
    safe_relative_path,
)
from reponpc.sharing.pages_transport import _MAX_RESPONSE_BYTES, _remaining
from tests.browser.a5_transport import GATEWAY_ORIGIN, PAGES_ORIGIN, GatewayFixtureTransport
from tests.integration.test_embedding_reindex import _profile, _system
from tests.integration.test_index_build import FIXTURE_CONFIG
from tests.integration.test_local_publication import FixtureParticipation, FixtureResolver
from tests.integration.test_reviewed_faq import OwnerLimits, SyntheticChat

# Public test credentials for this disposable loopback fixture only.
FIXTURE_USERNAME = "a5-fixture"
FIXTURE_PASSWORD = "A5 disposable browser fixture 2026"


def _pages_mapping_port(static_origin: str, gateway_port: int | None) -> int:
    if gateway_port is None:
        raise ValueError("--map-pages requires --gateway-port")
    parsed = urlsplit(static_origin)
    port = parsed.port
    if (
        any(character.isspace() or ord(character) < 32 for character in static_origin)
        or parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or port is None
        or not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or static_origin != f"http://{parsed.netloc}"
    ):
        raise ValueError("Pages fixture requires an HTTP loopback origin with an explicit port")
    return port


class A5AcceptanceApp:
    """Expose safe observations beside the real app; never replace API responses."""

    def __init__(
        self,
        application: Any,
        chat: SyntheticChat,
        *,
        web_dist: Path,
        audit_script: Path | None = None,
        gateway_port: int | None = None,
        static_origin: str = "http://127.0.0.1:8781",
        map_pages: bool = False,
        export_directory: Path | None = None,
    ) -> None:
        self.application = application
        self.web_dist = web_dist
        self.chat = chat
        self.audit_script = audit_script
        self.gateway_port = gateway_port
        self.static_origin = static_origin
        self.pages_port = _pages_mapping_port(static_origin, gateway_port) if map_pages else None
        self.export_directory = export_directory
        self.transports: list[GatewayFixtureTransport] = []
        self.delay_scene_preview = False

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            from reponpc.api import visitor_gateway as gateway_module
            from reponpc.sharing import pages as pages_module

            factory = gateway_module.create_visitor_gateway_app

            def fixture_gateway(*args: Any, **kwargs: Any) -> GatewayFixtureTransport:
                transport = GatewayFixtureTransport(
                    factory(*args, **kwargs),
                    gateway_port=self.gateway_port,
                    static_origin=self.static_origin,
                )
                self.transports.append(transport)
                return transport

            transport_patch = (
                patch.object(
                    gateway_module, "create_visitor_gateway_app", side_effect=fixture_gateway
                )
                if self.gateway_port is not None
                else nullcontext()
            )
            pages_patch = (
                patch.object(pages_module, "fetch_pages_resource", self._fetch_pages_resource)
                if self.pages_port is not None
                else nullcontext()
            )
            try:
                with transport_patch, pages_patch:

                    async def send_startup(message: Any) -> None:
                        if message["type"] == "lifespan.startup.complete" and self.export_directory:
                            self._export_browser_sites()
                        await send(message)

                    await self.application(scope, receive, send_startup)
            finally:
                with self.application.state.bundle_manager.acquire() as index:
                    index.close()
            return
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/__a5-test/delay-scene-preview"
        ):
            self.delay_scene_preview = True
            await JSONResponse({"armed": True})(scope, receive, send)
            return
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/api/admin/scene/preview"
            and self.delay_scene_preview
        ):
            self.delay_scene_preview = False
            await asyncio.sleep(0.75)
        if (
            scope["type"] == "http"
            and scope["method"] == "GET"
            and scope["path"] == "/__a5-test/state"
        ):
            manager = self.application.state.bundle_manager
            payload = {
                "model_calls": self.chat.calls,
                "active_bundle_id": manager.status().active_bundle_id,
                "index_ready": self.application.state.reponpc.index_ready,
                "gateway_requests": sum(transport.requests for transport in self.transports),
            }
            await JSONResponse(payload, headers={"Cache-Control": "no-store"})(scope, receive, send)
            return
        if self.audit_script is not None and scope["type"] == "http":
            scripts = {
                "/__a5-test/axe.js": self.audit_script,
                "/__a5-test/acceptance.js": Path(__file__).with_name("a5-acceptance.js"),
            }
            if scope["method"] == "GET" and scope["path"] in scripts:
                await FileResponse(
                    scripts[scope["path"]],
                    media_type="text/javascript",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
                )(scope, receive, send)
                return
            if scope["method"] == "GET":
                start: dict[str, Any] | None = None
                chunks: list[bytes] = []

                async def instrument_html(message: dict[str, Any]) -> None:
                    nonlocal start
                    if message["type"] == "http.response.start":
                        headers = dict(message["headers"])
                        if headers.get(b"content-type", b"").startswith(b"text/html"):
                            start = message
                            return
                    if start is not None and message["type"] == "http.response.body":
                        chunks.append(message.get("body", b""))
                        if not message.get("more_body", False):
                            content = acceptance_document(b"".join(chunks))
                            start["headers"] = [
                                (key, value)
                                for key, value in start["headers"]
                                if key.lower() != b"content-length"
                            ] + [(b"content-length", str(len(content)).encode("ascii"))]
                            await send(start)
                            await send({"type": "http.response.body", "body": content})
                        return
                    await send(message)

                await self.application(scope, receive, instrument_html)
                return
        await self.application(scope, receive, send)

    def _fetch_pages_resource(
        self,
        url: str,
        *,
        pages_origin: str,
        deadline: float,
        max_response_bytes: int,
    ) -> ProviderHttpResponse:
        if not isinstance(url, str) or any(
            character.isspace() or ord(character) < 32 for character in url
        ):
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        pages_target(url, pages_origin)
        parsed = urlsplit(url)
        if pages_origin != PAGES_ORIGIN or parsed.scheme + "://" + parsed.netloc != pages_origin:
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        if (
            isinstance(deadline, bool)
            or not math.isfinite(deadline)
            or not 0 < deadline - time.monotonic() <= 30
            or isinstance(max_response_bytes, bool)
            or not 0 < max_response_bytes <= _MAX_RESPONSE_BYTES
        ):
            raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")

        assert self.pages_port is not None
        connection: HTTPConnection | None = None
        timer: threading.Timer | None = None
        expired = threading.Event()
        try:
            connection = HTTPConnection("127.0.0.1", self.pages_port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as network_socket:
                network_socket.settimeout(_remaining(deadline))
                network_socket.connect(("127.0.0.1", self.pages_port))
                connection.sock = network_socket

                def interrupt() -> None:
                    expired.set()
                    with suppress(OSError, ValueError):
                        network_socket.shutdown(socket.SHUT_RDWR)

                # Bound drip-fed headers and chunked bodies by the shared deadline too.
                timer = threading.Timer(_remaining(deadline), interrupt)
                timer.daemon = True
                timer.start()
                network_socket.settimeout(_remaining(deadline))
                connection.request(
                    "GET",
                    parsed.path or "/",
                    headers={"Accept-Encoding": "identity", "Connection": "close"},
                )
                response = connection.getresponse()
                if response.status != 200:
                    raise SiteExportError("SHARING_VERIFICATION_FAILED")
                length = response.getheader("Content-Length")
                if length is not None and (
                    not length.isdecimal() or int(length) > max_response_bytes
                ):
                    raise SiteExportError("SHARING_VERIFICATION_FAILED")
                if response.getheader("Content-Encoding", "identity").casefold() != "identity":
                    raise SiteExportError("SHARING_VERIFICATION_FAILED")
                payload = bytearray()
                while True:
                    # A fully read plain-HTTP body closes the socket; do not re-arm its timeout.
                    _remaining(deadline)
                    chunk = response.read1(min(64 * 1024, max_response_bytes - len(payload) + 1))
                    if not chunk:
                        break
                    payload.extend(chunk)
                    if len(payload) > max_response_bytes:
                        raise SiteExportError("SHARING_VERIFICATION_FAILED")
                _remaining(deadline)
                if expired.is_set() or (length is not None and len(payload) != int(length)):
                    raise SiteExportError("SHARING_VERIFICATION_FAILED")
                return ProviderHttpResponse(
                    status=200,
                    headers={"content-type": response.getheader("Content-Type", "")},
                    body=bytes(payload),
                )
        except SiteExportError:
            raise
        except HTTPException, OSError, ValueError:
            raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE") from None
        finally:
            if timer is not None:
                timer.cancel()
            if connection is not None:
                connection.close()

    def _export_browser_sites(self) -> None:
        """Make checked production exports for this exact disposable gateway bundle."""
        assert self.export_directory is not None
        self.export_directory.mkdir(parents=True, exist_ok=False)
        for name, pages_url in (
            ("root", PAGES_ORIGIN + "/"),
            ("project", PAGES_ORIGIN + "/project/"),
        ):
            artifact = build_visitor_site_export(
                faq=self.application.state.faq_supplier(),
                scene_service=self.application.state.scene_supplier(),
                web_dist=self.web_dist,
                pages_url=pages_url,
                gateway_origin=GATEWAY_ORIGIN,
                pages_origin=PAGES_ORIGIN,
            )
            try:
                destination = self.export_directory / name
                destination.mkdir()
                with zipfile.ZipFile(artifact.path) as archive:
                    manifest = parse_manifest(archive.read("export-manifest.json"))
                    records = {record["path"]: record for record in manifest["files"]}
                    assert set(archive.namelist()) == {*records, "export-manifest.json"}
                    for path in archive.namelist():
                        assert safe_relative_path(path)
                        content = archive.read(path)
                        if path in records:
                            assert len(content) == records[path]["size"]
                            assert hashlib.sha256(content).hexdigest() == records[path]["sha256"]
                        target = destination / path
                        assert target.resolve().is_relative_to(destination.resolve())
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content)
                (self.export_directory / f"{name}.zip").write_bytes(artifact.path.read_bytes())
                print(
                    f"EXPORTED_SITE={destination} FILES={len(records)} "
                    f"ID={artifact.content_sha256}",
                    flush=True,
                )
            finally:
                artifact.cleanup()


def acceptance_document(content: bytes) -> bytes:
    """Add test scripts to an HTTP response; keep artifacts and their CSP intact."""

    if content.count(b"<head>") != 1:
        raise ValueError("browser fixture needs one head element")
    return content.replace(
        b"<head>",
        b'<head><script src="/__a5-test/axe.js"></script>'
        b'<script src="/__a5-test/acceptance.js"></script>',
        1,
    )


def build_application(
    runtime_root: Path,
    web_dist: Path,
    origin: str,
    *,
    audit_script: Path | None = None,
    gateway_port: int | None = None,
    static_origin: str = "http://127.0.0.1:8781",
    map_pages: bool = False,
    export_directory: Path | None = None,
) -> A5AcceptanceApp:
    """Build and activate a real immutable fixture bundle in a fresh directory."""

    if map_pages:
        _pages_mapping_port(static_origin, gateway_port)
    if (runtime_root / "runtime").exists() or (runtime_root / "data").exists():
        raise ValueError("a fresh disposable runtime is required")
    runtime_root.mkdir(parents=True, exist_ok=True)
    database, providers, manager, registry, _, transition = _system(runtime_root)
    provider = providers["a"]
    profile = registry.probe(registry.create(_profile(provider)).profile_id)
    store = LocalPortfolioStore(runtime_root / "data")
    draft = store.save(
        content=FIXTURE_CONFIG.read_text(encoding="utf-8"),
        sprite_base64=None,
        expected_revision=None,
    )
    resolver = FixtureResolver()
    builder = LocalPortfolioBuilder(
        draft,
        data_directory=runtime_root / "data",
        resolver=resolver,
        participation_collector=FixtureParticipation().participation,
        max_bundle_bytes=10 * 1024 * 1024,
    )
    coordinator = EmbeddingReindexCoordinator(
        registry=registry, manager=manager, builder=builder, provider_transition=transition
    )
    publication = LocalPublication(
        store=store,
        data_directory=runtime_root / "data",
        coordinator=coordinator,
        registry=registry,
        manager=manager,
        resolver=resolver,
        max_bundle_bytes=10 * 1024 * 1024,
        transition_factory=lambda _chat_profile_id: transition,
        stop_remote=lambda: None,
    )
    publication.prepare(
        expected_revision=draft.revision,
        embedding_profile_id=profile.profile_id,
        chat_profile_id="fixture-chat",
    )
    if not coordinator.wait(profile.profile_id, timeout=30).active:
        coordinator.shutdown()
        raise RuntimeError("fixture bundle activation failed")
    chat = SyntheticChat()
    service = GroundedChatService(
        bundles=manager,
        providers=ProviderRuntime(chat=chat, embedding=provider, max_attempts=1),
        limits=OwnerLimits(),
        max_output_tokens=16384,
        timeout_seconds=5,
    )
    faq = ReviewedFaq(database=database, bundles=manager, chat_supplier=lambda: service)
    for locale in ("zh-TW", "en"):
        entry = faq.initialize_queue(locale)["entries"][0]
        entry = faq.regenerate(entry["entry_id"], entry["revision"])
        faq.review(entry["entry_id"], entry["revision"], "approve")
    auth = AdminSessionService(
        database=database,
        username=FIXTURE_USERNAME,
        password_hash=PasswordHasher(type=Type.ID).hash(FIXTURE_PASSWORD),
        identity_hmac_key=secrets.token_bytes(32),
    )
    operations = AdminOperations(
        database=database,
        public_base_url=origin,
        embedding_profiles=registry,
        local_portfolio=store,
        local_publication=publication,
    )
    application = create_app(
        runtime_database=database,
        bundle_manager=manager,
        setup_state=SetupState(model_ready=True),
        chat_service=service,
        admin_session_service=auth,
        admin_origins=(origin,),
        admin_operations=operations,
        web_dist=web_dist,
    )
    application.state.embedding_reindex_coordinator = coordinator
    if gateway_port is not None:
        environment = load_environment(
            {
                "REPONPC_PUBLIC_BASE_URL": origin,
                "REPONPC_ADMIN_ORIGINS": origin,
                "REPONPC_VISITOR_GATEWAY_PORT": str(gateway_port),
                "REPONPC_SHUTDOWN_GRACE_SECONDS": "1",
            },
            secret_roots=(runtime_root,),
        )
        intent = VisitorGatewayStore(database)
        configured = intent.configure(
            revision=intent.get().revision,
            gateway_origin=GATEWAY_ORIGIN,
            pages_origin=PAGES_ORIGIN,
            visitor_port=None,
        )
        intent.set_enabled(revision=configured.revision, enabled=True)
        application.state.visitor_gateway = VisitorGateway(
            database=database,
            environment=environment,
            state_supplier=lambda: application.state.reponpc,
            bundle_manager_supplier=lambda: manager,
            chat_service_supplier=lambda: service,
            faq_supplier=application.state.faq_supplier,
            scene_supplier=application.state.scene_supplier,
            web_dist=web_dist,
        )
    return A5AcceptanceApp(
        application,
        chat,
        web_dist=web_dist,
        audit_script=audit_script,
        gateway_port=gateway_port,
        static_origin=static_origin,
        map_pages=map_pages,
        export_directory=export_directory,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--web-dist", type=Path, default=Path("apps/web/dist"))
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--axe-script", type=Path)
    parser.add_argument("--gateway-port", type=int)
    parser.add_argument("--static-origin", default="http://127.0.0.1:8781")
    parser.add_argument("--map-pages", action="store_true")
    parser.add_argument("--export-directory", type=Path)
    args = parser.parse_args()
    if args.map_pages and args.gateway_port is None:
        parser.error("--map-pages requires --gateway-port")
    origin = f"http://127.0.0.1:{args.port}"
    application = build_application(
        args.runtime.resolve(),
        args.web_dist.resolve(),
        origin,
        audit_script=args.axe_script,
        gateway_port=args.gateway_port,
        static_origin=args.static_origin,
        map_pages=args.map_pages,
        export_directory=args.export_directory,
    )
    print(f"BROWSER_URL={origin}/", flush=True)
    uvicorn.run(application, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
