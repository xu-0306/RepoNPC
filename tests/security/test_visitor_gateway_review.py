"""Independent A1 ingress checks against the real application boundary."""

from __future__ import annotations

import asyncio
import json
import socket
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from reponpc.api.public import SetupState
from reponpc.api.visitor_gateway import VisitorGateway
from reponpc.api.visitor_ingress import create_visitor_gateway_app
from reponpc.chat.limits import ChatLimitError, ChatLimits
from reponpc.chat.service import ChatDelivery, GroundedChatService
from reponpc.config.environment import load_environment
from reponpc.main import create_app
from reponpc.providers import ProviderError, ProviderFailureCode, ProviderUsage
from reponpc.providers.runtime import ProviderRuntime
from reponpc.runtime.database import RuntimeDatabase
from scripts.funnel_compose_preflight import supported
from tests.integration.test_chat_grounding_security import Bundles
from tests.integration.test_chat_sse_api import FixtureChatService
from tests.security.test_admin_assets import ORIGIN, _login, local_admin_application
from tests.unit.test_provider_runtime import READY, FixtureChat, FixtureEmbedding


def test_production_private_origin_guard_remains_active_without_admin_service():
    primary = create_app(admin_origins=(ORIGIN,))
    primary.state.deployment_profile = "production"
    with TestClient(primary, base_url=ORIGIN) as client:
        assert (
            client.get("/api/admin/setup", headers={"Host": "public.example.com"}).status_code
            == 403
        )
        assert client.post("/api/admin/session", content="invalid-json").status_code == 403
        assert client.get("/api/admin/setup", headers={"Origin": ORIGIN}).status_code != 403


async def _raw_asgi_request(
    app,
    *,
    raw_path=b"/api/public/status",
    method="GET",
    headers=(),
    body=b"",
    body_events=None,
    on_send=None,
    peer="127.0.0.1",
):
    """Preserve raw paths and expose streaming frames without a buffering client."""
    events = iter(
        body_events
        if body_events is not None
        else [{"type": "http.request", "body": body, "more_body": False}]
    )
    connected = asyncio.Event()
    frames = []

    async def receive():
        event = next(events, None)
        if event is not None:
            return event
        await connected.wait()
        return {"type": "http.disconnect"}

    async def send(frame):
        frames.append(dict(frame))
        if on_send is not None:
            on_send(frame)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "http",
        "method": method,
        "path": unquote(raw_path.decode("ascii")),
        "raw_path": raw_path,
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"fixture.ts.net"), *headers],
        "client": (peer, 54321) if peer is not None else None,
        "server": ("127.0.0.1", 8001),
    }
    await app(scope, receive, send)
    return frames


def _gateway(tmp_path, *, service=None, trusted=(), web_dist=None):
    current = SetupState(
        index_ready=True,
        index_version="fixture-index",
        model_ready=True,
        model_provider="PRIVATE_MODEL_CANARY",
        model_last_checked_at="2026-09-29T00:00:00Z",
    )
    settings = {
        "enabled": True,
        "listener_ready": True,
        "gateway_origin": "https://fixture.ts.net",
        "pages_origin": "https://fixture.github.io",
    }
    app = create_visitor_gateway_app(
        state_supplier=lambda: current,
        bundle_manager_supplier=lambda: None,
        chat_service_supplier=lambda: service,
        faq_supplier=lambda: None,
        gateway_origin=settings["gateway_origin"],
        pages_origin=settings["pages_origin"],
        listener_ready_supplier=lambda: settings["enabled"] and settings["listener_ready"],
        web_dist=web_dist,
        gateway_port=8001,
        trusted_proxy_cidrs=trusted,
        max_message_characters=2000,
        max_history_messages=6,
        max_history_characters=6000,
        global_concurrency=1,
        keepalive_seconds=0.01,
    )
    return app, settings


@pytest.mark.parametrize(
    "raw_path,method",
    [
        (b"/admin", "GET"),
        (b"/api/admin/setup", "GET"),
        (b"/api/admin/visitor-gateway", "GET"),
        (b"/v1/models", "GET"),
        (b"/data/runtime.sqlite", "GET"),
        (b"/openapi.json", "GET"),
        (b"/docs", "GET"),
        (b"/api/public/status/", "GET"),
        (b"/API/public/status", "GET"),
        (b"//api/public/status", "GET"),
        (b"/api/public/../admin/setup", "GET"),
        (b"/api%2fpublic/status", "GET"),
        (b"/api/public/%73tatus", "GET"),
        (b"/api/public/\\status", "GET"),
        (b"/api/public/status", "POST"),
        (b"/api/public/chat/stream", "GET"),
        (b"/healthz", "OPTIONS"),
        (b"/api/admin/setup", "OPTIONS"),
    ],
)
def test_gateway_raw_route_boundary_never_redirects_or_dispatches_private_paths(
    tmp_path, raw_path, method
):
    app, _settings = _gateway(tmp_path)
    frames = asyncio.run(_raw_asgi_request(app, raw_path=raw_path, method=method))
    start = next(frame for frame in frames if frame["type"] == "http.response.start")
    assert start["status"] == 404
    assert b"location" not in dict(start["headers"])
    assert b"set-cookie" not in dict(start["headers"])


