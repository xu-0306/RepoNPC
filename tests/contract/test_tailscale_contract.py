"""ADR-082 API injection, persisted gateway and browser-fixture contracts."""

from __future__ import annotations

import inspect
import json

import pytest
from fastapi.testclient import TestClient

from reponpc.api.admin import GatewayRevisionRequest, create_admin_router
from reponpc.tailscale.runner import serve_status_command, status_command
from reponpc.tailscale.state import parse_serve, parse_status
from tests.browser.tailscale_server import build_tailscale_application
from tests.security.test_a5_sharing_review import _visitor_build
from tests.support.fake_tailscale import HOST, FakeTailscaleRunner, fixture_state

pytestmark = pytest.mark.usefixtures("reponpc_logger")


def test_router_dependency_is_optional_and_additive():
    signature = inspect.signature(create_admin_router)
    parameter = signature.parameters["tailscale_supplier"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default() is None
    router = create_admin_router(service_supplier=lambda: None, origins_supplier=lambda: ())
    paths = {route.path for route in router.routes}
    assert {
        "/api/admin/tailscale/status",
        "/api/admin/tailscale/funnel/start",
        "/api/admin/tailscale/funnel/stop",
        "/api/admin/visitor-gateway",
    } <= paths
    assert set(GatewayRevisionRequest.model_fields) == {"revision"}
    assert GatewayRevisionRequest.model_config["extra"] == "forbid"


def test_synthetic_fixture_shape_and_version():
    fixture = fixture_state()
    assert fixture["status"]["Version"] == "1.104.4-tfixture-gfixture"
    assert parse_status(fixture["status"]).dns_name == HOST + "."
    assert parse_serve(fixture["serve"]).web == ()
    assert set(fixture["serve"]) == {"TCP", "Web", "AllowFunnel"}


def test_scripted_runner_reloads_file_on_every_call(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(fixture_state()), encoding="utf-8", newline="\n")
    runner = FakeTailscaleRunner(state_file=state_file)
    assert json.loads(runner.run(status_command()))["BackendState"] == "Running"
    data = fixture_state()
    data["status"]["BackendState"] = "NeedsLogin"
    state_file.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    assert json.loads(runner.run(status_command()))["BackendState"] == "NeedsLogin"
    assert json.loads(runner.run(serve_status_command())) == data["serve"]


def test_browser_fixture_loopback_status_tracks_editable_state(tmp_path, reponpc_logger):
    state_file = tmp_path / "tailscale-state.json"
    fixture, launch_url = build_tailscale_application(
        tmp_path / "runtime",
        _visitor_build(tmp_path),
        state_file,
        pages_url="https://fixture.github.io/project/",
    )
    application = fixture.application
    assert application.state.deployment_profile == "loopback_evaluation"
    assert application.state.tailscale_service.gateway is application.state.visitor_gateway
    origin = "http://127.0.0.1:8881"
    with TestClient(fixture, base_url=origin, client=("127.0.0.1", 54321)) as client:
        launch = client.post(
            "/api/admin/session/local-launch",
            headers={"Origin": origin},
            json={"grant": launch_url.split("#local-launch=")[1]},
        )
        assert launch.status_code == 200
        cookie = launch.headers["set-cookie"].split(";", 1)[0]
        headers = {"Origin": origin, "Cookie": cookie}
        ready = client.get("/api/admin/tailscale/status", headers=headers)
        assert ready.status_code == 200 and ready.json()["state"] == "ready"
        data = fixture_state()
        data["status"]["Self"]["Online"] = False
        state_file.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        offline = client.get("/api/admin/tailscale/status", headers=headers)
        assert offline.status_code == 200 and offline.json()["state"] == "offline"
        data["installed"] = False
        state_file.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        assert (
            client.get("/api/admin/tailscale/status", headers=headers).json()["state"]
            == "not_installed"
        )


@pytest.mark.parametrize("port,gateway_port", [(8090, 8882), (8881, 8090), (8881, 8881)])
def test_fixture_rejects_ports_outside_assignment(tmp_path, port, gateway_port):
    with pytest.raises(ValueError, match="fixture ports"):
        build_tailscale_application(
            tmp_path / "runtime",
            tmp_path / "web",
            tmp_path / "state.json",
            port=port,
            gateway_port=gateway_port,
        )
    assert not (tmp_path / "runtime").exists()
