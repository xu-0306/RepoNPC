"""Authenticated routes exercise only a synthetic runner, including hostile output."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import fields

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.auth import AdminSessionService, issue_admin_local_launch_grant
from reponpc.api.admin import create_admin_router
from reponpc.api.visitor_gateway import VisitorGateway
from reponpc.config.environment import load_environment
from reponpc.main import create_app
from reponpc.runtime.database import RuntimeDatabase
from reponpc.tailscale.service import TailscaleFunnelService
from reponpc.tailscale.state import FunnelStatus
from tests.support.fake_tailscale import FakeTailscaleRunner, add_route
from tests.unit.test_tailscale_service import Gateway

ROUTES = [
    ("GET", "/api/admin/tailscale/status"),
    ("POST", "/api/admin/tailscale/funnel/start"),
    ("POST", "/api/admin/tailscale/funnel/stop"),
]
ORIGIN = "http://127.0.0.1:8881"
STATUS_KEYS = {"state", "funnel_url", "port", "version"}
GATEWAY_KEYS = {
    "revision",
    "gateway_origin",
    "pages_origin",
    "enabled",
    "listener_ready",
    "error_code",
    "local_ready",
    "entry_configured",
    "external_verified",
    "verified_at",
    "verification_method",
    "active_bundle_id",
    "client_identity_mode",
    "visitor_port",
    "visitor_port_source",
}
pytestmark = pytest.mark.usefixtures("reponpc_logger")


@pytest.fixture
def api(tmp_path, reponpc_logger, caplog):
    # Capture the app sink directly even when an existing server disabled propagation.
    reponpc_logger.addHandler(caplog.handler)
    database = RuntimeDatabase(tmp_path / "runtime")
    database.initialize()
    auth = AdminSessionService(
        database=database, identity_hmac_key=b"f" * 32, deployment_profile="loopback_evaluation"
    )
    app = create_app(
        admin_session_service=auth, admin_origins=(ORIGIN,), web_dist=tmp_path / "missing"
    )
    app.state.deployment_profile = "loopback_evaluation"
    app.state.trusted_hosts = ("127.0.0.1",)
    gateway = Gateway()
    runner = FakeTailscaleRunner()
    pages = {"origin": "https://fixture.github.io"}
    service = TailscaleFunnelService(
        profile="loopback_evaluation",
        gateway=gateway,
        pages_origin_supplier=lambda: pages["origin"],
        runner=runner,
        executable_supplier=lambda: "/fixture/tailscale.exe",
    )
    # Exercise the same optional supplier used by production wiring, before the old routes.
    router = create_admin_router(
        service_supplier=lambda: auth,
        origins_supplier=lambda: (ORIGIN,),
        tailscale_supplier=lambda: service,
    )
    app.router.routes[0:0] = router.routes
    grant = issue_admin_local_launch_grant(database, deployment_profile="loopback_evaluation")
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 54321)) as client:
        launch = client.post(
            "/api/admin/session/local-launch", headers={"Origin": ORIGIN}, json={"grant": grant}
        )
        assert launch.status_code == 200
        cookie = launch.headers["set-cookie"].split(";", 1)[0]
        headers = {"Origin": ORIGIN, "Cookie": cookie, "X-CSRF-Token": launch.json()["csrf_token"]}
        yield client, headers, runner, gateway, pages, app, service, database


def request(client, method, path, headers, revision=1):
    return client.request(
        method,
        path,
        headers=headers,
        **({"json": {"revision": revision}} if method == "POST" else {}),
    )


def assert_private(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_status_start_stop_exact_response_keys_and_idempotency(api):
    client, headers, runner, _gateway, _pages, _app, _service, _db = api
    ready = client.get(ROUTES[0][1], headers=headers)
    assert ready.status_code == 200
    assert_private(ready)
    assert set(ready.json()) == STATUS_KEYS
    assert ready.json()["state"] == "ready"
    first = request(client, *ROUTES[1], headers)
    assert first.status_code == 200
    assert_private(first)
    assert set(first.json()) == {"tailscale", "gateway"}
    assert set(first.json()["tailscale"]) == STATUS_KEYS
    assert set(first.json()["gateway"]) == GATEWAY_KEYS
    assert first.json()["tailscale"]["state"] == "live"
    again = request(client, *ROUTES[1], headers, first.json()["gateway"]["revision"])
    assert again.status_code == 200
    assert again.json() == first.json()
    assert sum(command[1:3] == ("funnel", "--bg") for command in runner.calls) == 1
    stopped = request(client, *ROUTES[2], headers, first.json()["gateway"]["revision"])
    assert stopped.status_code == 200
    assert stopped.json()["tailscale"]["state"] == "ready"
    assert stopped.json()["gateway"]["listener_ready"] is False
    assert set(stopped.json()) == {"tailscale", "gateway"}


@pytest.mark.parametrize("method,path", ROUTES)
def test_each_route_requires_session(api, method, path):
    client, _headers, runner, *_ = api
    client.cookies.clear()
    response = request(client, method, path, {"Origin": ORIGIN, "X-CSRF-Token": "invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert_private(response)
    assert runner.calls == []


@pytest.mark.parametrize("method,path", ROUTES)
@pytest.mark.parametrize("origin", [None, "https://foreign.invalid", "http://localhost:8881"])
def test_each_route_requires_same_origin(api, method, path, origin):
    client, headers, runner, *_ = api
    headers = {key: value for key, value in headers.items() if key != "Origin"}
    if origin is not None:
        headers["Origin"] = origin
    response = request(client, method, path, headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
    assert_private(response)
    assert runner.calls == []


@pytest.mark.parametrize("method,path", ROUTES[1:])
@pytest.mark.parametrize("csrf", [None, "", "invalid"])
def test_each_write_requires_csrf(api, method, path, csrf):
    client, headers, runner, *_ = api
    headers = {key: value for key, value in headers.items() if key != "X-CSRF-Token"}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    response = request(client, method, path, headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"
    assert runner.calls == []


def test_status_read_does_not_require_csrf_but_requires_session_and_origin(api):
    client, headers, _runner, *_ = api
    response = client.get(
        ROUTES[0][1],
        headers={key: value for key, value in headers.items() if key != "X-CSRF-Token"},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("method,path", ROUTES[1:])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"revision": True},
        {"revision": "1"},
        {"revision": 1.0},
        {"revision": 0},
        {"revision": 1, "port": 443},
        {"revision": 1, "command": "reset"},
    ],
)
def test_write_models_are_strict_and_reject_extra_fields(api, method, path, body):
    client, headers, runner, *_ = api
    response = client.request(method, path, headers=headers, json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["details"]["fields"]
    assert runner.calls == []


def test_pages_missing_returns_422_before_any_command(api):
    client, headers, runner, _gateway, pages, *_ = api
    pages["origin"] = None
    response = request(client, *ROUTES[1], headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GATEWAY_CONFIGURATION_INVALID"
    assert runner.calls == []


@pytest.mark.parametrize("method,path", ROUTES)
def test_production_never_calls_service_or_cli(api, method, path):
    client, headers, runner, _gateway, _pages, app, *_ = api
    app.state.deployment_profile = "production"
    response = request(client, method, path, headers)
    if method == "GET":
        assert response.status_code == 200
        assert response.json() == {
            "state": "unavailable_profile",
            "funnel_url": None,
            "port": None,
            "version": None,
        }
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "TAILSCALE_NOT_READY"
    assert_private(response)
    assert runner.calls == []


@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "oversize"])
def test_canary_cli_failures_never_enter_response_or_logs(api, caplog, failure):
    client, headers, runner, *_ = api
    runner.state["failure"] = failure
    with caplog.at_level(logging.INFO, logger="reponpc"):
        status = client.get(ROUTES[0][1], headers=headers)
        start = request(client, *ROUTES[1], headers)
        stop = request(client, *ROUTES[2], headers)
    assert status.status_code == 200 and status.json()["state"] == "error"
    for response in (start, stop):
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "TAILSCALE_FAILED"
        assert (
            response.json()["error"]["message"] == "The Tailscale operation could not be completed."
        )
        assert set(response.json()) == {"error"}
        assert set(response.json()["error"]) == {
            "code",
            "message",
            "request_id",
            "details",
            "retry_after_seconds",
        }
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "CANARY-CLI-PRIVATE" not in status.text + start.text + stop.text
    assert any(record.getMessage().startswith("tailscale_state") for record in caplog.records)
    assert all("CANARY-CLI-PRIVATE" not in repr(record.__dict__) for record in caplog.records)


def test_canary_success_output_and_other_hosts_never_enter_response_or_logs(api, caplog):
    client, headers, runner, *_ = api
    canary = "canary-other-machine.tailnet-fixture.ts.net"
    runner.state["status"]["Peer"] = {canary: {"DNSName": canary}}
    add_route(runner.state["serve"], 443, host=canary, visitor_port=8883)
    with caplog.at_level(logging.INFO, logger="reponpc"):
        response = request(client, *ROUTES[1], headers)
        stopped = request(client, *ROUTES[2], headers, response.json()["gateway"]["revision"])
    assert response.status_code == stopped.status_code == 200
    assert canary not in response.text + stopped.text
    assert "CANARY-CLI-PRIVATE" not in response.text + stopped.text
    assert any(record.getMessage().startswith("tailscale_state") for record in caplog.records)
    for record in caplog.records:
        if record.name == "reponpc" and record.msg.startswith("tailscale_state"):
            assert record.state in {"live", "ready"}
            assert record.port in {8443, 10000, 443}
            assert record.visitor_port == 8882
            assert record.getMessage() == (
                f"tailscale_state state={record.state} port={record.port} visitor_port=8882"
            )
        assert canary not in repr(record.__dict__)
        assert "CANARY-CLI-PRIVATE" not in repr(record.__dict__)


def test_foreign_routes_on_every_port_cannot_be_changed_via_api(api):
    client, headers, runner, *_ = api
    for port in (443, 8443, 10000):
        add_route(runner.state["serve"], port, visitor_port=8883)
    before = deepcopy(runner.state)
    start = request(client, *ROUTES[1], headers)
    stop = request(client, *ROUTES[2], headers)
    assert start.status_code == 409
    assert start.json()["error"]["code"] == "TAILSCALE_NOT_READY"
    assert stop.status_code == 200
    assert runner.state == before
    assert all(command[1] != "funnel" for command in runner.calls)


@pytest.mark.parametrize("method,path", ROUTES[1:])
def test_conflict_is_409_and_fixed_error(api, method, path):
    client, headers, runner, *_ = api
    response = request(client, method, path, headers, revision=99)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GATEWAY_CONFLICT"
    assert response.json()["error"]["message"] == "The Tailscale operation could not be completed."
    assert runner.calls == []


def test_running_different_settings_is_422(api):
    client, headers, runner, gateway, *_ = api
    gateway.value.update(listener_ready=True, enabled=True, pages_origin="https://other.github.io")
    response = request(client, *ROUTES[1], headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GATEWAY_CONFIGURATION_INVALID"
    assert all(command[1] != "funnel" for command in runner.calls)


def test_response_dataclass_has_only_the_contract_fields():
    assert {field.name for field in fields(FunnelStatus)} == STATUS_KEYS


def test_real_gateway_revision_integration_without_binding_sockets(api, tmp_path, monkeypatch):
    client, headers, _runner, _gateway, _pages, _app, service, database = api
    environment = load_environment(
        {
            "REPONPC_DEPLOYMENT_PROFILE": "loopback_evaluation",
            "REPONPC_HOST": "127.0.0.1",
            "REPONPC_PORT": "8881",
            "REPONPC_PUBLIC_BASE_URL": ORIGIN,
            "REPONPC_ADMIN_ORIGINS": ORIGIN,
            "REPONPC_VISITOR_GATEWAY_PORT": "8882",
        }
    )
    gateway = VisitorGateway(
        database=database,
        environment=environment,
        state_supplier=lambda: None,
        bundle_manager_supplier=lambda: None,
        chat_service_supplier=lambda: None,
        faq_supplier=lambda: None,
        web_dist=tmp_path / "missing",
    )
    listening = False

    async def listen(_settings):
        nonlocal listening
        listening = True

    async def stop_listener():
        nonlocal listening
        listening = False
        return True

    monkeypatch.setattr(gateway, "_listen", listen)
    monkeypatch.setattr(gateway, "_stop_listener", stop_listener)
    monkeypatch.setattr(gateway, "_listener_ready", lambda: listening)
    service.gateway = gateway
    first = request(client, *ROUTES[1], headers)
    assert first.status_code == 200
    assert first.json()["gateway"]["revision"] == 3
    second = request(client, *ROUTES[1], headers, revision=3)
    assert second.status_code == 200 and second.json() == first.json()
    stopped = request(client, *ROUTES[2], headers, revision=3)
    # Stop bumps the revision 3 -> 4, then clearing the saved addresses bumps it 4 -> 5.
    assert stopped.status_code == 200 and stopped.json()["gateway"]["revision"] == 5
    assert stopped.json()["gateway"]["listener_ready"] is False
    assert stopped.json()["gateway"]["gateway_origin"] is None
    assert stopped.json()["gateway"]["pages_origin"] is None
    stored = gateway.snapshot()
    assert stored["gateway_origin"] is None and stored["pages_origin"] is None