@pytest.mark.parametrize("credential", ["Cookie", "Authorization", "X-CSRF-Token"])
def test_gateway_rejects_even_empty_credentials_and_spoofed_host(tmp_path, credential):
    app, _settings = _gateway(tmp_path)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        denied = client.get("/api/public/status", headers={credential: ""})
        spoofed = client.get(
            "/api/public/status",
            headers={"Host": "evil.example", "X-Forwarded-Host": "fixture.ts.net"},
        )
    assert denied.status_code == spoofed.status_code == 404
    assert "set-cookie" not in denied.headers


def test_gateway_status_head_and_cors_are_strict_public_projections(tmp_path):
    app, _settings = _gateway(tmp_path)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        response = client.get("/api/public/status", headers={"Origin": "https://fixture.github.io"})
        assert response.json() == {
            "status": "ready",
            "chat_available": True,
            "index": {"ready": True, "version": "fixture-index"},
        }
        assert "PRIVATE_" not in response.text
        assert response.headers["access-control-allow-origin"] == "https://fixture.github.io"
        assert "access-control-allow-credentials" not in response.headers
        assert client.head("/api/public/status").content == b""
        assert client.head("/healthz").content == b""
        assert client.head("/api/public/profile").content == b""
        assert (
            "access-control-allow-origin"
            not in client.get(
                "/api/public/status", headers={"Origin": "https://evil.example"}
            ).headers
        )
        preflight = {
            "Origin": "https://fixture.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        assert client.options("/api/public/chat/stream", headers=preflight).status_code == 204
        denied = client.options(
            "/api/public/chat/stream",
            headers={**preflight, "Access-Control-Request-Headers": "Content-Type,Authorization"},
        )
        assert denied.status_code == 404 and "access-control-allow-origin" not in denied.headers


def test_gateway_manifest_serves_only_static_dependency_closure_and_cannot_override_file(tmp_path):
    root = tmp_path / "web"
    (root / ".vite").mkdir(parents=True)
    (root / "assets").mkdir()
    for name in ["index.html", "assets/main.js", "assets/shared.js", "assets/theme.css"]:
        (root / name).write_text("VISITOR_" + name)
    (root / "assets/AdminPage.js").write_text("PRIVATE_ADMIN_CHUNK_CANARY")
    (root / "private.json").write_text("PRIVATE_FILE_CANARY")
    (root / ".vite/manifest.json").write_text(
        json.dumps(
            {
                "index.html": {
                    "isEntry": True,
                    "file": "assets/main.js",
                    "imports": ["_shared"],
                    "css": ["assets/theme.css"],
                    "dynamicImports": ["admin"],
                },
                "_shared": {"file": "assets/shared.js"},
                "admin": {"isDynamicEntry": True, "file": "assets/AdminPage.js"},
            }
        )
    )
    app, _settings = _gateway(tmp_path, web_dist=root)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        for path in ["/", "/assets/main.js", "/assets/shared.js", "/assets/theme.css"]:
            assert client.get(path).status_code == 200
            assert client.head(path).status_code == 200 and client.head(path).content == b""
        assert "PRIVATE_FILE" not in client.get("/assets/main.js?file=private.json").text
        for path in [
            "/admin",
            "/assets/AdminPage.js",
            "/.vite/manifest.json",
            "/private.json",
            "/unknown",
        ]:
            assert client.get(path).status_code == 404
    (root / ".vite/manifest.json").write_text("{}")
    closed, _settings = _gateway(tmp_path, web_dist=root)
    with TestClient(closed, base_url="https://fixture.ts.net") as client:
        assert client.get("/").status_code == client.get("/assets/main.js").status_code == 404


@pytest.mark.parametrize(
    "forwarded", [None, "", "192.0.2.1,198.51.100.1", "invalid", "192.0.2.1:80", "fe80::1%eth0"]
)
def test_gateway_trusted_mode_invalid_identity_never_admits_worker(tmp_path, forwarded):
    service = FixtureChatService()
    app, _settings = _gateway(tmp_path, service=service, trusted=("127.0.0.1/32",))
    headers = [] if forwarded is None else [(b"x-forwarded-for", forwarded.encode())]
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            headers=headers,
            body=b'{"message":"Question","locale":"en"}',
        )
    )
    assert frames[0]["status"] == 400
    assert service.calls == 0
    assert b"GATEWAY_IDENTITY_INVALID" in b"".join(frame.get("body", b"") for frame in frames)


