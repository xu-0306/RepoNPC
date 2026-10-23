"""P1 font delivery/export contracts without invoking a frontend build."""

from __future__ import annotations

import hashlib
import html
import json
import re
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from reponpc.admin.scene import AdminSceneService
from reponpc.api.visitor_ingress import _visitor_files
from reponpc.config.models import SceneConfig
from reponpc.scene.registry import default_scene_registry
from reponpc.scene.resolve import resolve_scene
from reponpc.sharing.export import (
    _rewrite_entry_html,
    _visitor_dependencies,
    build_visitor_site_export,
)
from reponpc.sharing.manifest import SiteExportError
from tests.integration.test_reviewed_faq import faq_system
from tests.security.test_a5_review import _sheet
from tests.security.test_visitor_gateway_review import _gateway
from tests.unit.test_site_export import _write_build

FONT_PATH = "assets/press-start-2p-fixture.woff2"
FONT_BYTES = b"wOF2\x00P1 fake build font\x00"
VISITOR_HTML = (
    b'<!doctype html><html lang="zh-TW" data-owner-mode="system" '
    b'data-visitor-toggle="true"><head><script src="./scene-mode.js"></script>'
    b'<link rel="stylesheet" href="/assets/visitor.css">'
    b'<script type="module" src="/assets/visitor.js"></script></head>'
    b'<body><div id="root"></div></body></html>'
)
GATEWAY_CSP = (
    "default-src 'none'; base-uri 'none'; connect-src 'self'; font-src 'self'; "
    "form-action 'self'; frame-ancestors 'none'; img-src 'self'; script-src 'self'; "
    "style-src 'self'"
)
EXPORT_CSP = (
    "default-src 'none'; base-uri 'none'; connect-src 'self' https://fixture.ts.net; "
    "font-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; "
    "form-action 'self'; object-src 'none'"
)


def _font_build(root: Path, *, shared_font: bool = False) -> None:
    _write_build(root)
    (root / "visitor.html").write_bytes(VISITOR_HTML)
    (root / "scene-mode.js").write_text("/* fixture mode script */", encoding="utf-8")
    (root / FONT_PATH).write_bytes(FONT_BYTES)
    (root / "assets/visitor.css").write_text(
        '@font-face { src: url("./press-start-2p-fixture.woff2"); }', encoding="utf-8"
    )
    manifest_path = root / ".vite/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["visitor.html"]["css"] = ["assets/visitor.css"]
    manifest["visitor.html"]["assets"] = [FONT_PATH]
    manifest["src/assets/font.woff2"] = {"file": FONT_PATH, "src": "src/assets/font.woff2"}
    if shared_font:
        manifest["admin.html"]["assets"] = [FONT_PATH]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_gateway_serves_manifest_font_with_explicit_mime_nosniff_and_unchanged_csp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "web"
    _font_build(root)
    assert _visitor_files(root)["/" + FONT_PATH] == root / FONT_PATH
    # Reproduce a host without a woff2 MIME registration.
    monkeypatch.setattr("starlette.responses.guess_type", lambda _name: (None, None))
    app, _ = _gateway(tmp_path, web_dist=root)
    with TestClient(app, base_url="https://fixture.ts.net") as client:
        response = client.get("/" + FONT_PATH)
        assert response.status_code == 200 and response.content == FONT_BYTES
        assert response.headers["content-type"] == "font/woff2"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-security-policy"] == GATEWAY_CSP
        head = client.head("/" + FONT_PATH)
        assert head.status_code == 200 and head.content == b""
        assert head.headers["content-type"] == "font/woff2"
        assert head.headers["x-content-type-options"] == "nosniff"
        assert client.get("/assets/admin.js").status_code == 404


def test_export_hashes_the_font_and_binds_snapshot_policy_without_a_visitor_choice(
    tmp_path: Path,
) -> None:
    database, manager, store, chat, _service, _limits, faq, _build = faq_system(tmp_path)
    scene = AdminSceneService(
        manager=manager, database=database, data_directory=manager.data_directory, portfolio=store
    )
    root = tmp_path / "web"
    _font_build(root)
    calls = chat.calls
    artifact = build_visitor_site_export(
        faq=faq,
        scene_service=scene,
        web_dist=root,
        pages_url="https://fixture.github.io/portfolio/",
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    try:
        with zipfile.ZipFile(artifact.path) as archive:
            assert archive.read(FONT_PATH) == FONT_BYTES
            manifest = json.loads(archive.read("export-manifest.json"))
            record = next(item for item in manifest["files"] if item["path"] == FONT_PATH)
            assert record["size"] == len(FONT_BYTES)
            assert record["sha256"] == hashlib.sha256(FONT_BYTES).hexdigest()
            scene_payload = json.loads(archive.read("profile-en.json"))["character"]["scene"]
            document = archive.read("index.html").decode()
            assert f'data-default-scheme="{scene_payload["scheme"]["id"]}"' in document
            assert 'data-visitor-scheme-choice="true"' in document
            assert "data-visitor-scheme=" not in document
            assert "reponpc.visitor.scheme" not in document
            csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', document)
            assert csp is not None and html.unescape(csp[1]) == EXPORT_CSP
            assert "assets/admin.js" not in archive.namelist()
        assert chat.calls == calls
    finally:
        artifact.cleanup()
        with manager.acquire() as index:
            index.close()


@pytest.mark.parametrize("choice", [True, False])
def test_export_root_policy_matches_a_nondefault_scheme_snapshot(choice: bool) -> None:
    scheme_id = next(reversed(default_scene_registry().schemes))
    scene = resolve_scene(
        SceneConfig(color_scheme=scheme_id, visitor_scheme_choice=choice),
        sprite_content=_sheet(),
        revision=1,
    ).public
    snapshot = SimpleNamespace(document=SimpleNamespace(character=SimpleNamespace(scene=scene)))
    files = {"index.html": VISITOR_HTML}
    _rewrite_entry_html(files, snapshot, "https://fixture.ts.net")
    document = files["index.html"]
    assert f'data-default-scheme="{scheme_id}"'.encode() in document
    assert f'data-visitor-scheme-choice="{str(choice).lower()}"'.encode() in document
    assert b"data-visitor-scheme=" not in document


def test_shared_font_stays_in_the_visitor_closure_without_admin_code(tmp_path: Path) -> None:
    _font_build(tmp_path, shared_font=True)
    files = _visitor_dependencies(tmp_path)
    assert files[FONT_PATH] == FONT_BYTES
    assert "assets/admin.js" not in files


@pytest.mark.parametrize("field", ["file", "css", "assets"])
def test_shared_executable_or_stylesheet_still_fails_closed(tmp_path: Path, field: str) -> None:
    _font_build(tmp_path)
    manifest_path = tmp_path / ".vite/manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["admin.html"][field] = (
        "assets/visitor.js" if field == "file" else ["assets/visitor.css"]
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SiteExportError):
        _visitor_dependencies(tmp_path)
