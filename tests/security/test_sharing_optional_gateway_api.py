"""The private Pages/README flow works before any visitor gateway exists."""

from __future__ import annotations

import io
import re
import zipfile
from types import SimpleNamespace

import pytest

from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.sharing import pages as pages_module
from reponpc.sharing.export import build_site_files
from reponpc.sharing.manifest import SiteExportError, canonical_json_bytes, parse_manifest
from tests.browser.a5_server import build_application
from tests.security.test_a5_pages_api_review import _login
from tests.security.test_a5_sharing_review import _visitor_build


@pytest.fixture
def site(tmp_path, monkeypatch):
    origin = "https://fixture.test"
    app = build_application(tmp_path / "runtime", _visitor_build(tmp_path), origin)
    resources = {}
    fetched = []

    def fetch(url, *, pages_origin, deadline, max_response_bytes):
        assert url.startswith(pages_origin + "/")
        assert deadline > 0
        fetched.append(url)
        content, kind = resources[url]
        assert len(content) <= max_response_bytes
        return ProviderHttpResponse(status=200, headers={"content-type": kind}, body=content)

    monkeypatch.setattr(pages_module, "fetch_pages_resource", fetch)
    client, headers = _login(app, origin)
    with client:
        previous = app.application.state.visitor_gateway
        app.application.state.visitor_gateway = None
        try:
            yield client, headers, resources, fetched, app.application
        finally:
            app.application.state.visitor_gateway = previous


def _download(client, headers, resources, pages_url):
    saved = client.put("/api/admin/sharing/pages", headers=headers, json={"pages_url": pages_url})
    assert saved.status_code == 200, saved.text
    exported = client.get("/api/admin/sharing/export")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"] == "application/zip"
    assert exported.headers["content-disposition"] == 'attachment; filename="reponpc-site.zip"'
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    resources[pages_url] = (files["index.html"], "text/html")
    resources[pages_url + "export-manifest.json"] = (
        files["export-manifest.json"],
        "application/json",
    )
    return files


@pytest.mark.parametrize("gateway_mode", ["absent", "empty"])
@pytest.mark.parametrize(
    ("pages_url", "locale"),
    [("https://fixture.github.io/project/", "en"), ("https://other.github.io/deep/site/", "zh-TW")],
)
def test_download_verify_and_readme_without_gateway(site, gateway_mode, pages_url, locale):
    client, headers, resources, fetched, application = site
    if gateway_mode == "empty":
        application.state.visitor_gateway = SimpleNamespace(
            snapshot=lambda: {"gateway_origin": None, "pages_origin": None}
        )
    initial = client.get("/api/admin/sharing/state")
    assert initial.status_code == 200
    assert initial.json() == {
        "pages_url": None,
        "pages_origin": None,
        "live_chat_origin": None,
        "configured": False,
        "verified": False,
        "verified_at": None,
        "verified_content_sha256": None,
    }
    files = _download(client, headers, resources, pages_url)
    manifest = parse_manifest(files["export-manifest.json"])
    assert manifest["schema_version"] == 2 and manifest["gateway_origin"] is None
    assert manifest["pages_url"] == pages_url
    assert b"connect-src &#x27;self&#x27;;" in files["index.html"]
    allowed_hosts = {manifest["pages_origin"].removeprefix("https://"), "github.com"}
    hosts = {
        host.decode()
        for payload in files.values()
        for host in re.findall(rb"https://([A-Za-z0-9.-]+)", payload)
    }
    assert hosts <= allowed_hosts
    assert not any("admin" in path or "gateway" in path for path in files)
    assert fetched == []
    verified = client.post("/api/admin/sharing/verify", headers=headers)
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True
    assert verified.json()["pages_origin"] == manifest["pages_origin"]
    assert verified.json()["live_chat_origin"] is None
    card_path = f"card-light-{locale}.gif"
    resources[pages_url + card_path] = (files[card_path], "image/gif")
    readme = client.get(f"/api/admin/sharing/readme?locale={locale}")
    assert readme.status_code == 200, readme.text
    assert readme.headers["content-disposition"] == 'attachment; filename="README.md"'
    assert pages_url + card_path in readme.text
    assert f"](<{pages_url}>)" in readme.text
    assert fetched == [pages_url, pages_url + "export-manifest.json", pages_url + card_path]


@pytest.mark.parametrize("gateway_origin", [None, "https://fixture.ts.net"])
def test_verify_rejects_v1_v2_mismatch(site, gateway_origin):
    client, headers, resources, _fetched, application = site
    application.state.visitor_gateway = SimpleNamespace(
        snapshot=lambda: {"gateway_origin": gateway_origin, "pages_origin": None}
    )
    pages_url = "https://fixture.github.io/project/"
    files = _download(client, headers, resources, pages_url)
    manifest = parse_manifest(files["export-manifest.json"])
    assert manifest["schema_version"] == (2 if gateway_origin is None else 1)
    assert client.get("/api/admin/sharing/state").json()["live_chat_origin"] == gateway_origin
    manifest["schema_version"] = 1 if gateway_origin is None else 2
    manifest["gateway_origin"] = "https://fixture.ts.net" if gateway_origin is None else None
    resources[pages_url + "export-manifest.json"] = (
        canonical_json_bytes(manifest) + b"\n",
        "application/json",
    )
    response = client.post("/api/admin/sharing/verify", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SHARING_VERIFICATION_FAILED"
    assert client.get("/api/admin/sharing/state").json()["verified"] is False


def test_origins_changed_during_remote_verification_conflict(site, monkeypatch):
    client, headers, resources, _fetched, application = site
    settings = {"gateway_origin": None, "pages_origin": None}
    application.state.visitor_gateway = SimpleNamespace(snapshot=lambda: settings)
    pages_url = "https://fixture.github.io/project/"
    _download(client, headers, resources, pages_url)
    original = pages_module.fetch_pages_resource

    def changed(url, **kwargs):
        response = original(url, **kwargs)
        if url.endswith("export-manifest.json"):
            settings["gateway_origin"] = "https://later.ts.net"
        return response

    monkeypatch.setattr(pages_module, "fetch_pages_resource", changed)
    response = client.post("/api/admin/sharing/verify", headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SHARING_CONFLICT"
    assert client.get("/api/admin/sharing/state").json()["verified"] is False


@pytest.mark.parametrize("phase", ["before", "after"])
def test_optional_origins_supplier_conflicts_at_both_export_checks(site, phase, tmp_path):
    client, headers, _resources, _fetched, application = site
    saved = client.put(
        "/api/admin/sharing/pages",
        headers=headers,
        json={"pages_url": "https://fixture.github.io/project/"},
    )
    assert saved.status_code == 200
    calls = 0

    def origins():
        nonlocal calls
        calls += 1
        return (
            "https://later.ts.net" if phase == "before" or calls > 1 else None,
            "https://fixture.github.io",
        )

    with pytest.raises(SiteExportError) as failure:
        build_site_files(
            faq=application.state.faq_supplier(),
            scene_service=application.state.scene_supplier(),
            web_dist=tmp_path / "web",
            pages_url="https://fixture.github.io/project/",
            gateway_origin=None,
            pages_origin="https://fixture.github.io",
            origins_supplier=origins,
        )
    assert failure.value.code == "SHARING_CONFLICT"
    assert calls == (1 if phase == "before" else 2)
