"""Bounded deterministic export of the dedicated visitor-site dependency closure."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from reponpc.admin.faq import FaqError, ReviewedFaq
from reponpc.admin.scene import AdminSceneService, PublishedProfileSnapshot
from reponpc.api.visitor_document import render_visitor_document
from reponpc.api.visitor_ingress import _visitor_files
from reponpc.bundles.archive import BundleError
from reponpc.bundles.index_reader import IndexReadError
from reponpc.bundles.manifest import BundleManifest, ManifestError, parse_bundle_manifest
from reponpc.domain.evidence import COMMIT_RE, EVIDENCE_ID_RE
from reponpc.indexing.public_profile import localized_public_profile_bytes
from reponpc.scene.images import SceneImageError, validate_scene_image
from reponpc.sharing.manifest import (
    MANIFEST_NAME,
    MAX_EXPORT_BYTES,
    SiteExportError,
    canonical_json_bytes,
    create_manifest,
    pages_target,
    safe_relative_path,
)

_MAX_HTML_BYTES = 1024 * 1024
_MAX_VITE_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_FAQ_BYTES = 16 * 1024 * 1024
_MAX_OWNER_ASSERTION_BYTES = 100_000
_MAX_OWNER_ASSERTIONS = 512
_SOURCE_ID = re.compile(r"^S[1-9][0-9]*$")
_REPOSITORY_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MAX_FILE_COUNT = 4096
_SCENE_PATH = re.compile(r"^public/scene/([0-9a-f]{64})\.(png|webp)$")
_PEM_SECRET = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_CREDENTIAL_CANARY = re.compile(
    rb"(?:PRIVATE_KEY_CANARY|A5_SECRET_CANARY|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})"
)

_CARD_PATHS = tuple(
    f"public/card-{theme}-{locale}.{extension}"
    for theme in ("light", "dark")
    for locale in ("zh-TW", "en")
    for extension in ("svg", "gif", "png")
)


@dataclass(frozen=True, slots=True)
class SiteExportArtifact:
    path: Path
    content_sha256: str
    bundle_id: str
    character_revision: int
    size: int

    def cleanup(self) -> None:
        with suppress(OSError):
            self.path.unlink(missing_ok=True)


def build_visitor_site_export(
    *,
    faq: ReviewedFaq,
    scene_service: AdminSceneService,
    web_dist: Path,
    pages_url: str | None,
    gateway_origin: str,
    pages_origin: str,
    origins_supplier: Callable[[], tuple[str, str]] | None = None,
) -> SiteExportArtifact:
    """Capture, recheck, and package one coherent public visitor snapshot."""

    artifact_path: Path | None = None
    try:
        files, expected_manifest = build_site_files(
            faq=faq,
            scene_service=scene_service,
            web_dist=web_dist,
            pages_url=pages_url,
            gateway_origin=gateway_origin,
            pages_origin=pages_origin,
            origins_supplier=origins_supplier,
        )
        manifest_content = canonical_json_bytes(expected_manifest) + b"\n"
        artifact_path = _write_zip_temp(files, manifest_content, expected_manifest)
        return SiteExportArtifact(
            path=artifact_path,
            content_sha256=expected_manifest["content_sha256"],
            bundle_id=expected_manifest["bundle_id"],
            character_revision=expected_manifest["character_revision"],
            size=artifact_path.stat().st_size,
        )
    except (OSError, BundleError, ManifestError, FaqError) as exc:
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        if isinstance(exc, FaqError) and exc.code in {"FAQ_STALE", "FAQ_CONFLICT"}:
            raise SiteExportError("SHARING_CONFLICT") from None
        raise SiteExportError("SHARING_EXPORT_UNAVAILABLE") from exc
    except BaseException:
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        raise


def build_site_files(
    *,
    faq: ReviewedFaq,
    scene_service: AdminSceneService,
    web_dist: Path,
    pages_url: str | None,
    gateway_origin: str,
    pages_origin: str,
    origins_supplier: Callable[[], tuple[str, str]] | None = None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build the deterministic public files and manifest without writing a ZIP."""

    manager = faq.bundles
    if scene_service.manager is not manager:
        raise SiteExportError("SHARING_CONFLICT")
    target = pages_target(pages_url, pages_origin)
    if origins_supplier is not None and origins_supplier() != (
        gateway_origin,
        pages_origin,
    ):
        raise SiteExportError("SHARING_CONFLICT")
    normalized_web_dist = Path(web_dist)
    if not normalized_web_dist.is_dir() or normalized_web_dist.is_symlink():
        raise SiteExportError("SHARING_EXPORT_UNAVAILABLE")

    try:
        with manager.acquire_snapshot() as (index, bundle_id, public_directory):
            snapshot = scene_service._snapshot_from_lease(bundle_id, public_directory)
            public_manifest = _bundle_manifest(public_directory, bundle_id)
            files = _visitor_dependencies(normalized_web_dist)
            _rewrite_entry_html(files, snapshot, gateway_origin)
            _add_public_documents(files, snapshot, faq, bundle_id)
            _add_bundle_assets(files, public_directory, public_manifest, snapshot)
            _put_file(files, ".nojekyll", b"")
            _add_cited_owner_assertions(files, index)
            _validate_public_links(files)
            _scan_public_secrets(files)
            expected_manifest = create_manifest(
                files=files,
                bundle_id=bundle_id,
                character_revision=snapshot.character_revision,
                pages=target,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
            )
            manifest_content = canonical_json_bytes(expected_manifest) + b"\n"
            if sum(map(len, files.values())) + len(manifest_content) > MAX_EXPORT_BYTES:
                raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
            if len(files) + 1 > _MAX_FILE_COUNT:
                raise SiteExportError("SHARING_EXPORT_INVALID")
            if manager.status().active_bundle_id != bundle_id:
                raise SiteExportError("SHARING_CONFLICT")
            if origins_supplier is not None and origins_supplier() != (
                gateway_origin,
                pages_origin,
            ):
                raise SiteExportError("SHARING_CONFLICT")
            latest = scene_service._snapshot_from_lease(bundle_id, public_directory)
            if _appearance_identity(latest) != _appearance_identity(snapshot):
                raise SiteExportError("SHARING_CONFLICT")
            return files, expected_manifest
    except (OSError, BundleError, ManifestError, FaqError) as exc:
        if isinstance(exc, FaqError) and exc.code in {"FAQ_STALE", "FAQ_CONFLICT"}:
            raise SiteExportError("SHARING_CONFLICT") from None
        raise SiteExportError("SHARING_EXPORT_UNAVAILABLE") from exc


