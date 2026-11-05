"""ADR-081 optional origins and the pre-change gateway export golden bytes."""

from __future__ import annotations

import hashlib
import json
import zipfile
from types import SimpleNamespace

import pytest

from reponpc.runtime.database import RuntimeDatabase
from reponpc.sharing.export import _rewrite_entry_html, _visitor_dependencies, _write_zip_temp
from reponpc.sharing.manifest import (
    SiteExportError,
    canonical_json_bytes,
    create_manifest,
    pages_target,
    parse_manifest,
)
from reponpc.sharing.pages import PagesSharingService
from tests.security.test_a5_sharing_review import _visitor_build

# Captured from 37f8766 before changing the manifest or HTML exporter.
GOLDEN_V1_MANIFEST = (
    b'{"base_path":"/project/","bundle_id":"adr081-golden","character_revision":0,'
    b'"content_sha256":"fd9f93c1886616cd51d85e33170e3ad263bde482d1eaf614effadd01fb915a0d",'
    b'"files":[{"path":".nojekyll","sha256":'
    b'"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","size":0},'
    b'{"path":"assets/visitor.js","sha256":'
    b'"e2a3460ed3aa9d6899892bacd0b7fdb04e63812232acb6a196c811331095da7c","size":28},'
    b'{"path":"index.html","sha256":'
    b'"0249bbfe807671ebe4ff8aaaf960a863bd8ac3071ca374524e452a9bc2e3ce08","size":663},'
    b'{"path":"scene-mode.js","sha256":'
    b'"9149322ae41ab42161615e3063997dc150141e5ecf691e1256d1e0ca624cd071","size":25}],'
    b'"gateway_origin":"https://fixture.ts.net","pages_origin":"https://fixture.github.io",'
    b'"pages_url":"https://fixture.github.io/project/","schema_version":1}\n'
)


def _service(tmp_path, settings):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    manager = object()
    gateway = None if settings is None else SimpleNamespace(snapshot=lambda: settings)
    return PagesSharingService(
        database=database,
        faq=SimpleNamespace(bundles=manager),
        scene_service=SimpleNamespace(manager=manager),
        gateway_supplier=lambda: gateway,
    )


@pytest.mark.parametrize("origin", ["https://fixture.github.io", "https://another-owner.github.io"])
@pytest.mark.parametrize("settings_kind", ["absent", "empty", "nulls", "matching", "live"])
def test_saved_pages_origin_does_not_require_a_gateway(tmp_path, origin, settings_kind):
    gateway_origin = "https://chat.example.test" if settings_kind == "live" else None
    settings = {
        "absent": None,
        "empty": {},
        "nulls": {"gateway_origin": None, "pages_origin": None},
        "matching": {"gateway_origin": None, "pages_origin": origin},
        "live": {"gateway_origin": gateway_origin, "pages_origin": origin},
    }[settings_kind]
    service = _service(tmp_path, settings)
    assert service.state()["pages_origin"] is None
    state = service.configure_pages(pages_url=origin + "/nested/project")
    assert state["pages_url"] == origin + "/nested/project/"
    assert state["pages_origin"] == origin
    assert state["live_chat_origin"] == gateway_origin
    assert service.current_origins() == (gateway_origin, origin)


@pytest.mark.parametrize("gateway_origin", [None, "https://chat.example.test"])
def test_gateway_pages_origin_must_match_the_saved_pages_url(tmp_path, gateway_origin):
    service = _service(
        tmp_path,
        {"gateway_origin": gateway_origin, "pages_origin": "https://different.github.io"},
    )
    with pytest.raises(SiteExportError) as failure:
        service.configure_pages(pages_url="https://fixture.github.io/project/")
    assert failure.value.code == "SHARING_CONFIGURATION_INVALID"
    assert service.state()["pages_url"] is None


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/project/",
        "http://fixture.github.io/project/",
        "https://fixture.github.io:443/project/",
        "https://fixture.github.io/a/../b/",
        "https://fixture.github.io/project/?x=1",
        "https://fixture.github.io/project/#chat",
        "https://fixture.github.io/ space/",
    ],
)
def test_gateway_free_pages_keeps_existing_url_validation(tmp_path, url):
    service = _service(tmp_path, None)
    with pytest.raises(SiteExportError) as failure:
        service.configure_pages(pages_url=url)
    assert failure.value.code == "SHARING_CONFIGURATION_INVALID"


