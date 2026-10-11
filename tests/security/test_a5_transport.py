"""Verify the disposable browser transport uses a real stoppable gateway."""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application


def test_browser_fixture_maps_exact_origin_and_stops_the_real_listener(tmp_path: Path) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    origin = "https://private.example.com"
    static_origin = "http://127.0.0.1:8781"
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_bytes(
        b'<html data-owner-mode="system" data-visitor-toggle="true"><head>'
        b"<title>Disposable fixture</title></head><body></body></html>"
    )
    audit_script = tmp_path / "test-audit.js"
    audit_script.write_bytes(b"/* transport test only */")
    app = build_application(
        tmp_path / "host",
        web,
        origin,
        audit_script=audit_script,
        gateway_port=port,
        static_origin=static_origin,
    )
    address = f"http://127.0.0.1:{port}"
    with TestClient(app, base_url=origin) as private:
        assert app.application.state.visitor_gateway.snapshot()["listener_ready"]
        entrance = private.get("/")
        assert entrance.status_code == 200
        assert b'src="/__a5-test/acceptance.js"' in entrance.content
        assert "script-src 'self'" in entrance.headers["content-security-policy"]
        assert "unsafe-inline" not in entrance.headers["content-security-policy"]
        response = httpx.get(
            address + "/api/public/profile?locale=en", headers={"Origin": static_origin}
        )
        assert response.status_code == 200
        assert set(response.json()["character"]["scene"]["themes"]) == {"light", "dark"}
        assert response.headers["access-control-allow-origin"] == static_origin
        assert "access-control-allow-credentials" not in response.headers
        assert (
            httpx.get(address + "/api/admin/setup", headers={"Origin": static_origin}).status_code
            == 404
        )
        wrong_origin = httpx.get(
            address + "/api/public/profile", headers={"Origin": "http://evil.example"}
        )
        assert "access-control-allow-origin" not in wrong_origin.headers
        login = private.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={
                "username": FIXTURE_USERNAME,
                "password": FIXTURE_PASSWORD,
            },
        )
        assert login.status_code == 200
        snapshot = app.application.state.visitor_gateway.snapshot()
        stopped = private.post(
            "/api/admin/visitor-gateway/stop",
            json={"revision": snapshot["revision"]},
            headers={
                "Origin": origin,
                "X-CSRF-Token": login.json()["csrf_token"],
            },
        )
        assert stopped.status_code == 200
        assert not stopped.json()["listener_ready"]
        with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
            httpx.get(address + "/api/public/status", timeout=1)
        assert private.get("/").status_code == 200
        assert app.chat.calls == 2  # Only the initial two FAQ generations.
