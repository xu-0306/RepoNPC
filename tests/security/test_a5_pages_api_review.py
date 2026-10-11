"""Exercise the simplified private Pages routes."""

from __future__ import annotations

import io
import json
import socket
import zipfile

from fastapi.testclient import TestClient

from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.sharing import pages as pages_module
from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application
from tests.integration.test_scene_publication import _expected_state, _proposal
from tests.security.test_a5_sharing_review import _visitor_build


def _login(app, origin: str):
    client = TestClient(app, base_url=origin)
    login = client.post(
        "/api/admin/session",
        headers={"Origin": origin},
        json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
    )
    assert login.status_code == 200
    client.headers["Referer"] = origin + "/admin"
    return client, {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}


def test_pages_routes_use_native_download_and_csrf_only_for_writes(tmp_path, monkeypatch):
    origin = "https://fixture.test"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    app = build_application(
        tmp_path / "runtime", _visitor_build(tmp_path), origin, gateway_port=port
    )
    resources = {}

    def fetch(url, *, pages_origin, deadline, max_response_bytes):
        assert pages_origin == "https://fixture.github.io"
        assert deadline > 0 and max_response_bytes > 0
        content, kind = resources[url]
        return ProviderHttpResponse(status=200, headers={"content-type": kind}, body=content)

    monkeypatch.setattr(pages_module, "fetch_pages_resource", fetch)
    client, headers = _login(app, origin)
    with client:
        assert client.get("/api/admin/sharing/export").status_code == 422
        assert (
            client.put(
                "/api/admin/sharing/pages",
                headers={"Origin": origin},
                json={"pages_url": "https://fixture.github.io/project/"},
            ).status_code
            == 403
        )
        saved = client.put(
            "/api/admin/sharing/pages",
            headers=headers,
            json={"pages_url": "https://fixture.github.io/project/"},
        )
        assert saved.status_code == 200
        before = client.get("/api/admin/sharing/state").json()
        exported = client.get("/api/admin/sharing/export")
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/zip"
        assert exported.headers["content-disposition"] == 'attachment; filename="reponpc-site.zip"'
        assert exported.headers["cache-control"] == "no-store"
        assert exported.headers["x-content-type-options"] == "nosniff"
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            manifest_bytes = archive.read("export-manifest.json")
            manifest = json.loads(manifest_bytes)
            resources[manifest["pages_url"]] = (archive.read("index.html"), "text/html")
            resources[manifest["pages_url"] + "export-manifest.json"] = (
                manifest_bytes,
                "application/json",
            )
            assert not any("admin" in name for name in archive.namelist())
        assert set(exported.headers) >= {"cache-control", "x-content-type-options"}
        assert not any(key.lower().startswith("x-reponpc-") for key in exported.headers)
        after = client.get("/api/admin/sharing/state").json()
        assert after == before
        verified_without_csrf = client.post("/api/admin/sharing/verify")
        assert verified_without_csrf.status_code == 403
        verified = client.post("/api/admin/sharing/verify", headers=headers)
        assert verified.status_code == 200, verified.text
        assert verified.json()["verified"] is True


def test_pages_state_is_invalidated_by_scene_write(tmp_path):
    origin = "https://fixture.test"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    app = build_application(
        tmp_path / "runtime", _visitor_build(tmp_path), origin, gateway_port=port
    )
    with TestClient(app, base_url=origin) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        client.headers["Referer"] = origin + "/admin"
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        configured = client.put(
            "/api/admin/sharing/pages",
            headers=headers,
            json={"pages_url": "https://fixture.github.io/project/"},
        )
        assert configured.status_code == 200
        appearance = client.get("/api/admin/portfolio/status").json()["scene_state"]
        proposal = _proposal(appearance, background="none")
        proposal["color_scheme"] = "ocean"
        applied = client.put(
            "/api/admin/scene",
            headers=headers,
            json={"proposal": proposal, "expected": _expected_state(appearance)},
        )
        assert applied.status_code == 200
        state = client.get("/api/admin/sharing/state").json()
        assert state["verified"] is False
