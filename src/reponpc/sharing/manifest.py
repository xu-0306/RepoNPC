"""Canonical public export manifest and strict Pages URL parsing."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from reponpc.api.visitor_gateway import _pages_origin
from reponpc.config.environment import _canonical_origin

MANIFEST_NAME = "export-manifest.json"
MAX_EXPORT_BYTES = 1_000_000_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BUNDLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
_PATH_PART_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class SiteExportError(ValueError):
    """Safe static-export failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("static site export could not be completed")


@dataclass(frozen=True, slots=True)
class PagesTarget:
    url: str
    origin: str
    base_path: str


@dataclass(frozen=True, slots=True)
class ExportFile:
    path: str
    size: int
    sha256: str

    @classmethod
    def from_bytes(cls, path: str, content: bytes) -> ExportFile:
        if not safe_relative_path(path):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        return cls(path=path, size=len(content), sha256=hashlib.sha256(content).hexdigest())

    def as_dict(self) -> dict[str, object]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}


def safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return (
        bool(path.parts)
        and not path.is_absolute()
        and path.as_posix() == value
        and all(part not in {"", ".", ".."} for part in path.parts)
        and all(_PATH_PART_RE.fullmatch(part) for part in path.parts)
    )


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise SiteExportError("SHARING_EXPORT_INVALID") from None


def pages_target(value: str | None, configured_origin: str | None) -> PagesTarget:
    """Accept root or project Pages paths only under the exact configured origin."""

    origin = _pages_origin(configured_origin) if configured_origin else None
    if origin is None:
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    if value is None:
        return PagesTarget(url=f"{origin}/", origin=origin, base_path="/")
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    try:
        parsed = urlsplit(value)
        if parsed.port is not None:
            raise ValueError
    except ValueError:
        raise SiteExportError("SHARING_CONFIGURATION_INVALID") from None
    canonical_origin = _pages_origin(urlunsplit((parsed.scheme, parsed.netloc, "", "", "")))
    if (
        canonical_origin != origin
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "%" in parsed.path
        or "\\" in parsed.path
        or "//" in parsed.path
    ):
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    raw_parts = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if any(part in {"", ".", ".."} or not _PATH_PART_RE.fullmatch(part) for part in raw_parts):
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    base_path = "/" + "/".join(raw_parts) + ("/" if raw_parts else "")
    return PagesTarget(url=f"{origin}{base_path}", origin=origin, base_path=base_path)


def create_manifest(
    *,
    files: dict[str, bytes],
    bundle_id: str,
    character_revision: int,
    pages: PagesTarget,
    gateway_origin: str,
    pages_origin: str,
) -> dict[str, Any]:
    if not _BUNDLE_RE.fullmatch(bundle_id) or character_revision < 0:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    normalized_gateway = _canonical_origin(gateway_origin, https_only=True)
    normalized_pages = _pages_origin(pages_origin)
    if normalized_gateway != gateway_origin or normalized_pages != pages_origin:
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    if MANIFEST_NAME in files:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    records = [ExportFile.from_bytes(path, content) for path, content in files.items()]
    records.sort(key=lambda record: record.path)
    identity_content = canonical_json_bytes([record.as_dict() for record in records])
    return {
        "schema_version": 1,
        "bundle_id": bundle_id,
        "character_revision": character_revision,
        "pages_url": pages.url,
        "base_path": pages.base_path,
        "pages_origin": pages_origin,
        "gateway_origin": gateway_origin,
        "content_sha256": hashlib.sha256(identity_content).hexdigest(),
        "files": [record.as_dict() for record in records],
    }


def parse_manifest(content: bytes) -> dict[str, Any]:
    if len(content) > 4 * 1024 * 1024:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SiteExportError("SHARING_EXPORT_INVALID") from None
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "bundle_id",
        "character_revision",
        "pages_url",
        "base_path",
        "pages_origin",
        "gateway_origin",
        "content_sha256",
        "files",
    }:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    canonical = canonical_json_bytes(value)
    if content not in {canonical, canonical + b"\n"}:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    if (
        not isinstance(value["schema_version"], int)
        or isinstance(value["schema_version"], bool)
        or value["schema_version"] != 1
        or not isinstance(value["bundle_id"], str)
        or not _BUNDLE_RE.fullmatch(value["bundle_id"])
        or not isinstance(value["character_revision"], int)
        or isinstance(value["character_revision"], bool)
        or value["character_revision"] < 0
        or not isinstance(value["pages_url"], str)
        or not isinstance(value["base_path"], str)
        or not isinstance(value["pages_origin"], str)
        or not isinstance(value["gateway_origin"], str)
        or not isinstance(value["content_sha256"], str)
        or not _SHA256_RE.fullmatch(value["content_sha256"])
        or not isinstance(value["files"], list)
        or len(value["files"]) > 4096
    ):
        raise SiteExportError("SHARING_EXPORT_INVALID")
    pages = pages_target(value["pages_url"], value["pages_origin"])
    if pages.base_path != value["base_path"] or pages.url != value["pages_url"]:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    if _canonical_origin(value["gateway_origin"], https_only=True) != value["gateway_origin"]:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    expected_identity: list[dict[str, object]] = []
    previous_path = ""
    total_size = len(content)
    for entry in value["files"]:
        if not isinstance(entry, dict):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        path = entry.get("path")
        size = entry.get("size")
        digest = entry.get("sha256")
        if (
            set(entry) != {"path", "size", "sha256"}
            or not isinstance(path, str)
            or not safe_relative_path(path)
            or path == MANIFEST_NAME
            or path <= previous_path
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
        ):
            raise SiteExportError("SHARING_EXPORT_INVALID")
        total_size += size
        if total_size > MAX_EXPORT_BYTES:
            raise SiteExportError("SHARING_EXPORT_TOO_LARGE")
        previous_path = path
        expected_identity.append({"path": path, "size": size, "sha256": digest})
    identity_content = canonical_json_bytes(expected_identity)
    if hashlib.sha256(identity_content).hexdigest() != value["content_sha256"]:
        raise SiteExportError("SHARING_EXPORT_INVALID")
    return value