def _appearance_identity(snapshot: PublishedProfileSnapshot) -> bytes:
    document = snapshot.document.model_dump(mode="json")
    return canonical_json_bytes(
        {
            "bundle_id": snapshot.bundle_id,
            "profile": document,
            "sprite_sha256": snapshot.sprite_sha256,
            "character_revision": snapshot.character_revision,
            "appearance_revision": snapshot.appearance_revision,
            "issued_revision": snapshot.issued_revision,
            "background_sha256": (
                hashlib.sha256(snapshot.background_content).hexdigest()
                if snapshot.background_content is not None
                else None
            ),
            "settings": snapshot.settings,
        }
    )


def _bundle_manifest(public_directory: Path, bundle_id: str) -> BundleManifest:
    try:
        manifest_content = _read_regular_file(
            public_directory.parent, "manifest.json", 4 * 1024 * 1024
        )
        manifest = parse_bundle_manifest(manifest_content)
        if manifest.bundle_id != bundle_id:
            raise ValueError
        return manifest
    except OSError, ManifestError, ValueError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None


def _visitor_dependencies(web_dist: Path) -> dict[str, bytes]:
    manifest_bytes = _read_regular_file(web_dist, ".vite/manifest.json", _MAX_VITE_MANIFEST_BYTES)
    try:
        manifest = json.loads(manifest_bytes)
    except UnicodeDecodeError, json.JSONDecodeError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    if not isinstance(manifest, dict):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    entry = manifest.get("visitor.html")
    if not isinstance(entry, dict) or entry.get("isEntry") is not True:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    paths = _visitor_files(web_dist)
    if not paths or "/" not in paths or paths["/"].name != "visitor.html":
        raise SiteExportError("SHARING_EXPORT_INVALID")
    if len(paths) > _MAX_FILE_COUNT:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    root = web_dist.resolve()
    try:
        closure_paths = {
            source.resolve(strict=True).relative_to(root).as_posix() for source in paths.values()
        }
    except OSError, ValueError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    for key, item in manifest.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        file_value = item.get("file")
        if not isinstance(file_value, str) or not safe_relative_path(file_value):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        if file_value in closure_paths:
            dynamic_imports = item.get("dynamicImports", [])
            if not isinstance(dynamic_imports, list) or dynamic_imports:
                raise SiteExportError("SHARING_EXPORT_INVALID")
        linked_values = [file_value]
        for field in ("css", "assets"):
            candidate = item.get(field, [])
            if not isinstance(candidate, list) or any(
                not isinstance(value, str) or not safe_relative_path(value) for value in candidate
            ):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            linked_values.extend(candidate)
        if (
            key != "visitor.html"
            and (item.get("isEntry") is True or item.get("isDynamicEntry") is True)
            and any(value in closure_paths for value in linked_values)
        ):
            raise SiteExportError("SHARING_EXPORT_INVALID")
    result: dict[str, bytes] = {}
    for public_path, source_path in sorted(paths.items()):
        try:
            relative = source_path.resolve(strict=True).relative_to(root).as_posix()
        except OSError, ValueError:
            raise SiteExportError("SHARING_EXPORT_INVALID") from None
        if public_path == "/":
            output_path = "index.html"
        else:
            if not public_path.startswith("/") or public_path[1:] != relative:
                raise SiteExportError("SHARING_EXPORT_INVALID")
            output_path = public_path[1:]
        if not safe_relative_path(output_path):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        remaining = MAX_EXPORT_BYTES - sum(map(len, result.values()))
        if remaining <= 0:
            raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        result[output_path] = _read_regular_file(
            root,
            relative,
            min(
                remaining,
                _MAX_HTML_BYTES if output_path in {"index.html", "scene-mode.js"} else remaining,
            ),
        )
    return result


