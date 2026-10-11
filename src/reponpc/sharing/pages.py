"""Persisted Pages configuration and owner-triggered publication checks."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reponpc.admin.faq import FaqError, ReviewedFaq
from reponpc.admin.scene import AdminSceneService, SceneServiceError
from reponpc.api.visitor_gateway import VisitorGateway, _pages_origin
from reponpc.bundles.manager import BundleManager
from reponpc.config.environment import _canonical_origin
from reponpc.runtime.database import RuntimeDatabase, RuntimeDatabaseError
from reponpc.sharing.export import build_site_files
from reponpc.sharing.manifest import (
    MANIFEST_NAME,
    SiteExportError,
    canonical_json_bytes,
    pages_target,
    parse_manifest,
)
from reponpc.sharing.pages_transport import fetch_pages_resource

_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_ENTRANCE_BYTES = 1024 * 1024
_VERIFY_DEADLINE_SECONDS = 20


class PagesSharingService:
    """Store only Pages configuration and the latest owner-triggered verification."""

    def __init__(
        self,
        *,
        database: RuntimeDatabase,
        faq: ReviewedFaq,
        scene_service: AdminSceneService,
        gateway_supplier: Callable[[], VisitorGateway | None],
    ) -> None:
        if faq.bundles is not scene_service.manager:
            raise ValueError("sharing sources must use one bundle manager")
        self.database = database
        self.faq = faq
        self.scene_service = scene_service
        self.manager: BundleManager = faq.bundles
        self.gateway_supplier = gateway_supplier

    def state(self) -> dict[str, object]:
        row = self._row()
        pages_url = row["pages_url"]
        verified = bool(
            isinstance(pages_url, str)
            and row["verified_pages_url"] == pages_url
            and row["verified_content_sha256"] is not None
            and row["verified_at"] is not None
        )
        return {
            "pages_url": pages_url,
            "configured": pages_url is not None,
            "verified": verified,
            "verified_at": row["verified_at"] if verified else None,
            "verified_content_sha256": (row["verified_content_sha256"] if verified else None),
        }

    def configure_pages(self, *, pages_url: str) -> dict[str, object]:
        pages_origin = self._current_origins()[1]
        target = _validated_target(pages_url, pages_origin)
        try:
            with self.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT pages_url FROM pages_sharing_state WHERE singleton_id=1"
                ).fetchone()
                if row is None:
                    raise SiteExportError("SHARING_EXPORT_UNAVAILABLE")
                if row["pages_url"] != target.url:
                    connection.execute(
                        "UPDATE pages_sharing_state SET pages_url=?, "
                        "verified_pages_url=NULL, verified_content_sha256=NULL, "
                        "verified_at=NULL WHERE singleton_id=1",
                        (target.url,),
                    )
                connection.commit()
        except SiteExportError:
            raise
        except (OSError, sqlite3.Error, RuntimeDatabaseError):
            raise SiteExportError("SHARING_EXPORT_UNAVAILABLE") from None
        return self.state()

    def verify(self, *, web_dist: Path) -> dict[str, object]:
        row = self._row()
        pages_url = row["pages_url"]
        if not isinstance(pages_url, str):
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        gateway_origin, pages_origin = self._current_origins()
        target = _validated_target(pages_url, pages_origin)
        if target.url != pages_url:
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        try:
            _files, expected_manifest = build_site_files(
                faq=self.faq,
                scene_service=self.scene_service,
                web_dist=web_dist,
                pages_url=pages_url,
                gateway_origin=gateway_origin,
                pages_origin=pages_origin,
                origins_supplier=self.current_origins,
            )
            manifest_content = canonical_json_bytes(expected_manifest) + b"\n"
            manifest_url = f"{target.origin}{target.base_path}{MANIFEST_NAME}"
            deadline = time.monotonic() + _VERIFY_DEADLINE_SECONDS
            entrance = fetch_pages_resource(
                target.url,
                pages_origin=target.origin,
                deadline=deadline,
                max_response_bytes=_MAX_ENTRANCE_BYTES,
            )
            remote_manifest = fetch_pages_resource(
                manifest_url,
                pages_origin=target.origin,
                deadline=deadline,
                max_response_bytes=_MAX_MANIFEST_BYTES,
            )
            if not _responses_match(
                entrance,
                remote_manifest,
                manifest_content=manifest_content,
                expected=expected_manifest,
            ):
                raise SiteExportError("SHARING_VERIFICATION_FAILED")
        except SiteExportError:
            self._clear_verification()
            raise
        except (OSError, ValueError, UnicodeError, FaqError, SceneServiceError):
            self._clear_verification()
            raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE") from None

        try:
            with self.database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                result = connection.execute(
                    "UPDATE pages_sharing_state SET verified_pages_url=?, "
                    "verified_content_sha256=?, verified_at=? "
                    "WHERE singleton_id=1 AND pages_url=?",
                    (pages_url, expected_manifest["content_sha256"], _timestamp(), pages_url),
                )
                if result.rowcount != 1:
                    connection.rollback()
                    raise SiteExportError("SHARING_CONFLICT")
                connection.commit()
        except SiteExportError:
            raise
        except (OSError, sqlite3.Error, RuntimeDatabaseError):
            raise SiteExportError("SHARING_CONFLICT") from None
        return self.state()

    def current_origins(self) -> tuple[str, str]:
        return self._current_origins()

    def _clear_verification(self) -> None:
        try:
            with self.database.connection() as connection:
                connection.execute(
                    "UPDATE pages_sharing_state SET verified_pages_url=NULL, "
                    "verified_content_sha256=NULL, verified_at=NULL WHERE singleton_id=1"
                )
                connection.commit()
        except (OSError, sqlite3.Error):
            return

    def _row(self) -> sqlite3.Row:
        try:
            with self.database.connection() as connection:
                row = connection.execute(
                    "SELECT * FROM pages_sharing_state WHERE singleton_id=1"
                ).fetchone()
            if row is None:
                raise SiteExportError("SHARING_EXPORT_UNAVAILABLE")
            return row
        except SiteExportError:
            raise
        except (OSError, sqlite3.Error, RuntimeDatabaseError):
            raise SiteExportError("SHARING_EXPORT_UNAVAILABLE") from None

    def _current_origins(self) -> tuple[str, str]:
        gateway = self.gateway_supplier()
        if gateway is None:
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        try:
            value = gateway.snapshot()
        except Exception:
            raise SiteExportError("SHARING_CONFIGURATION_INVALID") from None
        if not isinstance(value, dict):
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        gateway_origin = value.get("gateway_origin")
        pages_origin = value.get("pages_origin")
        normalized_gateway = (
            _canonical_origin(gateway_origin, https_only=True)
            if isinstance(gateway_origin, str)
            else None
        )
        normalized_pages = _pages_origin(pages_origin) if isinstance(pages_origin, str) else None
        if (
            normalized_gateway is None
            or normalized_gateway != gateway_origin
            or normalized_pages is None
            or normalized_pages != pages_origin
        ):
            raise SiteExportError("SHARING_CONFIGURATION_INVALID")
        return normalized_gateway, normalized_pages


def _validated_target(value: str, origin: str):
    if any(character.isspace() or ord(character) < 32 for character in value):
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    return pages_target(value, origin)


def _responses_match(
    entrance: Any,
    remote_manifest: Any,
    *,
    manifest_content: bytes,
    expected: dict[str, Any],
) -> bool:
    if entrance.status != 200 or remote_manifest.status != 200:
        return False
    entrance_type = (
        str(entrance.headers.get("content-type", "")).split(";", 1)[0].strip().casefold()
    )
    if entrance_type != "text/html":
        return False
    manifest_content_type = (
        str(remote_manifest.headers.get("content-type", "")).split(";", 1)[0].strip().casefold()
    )
    if manifest_content_type not in {"application/json", "text/json"}:
        return False
    if remote_manifest.body != manifest_content:
        return False
    try:
        remote = parse_manifest(remote_manifest.body)
    except SiteExportError:
        return False
    if remote != expected:
        return False
    entrance_record = next(
        (entry for entry in expected["files"] if entry["path"] == "index.html"), None
    )
    if not isinstance(entrance_record, dict):
        return False
    return (
        len(entrance.body) == entrance_record["size"]
        and hashlib.sha256(entrance.body).hexdigest() == entrance_record["sha256"]
    )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
