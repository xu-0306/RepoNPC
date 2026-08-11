"""ETag-driven, host-allowlisted bundle polling with last-known-good retention."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.bundles.archive import BundleError, verify_bundle_archive
from reponpc.bundles.manager import BundleActivationError, BundleManager
from reponpc.bundles.manifest import ManifestError, StableManifest, parse_stable_manifest
from reponpc.indexing.sources import EmbeddingIdentity
from reponpc.runtime.database import BundleRuntimeState, RuntimeDatabase


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Bounded HTTP response data independent of a concrete client library."""

    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, slots=True)
class DownloadResult:
    status: int
    headers: Mapping[str, str]
    size_bytes: int
    sha256: str


class BundleTransport(Protocol):
    """The polling boundary; tests inject deterministic responses here."""

    def get(self, url: str, *, headers: Mapping[str, str], max_bytes: int) -> HttpResponse:
        """Fetch an allowlisted resource without silently following redirects."""

    def download_to(
        self, url: str, *, headers: Mapping[str, str], destination: Path, max_bytes: int
    ) -> DownloadResult:
        """Stream an allowlisted asset to a newly-created destination."""


class _NoRedirect(HTTPRedirectHandler):
    """Follow only bounded HTTPS redirects whose every target is allowlisted."""

    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> Request | None:
        _allowed_https_url(newurl, self._allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


class UrllibBundleTransport:
    """Small production transport that rejects every unchecked redirect hop."""

    def __init__(self, *, allowed_hosts: frozenset[str], timeout_seconds: float = 15.0) -> None:
        self._allowed_hosts = {host.casefold() for host in allowed_hosts}
        self._timeout_seconds = timeout_seconds

    def get(self, url: str, *, headers: Mapping[str, str], max_bytes: int) -> HttpResponse:
        _allowed_https_url(url, self._allowed_hosts)
        request = Request(url, headers=dict(headers), method="GET")
        try:
            with build_opener(_NoRedirect(self._allowed_hosts)).open(
                request, timeout=self._timeout_seconds
            ) as response:
                _allowed_https_url(response.geturl(), self._allowed_hosts)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise BundleUpdateError("bundle_download_too_large")
                return HttpResponse(response.status, dict(response.headers.items()), body)
        except BundleUpdateError:
            raise
        except HTTPError as exc:
            if exc.code == 304:
                return HttpResponse(304, dict(exc.headers.items()), b"")
            raise BundleUpdateError("bundle_request_failed") from exc

    def download_to(
        self, url: str, *, headers: Mapping[str, str], destination: Path, max_bytes: int
    ) -> DownloadResult:
        if isinstance(max_bytes, bool) or max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        _allowed_https_url(url, self._allowed_hosts)
        digest = hashlib.sha256()
        written = 0
        created = False
        try:
            with destination.open("xb") as target:
                created = True
                response = build_opener(_NoRedirect(self._allowed_hosts)).open(
                    Request(url, headers=dict(headers), method="GET"),
                    timeout=self._timeout_seconds,
                )
                with response:
                    _allowed_https_url(response.geturl(), self._allowed_hosts)
                    if response.status != 200:
                        raise BundleUpdateError("bundle_download_invalid")
                    while chunk := response.read(64 * 1024):
                        written += len(chunk)
                        if written > max_bytes:
                            raise BundleUpdateError("bundle_download_too_large")
                        target.write(chunk)
                        digest.update(chunk)
                return DownloadResult(
                    200, dict(response.headers.items()), written, digest.hexdigest()
                )
        except BundleUpdateError:
            if created:
                _safe_unlink(destination)
            raise
        except (HTTPError, URLError, OSError) as exc:
            if created:
                _safe_unlink(destination)
            raise BundleUpdateError("bundle_request_failed") from exc


class BundleUpdateError(RuntimeError):
    """A safe, bounded updater error code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("bundle update failed")


class BundleUpdater:
    """One poll transaction; callers own its application lifecycle scheduling."""

    def __init__(
        self,
        *,
        manifest_url: str,
        transport: BundleTransport,
        manager: BundleManager,
        runtime_database: RuntimeDatabase,
        expected_embedding: EmbeddingIdentity,
        max_bundle_bytes: int,
        allowed_hosts: frozenset[str],
        data_directory: Path,
    ) -> None:
        self._manifest_url = manifest_url
        self._transport = transport
        self._manager = manager
        self._runtime = runtime_database
        self._embedding = expected_embedding
        self._max_bundle_bytes = max_bundle_bytes
        self._allowed_hosts = {host.casefold() for host in allowed_hosts}
        self._staging_root = Path(data_directory) / "bundles" / "staging"
        _allowed_https_url(manifest_url, self._allowed_hosts)
        self._staging_root.mkdir(parents=True, exist_ok=True)

    def poll_once(self) -> str:
        """Check once and return a non-secret outcome token for lifecycle logs."""

        state = self._runtime.bundle_state()
        headers = {"Accept": "application/json"}
        if state.manifest_etag:
            headers["If-None-Match"] = state.manifest_etag
        try:
            response = self._transport.get(
                self._manifest_url,
                headers=headers,
                max_bytes=min(self._max_bundle_bytes, 256 * 1024),
            )
            if response.status == 304:
                self._save_check(state, etag=state.manifest_etag, error=None)
                return "not_modified"
            if response.status != 200:
                raise BundleUpdateError("stable_manifest_response_invalid")
            stable = parse_stable_manifest(response.body)
            _allowed_https_url(stable.asset_url, self._allowed_hosts)
            etag = response.headers.get("ETag")
            manager_status = self._manager.status()
            if stable.bundle_id == manager_status.active_bundle_id:
                self._save_check(state, etag=etag, error=None)
                return "already_active"
            if manager_status.pinned_bundle_id is not None:
                self._save_check(state, etag=etag, error=None)
                return "pinned_newer_available"
            self._download_verify_activate(stable)
            self._save_check(state, etag=etag, error=None)
            return "activated"
        except (BundleUpdateError, BundleError, BundleActivationError, ManifestError) as exc:
            self._save_check(state, etag=state.manifest_etag, error=_safe_code(exc))
            return "rejected"

    def _download_verify_activate(self, stable: StableManifest) -> None:
        if stable.asset_size > self._max_bundle_bytes:
            raise BundleUpdateError("bundle_download_too_large")
        archive_path = self._staging_root / f".{stable.bundle_id}.{uuid.uuid4().hex}.tar.zst"
        try:
            response = self._transport.download_to(
                stable.asset_url,
                headers={"Accept": "application/octet-stream"},
                destination=archive_path,
                max_bytes=self._max_bundle_bytes,
            )
            if response.status != 200 or response.size_bytes != stable.asset_size:
                raise BundleUpdateError("bundle_download_invalid")
            if response.sha256 != stable.asset_sha256:
                raise BundleUpdateError("bundle_outer_checksum_invalid")
            staging = self._staging_root / uuid.uuid4().hex
            candidate = verify_bundle_archive(
                archive_path=archive_path,
                staging_directory=staging,
                expected_outer_sha256=stable.asset_sha256,
                expected_embedding=self._embedding,
                max_bundle_bytes=self._max_bundle_bytes,
            )
            if candidate.manifest.bundle_id != stable.bundle_id:
                candidate.close()
                shutil.rmtree(candidate.directory, ignore_errors=True)
                raise BundleUpdateError("stable_bundle_id_mismatch")
            self._manager.activate(candidate)
        finally:
            _safe_unlink(archive_path)

    def _save_check(
        self, state: BundleRuntimeState, *, etag: str | None, error: str | None
    ) -> None:
        status = self._manager.status()
        self._runtime.save_bundle_state(
            BundleRuntimeState(
                active_bundle_id=status.active_bundle_id,
                previous_bundle_id=status.previous_bundle_id,
                pinned_bundle_id=status.pinned_bundle_id,
                manifest_etag=etag,
                last_checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
                safe_update_error=error,
            )
        )


def _allowed_https_url(value: str, allowed_hosts: set[str]) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.casefold() not in allowed_hosts
        or parsed.username
        or parsed.password
    ):
        raise BundleUpdateError("bundle_host_not_allowed")


def _safe_code(error: Exception) -> str:
    return (
        error.code
        if isinstance(error, (BundleUpdateError, BundleError, BundleActivationError))
        else "bundle_invalid"
    )


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise BundleUpdateError("bundle_staging_cleanup_failed") from exc