def _rewrite_entry_html(
    files: dict[str, bytes], snapshot: PublishedProfileSnapshot, gateway_origin: str
) -> None:
    content = files.get("index.html")
    if content is None:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    try:
        document = content.decode("utf-8")
    except UnicodeDecodeError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    if (
        document.count('<script src="./scene-mode.js"></script>') != 1
        or '<html lang="zh-TW" data-owner-mode="system" data-visitor-toggle="true">' not in document
        or document.count("<head>") != 1
        or "<base " in document.lower()
    ):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    scene = snapshot.document.character.scene
    if scene is None:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    try:
        document = render_visitor_document(
            content,
            color_mode=scene.color_mode,
            visitor_mode_toggle=scene.visitor_mode_toggle,
            default_scheme=scene.scheme.id,
            visitor_scheme_choice=scene.visitor_scheme_choice,
        ).decode("utf-8")
    except ValueError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    document = re.sub(r"(<html\s[^>]*)(>)", r'\1 data-static-export="true"\2', document, count=1)
    document = document.replace('="/assets/', '="./assets/')
    csp = (
        "default-src 'none'; base-uri 'none'; connect-src 'self' "
        + gateway_origin
        + "; font-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; "
        "form-action 'self'; object-src 'none'"
    )
    meta = (
        '<meta http-equiv="Content-Security-Policy" content="'
        + html.escape(csp, quote=True)
        + '" />'
    )
    document = document.replace("<head>", "<head>\n    " + meta, 1)
    if '="/api/public/' in document or "/src/main.tsx" in document:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    _put_file(files, "index.html", document.encode("utf-8"))


