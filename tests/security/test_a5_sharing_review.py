"""Independent negative checks for the untrusted public export manifest."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from reponpc.admin.faq import normalize_question
from reponpc.admin.scene import AdminSceneService
from reponpc.bundles.index_reader import ReadOnlyIndex
from reponpc.scene.registry import SceneRegistry
from reponpc.sharing.export import _add_cited_owner_assertions, build_visitor_site_export
from reponpc.sharing.manifest import (
    SiteExportError,
    canonical_json_bytes,
    create_manifest,
    pages_target,
    parse_manifest,
)
from tests.browser.a5_server import FIXTURE_PASSWORD, FIXTURE_USERNAME, build_application
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _build,
)
from tests.integration.test_reviewed_faq import FAQ_NORMALIZATION_CASES, faq_system
from tests.integration.test_scene_publication import _expected_state, _proposal


def _manifest() -> dict[str, object]:
    return create_manifest(
        files={"index.html": b"A5 public fixture"},
        bundle_id="a5-fixture",
        character_revision=0,
        pages=pages_target("https://fixture.github.io/portfolio/", "https://fixture.github.io"),
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )


def test_public_manifest_version_is_not_boolean() -> None:
    manifest = _manifest()
    manifest["schema_version"] = True
    with pytest.raises(SiteExportError):
        parse_manifest(canonical_json_bytes(manifest))


def test_manifest_cannot_claim_its_own_file_hash() -> None:
    manifest = _manifest()
    records = [{"path": "export-manifest.json", "size": 1, "sha256": "a" * 64}]
    manifest["files"] = records
    manifest["content_sha256"] = hashlib.sha256(canonical_json_bytes(records)).hexdigest()
    with pytest.raises(SiteExportError):
        parse_manifest(canonical_json_bytes(manifest))


@pytest.mark.parametrize(
    "url",
    [
        "https://other.github.io/portfolio/",
        "https://fixture.github.io/portfolio/%2e%2e/admin/",
        "https://fixture.github.io/portfolio/../admin/",
        "https://fixture.github.io/portfolio/?redirect=https://127.0.0.1/",
        "https://fixture.github.io:443/portfolio/",
    ],
)
def test_pages_target_cannot_expand_configured_authority_or_path(url: str) -> None:
    with pytest.raises(SiteExportError):
        pages_target(url, "https://fixture.github.io")


def test_manifest_bytes_are_canonical_and_accept_revision_zero() -> None:
    manifest = _manifest()
    content = canonical_json_bytes(manifest)
    assert parse_manifest(content) == json.loads(content)
    assert canonical_json_bytes(parse_manifest(content)) == content


def _visitor_build(tmp_path: Path) -> Path:
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / ".vite").mkdir()
    (web / "visitor.html").write_text(
        '<!doctype html><html lang="zh-TW" data-owner-mode="system" '
        'data-visitor-toggle="true"><head><script src="./scene-mode.js"></script>'
        '<script type="module" src="/assets/visitor.js"></script></head>'
        '<body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (web / "index.html").write_text(
        "<!doctype html><html><head></head><body>Private admin fixture</body></html>",
        encoding="utf-8",
    )
    (web / "scene-mode.js").write_text("/* fixture mode script */", encoding="utf-8")
    (web / "assets/visitor.js").write_text("/* fixture visitor script */", encoding="utf-8")
    (web / ".vite/manifest.json").write_text(
        json.dumps({"visitor.html": {"isEntry": True, "file": "assets/visitor.js"}}),
        encoding="utf-8",
    )
    return web


def test_export_follows_applied_background_without_rebuilding_bundle(tmp_path: Path) -> None:
    web = _visitor_build(tmp_path)
    origin = "https://fixture.test"
    app = build_application(tmp_path / "runtime", web, origin)
    with TestClient(app, base_url=origin) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = f"{origin}/admin"
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        service = app.application.state.scene_supplier()
        faq = app.application.state.faq_supplier()
        bundle_id = service.manager.status().active_bundle_id
        with service.manager.acquire_snapshot() as (_index, _bundle, public_directory):
            source_manifest_path = public_directory.parent / "manifest.json"
            source_manifest = source_manifest_path.read_bytes()
        for color in ((20, 40, 60, 255), (120, 50, 20, 255), None):
            state = client.get("/api/admin/portfolio/status").json()["scene_state"]
            if color is None:
                background = "none"
            else:
                output = io.BytesIO()
                Image.new("RGBA", (640, 360), color).save(output, "PNG")
                upload = client.post(
                    "/api/admin/assets/scene/background-drafts",
                    headers=headers,
                    files={"file": ("background.png", output.getvalue(), "image/png")},
                )
                assert upload.status_code == 200
                background = "draft:" + upload.json()["draft_id"]
            applied = client.put(
                "/api/admin/scene",
                headers=headers,
                json={
                    "proposal": _proposal(state, background=background),
                    "expected": _expected_state(state),
                },
            )
            assert applied.status_code == 200
            artifact = build_visitor_site_export(
                faq=faq,
                scene_service=service,
                web_dist=web,
                pages_url="https://fixture.github.io/portfolio/",
                gateway_origin="https://fixture.ts.net",
                pages_origin="https://fixture.github.io",
            )
            try:
                with zipfile.ZipFile(artifact.path) as archive:
                    profile = json.loads(archive.read("profile-en.json"))
                    published = client.get("/api/public/profile?locale=en").json()
                    assert profile["character"]["revision"] == published["character"]["revision"]
                    scene = profile["character"]["scene"]
                    assert scene["themes"] == published["character"]["scene"]["themes"]
                    if color is None:
                        assert scene["background_url"] is None
                        assert not any(name.startswith("scene/") for name in archive.namelist())
                    else:
                        exported = archive.read(scene["background_url"].removeprefix("./"))
                        assert (
                            exported
                            == client.get(published["character"]["scene"]["background_url"]).content
                        )
                    assert not any(
                        "draft" in name or "admin" in name for name in archive.namelist()
                    )
            finally:
                artifact.cleanup()
            assert service.manager.status().active_bundle_id == bundle_id
            assert source_manifest_path.read_bytes() == source_manifest
        assert app.chat.calls == 2


def test_question_variant_export_and_matcher_inputs(tmp_path: Path) -> None:
    web = _visitor_build(tmp_path)
    origin = "https://fixture.test"
    app = build_application(tmp_path / "runtime", web, origin)
    cases = []
    with TestClient(app, base_url=origin) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = origin + "/admin"
        headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]}
        for locale in ("zh-TW", "en"):
            queue = client.get(f"/api/admin/portfolio/faq?locale={locale}").json()
            approved = queue["entries"][0]
            question = approved["question"]
            variant = " ".join(question) if locale == "zh-TW" else question.replace(" ", "-")
            path = f"/api/admin/portfolio/faq/{approved['entry_id']}/variants"
            body = {
                "bundle_id": approved["bundle_id"],
                "revision": approved["revision"],
                "variants": [variant],
            }
            assert client.put(path, headers={"Origin": origin}, json=body).status_code == 403
            updated_response = client.put(path, headers=headers, json=body)
            assert updated_response.status_code == 200
            updated = updated_response.json()
            assert updated["revision"] == approved["revision"] + 1
            assert updated["review_state"] == "pending"
            assert updated["answer_markdown"] == approved["answer_markdown"]
            assert updated["citations"] == approved["citations"]
            assert client.put(path, headers=headers, json=body).status_code == 409
            public_pending = client.get(f"/api/public/faq?locale={locale}").json()
            assert public_pending["entries"] == []

            artifact = build_visitor_site_export(
                faq=app.application.state.faq_supplier(),
                scene_service=app.application.state.scene_supplier(),
                web_dist=web,
                pages_url="https://fixture.github.io/portfolio/",
                gateway_origin="https://fixture.ts.net",
                pages_origin="https://fixture.github.io",
            )
            try:
                with zipfile.ZipFile(artifact.path) as archive:
                    exported_pending = json.loads(archive.read(f"faq-{locale}.json"))
                    assert exported_pending == public_pending
            finally:
                artifact.cleanup()

            review = client.post(
                f"/api/admin/portfolio/faq/{updated['entry_id']}/review",
                headers=headers,
                json={
                    "revision": updated["revision"],
                    "action": "approve",
                },
            )
            assert review.status_code == 200
            public = client.get(f"/api/public/faq?locale={locale}").json()
            assert public["entries"][0]["variants"] == [variant]
            artifact = build_visitor_site_export(
                faq=app.application.state.faq_supplier(),
                scene_service=app.application.state.scene_supplier(),
                web_dist=web,
                pages_url="https://fixture.github.io/portfolio/",
                gateway_origin="https://fixture.ts.net",
                pages_origin="https://fixture.github.io",
            )
            try:
                with zipfile.ZipFile(artifact.path) as archive:
                    exported = json.loads(archive.read(f"faq-{locale}.json"))
                    assert exported == public
                    cases.append({"faq": exported, "pending": exported_pending, "variant": variant})
            finally:
                artifact.cleanup()
        assert app.chat.calls == 2
    proof = {
        "cases": cases,
        "normalization": [
            (value, normalize_question(value)) for value, _ in FAQ_NORMALIZATION_CASES
        ],
    }
    (tmp_path / "faq-matcher-cases.json").write_text(json.dumps(proof), encoding="utf-8")


def test_reopened_retired_scheme_keeps_public_profile_and_export_tokens(tmp_path: Path) -> None:
    web = _visitor_build(tmp_path)
    origin = "https://fixture.test"
    app = build_application(tmp_path / "runtime", web, origin)
    with TestClient(app, base_url=origin) as client:
        login = client.post(
            "/api/admin/session",
            headers={"Origin": origin},
            json={"username": FIXTURE_USERNAME, "password": FIXTURE_PASSWORD},
        )
        assert login.status_code == 200
        client.headers["Referer"] = origin + "/admin"
        state = client.get("/api/admin/portfolio/status").json()["scene_state"]
        applied = client.put(
            "/api/admin/scene",
            headers={"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]},
            json={
                "proposal": _proposal(state, background="none"),
                "expected": _expected_state(state),
            },
        )
        assert applied.status_code == 200
        before = client.get("/api/public/profile?locale=en").json()["character"]["scene"]
        service = app.application.state.scene_supplier()
        old_id = before["scheme"]["id"]
        schemes = dict(service.registry.schemes)
        successor = next(
            key
            for key, value in schemes.items()
            if key != old_id
            and value.version == before["scheme"]["version"]
            and value.light != schemes[old_id].light
        )
        del schemes[old_id]
        registry = SceneRegistry(
            MappingProxyType(schemes),
            MappingProxyType({**service.registry.aliases, old_id: successor}),
            service.registry.source_sha256,
        )
        reopened = AdminSceneService(
            manager=service.manager,
            database=service.database,
            data_directory=service.data_directory,
            portfolio=service.portfolio,
            registry=registry,
        )
        app.application.state.scene_service = reopened
        editor = client.get("/api/admin/portfolio/status")
        assert editor.status_code == 200
        assert editor.json()["scene_state"]["settings"]["color_scheme"] == successor
        for locale in ("zh-TW", "en"):
            response = client.get("/api/public/profile?locale=" + locale)
            assert response.status_code == 200
            assert response.json()["character"]["scene"] == before
        artifact = build_visitor_site_export(
            faq=app.application.state.faq_supplier(),
            scene_service=reopened,
            web_dist=web,
            pages_url="https://fixture.github.io/portfolio/",
            gateway_origin="https://fixture.ts.net",
            pages_origin="https://fixture.github.io",
        )
        try:
            with zipfile.ZipFile(artifact.path) as archive:
                for locale in ("zh-TW", "en"):
                    profile = json.loads(archive.read(f"profile-{locale}.json"))
                    assert profile["character"]["scene"] == before
        finally:
            artifact.cleanup()
        editor_state = editor.json()["scene_state"]
        proposal = _proposal(editor_state, background="none")
        proposal["color_scheme"] = successor
        updated = client.put(
            "/api/admin/scene",
            headers={"Origin": origin, "X-CSRF-Token": login.json()["csrf_token"]},
            json={"proposal": proposal, "expected": _expected_state(editor_state)},
        )
        assert updated.status_code == 200
        after = client.get("/api/public/profile?locale=en").json()["character"]["scene"]
        assert after["scheme"]["id"] == successor
        assert after["themes"] != before["themes"]
        assert after["revision"] > before["revision"]
        assert app.chat.calls == 2


def test_export_copies_only_actually_cited_owner_assertions(tmp_path: Path) -> None:
    import re

    from reponpc.providers import ProviderResult
    from tests.integration.test_reviewed_faq import save_owner_statement

    database, manager, store, chat, _service, _limits, faq, build = faq_system(tmp_path)
    save_owner_statement(store)

    def generate(messages, response_schema, max_output_tokens, timeout):
        packed = "\n".join(item.content for item in messages)
        source = re.search(
            r"\[UNTRUSTED DATA (S\d+) persistent_id=\S+ class=OWNER_ASSERTION", packed
        )
        assert source is not None
        return ProviderResult(
            {
                "segments": [
                    {
                        "kind": "inference",
                        "text": "A documented capability.",
                        "source_ids": [source[1]],
                    }
                ],
                "insufficient_evidence": False,
            },
            "stop",
            None,
            None,
            1.0,
        )

    chat.generate = generate
    for locale in ("zh-TW", "en"):
        faq.initialize_queue(locale)
    build()
    expected = {}
    for locale in ("zh-TW", "en"):
        entry = faq.view(locale)["entries"][0]
        entry = faq.regenerate(entry["entry_id"], entry["revision"])
        faq.review(entry["entry_id"], entry["revision"], "approve")
        expected[locale] = faq.public_payload(locale)
        assert expected[locale]["entries"][0]["citations"][0]["evidence_class"] == "OWNER_ASSERTION"
    scene = AdminSceneService(
        manager=manager, database=database, data_directory=manager.data_directory, portfolio=store
    )
    with manager.acquire_snapshot() as (_index, _bundle, public_directory):
        source_path = public_directory.parent / "manifest.json"
        before = source_path.read_bytes()
    artifact = build_visitor_site_export(
        faq=faq,
        scene_service=scene,
        web_dist=_visitor_build(tmp_path),
        pages_url="https://fixture.github.io/portfolio/",
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    try:
        with zipfile.ZipFile(artifact.path) as archive, manager.acquire() as index:
            cited_paths = set()
            for locale in ("zh-TW", "en"):
                exported = json.loads(archive.read(f"faq-{locale}.json"))
                assert exported["bundle_id"] == expected[locale]["bundle_id"]
                for entry in exported["entries"]:
                    for citation in entry["citations"]:
                        if citation["evidence_class"] != "OWNER_ASSERTION":
                            continue
                        evidence_id = citation["evidence_id"]
                        path = f"owner-statements/{citation['commit_sha']}/{evidence_id}.txt"
                        assert citation["url"] == "./" + path
                        evidence = index.evidence(citation["evidence_id"])
                        assert evidence is not None
                        assert archive.read(path).decode("utf-8") == (
                            "Owner-confirmed statement / 本人確認的陳述\n\n" + evidence.content
                        )
                        cited_paths.add(path)
            assert cited_paths == {
                name for name in archive.namelist() if name.startswith("owner-statements/")
            }
            assert source_path.read_bytes() == before
    finally:
        artifact.cleanup()


@pytest.mark.parametrize(
    "field",
    [None, "repository", "path", "start_line", "end_line", "url", "commit_sha", "evidence_id"],
)
def test_github_owner_citation_is_bound_to_real_readonly_index(tmp_path: Path, field: str | None):
    provider = DeterministicEmbeddingProvider()
    built = _build(tmp_path, provider=provider)
    reader = ReadOnlyIndex.open(built.database_path, expected_embedding=provider.identity())
    try:
        evidence_id = reader._connection.execute(
            "SELECT evidence_id FROM evidence WHERE evidence_class='OWNER_ASSERTION' LIMIT 1"
        ).fetchone()[0]
        evidence = reader.evidence(evidence_id)
        assert evidence is not None and evidence.repository_slug != "local/portfolio"
        citation = {
            "id": "S1",
            "evidence_id": evidence.evidence_id,
            "evidence_class": evidence.evidence_class,
            "repository": evidence.repository_slug,
            "commit_sha": evidence.commit_sha,
            "path": evidence.path,
            "start_line": evidence.start_line,
            "end_line": evidence.end_line,
            "title": evidence.title or evidence.symbol or evidence.path,
            "excerpt": evidence.content[:500],
            "url": evidence.github_permalink,
        }
        if field is not None:
            citation[field] = {
                "repository": "other-owner/other-repo",
                "path": "other.yml",
                "start_line": evidence.start_line + 1,
                "end_line": evidence.end_line + 1,
                "url": evidence.github_permalink.replace("/blob/", "/tree/"),
                "commit_sha": "b" * 40,
                "evidence_id": "E_" + "f" * 24,
            }[field]
        payload = canonical_json_bytes({"entries": [{"citations": [citation]}]})
        files = {f"faq-{locale}.json": payload for locale in ("zh-TW", "en")}
        if field is not None:
            with pytest.raises(SiteExportError):
                _add_cited_owner_assertions(files, reader)
        else:
            _add_cited_owner_assertions(files, reader)
            assert not any(path.startswith("owner-statements/") for path in files)
            for content in files.values():
                assert (
                    json.loads(content)["entries"][0]["citations"][0]["url"]
                    == evidence.github_permalink
                )
    finally:
        reader.close()
