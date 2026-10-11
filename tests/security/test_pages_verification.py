from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from reponpc.providers.http_transport import ProviderHttpResponse
from reponpc.runtime.database import RuntimeDatabase
from reponpc.sharing import pages as pages_module
from reponpc.sharing.manifest import canonical_json_bytes, create_manifest, pages_target
from reponpc.sharing.pages import PagesSharingService


class _BundleManager:
    def __init__(self) -> None:
        self.bundle_id = "pages-fixture-bundle"
        self.lock = threading.RLock()

    @contextlib.contextmanager
    def acquire_snapshot(self) -> Iterator[tuple[object, str, Path]]:
        with self.lock:
            yield object(), self.bundle_id, Path("public")

    @contextlib.contextmanager
    def guard_active_bundle(self, bundle_id: str) -> Iterator[None]:
        with self.lock:
            if bundle_id != self.bundle_id:
                raise RuntimeError("bundle changed")
            yield


class _Faq:
    def __init__(self, manager: _BundleManager) -> None:
        self.bundles = manager
        self.content = "Approved fixture answer"


class _SceneService:
    def __init__(self, manager: _BundleManager) -> None:
        self.manager = manager
        self.lock = threading.RLock()
        self.character_revision = 7

    @contextlib.contextmanager
    def _portfolio_lock(self) -> Iterator[None]:
        with self.lock:
            yield

    def _snapshot_from_lease(self, bundle_id: str, _directory: Path) -> object:
        assert bundle_id == self.manager.bundle_id
        return SimpleNamespace(bundle_id=bundle_id, character_revision=self.character_revision)

    @contextlib.contextmanager
    def published_profile(self) -> Iterator[object]:
        with (
            self.manager.acquire_snapshot() as (_index, bundle_id, directory),
            self._portfolio_lock(),
        ):
            yield self._snapshot_from_lease(bundle_id, directory)


class _Gateway:
    gateway_origin = "https://chat.example.test"
    pages_origin = "https://fixture.github.io"

    def snapshot(self) -> dict[str, str]:
        return {"gateway_origin": self.gateway_origin, "pages_origin": self.pages_origin}


@pytest.fixture
def configured_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = RuntimeDatabase(tmp_path)
    database.initialize()
    manager = _BundleManager()
    faq = _Faq(manager)
    scene = _SceneService(manager)
    gateway = _Gateway()
    service = PagesSharingService(
        database=database,
        faq=faq,  # type: ignore[arg-type]
        scene_service=scene,  # type: ignore[arg-type]
        gateway_supplier=lambda: gateway,  # type: ignore[arg-type]
    )
    service.configure_pages(pages_url="https://fixture.github.io/project")
    entrance = b"<!doctype html><title>Fixture visitor</title>"
    expected_manifest = create_manifest(
        files={"index.html": entrance},
        bundle_id=manager.bundle_id,
        character_revision=scene.character_revision,
        pages=pages_target("https://fixture.github.io/project/", gateway.pages_origin),
        gateway_origin=gateway.gateway_origin,
        pages_origin=gateway.pages_origin,
    )
    manifest_content = canonical_json_bytes(expected_manifest) + b"\n"
    monkeypatch.setattr(
        pages_module,
        "build_site_files",
        lambda **_kwargs: ({"index.html": entrance}, expected_manifest),
    )
    web_dist = tmp_path / "web"
    web_dist.mkdir()
    yield service, database, entrance, manifest_content, expected_manifest, web_dist


def _response_for(
    url: str,
    entrance: bytes,
    manifest: bytes,
    *,
    entrance_status: int = 200,
    entrance_type: str = "text/html; charset=utf-8",
    manifest_status: int = 200,
    manifest_type: str = "application/json",
    manifest_body: bytes | None = None,
    entrance_body: bytes | None = None,
) -> ProviderHttpResponse:
    if url == "https://fixture.github.io/project/":
        return ProviderHttpResponse(
            status=entrance_status,
            headers={"content-type": entrance_type},
            body=entrance if entrance_body is None else entrance_body,
        )
    if url == "https://fixture.github.io/project/export-manifest.json":
        return ProviderHttpResponse(
            status=manifest_status,
            headers={"content-type": manifest_type},
            body=manifest if manifest_body is None else manifest_body,
        )
    raise AssertionError(f"unexpected Pages URL: {url}")


def _verify_success(service, web_dist, entrance, manifest, monkeypatch) -> dict[str, object]:
    monkeypatch.setattr(
        pages_module,
        "fetch_pages_resource",
        lambda url, **_kwargs: _response_for(url, entrance, manifest),
    )
    return service.verify(web_dist=web_dist)


def test_verification_rebuilds_manifest_and_records_only_verified_fields(
    configured_service, monkeypatch
) -> None:
    service, database, entrance, manifest, expected, web_dist = configured_service
    state = _verify_success(service, web_dist, entrance, manifest, monkeypatch)

    assert state["verified"] is True
    assert state["verified_content_sha256"] == expected["content_sha256"]
    with database.connection() as connection:
        row = connection.execute("SELECT * FROM pages_sharing_state").fetchone()
    assert set(row.keys()) == {
        "singleton_id",
        "pages_url",
        "verified_pages_url",
        "verified_content_sha256",
        "verified_at",
    }
    assert row["verified_pages_url"] == row["pages_url"]