def _add_public_documents(
    files: dict[str, bytes],
    snapshot: PublishedProfileSnapshot,
    faq: ReviewedFaq,
    bundle_id: str,
) -> None:
    with faq.database.connection() as connection:
        connection.execute("BEGIN")
        for locale in ("zh-TW", "en"):
            try:
                profile = json.loads(localized_public_profile_bytes(snapshot.document, locale))
            except TypeError, ValueError:
                raise SiteExportError("SHARING_EXPORT_INVALID") from None
            if not isinstance(profile, dict) or not isinstance(profile.get("character"), dict):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            profile["character"]["asset_url"] = "./character.png"
            scene = profile["character"].get("scene")
            if isinstance(scene, dict):
                scene["background_url"] = _static_background_path(snapshot)
            _put_file(files, f"profile-{locale}.json", canonical_json_bytes(profile))
            faq_payload = faq.public_payload_for_bundle(locale, bundle_id, connection)
            if len(canonical_json_bytes(faq_payload)) > _MAX_FAQ_BYTES:
                raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
            _put_file(files, f"faq-{locale}.json", canonical_json_bytes(faq_payload))


def _static_background_path(snapshot: PublishedProfileSnapshot) -> str | None:
    if snapshot.background_content is None:
        return None
    extension = "webp" if snapshot.background_content.startswith(b"RIFF") else "png"
    digest = hashlib.sha256(snapshot.background_content).hexdigest()
    return f"./scene/{digest}.{extension}"


def _add_bundle_assets(
    files: dict[str, bytes],
    public_directory: Path,
    manifest: BundleManifest,
    snapshot: PublishedProfileSnapshot,
) -> None:
    records = {item.path: item for item in manifest.files}
    sprite_record = records.get("public/character.png")
    if (
        sprite_record is None
        or sprite_record.size != len(snapshot.sprite_content)
        or sprite_record.sha256 != hashlib.sha256(snapshot.sprite_content).hexdigest()
    ):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    _put_file(files, "character.png", snapshot.sprite_content)
    for path in _CARD_PATHS:
        record = records.get(path)
        if record is None:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        remaining = MAX_EXPORT_BYTES - sum(map(len, files.values()))
        if remaining <= 0:
            raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        payload = _read_bundle_file(public_directory, path, min(record.size, remaining))
        if len(payload) != record.size or hashlib.sha256(payload).hexdigest() != record.sha256:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        _put_file(files, path.removeprefix("public/"), payload)
    scene = snapshot.document.character.scene
    scene_paths = [path for path in records if path.startswith("public/scene/")]
    if snapshot.background_content is None:
        if scene is None or scene.background_url is not None:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        if snapshot.appearance_revision is None and scene_paths:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        return
    if scene is None or scene.background_url is None:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    extension = "webp" if snapshot.background_content.startswith(b"RIFF") else "png"
    try:
        canonical = validate_scene_image(
            snapshot.background_content, filename=f"background.{extension}"
        )
    except SceneImageError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    if canonical.content != snapshot.background_content or canonical.format != extension:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    if snapshot.appearance_revision is None:
        if len(scene_paths) != 1:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        match = _SCENE_PATH.fullmatch(scene_paths[0])
        if match is None:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        record = records[scene_paths[0]]
        if record.size != len(snapshot.background_content) or record.sha256 != canonical.sha256:
            raise SiteExportError("SHARING_EXPORT_INVALID")
        remaining = MAX_EXPORT_BYTES - sum(map(len, files.values()))
        if remaining <= 0 or record.size > remaining:
            raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        payload = _read_bundle_file(public_directory, scene_paths[0], min(record.size, remaining))
        if (
            payload != snapshot.background_content
            or canonical.sha256 != match.group(1)
            or canonical.sha256 != record.sha256
            or len(payload) != record.size
        ):
            raise SiteExportError("SHARING_EXPORT_INVALID")
    remaining = MAX_EXPORT_BYTES - sum(map(len, files.values()))
    if remaining <= 0 or len(snapshot.background_content) > remaining:
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    digest = hashlib.sha256(snapshot.background_content).hexdigest()
    _put_file(files, f"scene/{digest}.{extension}", snapshot.background_content)


