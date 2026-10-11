"""Bounded, authenticated-session-scoped storage for transient preview images."""

from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

PreviewMediaType = Literal["image/png", "image/gif", "image/svg+xml", "image/webp"]
_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    {"image/png", "image/gif", "image/svg+xml", "image/webp"}
)
_DEFAULT_TTL_SECONDS: Final = 20 * 60
_DEFAULT_MAX_ASSET_BYTES: Final = 8 * 1024 * 1024
_DEFAULT_MAX_TOTAL_BYTES: Final = 64 * 1024 * 1024
_DEFAULT_MAX_ASSETS: Final = 512
_DEFAULT_MAX_SESSION_ASSETS: Final = 96


class PreviewAssetError(ValueError):
    """Safe preview-store failure with a stable internal code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("preview asset is unavailable")


@dataclass(frozen=True, slots=True)
class ProtectedPreviewAsset:
    """Canonical bytes resolved only after owner-session authorization."""

    content: bytes
    media_type: PreviewMediaType
    expires_at: float


@dataclass(frozen=True, slots=True)
class _StoredAsset:
    owner_session_hash: str
    content: bytes
    media_type: PreviewMediaType
    created_at: float
    expires_at: float


class PreviewAssetStore:
    """Keep only bounded transient bytes; random IDs are lookup keys, not authority."""

    def __init__(
        self,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_asset_bytes: int = _DEFAULT_MAX_ASSET_BYTES,
        max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
        max_assets: int = _DEFAULT_MAX_ASSETS,
        max_session_assets: int = _DEFAULT_MAX_SESSION_ASSETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            ttl_seconds <= 0
            or max_asset_bytes <= 0
            or max_total_bytes < max_asset_bytes
            or max_assets <= 0
            or max_session_assets <= 0
            or max_session_assets > max_assets
        ):
            raise ValueError("preview asset limits must be positive and consistent")
        self._ttl = ttl_seconds
        self._max_asset_bytes = max_asset_bytes
        self._max_total_bytes = max_total_bytes
        self._max_assets = max_assets
        self._max_session_assets = max_session_assets
        self._clock = clock
        self._lock = threading.RLock()
        self._assets: dict[str, _StoredAsset] = {}
        self._total_bytes = 0

    def put(
        self,
        *,
        owner_session_hash: str,
        content: bytes,
        media_type: PreviewMediaType,
    ) -> str:
        """Store trusted canonical bytes with bounded lifetime and session scope."""

        if not _valid_session_hash(owner_session_hash):
            raise PreviewAssetError("PREVIEW_ASSET_INVALID")
        if media_type not in _MEDIA_TYPES or not isinstance(content, bytes) or not content:
            raise PreviewAssetError("PREVIEW_ASSET_INVALID")
        if len(content) > self._max_asset_bytes:
            raise PreviewAssetError("PREVIEW_ASSET_TOO_LARGE")
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            self._evict_for_insert(owner_session_hash, len(content))
            asset_id = secrets.token_urlsafe(32)
            self._assets[asset_id] = _StoredAsset(
                owner_session_hash=owner_session_hash,
                content=bytes(content),
                media_type=media_type,
                created_at=now,
                expires_at=now + self._ttl,
            )
            self._total_bytes += len(content)
            return asset_id

    def get(self, *, asset_id: str, owner_session_hash: str) -> ProtectedPreviewAsset:
        """Return bytes only for the authenticated owner session that created them."""

        if not _valid_asset_id(asset_id) or not _valid_session_hash(owner_session_hash):
            raise PreviewAssetError("NOT_FOUND")
        now = self._clock()
        with self._lock:
            stored = self._assets.get(asset_id)
            if stored is None:
                raise PreviewAssetError("NOT_FOUND")
            if stored.expires_at <= now:
                self._remove(asset_id)
                raise PreviewAssetError("NOT_FOUND")
            if not secrets.compare_digest(stored.owner_session_hash, owner_session_hash):
                raise PreviewAssetError("NOT_FOUND")
            return ProtectedPreviewAsset(
                content=stored.content,
                media_type=stored.media_type,
                expires_at=stored.expires_at,
            )

    def delete(self, *, asset_id: str, owner_session_hash: str) -> None:
        """Delete one asset only when its session owner matches."""

        if not _valid_asset_id(asset_id) or not _valid_session_hash(owner_session_hash):
            raise PreviewAssetError("NOT_FOUND")
        with self._lock:
            stored = self._assets.get(asset_id)
            if stored is None or not secrets.compare_digest(
                stored.owner_session_hash, owner_session_hash
            ):
                raise PreviewAssetError("NOT_FOUND")
            self._remove(asset_id)

    def delete_session(self, owner_session_hash: str) -> None:
        """Remove transient bytes after logout or session revocation."""

        if not _valid_session_hash(owner_session_hash):
            return
        with self._lock:
            for asset_id, stored in tuple(self._assets.items()):
                if secrets.compare_digest(stored.owner_session_hash, owner_session_hash):
                    self._remove(asset_id)

    def clear(self) -> None:
        """Clear all transient assets for tests and application shutdown."""

        with self._lock:
            self._assets.clear()
            self._total_bytes = 0

    def _evict_for_insert(self, owner_session_hash: str, incoming_size: int) -> None:
        if incoming_size > self._max_total_bytes:
            raise PreviewAssetError("PREVIEW_ASSET_TOO_LARGE")
        session_assets = sorted(
            (
                (asset_id, stored)
                for asset_id, stored in self._assets.items()
                if secrets.compare_digest(stored.owner_session_hash, owner_session_hash)
            ),
            key=lambda item: item[1].created_at,
        )
        while (
            len(session_assets) >= self._max_session_assets
            or len(self._assets) >= self._max_assets
            or self._total_bytes + incoming_size > self._max_total_bytes
        ):
            if session_assets:
                asset_id, _stored = session_assets.pop(0)
            else:
                asset_id = min(self._assets, key=lambda item: self._assets[item].created_at)
            self._remove(asset_id)

    def _purge_expired(self, now: float) -> None:
        for asset_id, stored in tuple(self._assets.items()):
            if stored.expires_at <= now:
                self._remove(asset_id)

    def _remove(self, asset_id: str) -> None:
        stored = self._assets.pop(asset_id, None)
        if stored is not None:
            self._total_bytes -= len(stored.content)


def _valid_asset_id(asset_id: str) -> bool:
    return (
        isinstance(asset_id, str)
        and 32 <= len(asset_id) <= 64
        and all(character.isalnum() or character in "-_" for character in asset_id)
    )


def _valid_session_hash(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