@pytest.mark.parametrize("source", ["bundle", "character", "faq", "gateway"])
def test_local_changes_preserve_last_successful_verification(
    configured_service, monkeypatch, source
) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    verified = _verify_success(service, web_dist, entrance, manifest, monkeypatch)
    if source == "bundle":
        service.manager.bundle_id = "changed-bundle"
    elif source == "character":
        service.scene_service.character_revision += 1
    elif source == "faq":
        service.faq.content = "Changed approved answer"
    else:
        monkeypatch.setattr(_Gateway, "gateway_origin", "https://changed.ts.net")
    assert service.state() == verified


def test_saving_same_normalized_pages_url_preserves_verification(
    configured_service, monkeypatch
) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    verified = _verify_success(service, web_dist, entrance, manifest, monkeypatch)
    assert service.configure_pages(pages_url=str(verified["pages_url"]).rstrip("/")) == verified


def test_semantically_equal_manifest_with_different_bytes_fails_verification(
    configured_service, monkeypatch
) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    _verify_success(service, web_dist, entrance, manifest, monkeypatch)
    monkeypatch.setattr(
        pages_module,
        "fetch_pages_resource",
        lambda url, **_kwargs: _response_for(
            url, entrance, manifest, manifest_body=manifest.rstrip(b"\n")
        ),
    )
    with pytest.raises(pages_module.SiteExportError) as failure:
        service.verify(web_dist=web_dist)
    assert failure.value.code == "SHARING_VERIFICATION_FAILED"
    assert service.state()["verified"] is False


def test_manifest_or_entrance_mismatch_clears_verification(configured_service, monkeypatch) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    _verify_success(service, web_dist, entrance, manifest, monkeypatch)
    monkeypatch.setattr(
        pages_module,
        "fetch_pages_resource",
        lambda url, **_kwargs: _response_for(url, entrance, manifest, manifest_body=b"{}"),
    )
    with pytest.raises(pages_module.SiteExportError) as failure:
        service.verify(web_dist=web_dist)
    assert failure.value.code == "SHARING_VERIFICATION_FAILED"
    assert service.state()["verified"] is False


def test_pages_url_change_clears_verification(configured_service, monkeypatch) -> None:
    service, database, entrance, manifest, _expected, web_dist = configured_service
    _verify_success(service, web_dist, entrance, manifest, monkeypatch)
    updated = service.configure_pages(pages_url="https://fixture.github.io/other")
    assert updated == {
        "pages_url": "https://fixture.github.io/other/",
        "configured": True,
        "verified": False,
        "verified_at": None,
        "verified_content_sha256": None,
    }
    with database.connection() as connection:
        row = connection.execute(
            "SELECT verified_pages_url, verified_content_sha256, verified_at "
            "FROM pages_sharing_state"
        ).fetchone()
    assert tuple(row) == (None, None, None)


def test_pages_url_race_never_writes_verification(configured_service, monkeypatch) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    changed = False

    def fetch(url: str, **_kwargs):
        nonlocal changed
        if not changed:
            changed = True
            service.configure_pages(pages_url="https://fixture.github.io/other")
        return _response_for(url, entrance, manifest)

    monkeypatch.setattr(pages_module, "fetch_pages_resource", fetch)
    with pytest.raises(pages_module.SiteExportError) as failure:
        service.verify(web_dist=web_dist)
    assert failure.value.code == "SHARING_CONFLICT"
    assert service.state()["pages_url"] == "https://fixture.github.io/other/"
    assert service.state()["verified"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"entrance_status": 404},
        {"manifest_status": 500},
        {"entrance_type": "application/json"},
        {"manifest_type": "text/html"},
        {"entrance_body": b"wrong entrance"},
        {"manifest_body": b"{}"},
    ],
)
def test_wrong_remote_status_type_or_content_rejects_verification(
    configured_service, monkeypatch, kwargs
) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    monkeypatch.setattr(
        pages_module,
        "fetch_pages_resource",
        lambda url, **_options: _response_for(url, entrance, manifest, **kwargs),
    )
    with pytest.raises(pages_module.SiteExportError) as failure:
        service.verify(web_dist=web_dist)
    assert failure.value.code == "SHARING_VERIFICATION_FAILED"
    assert service.state()["verified"] is False


def test_oversized_entrance_is_rejected(configured_service, monkeypatch) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    oversized = entrance + b"x" * (1024 * 1024)
    monkeypatch.setattr(
        pages_module,
        "fetch_pages_resource",
        lambda url, **_kwargs: _response_for(url, entrance, manifest, entrance_body=oversized),
    )
    with pytest.raises(pages_module.SiteExportError):
        service.verify(web_dist=web_dist)
    assert service.state()["verified"] is False


def test_transport_failure_clears_verification(configured_service, monkeypatch) -> None:
    service, _database, entrance, manifest, _expected, web_dist = configured_service
    _verify_success(service, web_dist, entrance, manifest, monkeypatch)

    def unavailable(*_args, **_kwargs):
        raise pages_module.SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")

    monkeypatch.setattr(pages_module, "fetch_pages_resource", unavailable)
    with pytest.raises(pages_module.SiteExportError) as failure:
        service.verify(web_dist=web_dist)
    assert failure.value.code == "SHARING_VERIFICATION_UNAVAILABLE"
    assert service.state()["verified"] is False