def _manifest(gateway_origin):
    return create_manifest(
        files={"index.html": b"Static visitor"},
        bundle_id="another-bundle",
        character_revision=3,
        pages=pages_target("https://another.github.io/site/", "https://another.github.io"),
        gateway_origin=gateway_origin,
        pages_origin="https://another.github.io",
    )


@pytest.mark.parametrize("gateway_origin", [None, "https://chat.example.test"])
def test_manifest_versions_have_the_same_keys_and_round_trip(gateway_origin):
    manifest = _manifest(gateway_origin)
    assert manifest["schema_version"] == (2 if gateway_origin is None else 1)
    assert manifest["gateway_origin"] == gateway_origin
    assert set(manifest) == set(json.loads(GOLDEN_V1_MANIFEST))
    assert parse_manifest(canonical_json_bytes(manifest) + b"\n") == manifest


@pytest.mark.parametrize(
    ("version", "gateway_origin"),
    [(1, None), (2, "https://chat.example.test"), (0, None), (3, None), (True, None), (2, 5)],
)
def test_manifest_rejects_mixed_versions_and_origins(version, gateway_origin):
    manifest = {**_manifest(None), "schema_version": version, "gateway_origin": gateway_origin}
    with pytest.raises(SiteExportError) as failure:
        parse_manifest(canonical_json_bytes(manifest))
    assert failure.value.code == "SHARING_EXPORT_INVALID"


def _snapshot():
    scene = SimpleNamespace(
        color_mode="system",
        visitor_mode_toggle=True,
        scheme=SimpleNamespace(id="meadow"),
        visitor_scheme_choice=True,
    )
    return SimpleNamespace(document=SimpleNamespace(character=SimpleNamespace(scene=scene)))


@pytest.mark.parametrize(
    ("path", "relative"), [("assets/visitor.css", "."), ("assets/nested/scene.css", "..")]
)
@pytest.mark.parametrize("quote", ["", '"', "'"])
@pytest.mark.parametrize("gateway_origin", [None, "https://fixture.ts.net"])
def test_gateway_free_css_assets_are_relative_on_project_pages(
    tmp_path, path, relative, quote, gateway_origin
):
    files = _visitor_dependencies(_visitor_build(tmp_path))
    original = f"@font-face{{src:url({quote}/assets/another-font.woff2{quote})}}".encode()
    files[path] = original
    _rewrite_entry_html(files, _snapshot(), gateway_origin, "en")
    assert files[path] == (
        f"@font-face{{src:url({quote}{relative}/another-font.woff2{quote})}}".encode()
        if gateway_origin is None
        else original
    )


def test_gateway_export_matches_pre_adr081_golden_bytes(tmp_path):
    files = _visitor_dependencies(_visitor_build(tmp_path))
    snapshot = _snapshot()
    _rewrite_entry_html(files, snapshot, "https://fixture.ts.net", "zh-TW")
    files[".nojekyll"] = b""
    manifest = create_manifest(
        files=files,
        bundle_id="adr081-golden",
        character_revision=0,
        pages=pages_target("https://fixture.github.io/project/", "https://fixture.github.io"),
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    content = canonical_json_bytes(manifest) + b"\n"
    assert content == GOLDEN_V1_MANIFEST
    assert manifest["content_sha256"] == json.loads(GOLDEN_V1_MANIFEST)["content_sha256"]
    path = _write_zip_temp(files, content, manifest)
    try:
        with zipfile.ZipFile(path) as archive:
            assert archive.read("export-manifest.json") == GOLDEN_V1_MANIFEST
        assert hashlib.sha256(path.read_bytes()).hexdigest() == (
            "4eb07893da4a71f12976288fcb85bf0f4edabda98e38b2b72e0ac695fbce9346"
        )
    finally:
        path.unlink()
