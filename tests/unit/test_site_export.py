from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from reponpc.admin.scene import AdminSceneService
from reponpc.bundles.index_reader import IndexedEvidence
from reponpc.sharing.export import (
    _add_cited_owner_assertions,
    _visitor_dependencies,
    _write_zip_temp,
    build_visitor_site_export,
)
from reponpc.sharing.manifest import (
    SiteExportError,
    canonical_json_bytes,
    create_manifest,
    pages_target,
)
from tests.integration.test_reviewed_faq import faq_system


def _write_build(
    root: Path,
    *,
    visitor_imports: list[str] | None = None,
    visitor_dynamic_imports: list[str] | None = None,
) -> None:
    (root / ".vite").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "visitor.html").write_text(
        '<!doctype html><html><head></head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (root / "assets" / "visitor.js").write_text("visitor", encoding="utf-8")
    (root / "assets" / "admin.js").write_text("admin", encoding="utf-8")
    manifest = {
        "visitor.html": {
            "isEntry": True,
            "file": "assets/visitor.js",
            "imports": visitor_imports or [],
            "dynamicImports": visitor_dynamic_imports or [],
            "css": [],
            "assets": [],
        },
        "admin.html": {
            "isEntry": True,
            "file": "assets/admin.js",
            "imports": [],
            "css": [],
            "assets": [],
        },
    }
    (root / ".vite" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_visitor_export_copies_only_its_vite_dependency_closure(tmp_path: Path) -> None:
    _write_build(tmp_path)

    files = _visitor_dependencies(tmp_path)

    assert set(files) == {"index.html", "assets/visitor.js"}
    assert all(b"admin" not in content for content in files.values())


@pytest.mark.parametrize("field", ["file", "css", "assets"])
def test_export_rejects_malformed_unvisited_manifest_paths(tmp_path: Path, field: str) -> None:
    _write_build(tmp_path)
    path = tmp_path / ".vite" / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["admin.html"][field] = {} if field == "file" else [{}]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SiteExportError, match="static site export could not be completed"):
        _visitor_dependencies(tmp_path)


def test_export_archive_is_byte_reproducible_and_manifest_does_not_hash_itself() -> None:
    files = {".nojekyll": b"", "index.html": b"<main>visitor</main>"}
    manifest = create_manifest(
        files=files,
        bundle_id="fixture-bundle",
        character_revision=0,
        pages=pages_target("https://fixture.github.io/portfolio/", "https://fixture.github.io"),
        gateway_origin="https://fixture.ts.net",
        pages_origin="https://fixture.github.io",
    )
    manifest_bytes = canonical_json_bytes(manifest) + b"\n"
    first = _write_zip_temp(files, manifest_bytes, manifest)
    second = _write_zip_temp(files, manifest_bytes, manifest)
    try:
        assert first.read_bytes() == second.read_bytes()
        with zipfile.ZipFile(first) as archive:
            assert set(archive.namelist()) == {".nojekyll", "index.html", "export-manifest.json"}
            exported = json.loads(archive.read("export-manifest.json"))
            assert all(item["path"] != "export-manifest.json" for item in exported["files"])
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


@pytest.mark.parametrize("pages_path", ["/", "/portfolio/"])
@pytest.mark.parametrize("withdraw_during_export", [False, True])
def test_same_public_snapshot_exports_identical_manifest_and_zip_bytes(
    tmp_path: Path, pages_path: str, withdraw_during_export: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, manager, store, chat, _service, _limits, faq, _build = faq_system(tmp_path)
    for locale in ("zh-TW", "en"):
        entry = faq.initialize_queue(locale)["entries"][0]
        entry = faq.regenerate(entry["entry_id"], entry["revision"])
        faq.review(entry["entry_id"], entry["revision"], "approve")
    scene = AdminSceneService(
        manager=manager, database=database, data_directory=manager.data_directory, portfolio=store
    )
    web = tmp_path / "web"
    _write_build(web)
    (web / "visitor.html").write_text(
        '<!doctype html><html lang="zh-TW" data-owner-mode="system" '
        'data-visitor-toggle="true"><head><script src="./scene-mode.js"></script>'
        '<script type="module" src="/assets/visitor.js"></script></head>'
        '<body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (web / "scene-mode.js").write_text("/* fixture mode script */", encoding="utf-8")
    model_calls = chat.calls
    if withdraw_during_export:
        original_payload = faq.public_payload_for_bundle

        def withdraw_after_first_locale(locale, bundle_id, connection):
            assert connection.in_transaction
            payload = original_payload(locale, bundle_id, connection)
            if locale == "zh-TW":
                with database.connection() as writer:
                    writer.execute("UPDATE faq_entries SET review_state = 'rejected'")
            return payload

        monkeypatch.setattr(faq, "public_payload_for_bundle", withdraw_after_first_locale)
    artifacts = []
    try:
        for _ in range(2):
            artifacts.append(
                build_visitor_site_export(
                    faq=faq,
                    scene_service=scene,
                    web_dist=web,
                    pages_url=f"https://fixture.github.io{pages_path}",
                    gateway_origin="https://fixture.ts.net",
                    pages_origin="https://fixture.github.io",
                )
            )
        first, second = artifacts
        assert first.path != second.path
        with (
            zipfile.ZipFile(first.path) as first_archive,
            zipfile.ZipFile(second.path) as second_archive,
        ):
            for locale in ("zh-TW", "en"):
                assert json.loads(first_archive.read(f"faq-{locale}.json"))["entries"]
                assert json.loads(first_archive.read(f"profile-{locale}.json"))["locale"] == locale
                if withdraw_during_export:
                    assert json.loads(second_archive.read(f"faq-{locale}.json"))["entries"] == []
            if not withdraw_during_export:
                assert first_archive.read("export-manifest.json") == second_archive.read(
                    "export-manifest.json"
                )
        if not withdraw_during_export:
            assert first.path.read_bytes() == second.path.read_bytes()
        assert chat.calls == model_calls
    finally:
        for artifact in artifacts:
            artifact.cleanup()
        with manager.acquire() as index:
            index.close()


@pytest.mark.parametrize(
    ("imports", "dynamic_imports"),
    [(["admin.html"], None), (None, ["admin.html"])],
)
def test_visitor_export_rejects_sibling_admin_entry_closure(
    tmp_path: Path,
    imports: list[str] | None,
    dynamic_imports: list[str] | None,
) -> None:
    _write_build(
        tmp_path,
        visitor_imports=imports,
        visitor_dynamic_imports=dynamic_imports,
    )

    with pytest.raises(SiteExportError):
        _visitor_dependencies(tmp_path)


def _owner_evidence(
    *,
    evidence_id: str,
    repository: str,
    revision: str,
    origin: str,
    path: str = "reponpc.yml",
) -> IndexedEvidence:
    return IndexedEvidence(
        evidence_id=evidence_id,
        evidence_class="OWNER_ASSERTION",
        repository_slug=repository,
        commit_sha=revision,
        path=path,
        start_line=2,
        end_line=3,
        title="profile_headline",
        symbol=None,
        content="Owner-confirmed headline",
        language="yaml",
        metadata={"origin": origin},
    )


def _citation(evidence: IndexedEvidence, source_id: str) -> dict[str, object]:
    return {
        "id": source_id,
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


def test_export_preserves_verified_github_owner_citations_and_copies_local_ones() -> None:
    local = _owner_evidence(
        evidence_id="E_" + "a" * 24,
        repository="local/portfolio",
        revision="a" * 40,
        origin="local",
    )
    github = _owner_evidence(
        evidence_id="E_" + "b" * 24,
        repository="sample-owner/sample-repo",
        revision="b" * 40,
        origin="github",
    )
    repository_fact = {
        "id": "S3",
        "evidence_id": "E_" + "c" * 24,
        "evidence_class": "REPOSITORY_FACT",
        "repository": "sample-owner/sample-repo",
        "commit_sha": "c" * 40,
        "path": "src/main.py",
        "start_line": 8,
        "end_line": 8,
        "title": "main",
        "excerpt": "print('hello')",
        "url": "https://github.com/sample-owner/sample-repo/blob/" + "c" * 40 + "/src/main.py#L8",
    }
    entries = [
        {
            "question": "Which project?",
            "citations": [
                _citation(github, "S1"),
                _citation(local, "S2"),
                repository_fact,
            ],
        }
    ]
    files = {
        f"faq-{locale}.json": canonical_json_bytes({"entries": entries})
        for locale in ("zh-TW", "en")
    }

    class EvidenceIndex:
        def evidence(self, evidence_id: str) -> IndexedEvidence | None:
            return {local.evidence_id: local, github.evidence_id: github}.get(evidence_id)

    _add_cited_owner_assertions(files, EvidenceIndex())

    exported = json.loads(files["faq-en.json"])["entries"][0]["citations"]
    assert exported[0]["url"] == github.github_permalink
    assert exported[1]["url"] == f"./owner-statements/{local.commit_sha}/{local.evidence_id}.txt"
    assert exported[2] == repository_fact
    assert files[f"owner-statements/{local.commit_sha}/{local.evidence_id}.txt"].startswith(
        b"Owner-confirmed statement /"
    )
    assert not any(path.startswith("owner-statements/b") for path in files)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("id", "S0"),
        ("evidence_id", "E_" + "c" * 24),
        ("commit_sha", "d" * 40),
        ("repository", "attacker/repo"),
        ("path", "attacker.yml"),
        ("url", "https://github.com/attacker/repo/blob/" + "b" * 40 + "/reponpc.yml#L2-L3"),
        ("start_line", True),
    ],
)
def test_export_rejects_owner_citation_identity_mismatch(field: str, invalid: object) -> None:
    github = _owner_evidence(
        evidence_id="E_" + "b" * 24,
        repository="sample-owner/sample-repo",
        revision="b" * 40,
        origin="github",
    )
    citation = _citation(github, "S1")
    citation[field] = invalid
    files = {
        f"faq-{locale}.json": canonical_json_bytes(
            {"entries": [{"question": "Question?", "citations": [citation]}]}
        )
        for locale in ("zh-TW", "en")
    }

    class EvidenceIndex:
        def evidence(self, evidence_id: str) -> IndexedEvidence | None:
            return github if evidence_id == github.evidence_id else None

    with pytest.raises(SiteExportError):
        _add_cited_owner_assertions(files, EvidenceIndex())