def test_gateway_chunked_body_counts_actual_bytes_before_decoding_or_worker(tmp_path):
    service = FixtureChatService()
    app, _settings = _gateway(tmp_path, service=service)
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            headers=[(b"content-length", b"1")],
            body_events=[
                {"type": "http.request", "body": b"x" * 40000, "more_body": True},
                {"type": "http.request", "body": b"x" * 25537, "more_body": False},
            ],
        )
    )
    assert frames[0]["status"] == 413
    assert service.calls == 0 and app.state.visitor_workers.active_count == 0


class _HeldVisitorAnswer:
    def __init__(self, timeout=1):
        self.timeout_seconds = timeout
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.calls = []

    def answer(self, **kwargs):
        self.calls.append(kwargs)
        self.started.set()
        try:
            assert self.release.wait(3), "synthetic test worker was not released"
            return ChatDelivery(
                "fixture-index",
                "en",
                0,
                "Reviewed answer.",
                (),
                "PRIVATE_FINISH_REASON_CANARY",
                ProviderUsage(41, 23),
                False,
            )
        finally:
            self.finished.set()


def test_gateway_real_asgi_headers_and_heartbeats_precede_buffered_answer(tmp_path):
    service = _HeldVisitorAnswer()
    app, _settings = _gateway(tmp_path, service=service)

    async def exercise():
        heartbeats = 0
        observed = asyncio.Event()
        captured = []

        def inspect(frame):
            nonlocal heartbeats
            captured.append(frame)
            if frame.get("body", b"").startswith(b":"):
                heartbeats += 1
                if heartbeats >= 2:
                    observed.set()

        task = asyncio.create_task(
            _raw_asgi_request(
                app,
                raw_path=b"/api/public/chat/stream",
                method="POST",
                body=b'{"message":"Question","locale":"en"}',
                on_send=inspect,
            )
        )
        try:
            await asyncio.wait_for(observed.wait(), 1)
            assert captured[0]["status"] == 200 and not service.finished.is_set()
            assert dict(captured[0]["headers"])[b"content-type"].startswith(b"text/event-stream")
            assert app.state.visitor_workers.active_count == 1
            assert not any(b"event: token" in frame.get("body", b"") for frame in captured)
        finally:
            service.release.set()
        frames = await asyncio.wait_for(task, 1)
        payload = b"".join(frame.get("body", b"") for frame in frames)
        assert b'"usage":null' in payload and b"PRIVATE_" not in payload
        assert payload.count(b"event: complete") == 1
        assert service.calls[0]["client_ip"] is None and service.calls[0]["allow_retry"] is False
        assert app.state.visitor_workers.active_count == 0

    asyncio.run(exercise())


def test_gateway_timeout_retains_capacity_until_actual_thread_exit(tmp_path):
    service = _HeldVisitorAnswer(timeout=0.05)
    app, _settings = _gateway(tmp_path, service=service)

    async def exercise():
        try:
            frames = await asyncio.wait_for(
                _raw_asgi_request(
                    app,
                    raw_path=b"/api/public/chat/stream",
                    method="POST",
                    body=b'{"message":"Question","locale":"en"}',
                ),
                1,
            )
            payload = b"".join(frame.get("body", b"") for frame in frames)
            assert payload.count(b"event: error") == 1 and b"REQUEST_TIMEOUT" in payload
            assert app.state.visitor_workers.active_count == 1 and not service.finished.is_set()
            second = await _raw_asgi_request(
                app,
                raw_path=b"/api/public/chat/stream",
                method="POST",
                body=b'{"message":"Question","locale":"en"}',
            )
            assert second[0]["status"] == 429
            assert len(service.calls) == 1
        finally:
            service.release.set()
            await asyncio.to_thread(service.finished.wait, 1)
        assert app.state.visitor_workers.active_count == 0

    asyncio.run(exercise())