def _add_cited_owner_assertions(files: dict[str, bytes], index: Any) -> None:
    payloads: dict[str, dict[str, Any]] = {}
    cited: dict[str, Any] = {}
    for locale in ("zh-TW", "en"):
        faq_path = f"faq-{locale}.json"
        try:
            payload = json.loads(files[faq_path])
        except KeyError, UnicodeDecodeError, json.JSONDecodeError:
            raise SiteExportError("SHARING_EXPORT_INVALID") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        payloads[faq_path] = payload
        for entry in payload["entries"]:
            if not isinstance(entry, dict) or not isinstance(entry.get("citations"), list):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            source_ids: set[str] = set()
            for citation in entry["citations"]:
                if not isinstance(citation, dict):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                source_id = citation.get("id")
                if isinstance(source_id, str):
                    if source_id in source_ids:
                        raise SiteExportError("SHARING_EXPORT_INVALID")
                    source_ids.add(source_id)
                if citation.get("evidence_class") != "OWNER_ASSERTION":
                    continue
                revision = citation.get("commit_sha")
                evidence_id = citation.get("evidence_id")
                if (
                    not isinstance(source_id, str)
                    or not _SOURCE_ID.fullmatch(source_id)
                    or not isinstance(revision, str)
                    or not COMMIT_RE.fullmatch(revision)
                    or not isinstance(evidence_id, str)
                    or not EVIDENCE_ID_RE.fullmatch(evidence_id)
                ):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                evidence = cited.get(evidence_id)
                if evidence is None:
                    evidence = index.evidence(evidence_id)
                    if evidence is None:
                        raise SiteExportError("SHARING_EXPORT_INVALID")
                    cited[evidence_id] = evidence
                metadata = evidence.metadata
                origin = metadata.get("origin") if isinstance(metadata, dict) else None
                valid_origin = (
                    origin == "local" and evidence.repository_slug == "local/portfolio"
                ) or (
                    origin == "github"
                    and isinstance(evidence.repository_slug, str)
                    and _REPOSITORY_SLUG.fullmatch(evidence.repository_slug) is not None
                )
                if (
                    evidence.evidence_id != evidence_id
                    or evidence.evidence_class != "OWNER_ASSERTION"
                    or evidence.commit_sha != revision
                    or not valid_origin
                    or not isinstance(evidence.content, str)
                    or len(evidence.content.encode("utf-8")) > _MAX_OWNER_ASSERTION_BYTES
                ):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                try:
                    expected_url = evidence.github_permalink
                except IndexReadError, TypeError, ValueError, AttributeError:
                    raise SiteExportError("SHARING_EXPORT_INVALID") from None
                if (
                    citation.get("evidence_class") != evidence.evidence_class
                    or citation.get("repository") != evidence.repository_slug
                    or citation.get("path") != evidence.path
                    or type(citation.get("start_line")) is not int
                    or citation.get("start_line") != evidence.start_line
                    or type(citation.get("end_line")) is not int
                    or citation.get("end_line") != evidence.end_line
                    or citation.get("title") != (evidence.title or evidence.symbol or evidence.path)
                    or citation.get("excerpt") != evidence.content[:500]
                    or citation.get("url") != expected_url
                ):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                if origin == "local":
                    citation["url"] = f"./owner-statements/{revision}/{evidence_id}.txt"
    if len(cited) > _MAX_OWNER_ASSERTIONS:
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    for evidence_id, evidence in sorted(cited.items()):
        if evidence.metadata.get("origin") != "local":
            continue
        path = f"owner-statements/{evidence.commit_sha}/{evidence_id}.txt"
        content = ("Owner-confirmed statement / 本人確認的陳述\n\n" + evidence.content).encode(
            "utf-8"
        )
        _put_file(files, path, content)
    for faq_path, payload in payloads.items():
        _put_file(files, faq_path, canonical_json_bytes(payload))


