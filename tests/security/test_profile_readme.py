"""Confirmed README content, actual Pages card and private download boundaries."""

from __future__ import annotations

import io
import json
import socket
import zipfile

import pytest

from reponpc.indexing.public_profile import LocalizedPublicProfile
from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.sharing import pages as pages_module
from reponpc.sharing.readme import render_profile_readme
from tests.browser.a5_server import build_application
from tests.security.test_a5_pages_api_review import _login
from tests.security.test_a5_sharing_review import _visitor_build


@pytest.fixture
def readme_site(tmp_path, monkeypatch):
    origin = "https://fixture.test"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    app = build_application(
        tmp_path / "runtime", _visitor_build(tmp_path), origin, gateway_port=port
    )
    resources: dict[str, tuple[bytes, str, int]] = {}
    fetched = []

    def fetch(url, *, pages_origin, deadline, max_response_bytes):
        assert pages_origin == "https://fixture.github.io"
        assert deadline > 0 and max_response_bytes > 0
        fetched.append(url)
        content, kind, status = resources[url]
        assert len(content) <= max_response_bytes
        return ProviderHttpResponse(status=status, headers={"content-type": kind}, body=content)

    monkeypatch.setattr(pages_module, "fetch_pages_resource", fetch)
    client, headers = _login(app, origin)
    with client:
        yield client, headers, resources, fetched, app


def publish_fixture(client, headers, resources, base_path="project/"):
    pages_url = "https://fixture.github.io/" + base_path
    saved = client.put("/api/admin/sharing/pages", headers=headers, json={"pages_url": pages_url})
    assert saved.status_code == 200
    export = client.get("/api/admin/sharing/export")
    assert export.status_code == 200, export.text
    with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
        documents = {name: archive.read(name) for name in archive.namelist()}
    resources[pages_url] = (documents["index.html"], "text/html", 200)
    resources[pages_url + "export-manifest.json"] = (
        documents["export-manifest.json"],
        "application/json",
        200,
    )
    for locale in ("zh-TW", "en"):
        path = f"card-light-{locale}.gif"
        resources[pages_url + path] = (documents[path], "image/gif", 200)
    verified = client.post("/api/admin/sharing/verify", headers=headers)
    assert verified.status_code == 200 and verified.json()["verified"] is True
    return pages_url, documents


@pytest.mark.parametrize("locale,base_path", [("zh-TW", ""), ("en", "portfolio/with-path/")])
def test_download_uses_verified_public_snapshot_and_actual_card(readme_site, locale, base_path):
    client, headers, resources, fetched, app = readme_site
    pages_url, documents = publish_fixture(client, headers, resources, base_path)
    state_before = client.get("/api/admin/sharing/state").json()
    draft_before = client.get("/api/admin/portfolio").json()
    changed = client.put(
        "/api/admin/portfolio",
        headers=headers,
        json={
            "content": draft_before["content"].replace(
                "Fixture Developer", "Unapplied Draft Canary"
            ),
            "sprite_base64": draft_before["sprite_base64"],
            "expected_revision": draft_before["revision"],
        },
    )
    assert changed.status_code == 200, changed.text
    draft_before = changed.json()
    manager = app.application.state.scene_supplier().manager
    bundle_before = manager.status().active_bundle_id
    fetched.clear()
    result = client.get(f"/api/admin/sharing/readme?locale={locale}")
    assert result.status_code == 200, result.text
    assert result.headers["content-disposition"] == 'attachment; filename="README.md"'
    assert result.headers["content-type"] == "text/markdown; charset=utf-8"
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["x-content-type-options"] == "nosniff"
    exported = json.loads(documents[f"profile-{locale}.json"])
    assert exported["profile"]["display_name"] in result.text
    assert "https://github.com/" + exported["repositories"][0]["slug"] in result.text
    assert f"{pages_url}card-light-{locale}.gif" in result.text
    assert f"](<{pages_url}>)" in result.text
    assert ("與我的 NPC 對話" if locale == "zh-TW" else "Chat with my NPC") in result.text
    assert "./reponpc-card.gif" not in result.text
    assert "/api/admin" not in result.text
    assert "PRIVATE_KEY_CANARY" not in result.text
    assert "Unapplied Draft Canary" not in result.text
    assert fetched == [f"{pages_url}card-light-{locale}.gif"]
    assert client.get("/api/admin/sharing/state").json() == state_before
    assert client.get("/api/admin/portfolio").json() == draft_before
    assert manager.status().active_bundle_id == bundle_before