def test_gateway_unfinished_body_obeys_original_deadline_without_worker(tmp_path):
    service = _HeldVisitorAnswer(timeout=0.02)
    app, _settings = _gateway(tmp_path, service=service)
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            body_events=[{"type": "http.request", "body": b"{", "more_body": True}],
        )
    )
    assert frames[0]["status"] == 504 and service.calls == []


@pytest.mark.parametrize("stage", ["headers", "comment", "stop"])
def test_gateway_disconnect_or_stop_signals_actual_worker_without_freeing_it(tmp_path, stage):
    service = _HeldVisitorAnswer()
    app, settings = _gateway(tmp_path, service=service)

    async def exercise():
        def interrupt(frame):
            if stage == "headers" and frame["type"] == "http.response.start":
                raise OSError("synthetic peer disconnected before first body")
            if frame.get("body", b"").startswith(b":"):
                if stage == "comment":
                    raise OSError("synthetic peer disconnected")
                if stage == "stop":
                    settings["enabled"] = False
                    app.state.visitor_workers.cancel_all()

        try:
            try:
                frames = await _raw_asgi_request(
                    app,
                    raw_path=b"/api/public/chat/stream",
                    method="POST",
                    body=b'{"message":"Question","locale":"en"}',
                    on_send=interrupt,
                )
            except Exception as exc:
                assert stage != "stop" and type(exc).__name__ in {"OSError", "ClientDisconnect"}
            else:
                payload = b"".join(frame.get("body", b"") for frame in frames)
                assert b"event: complete" not in payload and b"SERVICE_NOT_READY" in payload
            assert await asyncio.to_thread(service.started.wait, 1)
            assert service.calls[0]["cancel_requested"].is_set()
            assert app.state.visitor_workers.active_count == 1
            if stage == "stop":
                denied = await _raw_asgi_request(app)
                assert denied[0]["status"] == 503
        finally:
            service.release.set()
            await asyncio.to_thread(service.finished.wait, 1)
        assert app.state.visitor_workers.active_count == 0

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "failure,code",
    [
        (
            ProviderError(
                ProviderFailureCode.AUTHENTICATION, upstream_message="PRIVATE_KEY_CANARY"
            ),
            "REQUEST_FAILED",
        ),
        (
            ProviderError(ProviderFailureCode.UNAVAILABLE, upstream_message="PRIVATE_URL_CANARY"),
            "SERVICE_NOT_READY",
        ),
        (ProviderError(ProviderFailureCode.TIMEOUT), "REQUEST_TIMEOUT"),
        (ChatLimitError("PRIVATE_UNKNOWN_LIMIT_CANARY"), "REQUEST_FAILED"),
        (RuntimeError("PRIVATE_DIAGNOSTIC_CANARY"), "REQUEST_FAILED"),
    ],
)
def test_gateway_worker_failures_have_one_safe_terminal_event(tmp_path, failure, code):
    class FailingAnswer:
        def answer(self, **_kwargs):
            raise failure

    app, _settings = _gateway(tmp_path, service=FailingAnswer())
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            body=b'{"message":"Question","locale":"en"}',
        )
    )
    payload = b"".join(frame.get("body", b"") for frame in frames)
    assert frames[0]["status"] == 200 and payload.count(b"event: error") == 1
    assert code.encode() in payload and b"PRIVATE_" not in payload
    assert b"event: complete" not in payload and b"event: token" not in payload
    assert app.state.visitor_workers.active_count == 0


@pytest.mark.parametrize("peer", [None, "192.0.2.1"])
def test_gateway_trusted_mode_rejects_missing_or_untrusted_actual_peer(tmp_path, peer):
    service = FixtureChatService()
    app, _settings = _gateway(tmp_path, service=service, trusted=("127.0.0.1/32",))
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            peer=peer,
            headers=[(b"x-forwarded-for", b"198.51.100.1")],
            body=b'{"message":"Question","locale":"en"}',
        )
    )
    assert frames[0]["status"] == 400 and service.calls == 0


def test_gateway_trusted_mode_rejects_duplicate_forwarded_headers(tmp_path):
    service = FixtureChatService()
    app, _settings = _gateway(tmp_path, service=service, trusted=("127.0.0.1/32",))
    frames = asyncio.run(
        _raw_asgi_request(
            app,
            raw_path=b"/api/public/chat/stream",
            method="POST",
            headers=[(b"x-forwarded-for", b"198.51.100.1"), (b"x-forwarded-for", b"198.51.100.1")],
            body=b'{"message":"Question","locale":"en"}',
        )
    )
    assert frames[0]["status"] == 400 and service.calls == 0


