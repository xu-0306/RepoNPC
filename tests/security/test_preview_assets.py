from __future__ import annotations

import pytest

from reponpc.admin.preview_assets import PreviewAssetError, PreviewAssetStore


def _session(value: str = "a") -> str:
    return value * 64


def test_preview_assets_are_bound_to_the_authenticated_session() -> None:
    store = PreviewAssetStore()
    asset_id = store.put(
        owner_session_hash=_session(),
        content=b"canonical-image",
        media_type="image/png",
    )

    assert store.get(asset_id=asset_id, owner_session_hash=_session()).content == b"canonical-image"
    with pytest.raises(PreviewAssetError) as captured:
        store.get(asset_id=asset_id, owner_session_hash=_session("b"))
    assert captured.value.code == "NOT_FOUND"
    with pytest.raises(PreviewAssetError):
        store.delete(asset_id=asset_id, owner_session_hash=_session("b"))
    assert store.get(asset_id=asset_id, owner_session_hash=_session()).content == b"canonical-image"


def test_expired_preview_asset_is_unavailable_and_removed() -> None:
    now = [100.0]
    store = PreviewAssetStore(ttl_seconds=30, clock=lambda: now[0])
    asset_id = store.put(owner_session_hash=_session(), content=b"image", media_type="image/webp")
    now[0] += 30

    with pytest.raises(PreviewAssetError) as captured:
        store.get(asset_id=asset_id, owner_session_hash=_session())
    assert captured.value.code == "NOT_FOUND"
    assert store._total_bytes == 0


def test_storage_is_bounded_and_evicts_only_oldest_owned_preview_first() -> None:
    now = [0.0]
    store = PreviewAssetStore(
        ttl_seconds=100,
        max_asset_bytes=4,
        max_total_bytes=8,
        max_assets=2,
        max_session_assets=1,
        clock=lambda: now[0],
    )
    first = store.put(owner_session_hash=_session(), content=b"one", media_type="image/png")
    other = store.put(owner_session_hash=_session("b"), content=b"two", media_type="image/png")
    now[0] += 1
    replacement = store.put(owner_session_hash=_session(), content=b"new", media_type="image/png")

    with pytest.raises(PreviewAssetError):
        store.get(asset_id=first, owner_session_hash=_session())
    assert store.get(asset_id=other, owner_session_hash=_session("b")).content == b"two"
    assert store.get(asset_id=replacement, owner_session_hash=_session()).content == b"new"


@pytest.mark.parametrize("media_type", ["text/html", "application/octet-stream"])
def test_preview_assets_reject_non_image_media_types(media_type: str) -> None:
    store = PreviewAssetStore()
    with pytest.raises(PreviewAssetError) as captured:
        store.put(owner_session_hash=_session(), content=b"bytes", media_type=media_type)  # type: ignore[arg-type]
    assert captured.value.code == "PREVIEW_ASSET_INVALID"


def test_asset_ids_and_session_hashes_are_not_authority_by_themselves() -> None:
    store = PreviewAssetStore()
    with pytest.raises(PreviewAssetError):
        store.get(asset_id="path/to/file", owner_session_hash=_session())
    with pytest.raises(PreviewAssetError):
        store.put(owner_session_hash="not-a-session-hash", content=b"x", media_type="image/png")
