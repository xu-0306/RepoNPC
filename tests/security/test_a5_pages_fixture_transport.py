"""Keep the opt-in Pages fixture tied to real, stoppable loopback responses."""

from __future__ import annotations

import io
import socket
import sys
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient

from reponpc.sharing import pages as pages_module
from reponpc.sharing import pages_transport
from reponpc.sharing.manifest import SiteExportError
from tests.browser import a5_server, a5_transport
from tests.security.test_a5_pages_api_review import _login
from tests.security.test_a5_sharing_review import _visitor_build


def _free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return reservation.getsockname()[1]


@pytest.fixture
def mapped_client(tmp_path):
    gateway_port = _free_port()
    static_port = _free_port()
    origin = "https://fixture.test"
    app = a5_server.build_application(
        tmp_path / "runtime",
        _visitor_build(tmp_path),
        origin,
        gateway_port=gateway_port,
        static_origin=f"http://127.0.0.1:{static_port}",
        map_pages=True,
    )
    client, headers = _login(app, origin)
    with client:
        yield app, client, headers, static_port


@pytest.mark.parametrize("condition", ["running", "stopped", "changed"], ids=["A", "B", "C"])
def test_pages_verification_reads_the_real_static_listener(mapped_client, tmp_path, condition):
    app, client, headers, static_port = mapped_client
    saved = client.put(
        "/api/admin/sharing/pages",
        headers=headers,
        json={"pages_url": "https://fixture.github.io/project/"},
    )
    assert saved.status_code == 200, saved.text
    exported = client.get("/api/admin/sharing/export")
    assert exported.status_code == 200, exported.text
    site = tmp_path / "site"
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        archive.extractall(site)
    with a5_transport.static_server(
        site=site, base_path="/project/", port=static_port, gateway_port=app.gateway_port
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            verified = client.post("/api/admin/sharing/verify", headers=headers)
            assert verified.status_code == 200, verified.text
            assert verified.json()["verified"] is True
            state = client.get("/api/admin/sharing/state")
            assert state.status_code == 200
            assert state.json()["verified"] is True
            if condition == "running":
                return
            if condition == "stopped":
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                assert not thread.is_alive()
                status, code = 503, "SHARING_VERIFICATION_UNAVAILABLE"
            else:
                manifest = site / "export-manifest.json"
                manifest.write_bytes(manifest.read_bytes() + b" ")
                status, code = 422, "SHARING_VERIFICATION_FAILED"
            rejected = client.post("/api/admin/sharing/verify", headers=headers)
            assert rejected.status_code == status, rejected.text
            assert rejected.json()["error"]["code"] == code
            state = client.get("/api/admin/sharing/state")
            assert state.status_code == 200
            assert state.json()["verified"] is False
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_other_pages_origins_are_rejected_before_network(mapped_client, monkeypatch):
    with monkeypatch.context() as guard:
        guard.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("unexpected DNS")))
        guard.setattr(
            socket, "create_connection", Mock(side_effect=AssertionError("unexpected connection"))
        )
        with pytest.raises(SiteExportError) as raised:
            pages_module.fetch_pages_resource(
                "https://example.com/",
                pages_origin="https://example.com",
                deadline=time.monotonic() + 5,
                max_response_bytes=1024,
            )
    assert raised.value.code == "SHARING_CONFIGURATION_INVALID"


@pytest.mark.parametrize("map_pages", [False, True])
def test_pages_mapping_is_opt_in_and_restored_after_lifespan(tmp_path, map_pages):
    production_fetch = pages_transport.fetch_pages_resource
    assert pages_module.fetch_pages_resource is production_fetch
    app = a5_server.build_application(
        tmp_path / "runtime",
        _visitor_build(tmp_path),
        "https://fixture.test",
        gateway_port=_free_port(),
        map_pages=map_pages,
    )
    with TestClient(app, base_url="https://fixture.test"):
        if map_pages:
            assert pages_module.fetch_pages_resource is not production_fetch
        else:
            assert pages_module.fetch_pages_resource is production_fetch
    assert pages_module.fetch_pages_resource is production_fetch


@pytest.mark.parametrize(
    "static_origin",
    [
        "http://localhost:12345",
        "http://[::1]:12345",
        "http://127.0.0.1",
        "https://127.0.0.1:12345",
        "http://192.168.0.5:12345",
        "http://127.0.0.1:12345/x",
        "http://user@127.0.0.1:12345",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://127.0.0.1:12345?query=1",
        "http://127.0.0.1:12345#fragment",
    ],
)
def test_pages_mapping_rejects_non_loopback_static_origins(tmp_path, static_origin):
    with pytest.raises(ValueError):
        a5_server.build_application(
            tmp_path / "runtime",
            tmp_path / "web",
            "https://fixture.test",
            gateway_port=8782,
            static_origin=static_origin,
            map_pages=True,
        )
    assert not (tmp_path / "runtime").exists()
    with pytest.raises(ValueError):
        a5_server.A5AcceptanceApp(
            None,
            None,
            web_dist=tmp_path,
            gateway_port=8782,
            static_origin=static_origin,
            map_pages=True,
        )