def test_readme_requires_verification_private_session_origin_and_valid_locale(readme_site):
    client, headers, resources, fetched, _app = readme_site
    response = client.get("/api/admin/sharing/readme")
    assert response.status_code == 409
    assert fetched == []
    assert "content-disposition" not in response.headers
    publish_fixture(client, headers, resources)
    fetched.clear()
    assert client.get("/api/admin/sharing/readme?locale=unknown").status_code == 400
    assert (
        client.get(
            "/api/admin/sharing/readme", headers={"Origin": "https://attacker.test"}
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get("/api/admin/sharing/readme").status_code == 401
    assert fetched == []


@pytest.mark.parametrize("failure", ["missing", "wrong_type", "different_bytes", "unavailable"])
def test_remote_card_failure_never_exports_a_broken_readme(readme_site, monkeypatch, failure):
    client, headers, resources, _fetched, _app = readme_site
    pages_url, _documents = publish_fixture(client, headers, resources)
    before = client.get("/api/admin/sharing/state").json()
    if failure == "unavailable":

        def unavailable(*_args, **_kwargs):
            raise pages_module.SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")

        monkeypatch.setattr(pages_module, "fetch_pages_resource", unavailable)
    else:
        path = pages_url + "card-light-en.gif"
        content, kind, status = resources[path]
        resources[path] = (
            b"wrong" if failure == "different_bytes" else content,
            "text/html" if failure == "wrong_type" else kind,
            404 if failure == "missing" else status,
        )
    result = client.get("/api/admin/sharing/readme?locale=en")
    assert result.status_code == (503 if failure == "unavailable" else 422)
    assert "content-disposition" not in result.headers
    assert "# " not in result.text
    assert client.get("/api/admin/sharing/state").json() == before


@pytest.mark.parametrize("during_fetch", [False, True])
def test_stale_snapshot_receipt_rejects_readme_without_mutating_state(
    readme_site, monkeypatch, during_fetch
):
    client, headers, resources, _fetched, _app = readme_site
    publish_fixture(client, headers, resources)
    before = client.get("/api/admin/sharing/state").json()
    build = pages_module.build_site_files
    count = 0

    def changed(**kwargs):
        nonlocal count
        count += 1
        files, manifest = build(**kwargs)
        if not during_fetch or count > 1:
            manifest = {**manifest, "content_sha256": "0" * 64}
        return files, manifest

    monkeypatch.setattr(pages_module, "build_site_files", changed)
    result = client.get("/api/admin/sharing/readme?locale=en")
    assert result.status_code == 409 and result.json()["error"]["code"] == "SHARING_CONFLICT"
    assert "content-disposition" not in result.headers
    assert client.get("/api/admin/sharing/state").json() == before


def test_public_text_and_links_cannot_inject_markdown_or_html():
    document = LocalizedPublicProfile.model_validate(
        {
            "profile": {
                "display_name": "Nova\n![injected](https://evil.test)",
                "headline": "<script>alert(1)</script>",
                "bio": "# Forged heading\n[Injected](javascript:alert(1))\n```html\n<img src=x>",
                "greeting": "Hello",
                "links": [
                    {
                        "label": "Website] ![forged",
                        "url": "https://public.example/path?q=)\n![x](javascript:x)",
                    }
                ],
            },
            "repositories": [
                {
                    "slug": "another-owner/useful-project",
                    "summary": "Confirmed [summary]",
                    "role": "Confirmed **role**",
                    "tags": ["C++"],
                    "demo_url": "https://demo.example/run(test)",
                }
            ],
            "suggested_questions": ["What did you build?"],
        }
    )
    result = render_profile_readme(
        document, pages_url="https://owner.github.io/site/", locale="en"
    ).decode()
    assert "<script>" not in result and "<img" not in result
    assert "![injected](" not in result and "[Injected](" not in result and "```html" not in result
    assert "&lt;script&gt;" in result and "Confirmed \\[summary\\]" in result
    assert "Confirmed \\*\\*role\\*\\*" in result
    assert "https://demo.example/run%28test%29" in result
    assert "https://github.com/another-owner/useful-project" in result
    assert "\n# Forged heading" not in result


def test_readme_rejects_an_oversized_escaped_document():
    document = LocalizedPublicProfile.model_validate(
        {
            "profile": {
                "display_name": "Large public portfolio",
                "headline": "Confirmed introduction",
                "bio": "<" * 100_000,
                "greeting": "Hello",
                "links": [],
            },
            "repositories": [
                {
                    "slug": "owner/project",
                    "summary": "<" * 100_000,
                    "role": "Confirmed role",
                    "tags": [],
                }
            ],
            "suggested_questions": ["What did you build?"],
        }
    )
    with pytest.raises(pages_module.SiteExportError) as failure:
        render_profile_readme(document, pages_url="https://owner.github.io/", locale="en")
    assert failure.value.code == "SHARING_EXPORT_TOO_LARGE"
