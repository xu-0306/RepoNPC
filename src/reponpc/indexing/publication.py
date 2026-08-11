"""Publication-last coordination for immutable Release bundle assets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from reponpc.bundles.archive import BuiltBundle
from reponpc.bundles.manifest import StableManifest


class PublicationError(RuntimeError):
    """Safe publication error; upstream responses and URLs are not reflected."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("bundle publication failed")


class ReleasePublisher(Protocol):
    """The only external mutation boundary used by the publication coordinator."""

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        """Create a new immutable Release container and return its ID."""

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        """Upload the archive once and return its immutable HTTPS asset URL."""

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        """Verify that exact published bytes are reachable before any pointer mutation."""

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        """Perform the sole mutable stable-manifest write as publication's final step."""


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """The immutable tag/asset plus final stable manifest pointer."""

    release_tag: str
    asset_url: str
    stable_manifest: StableManifest


class PublicationCoordinator:
    """Fail closed: no stable-manifest write occurs before all immutable stages pass."""

    def __init__(self, publisher: ReleasePublisher) -> None:
        self._publisher = publisher

    def publish(self, bundle: BuiltBundle, *, now: datetime) -> PublicationResult:
        """Create, upload, verify, and only then advance the stable pointer."""

        if now.tzinfo is None:
            raise ValueError("publication timestamp must be timezone-aware")
        asset_name = bundle.archive_path.name
        expected_name = f"reponpc-index-{bundle.manifest.bundle_id}.tar.zst"
        if asset_name != expected_name:
            raise PublicationError("bundle_asset_name_invalid")
        release_tag = f"index-{bundle.manifest.bundle_id}"
        try:
            release_id = self._publisher.create_immutable_release(tag=release_tag, name=release_tag)
            asset_url = self._publisher.upload_immutable_asset(
                release_id=release_id,
                name=asset_name,
                content=bundle.archive_path.read_bytes(),
            )
            self._publisher.verify_asset(
                asset_url=asset_url,
                size=bundle.archive_size,
                sha256=bundle.archive_sha256,
            )
            stable = StableManifest(
                bundle_id=bundle.manifest.bundle_id,
                release_tag=release_tag,
                asset_url=asset_url,
                asset_size=bundle.archive_size,
                asset_sha256=bundle.archive_sha256,
                published_at=now.astimezone(UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
            )
            self._publisher.update_stable_manifest_last(content=stable.canonical_bytes())
        except PublicationError:
            raise
        except OSError as exc:
            raise PublicationError("bundle_publication_failed") from exc
        return PublicationResult(
            release_tag=release_tag, asset_url=asset_url, stable_manifest=stable
        )