def test_pages_mapping_requires_a_gateway_port(tmp_path):
    with pytest.raises(ValueError, match="--map-pages requires --gateway-port"):
        a5_server.build_application(
            tmp_path / "runtime", tmp_path / "web", "https://fixture.test", map_pages=True
        )
    assert not (tmp_path / "runtime").exists()
    with pytest.raises(ValueError, match="--map-pages requires --gateway-port"):
        a5_server.A5AcceptanceApp(None, None, web_dist=tmp_path, map_pages=True)


def test_cli_rejects_pages_mapping_without_gateway(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["a5_server", "--runtime", str(tmp_path / "runtime"), "--map-pages"]
    )
    with pytest.raises(SystemExit) as raised:
        a5_server.main()
    assert raised.value.code == 2
    assert "--map-pages requires --gateway-port" in capsys.readouterr().err
    assert not (tmp_path / "runtime").exists()


@pytest.mark.parametrize(
    ("remaining", "limit"),
    [(0, 4), (31, 4), (float("nan"), 4), (float("inf"), 4), (5, 0), (5, True), (5, 4194305)],
)
def test_pages_mapping_checks_bounds_before_connect(tmp_path, monkeypatch, remaining, limit):
    app = a5_server.A5AcceptanceApp(
        None, None, web_dist=tmp_path, gateway_port=8782, map_pages=True
    )
    monkeypatch.setattr(socket, "socket", Mock(side_effect=AssertionError("unexpected socket")))
    with pytest.raises(SiteExportError) as raised:
        app._fetch_pages_resource(
            "https://fixture.github.io/",
            pages_origin=a5_transport.PAGES_ORIGIN,
            deadline=time.monotonic() + remaining,
            max_response_bytes=limit,
        )
    assert raised.value.code == "SHARING_VERIFICATION_UNAVAILABLE"


@pytest.mark.parametrize(
    ("status", "headers", "body", "valid"),
    [
        (200, {"Content-Length": "4", "Content-Type": "text/html"}, b"site", True),
        (200, {}, b"site", True),
        (302, {"Location": "https://example.com/"}, b"", False),
        (200, {"Content-Length": "x"}, b"site", False),
        (200, {"Content-Length": "5"}, b"site", False),
        (200, {"Content-Encoding": "gzip"}, b"site", False),
        (200, {}, b"sites", False),
        (200, {"Content-Length": "3"}, b"site", False),
    ],
)
def test_pages_mapping_preserves_response_limits(
    tmp_path, monkeypatch, status, headers, body, valid
):
    app = a5_server.A5AcceptanceApp(
        None, None, web_dist=tmp_path, gateway_port=8782, map_pages=True
    )
    response = Mock(status=status)
    response.getheader.side_effect = lambda name, default=None: headers.get(name, default)
    response.read1.side_effect = [body, b""]
    connection = Mock()
    connection.getresponse.return_value = response
    network = MagicMock()
    monkeypatch.setattr(a5_server, "HTTPConnection", Mock(return_value=connection))
    monkeypatch.setattr(socket, "socket", Mock(return_value=network))
    monkeypatch.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("unexpected DNS")))
    monkeypatch.setattr(
        socket, "create_connection", Mock(side_effect=AssertionError("unexpected connection"))
    )
    arguments = {
        "pages_origin": a5_transport.PAGES_ORIGIN,
        "deadline": time.monotonic() + 5,
        "max_response_bytes": 4,
    }
    if valid:
        result = app._fetch_pages_resource("https://fixture.github.io/other/", **arguments)
        assert result.status == 200
        assert result.headers == {"content-type": headers.get("Content-Type", "")}
        assert result.body == body
    else:
        with pytest.raises(SiteExportError) as raised:
            app._fetch_pages_resource("https://fixture.github.io/other/", **arguments)
        assert raised.value.code == "SHARING_VERIFICATION_FAILED"
    network.__enter__.return_value.connect.assert_called_once_with(("127.0.0.1", 8781))
    connection.request.assert_called_once_with(
        "GET", "/other/", headers={"Accept-Encoding": "identity", "Connection": "close"}
    )
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    ("content_length", "limit", "valid"),
    [(True, 4, True), (True, 3, False), (False, 4, True)],
)
def test_pages_mapping_reads_real_http_responses(tmp_path, content_length, limit, valid):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            if content_length:
                self.send_header("Content-Length", "4")
            self.end_headers()
            self.wfile.write(b"site")

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        port = server.server_address[1]
        app = a5_server.A5AcceptanceApp(
            None,
            None,
            web_dist=tmp_path,
            gateway_port=port,
            static_origin=f"http://127.0.0.1:{port}",
            map_pages=True,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            arguments = {
                "pages_origin": a5_transport.PAGES_ORIGIN,
                "deadline": time.monotonic() + 5,
                "max_response_bytes": limit,
            }
            if valid:
                result = app._fetch_pages_resource("https://fixture.github.io/x/", **arguments)
                assert result.body == b"site"
                assert result.status == 200
                assert result.headers == {"content-type": "text/html"}
            else:
                with pytest.raises(SiteExportError) as raised:
                    app._fetch_pages_resource("https://fixture.github.io/x/", **arguments)
                assert raised.value.code == "SHARING_VERIFICATION_FAILED"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()