def test_gateway_revalidates_static_files_after_the_build_changes(tmp_path):
    root = tmp_path / "web"
    (root / ".vite").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "index.html").write_text("visitor")
    asset = root / "assets/main.js"
    asset.write_text("visitor")
    (root / ".vite/manifest.json").write_text(
        json.dumps(
            {
                "index.html": {"isEntry": True, "file": "assets/main.js"},
            }
        )
    )
    app, _settings = _gateway(tmp_path, web_dist=root)
    asset.unlink()
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        assert client.get("/assets/main.js").status_code == 404


def test_gateway_preheader_failure_and_stopped_head_use_safe_envelopes(tmp_path):
    app, settings = _gateway(tmp_path)
    for route in app.routes:
        if getattr(route, "path", None) == "/api/public/status":

            async def broken():
                raise RuntimeError("PRIVATE_URL_CANARY")

            route.dependant.call = broken
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        failed = client.get("/api/public/status", headers={"Origin": "https://fixture.github.io"})
        assert failed.status_code == 502 and failed.json()["error"]["code"] == "REQUEST_FAILED"
        assert "PRIVATE_" not in failed.text and "x-content-type-options" in failed.headers
        assert failed.headers["access-control-allow-origin"] == "https://fixture.github.io"
    settings["enabled"] = False
    frames = asyncio.run(_raw_asgi_request(app, method="HEAD"))
    assert frames[0]["status"] == 503
    assert b"".join(frame.get("body", b"") for frame in frames) == b""


@pytest.mark.parametrize(
    "version,accepted",
    [
        ("2.24.3", False),
        ("2.24.4", True),
        ("v2.39.4-desktop.1", True),
        ("5.0.0", True),
        ("2.24.4-rc.1", False),
        ("not-a-version", False),
    ],
)
def test_funnel_compose_baseline_rejects_unsupported_versions(version, accepted):
    assert supported(version) is accepted


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": ORIGIN, "Host": "evil.example"},
        {"Origin": ORIGIN + "/admin"},
        {"Origin": ORIGIN + "?ignored=true"},
        {"Origin": ORIGIN + "#ignored"},
        [("Origin", ORIGIN), ("Origin", "https://evil.example")],
        [("Host", "portfolio.example.com"), ("Host", "evil.example"), ("Origin", ORIGIN)],
    ],
)
def test_private_login_rejects_ambiguous_or_unbound_authority(tmp_path, headers):
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        response = client.post(
            "/api/admin/session",
            headers=headers,
            json={"username": "owner", "password": "incorrect-synthetic-password"},
        )
    assert response.status_code in {400, 403}
    assert "set-cookie" not in response.headers
    assert "incorrect-synthetic-password" not in response.text


@pytest.mark.parametrize("path", ["/api/admin/setup", "/api/admin/auth/methods"])
def test_private_auth_reads_bind_host_origin_and_allow_same_origin_referer(tmp_path, path):
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get(path, headers={"Origin": ORIGIN}).status_code == 200
        assert client.get(path, headers={"Referer": ORIGIN + "/admin"}).status_code == 200
        assert client.get(path).status_code in {400, 403}
        assert client.get(path, headers={"Origin": ORIGIN, "Host": "evil.example"}).status_code in {
            400,
            403,
        }


def test_private_origin_is_bound_to_actual_request_scheme(tmp_path):
    app = local_admin_application(tmp_path)
    with TestClient(app, base_url=ORIGIN.replace("https:", "http:")) as client:
        response = client.get("/api/admin/setup", headers={"Origin": ORIGIN})
    assert response.status_code in {400, 403}


def test_gateway_projection_does_not_rewrite_the_existing_local_status_contract():
    app = create_app(setup_state=SetupState(model_ready=True, model_provider="ollama"))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/public/status")
    assert response.status_code == 200
    assert response.json()["model"]["provider"] == "ollama"


def test_primary_built_admin_html_binds_actual_host_and_scheme(tmp_path):
    build = tmp_path / "web"
    build.mkdir()
    (build / "index.html").write_text("synthetic private admin shell")
    app = create_app(web_dist=build, admin_origins=(ORIGIN,))
    app.state.deployment_profile = "production"
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/admin").status_code == 200
        assert client.get("/admin", headers={"Host": "fixture.ts.net"}).status_code == 404
        assert (
            client.get(
                "/admin",
                headers={"Host": "evil.example", "X-Forwarded-Host": "portfolio.example.com"},
            ).status_code
            == 404
        )
    with TestClient(app, base_url=ORIGIN.replace("https:", "http:")) as client:
        assert client.get("/admin").status_code == 404