def _validate_public_links(files: dict[str, bytes]) -> None:
    for locale in ("zh-TW", "en"):
        try:
            payload = json.loads(files[f"faq-{locale}.json"])
        except KeyError, UnicodeDecodeError, json.JSONDecodeError:
            raise SiteExportError("SHARING_EXPORT_INVALID") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        for entry in payload["entries"]:
            for citation in entry.get("citations", []):
                url = citation.get("url") if isinstance(citation, dict) else None
                if not isinstance(url, str):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                if url.startswith("./owner-statements/"):
                    path = url.removeprefix("./")
                    if path not in files:
                        raise SiteExportError("SHARING_EXPORT_INVALID")
                    continue
                try:
                    parsed = urlsplit(url)
                    valid_github = (
                        parsed.scheme == "https"
                        and parsed.hostname == "github.com"
                        and parsed.username is None
                        and parsed.password is None
                        and not parsed.port
                    )
                except ValueError:
                    valid_github = False
                if not valid_github:
                    raise SiteExportError("SHARING_EXPORT_INVALID")


def _scan_public_secrets(files: dict[str, bytes]) -> None:
    for content in files.values():
        if _PEM_SECRET.search(content) or _CREDENTIAL_CANARY.search(content):
            raise SiteExportError("SHARING_EXPORT_INVALID")


def _put_file(files: dict[str, bytes], path: str, content: bytes) -> None:
    if not safe_relative_path(path):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    existing = len(files.get(path, b""))
    total = sum(map(len, files.values())) - existing
    if total + len(content) > MAX_EXPORT_BYTES:
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    if path not in files and len(files) >= _MAX_FILE_COUNT - 1:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    files[path] = content


def _read_bundle_file(public_directory: Path, path: str, max_bytes: int) -> bytes:
    if not safe_relative_path(path.removeprefix("public/")) or not path.startswith("public/"):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    return _read_regular_file(public_directory, path.removeprefix("public/"), max_bytes)


def _read_regular_file(root: Path, relative: str, max_bytes: int) -> bytes:
    if not safe_relative_path(relative):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    candidate = root
    try:
        for index, part in enumerate(PurePosixPath(relative).parts):
            candidate = candidate / part
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            if index + 1 < len(PurePosixPath(relative).parts):
                if not stat.S_ISDIR(metadata.st_mode):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
            elif not stat.S_ISREG(metadata.st_mode):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            elif metadata.st_size > max_bytes:
                raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        with candidate.open("rb") as source:
            payload = source.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        return payload
    except SiteExportError:
        raise
    except OSError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None


def _write_zip_temp(
    files: dict[str, bytes], manifest_content: bytes, expected_manifest: dict[str, Any]
) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix="reponpc-site-export-", suffix=".zip")
    os.close(descriptor)
    path = Path(raw_path)
    entries = dict(files)
    entries[MANIFEST_NAME] = manifest_content
    if (
        len(entries) > _MAX_FILE_COUNT
        or sum(map(len, entries.values())) > MAX_EXPORT_BYTES
        or any(not safe_relative_path(name) for name in entries)
    ):
        path.unlink(missing_ok=True)
        raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
    try:
        with zipfile.ZipFile(
            path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for name in sorted(entries):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.extra = b""
                info.comment = b""
                archive.writestr(
                    info, entries[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
                )
        _verify_written_export(path, expected_manifest, files)
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _verify_written_export(
    path: Path, expected_manifest: dict[str, Any], expected_files: dict[str, bytes]
) -> None:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            info_list = archive.infolist()
            names = [info.filename for info in info_list]
            expected_names = sorted((*expected_files, MANIFEST_NAME))
            if names != expected_names or len(names) != len(set(names)):
                raise SiteExportError("SHARING_EXPORT_INVALID")
            expected_content = {
                **expected_files,
                MANIFEST_NAME: canonical_json_bytes(expected_manifest) + b"\n",
            }
            total = 0
            for info in info_list:
                if not safe_relative_path(info.filename) or info.file_size < 0:
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                total += info.file_size
                if total > MAX_EXPORT_BYTES:
                    raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
                expected = expected_content[info.filename]
                if info.file_size != len(expected):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
                offset = 0
                with archive.open(info, "r") as member:
                    while chunk := member.read(64 * 1024):
                        next_offset = offset + len(chunk)
                        if chunk != expected[offset:next_offset]:
                            raise SiteExportError("SHARING_EXPORT_INVALID")
                        offset = next_offset
                if offset != len(expected):
                    raise SiteExportError("SHARING_EXPORT_INVALID")
    except OSError, zipfile.BadZipFile, RuntimeError:
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
