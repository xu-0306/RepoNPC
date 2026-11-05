"""ADR-080 exercises sharing and local sign-in through real application requests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService, issue_admin_local_launch_grant
from reponpc.api.visitor_gateway import VisitorGateway, VisitorGatewayError
from reponpc.config.environment import EnvironmentValidationError, load_environment
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase


@pytest.fixture(params=[8842, 9123])
def sharing(request, tmp_path: Path):
    origin = f"http://localhost:{request.param}"
    settings = load_environment(
        {
            "REPONPC_DEPLOYMENT_PROFILE": "loopback_evaluation",
            "REPONPC_HOST": "127.0.0.1",
            "REPONPC_PORT": str(request.param),
            "REPONPC_PUBLIC_BASE_URL": origin,
            "REPONPC_ADMIN_ORIGINS": origin,
            "REPONPC_TRUSTED_HOSTS": "localhost,127.0.0.1",
            "REPONPC_VISITOR_GATEWAY_PORT": "8942",
            "REPONPC_DATA_DIR": str(tmp_path / "prepared"),
            "REPONPC_IP_HASH_KEY": "host-boundary-fixture",
        }
    )
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    service = AdminSessionService(
        database=database,
        identity_hmac_key=b"i" * 32,
        deployment_profile=settings.deployment_profile,
    )
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>Admin</html>", encoding="utf-8")
    (web / "asset.js").write_text("console.log('fixture');", encoding="utf-8")
    app = create_app(
        admin_session_service=service, admin_origins=settings.admin_origins, web_dist=web
    )
    app.state.deployment_profile = settings.deployment_profile
    app.state.trusted_hosts = settings.trusted_hosts
    gateway = VisitorGateway(
        database=database,
        environment=settings,
        state_supplier=lambda: app.state.reponpc,
        bundle_manager_supplier=lambda: None,
        chat_service_supplier=lambda: None,
        faq_supplier=lambda: None,
        web_dist=tmp_path / "missing-web",
    )
    app.state.visitor_gateway = gateway
    return app, database, gateway, settings, origin


def _configure(gateway: VisitorGateway):
    return asyncio.run(
        gateway.configure(
            revision=1,
            gateway_origin="https://example.ts.net",
            pages_origin="https://portfolio.github.io",
        )
    )


@pytest.mark.parametrize("endpoint", ["local-launch", "resume"])
def test_funnel_host_is_refused_by_trusted_host_before_admin(sharing, endpoint: str):
    app, database, gateway, _settings, origin = sharing
    _configure(gateway)
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        response = client.post(
            f"/api/admin/session/{endpoint}",
            headers={"Host": "example.ts.net", "Origin": origin},
            json={"grant": grant} if endpoint == "local-launch" else None,
        )
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0] == 0
    assert "set-cookie" not in response.headers
    assert response.status_code == 400
    assert response.text == "Invalid host header"


@pytest.mark.parametrize("endpoint", ["local-launch", "resume"])
@pytest.mark.parametrize("header", ["X-Forwarded-For", "Forwarded"])
def test_forwarded_loopback_request_cannot_exchange_or_resume(sharing, endpoint, header):
    app, database, gateway, _settings, origin = sharing
    _configure(gateway)
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        launched = client.post(
            "/api/admin/session/local-launch",
            headers={"Origin": origin},
            json={"grant": grant},
        )
        assert launched.status_code == 200
        cookie = launched.headers["set-cookie"].split(";", 1)[0]
        fresh = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
        response = client.post(
            f"/api/admin/session/{endpoint}",
            headers={
                "Host": origin.removeprefix("http://"),
                "Origin": origin,
                "Cookie": cookie,
                header: "203.0.113.42" if header == "X-Forwarded-For" else "for=203.0.113.42",
            },
            json={"grant": fresh} if endpoint == "local-launch" else None,
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == (
        "LOCAL_LAUNCH_DENIED" if endpoint == "local-launch" else "AUTHENTICATION_REQUIRED"
    )
    assert "set-cookie" not in response.headers
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT consumed_at FROM admin_local_launch_grants WHERE state_key = 'current'"
            ).fetchone()[0]
            is None
        )


def test_loopback_gateway_accepts_explicit_separate_hosts(sharing):
    _app, _database, gateway, _settings, _origin = sharing
    snapshot = _configure(gateway)
    assert snapshot["gateway_origin"] == "https://example.ts.net"
    assert snapshot["pages_origin"] == "https://portfolio.github.io"
    assert snapshot["client_identity_mode"] == "aggregate"


@pytest.mark.parametrize(
    "changes,gateway_origin,pages_origin",
    [
        ({"admin_origins_explicit": False}, "https://example.ts.net", "https://a.github.io"),
        ({}, "http://example.ts.net", "https://a.github.io"),
        ({}, "https://a.github.io", "https://a.github.io"),
        (
            {"admin_origins": ("https://example.ts.net",)},
            "https://example.ts.net",
            "https://a.github.io",
        ),
        (
            {"admin_origins": ("https://a.github.io",)},
            "https://example.ts.net",
            "https://a.github.io",
        ),
    ],
)
def test_loopback_gateway_keeps_origin_rejections(sharing, changes, gateway_origin, pages_origin):
    _app, _database, gateway, settings, _origin = sharing
    gateway._environment = replace(settings, **changes)
    with pytest.raises(VisitorGatewayError) as raised:
        asyncio.run(
            gateway.configure(revision=1, gateway_origin=gateway_origin, pages_origin=pages_origin)
        )
    assert raised.value.code == "GATEWAY_CONFIGURATION_INVALID"


@pytest.mark.parametrize("origin", ["https://admin.example.net", "https://remote.example.org:9443"])
def test_loopback_environment_still_refuses_public_admin_origins(origin: str):
    with pytest.raises(EnvironmentValidationError) as raised:
        load_environment(
            {
                "REPONPC_DEPLOYMENT_PROFILE": "loopback_evaluation",
                "REPONPC_HOST": "127.0.0.1",
                "REPONPC_PUBLIC_BASE_URL": "http://localhost:8842",
                "REPONPC_ADMIN_ORIGINS": origin,
            }
        )
    assert any(issue.code == "loopback_profile_exposed" for issue in raised.value.issues)


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://other.example.org"}])
def test_loopback_configured_admin_origins_guard_writes_before_body_parsing(sharing, headers):
    app, database, _gateway, _settings, origin = sharing
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        response = client.post("/api/admin/session", headers=headers, content=b"{")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
    assert "set-cookie" not in response.headers
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0] == 0


@pytest.mark.parametrize("profile", ["production", "loopback_evaluation"])
def test_unconfigured_admin_origins_preserve_unguarded_auth_discovery(profile: str):
    app = create_app()
    app.state.deployment_profile = profile
    with TestClient(app, base_url="http://localhost:9123") as client:
        response = client.get("/api/admin/auth/methods")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_NOT_READY"


def test_loopback_origin_guard_covers_reads_and_mismatched_host(sharing):
    app, _database, _gateway, _settings, origin = sharing
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        assert client.get("/api/admin/auth/methods").status_code == 403
        assert client.get("/api/admin/auth/methods", headers={"Origin": origin}).status_code == 200
        rejected = client.get(
            "/api/admin/auth/methods",
            headers={"Host": "127.0.0.1:9123", "Origin": origin},
        )
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_FAILED"


HOST_HEADERS = [
    pytest.param([("Host", "example.ts.net")], id="public"),
    pytest.param([("Host", "localhost.evil.test")], id="localhost-lookalike"),
    pytest.param([("Host", "127.0.0.1.evil.test")], id="ip-lookalike"),
    pytest.param([("Host", "")], id="empty"),
    pytest.param([], id="missing"),
    pytest.param([("Host", "localhost"), ("Host", "example.ts.net")], id="duplicate-last-bad"),
    pytest.param([("Host", "example.ts.net"), ("Host", "localhost")], id="duplicate-first-bad"),
    pytest.param([("Host", "localhost"), ("Host", "localhost")], id="duplicate-allowed"),
]
HOST_ROUTES = [
    ("GET", "/admin"),
    ("GET", "/asset.js"),
    ("GET", "/healthz"),
    ("GET", "/api/public/status"),
    ("POST", "/api/admin/session/local-launch"),
]


def _host_request(client, method, path, host_headers, origin, grant):
    request = client.build_request(
        method,
        path,
        headers={"Origin": origin, "X-Request-ID": "00000000-0000-4000-8000-000000000001"},
        json={"grant": grant} if method == "POST" else None,
    )
    del request.headers["host"]
    request.headers = httpx.Headers([*request.headers.multi_items(), *host_headers])

    async def send():
        # TestClient inserts a missing Host; ASGITransport preserves the raw headers.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client.app, client=("127.0.0.1", 54321))
        ) as transport:
            return await transport.send(request)

    return client.portal.call(send)


@pytest.mark.parametrize("host_headers", HOST_HEADERS)
def test_loopback_host_allowlist_rejects_every_main_route(sharing, host_headers):
    app, database, _gateway, _settings, origin = sharing
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        for method, path in HOST_ROUTES:
            response = _host_request(client, method, path, host_headers, origin, grant)
            assert response.status_code == 400, path
            assert response.text == "Invalid host header", path
            assert "set-cookie" not in response.headers
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0] == 0
        assert (
            connection.execute(
                "SELECT consumed_at FROM admin_local_launch_grants WHERE state_key = 'current'"
            ).fetchone()[0]
            is None
        )


@pytest.mark.parametrize("host_headers", HOST_HEADERS)
@pytest.mark.parametrize("profile", ["production", "loopback_evaluation"])
def test_host_allowlist_preserves_production_and_empty_list_responses(
    sharing, host_headers, profile
):
    app, database, _gateway, _settings, origin = sharing
    app.state.deployment_profile = profile
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        for method, path in HOST_ROUTES:
            app.state.trusted_hosts = ()
            baseline = _host_request(client, method, path, host_headers, origin, grant)
            # Existing static-file and launch-origin guards still reject unsuitable hosts.
            assert baseline.status_code == (
                (403 if profile == "production" else 401)
                if method == "POST"
                else 404
                if profile == "production" and path in {"/admin", "/asset.js"}
                else 200
            ), path
            assert baseline.text != "Invalid host header"
            if profile == "production":
                app.state.trusted_hosts = ("localhost", "127.0.0.1")
                response = _host_request(client, method, path, host_headers, origin, grant)
                assert response.status_code == baseline.status_code, path
                assert response.content == baseline.content, path


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "LOCALHOST"])
def test_allowed_host_ports_support_admin_launch_sharing_and_separate_gateway(sharing, host):
    app, database, gateway, settings, _origin = sharing
    origin = f"http://{host.lower()}:{settings.port}"
    app.state.admin_origins = (origin,)
    gateway._environment = replace(settings, admin_origins=(origin,))
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    headers = {"Host": f"{host}:{settings.port}", "Origin": origin}
    with TestClient(app, base_url=origin, client=("127.0.0.1", 54321)) as client:
        for path in ("/healthz", "/admin", "/asset.js", "/api/public/status"):
            assert client.get(path, headers=headers).status_code == 200, path
        launched = client.post(
            "/api/admin/session/local-launch", headers=headers, json={"grant": grant}
        )
        assert launched.status_code == 200
        headers["Cookie"] = launched.headers["set-cookie"].split(";", 1)[0]
        headers["X-CSRF-Token"] = launched.json()["csrf_token"]
        configured = client.put(
            "/api/admin/visitor-gateway",
            headers=headers,
            json={
                "revision": 1,
                "gateway_origin": "https://example.ts.net",
                "pages_origin": "https://portfolio.github.io",
            },
        )
        assert configured.status_code == 200
        started = client.post(
            "/api/admin/visitor-gateway/start",
            headers=headers,
            json={"revision": configured.json()["revision"]},
        )
        assert started.status_code == 200
        assert started.json()["listener_ready"] is True
        assert client.get("/api/admin/visitor-gateway", headers=headers).status_code == 200
        public = httpx.get(
            "http://127.0.0.1:8942/api/public/status",
            headers={"Host": "example.ts.net", "Origin": "https://portfolio.github.io"},
            trust_env=False,
        )
        assert public.status_code == 200
        assert public.json()["status"] == "resting"


def test_prepare_application_updates_host_policy_without_readding_middleware(
    sharing, monkeypatch, reponpc_logger
):
    import reponpc.main as main

    app, _database, _gateway, settings, origin = sharing
    monkeypatch.setattr(main, "app", app)
    assert main.prepare_application(settings, owned_host=False) is app
    assert main.prepare_application(settings, owned_host=False) is app
    with TestClient(app, base_url=origin) as client:
        assert client.get("/healthz", headers={"Host": "example.ts.net"}).status_code == 400
        assert (
            main.prepare_application(replace(settings, trusted_hosts=()), owned_host=False) is app
        )
        assert client.get("/healthz", headers={"Host": "example.ts.net"}).status_code == 200
        assert (
            main.prepare_application(
                replace(settings, trusted_hosts=("OTHER.Local",)), owned_host=False
            )
            is app
        )
        assert client.get("/healthz", headers={"Host": "other.LOCAL:9234"}).status_code == 200
        assert client.get("/healthz", headers={"Host": "localhost:8842"}).status_code == 400
    assert len(app.user_middleware) == 1