def test_gateway_resume_failure_preserves_primary_service_and_cleanup():
    class UnavailableGateway:
        stopped = False

        async def resume(self):
            raise RuntimeError("PRIVATE_GATEWAY_CANARY")

        async def shutdown(self):
            self.stopped = True

    gateway = UnavailableGateway()
    app = create_app()
    app.state.visitor_gateway = gateway
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "alive"}
        assert "PRIVATE_" not in client.get("/api/public/status").text
    assert gateway.stopped


def test_private_gateway_routes_drive_real_listener_with_auth_csrf_and_dated_report(tmp_path):
    primary = local_admin_application(tmp_path)
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    environment = load_environment(
        {
            "REPONPC_PUBLIC_BASE_URL": ORIGIN,
            "REPONPC_ADMIN_ORIGINS": ORIGIN,
            "REPONPC_VISITOR_GATEWAY_PORT": str(port),
            "REPONPC_SHUTDOWN_GRACE_SECONDS": "1",
        }
    )
    gateway = VisitorGateway(
        database=RuntimeDatabase(tmp_path),
        environment=environment,
        state_supplier=lambda: primary.state.reponpc,
        bundle_manager_supplier=lambda: None,
        chat_service_supplier=lambda: None,
        faq_supplier=lambda: None,
        web_dist=tmp_path / "missing-web",
    )
    primary.state.visitor_gateway = gateway
    base = "/api/admin/visitor-gateway"
    with TestClient(primary, base_url=ORIGIN) as client:
        assert client.get(base, headers={"Origin": ORIGIN}).status_code == 401
        csrf = _login(client)
        primary.state.reponpc = SetupState(
            index_ready=True, model_ready=True, index_version="fixture-index"
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        assert client.get(base).json()["revision"] == 1
        body = {
            "revision": 1,
            "gateway_origin": "https://fixture.ts.net",
            "pages_origin": "https://fixture.github.io",
        }
        assert client.put(base, json=body).status_code == 403
        assert (
            client.put(base, json={**body, "secret": "PRIVATE_CANARY"}, headers=headers).status_code
            == 400
        )
        assert client.put(base, json={**body, "revision": True}, headers=headers).status_code == 400
        assert (
            client.put(base, json={**body, "pages_origin": None}, headers=headers).status_code
            == 422
        )
        configured = client.put(base, json=body, headers=headers)
        assert configured.status_code == 200 and configured.json()["revision"] == 2
        started = client.post(base + "/start", json={"revision": 2}, headers=headers)
        assert started.status_code == 200 and started.json()["listener_ready"]
        assert not started.json()["external_verified"]
        revision = started.json()["revision"]
        for path in ("/api/admin/setup", "/admin", "/unknown"):
            assert (
                httpx.get(
                    f"http://127.0.0.1:{port}{path}", headers={"Host": "fixture.ts.net"}
                ).status_code
                == 404
            )
        status = httpx.get(
            f"http://127.0.0.1:{port}/api/public/status", headers={"Host": "fixture.ts.net"}
        )
        assert status.status_code == 200 and "model" not in status.json()
        proof = {
            "revision": revision,
            "external_checks_confirmed": True,
        }
        assert (
            client.post(
                base + "/verify", json={**proof, "bundle_id": "removed-field"}, headers=headers
            ).status_code
            == 400
        )
        assert (
            client.post(
                base + "/verify", json={**proof, "external_checks_confirmed": 1}, headers=headers
            ).status_code
            == 400
        )
        verified = client.post(base + "/verify", json=proof, headers=headers)
        assert verified.status_code == 200 and verified.json()["external_verified"]
        assert verified.json()["verification_method"] == "owner_reported"
        revision = verified.json()["revision"]
        assert (
            client.put(base, json={**body, "revision": revision}, headers=headers).status_code
            == 422
        )
        primary.state.reponpc = SetupState(
            index_ready=True, model_ready=False, index_version="fixture-index"
        )
        primary.state.reponpc = SetupState(
            index_ready=True, model_ready=True, index_version="fixture-index"
        )
        observed = client.get(base)
        assert observed.json()["external_verified"] and observed.json()["verified_at"]
        with pytest.MonkeyPatch.context() as patches:

            def owner_database_read_forbidden(*_args, **_kwargs):
                raise AssertionError("visitor request touched owner gateway settings")

            patches.setattr(gateway._store, "get", owner_database_read_forbidden)
            patches.setattr(gateway._store, "clear_verification", owner_database_read_forbidden)
            assert (
                httpx.get(
                    f"http://127.0.0.1:{port}/api/public/status",
                    headers={"Host": "fixture.ts.net", "Origin": "https://fixture.github.io"},
                ).status_code
                == 200
            )
            unavailable = httpx.post(
                f"http://127.0.0.1:{port}/api/public/chat/stream",
                headers={"Host": "fixture.ts.net"},
                json={"message": "Question", "locale": "en"},
            )
            assert (
                unavailable.status_code == 503
                and unavailable.json()["error"]["code"] == "SERVICE_NOT_READY"
            )
        assert client.post(base + "/verify", json=proof, headers=headers).status_code == 409
        stopped = client.post(base + "/stop", json={"revision": revision}, headers=headers)
        assert stopped.status_code == 200 and not stopped.json()["listener_ready"]
        assert stopped.json()["verified_at"] is None
        unavailable = client.post(
            base + "/verify",
            headers=headers,
            json={"revision": stopped.json()["revision"], "external_checks_confirmed": True},
        )
        assert (
            unavailable.status_code == 503
            and unavailable.json()["error"]["code"] == "GATEWAY_UNAVAILABLE"
        )
        cleared = client.put(
            base,
            json={
                "revision": stopped.json()["revision"],
                "gateway_origin": None,
                "pages_origin": None,
            },
            headers=headers,
        )
        assert cleared.status_code == 200 and cleared.json()["gateway_origin"] is None
        assert not cleared.json()["enabled"] and "set-cookie" not in cleared.headers
        assert cleared.headers["cache-control"] == "no-store"


def test_private_visitor_port_put_is_tri_state_and_bounded(tmp_path):
    primary = local_admin_application(tmp_path)
    environment = load_environment(
        {
            "REPONPC_PUBLIC_BASE_URL": ORIGIN,
            "REPONPC_ADMIN_ORIGINS": ORIGIN,
            "REPONPC_VISITOR_GATEWAY_PORT": "18001",
        }
    )
    gateway = VisitorGateway(
        database=RuntimeDatabase(tmp_path),
        environment=environment,
        state_supplier=lambda: primary.state.reponpc,
        bundle_manager_supplier=lambda: None,
        chat_service_supplier=lambda: None,
        faq_supplier=lambda: None,
        web_dist=tmp_path / "missing-web",
    )
    primary.state.visitor_gateway = gateway
    base = "/api/admin/visitor-gateway"
    origins = {
        "gateway_origin": "https://fixture.ts.net",
        "pages_origin": "https://fixture.github.io",
    }
    with TestClient(primary, base_url=ORIGIN) as client:
        csrf = _login(client)
        primary.state.reponpc = SetupState(
            index_ready=True, model_ready=True, index_version="fixture-index"
        )
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        status = client.get(base).json()
        assert status["visitor_port"] == 18001
        assert status["visitor_port_source"] == "environment"

        owner = client.put(
            base, json={"revision": 1, **origins, "visitor_port": 19000}, headers=headers
        )
        assert owner.status_code == 200
        assert owner.json()["visitor_port"] == 19000
        assert owner.json()["visitor_port_source"] == "owner"
        kept = client.put(base, json={"revision": 2, **origins}, headers=headers)
        assert kept.status_code == 200
        assert kept.json()["visitor_port"] == 19000
        assert kept.json()["visitor_port_source"] == "owner"
        cleared = client.put(
            base, json={"revision": 3, **origins, "visitor_port": None}, headers=headers
        )
        assert cleared.status_code == 200
        assert cleared.json()["visitor_port"] == 18001
        assert cleared.json()["visitor_port_source"] == "environment"

        revision = cleared.json()["revision"]
        for invalid in (1023, 65536, "19000", True):
            rejected = client.put(
                base,
                json={"revision": revision, **origins, "visitor_port": invalid},
                headers=headers,
            )
            assert rejected.status_code == 400, invalid
        app_port_conflict = client.put(
            base,
            json={"revision": revision, **origins, "visitor_port": environment.port},
            headers=headers,
        )
        assert app_port_conflict.status_code == 422
        assert app_port_conflict.json()["error"]["code"] == "GATEWAY_CONFIGURATION_INVALID"
        assert client.get(base).json()["revision"] == revision


def test_aggregate_admission_keeps_atomic_daily_budget_without_a_fake_ip_bucket(tmp_path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    limits = ChatLimits(
        database,
        ip_hash_key=b"synthetic-only-test-key" * 2,
        requests_per_minute=1,
        daily_budget=3,
        global_concurrency=2,
    )

    def admit(_index):
        try:
            limits.admit_public_chat(None)
        except ChatLimitError as exc:
            return exc.code
        return "accepted"

    with ThreadPoolExecutor(max_workers=5) as executor:
        outcomes = list(executor.map(admit, range(5)))
    assert outcomes.count("accepted") == 3
    assert outcomes.count("DAILY_BUDGET_EXHAUSTED") == 2
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rate_buckets").fetchone()[0] == 0
        assert connection.execute("SELECT SUM(accepted_count) FROM daily_usage").fetchone()[0] == 3


@pytest.mark.parametrize("failing_stage", ["embedding", "generation"])
def test_gateway_grounded_flow_charges_once_and_never_retries_provider(tmp_path, failing_stage):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    limits = ChatLimits(
        database,
        ip_hash_key=b"synthetic-only-test-key" * 2,
        requests_per_minute=1,
        daily_budget=3,
        global_concurrency=1,
    )
    chat = FixtureChat(
        READY, [ProviderFailureCode.UNAVAILABLE] if failing_stage == "generation" else []
    )
    embedding = FixtureEmbedding(
        READY, [ProviderFailureCode.UNAVAILABLE] if failing_stage == "embedding" else []
    )
    service = GroundedChatService(
        bundles=Bundles(),
        providers=ProviderRuntime(chat=chat, embedding=embedding, max_attempts=3),
        limits=limits,
        max_output_tokens=100,
        timeout_seconds=45,
    )
    with pytest.raises(ProviderError) as rejected:
        service.answer(
            message="What is implemented?",
            locale="en",
            history=(),
            client_ip=None,
            timeout_seconds=1,
            allow_retry=False,
        )
    assert rejected.value.code is ProviderFailureCode.UNAVAILABLE
    assert embedding.calls == 1
    assert len(chat.calls) == (1 if failing_stage == "generation" else 0)
    if chat.calls:
        assert 0 < chat.calls[0] <= 1
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rate_buckets").fetchone()[0] == 0
        assert connection.execute("SELECT SUM(accepted_count) FROM daily_usage").fetchone()[0] == 1


@pytest.mark.parametrize(
    "assignment,parameters",
    [
        ("id = ?", (2,)),
        ("revision = ?", (0,)),
        ("enabled = ?", (2,)),
        ("gateway_origin = ?", ("https://fixture.ts.net",)),
        ("verified_at = ?", ("2026-09-29T00:00:00Z",)),
        ("verification_method = ?", ("automatically_probed",)),
        ("verification_bundle_id = ?", ("x" * 129,)),
    ],
)
def test_gateway_runtime_schema_rejects_partial_or_impossible_state(
    tmp_path, assignment, parameters
):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO visitor_gateway_settings(id,revision,enabled) VALUES(1,1,0)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE visitor_gateway_settings SET " + assignment + " WHERE id = 1",
                parameters,
            )
        row = connection.execute(
            "SELECT revision,enabled,gateway_origin,pages_origin,verified_at "
            "FROM visitor_gateway_settings WHERE id = 1"
        ).fetchone()
        assert tuple(row) == (1, 0, None, None, None)


def test_gateway_complete_report_has_bounded_fields_and_cannot_become_partial(tmp_path):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    with database.connection() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO visitor_gateway_settings(id,revision,enabled) VALUES(1,1,0)"
        )
        connection.execute(
            "UPDATE visitor_gateway_settings SET gateway_origin=?,pages_origin=?,"
            "verification_gateway_origin=?,verification_pages_origin=?,"
            "verification_bundle_id=?,verified_at=?,verification_method=? WHERE id=1",
            (
                "https://fixture.ts.net",
                "https://fixture.github.io",
                "https://fixture.ts.net",
                "https://fixture.github.io",
                "fixture-index",
                "2026-09-29T00:00:00Z",
                "owner_reported",
            ),
        )
        original = tuple(
            connection.execute("SELECT * FROM visitor_gateway_settings WHERE id=1").fetchone()
        )
        for field, value in [
            ("gateway_origin", "x" * 2049),
            ("verification_gateway_origin", "x" * 2049),
            ("verification_bundle_id", "x" * 129),
            ("verified_at", "x" * 33),
            ("verification_method", "automatically_probed"),
            ("verification_bundle_id", None),
        ]:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE visitor_gateway_settings SET " + field + "=? WHERE id=1", (value,)
                )
            assert (
                tuple(
                    connection.execute(
                        "SELECT * FROM visitor_gateway_settings WHERE id=1"
                    ).fetchone()
                )
                == original
            )
