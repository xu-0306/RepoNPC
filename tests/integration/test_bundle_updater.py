"""ETag polling and candidate failure behavior through the real updater."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

import reponpc.bundles.updater as updater_module
from reponpc.bundles.manager import BundleManager
from reponpc.bundles.manifest import StableManifest
from reponpc.bundles.updater import (
    BundleUpdateError,
    BundleUpdater,
    DownloadResult,
    HttpResponse,
    UrllibBundleTransport,
)
from reponpc.runtime.database import RuntimeDatabase
from tests.integration.test_bundle_producer_consumer import _bundle


class FixtureTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, Mapping[str, str]]] = []

    def get(self, url: str, *, headers: Mapping[str, str], max_bytes: int) -> HttpResponse:
        self.calls.append((url, headers))
        response = self._responses.pop(0)
        assert len(response.body) <= max_bytes
        return response

    def download_to(
        self, url: str, *, headers: Mapping[str, str], destination: Path, max_bytes: int
    ) -> DownloadResult:
        self.calls.append((url, headers))
        response = self._responses.pop(0)
        if response.status != 200:
            return DownloadResult(response.status, response.headers, 0, "")
        digest = hashlib.sha256()
        with destination.open("xb") as target:
            for offset in range(0, len(response.body), 64 * 1024):
                chunk = response.body[offset : offset + 64 * 1024]
                if target.tell() + len(chunk) > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise RuntimeError("fixture size overflow")
                target.write(chunk)
                digest.update(chunk)
        return DownloadResult(200, response.headers, len(response.body), digest.hexdigest())


def test_production_download_collision_preserves_existing_destination(tmp_path: Path) -> None:
    destination = tmp_path / "existing.tar.zst"
    destination.write_bytes(b"do-not-overwrite")
    transport = UrllibBundleTransport(allowed_hosts=frozenset({"example.test"}))
    with pytest.raises(BundleUpdateError) as error:
        transport.download_to(
            "https://example.test/bundle",
            headers={},
            destination=destination,
            max_bytes=1,
        )
    assert destination.read_bytes() == b"do-not-overwrite"
    assert error.value.code == "bundle_request_failed"


class _Response:
    def __init__(self, body: bytes, *, url: str = "https://example.test/final") -> None:
        self._body = body
        self._url = url
        self.status = 200
        self.headers = {"X-Fixture": "yes"}
        self.read_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        value, self._body = self._body[:size], self._body[size:]
        return value

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.request = request
        self.timeout = timeout
        return self.response


def test_production_download_streams_64k_chunks_and_hashes(tmp_path: Path, monkeypatch) -> None:
    payload = b"a" * (64 * 1024 + 1)
    response = _Response(payload)
    opener = _Opener(response)
    monkeypatch.setattr(updater_module, "build_opener", lambda *_: opener)
    target = tmp_path / "bundle"
    result = UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
        "https://example.test/b",
        headers={"X-Test": "yes"},
        destination=target,
        max_bytes=len(payload),
    )
    assert target.read_bytes() == payload
    assert (result.size_bytes, result.sha256, dict(result.headers)) == (
        len(payload),
        hashlib.sha256(payload).hexdigest(),
        {"X-Fixture": "yes"},
    )
    assert response.read_sizes == [64 * 1024, 64 * 1024, 64 * 1024]
    assert opener.timeout == 15.0
    assert opener.request.get_header("X-test") == "yes"


def test_production_download_overrun_removes_partial_destination(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        updater_module, "build_opener", lambda *_: _Opener(_Response(b"a" * (64 * 1024 + 1)))
    )
    target = tmp_path / "partial"
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=64 * 1024
        )
    assert not target.exists()
    assert error.value.code == "bundle_download_too_large"


def test_no_redirect_rejects_unsafe_hop() -> None:
    with pytest.raises(BundleUpdateError) as error:
        updater_module._NoRedirect({"example.test"}).redirect_request(
            None, None, 302, "", None, "https://evil.test/x"
        )  # type: ignore[arg-type]
    assert error.value.code == "bundle_host_not_allowed"


def test_production_download_rejects_unsafe_final_url_and_cleans(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        updater_module,
        "build_opener",
        lambda *_: _Opener(_Response(b"x", url="https://evil.test/x")),
    )
    target = tmp_path / "partial"
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=2
        )
    assert not target.exists()
    assert error.value.code == "bundle_host_not_allowed"


def test_production_download_rejects_boolean_or_zero_bound_without_destination(
    tmp_path: Path,
) -> None:
    transport = UrllibBundleTransport(allowed_hosts=frozenset({"example.test"}))
    for maximum in (True, 0):
        destination = tmp_path / str(maximum)
        with pytest.raises(ValueError):
            transport.download_to(
                "https://example.test/bundle",
                headers={},
                destination=destination,
                max_bytes=maximum,
            )
        assert not destination.exists()


def test_production_download_opener_failure_cleans_destination(tmp_path: Path, monkeypatch) -> None:
    from urllib.error import URLError

    class FailingOpener:
        def open(self, request: object, timeout: float) -> object:
            raise URLError("offline")

    monkeypatch.setattr(updater_module, "build_opener", lambda *_: FailingOpener())
    target = tmp_path / "partial"
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=2
        )
    assert error.value.code == "bundle_request_failed"
    assert not target.exists()


def test_production_manifest_request_failure_is_safe(tmp_path: Path, monkeypatch) -> None:
    from urllib.error import URLError

    private_canary = "CANARY private manifest path and URL"

    class FailingOpener:
        def open(self, request: object, timeout: float) -> object:
            raise URLError(private_canary)

    monkeypatch.setattr(updater_module, "build_opener", lambda *_: FailingOpener())
    _, runtime, manager, updater = _updater(
        tmp_path,
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})),
    )

    assert updater.poll_once() == "rejected"
    state = runtime.bundle_state()
    assert state.safe_update_error == "bundle_request_failed"
    assert private_canary not in state.safe_update_error
    assert manager.status().active_bundle_id is None


def test_production_download_read_failure_cleans_partial_destination(
    tmp_path: Path, monkeypatch
) -> None:
    from urllib.error import URLError

    class FailingResponse(_Response):
        def read(self, size: int) -> bytes:
            if self.read_sizes:
                raise URLError("read failure")
            return super().read(size)

    monkeypatch.setattr(updater_module, "build_opener", lambda *_: _Opener(FailingResponse(b"xx")))
    target = tmp_path / "partial"
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=3
        )
    assert error.value.code == "bundle_request_failed"
    assert not target.exists()


def test_production_download_non_success_cleans_destination(tmp_path: Path, monkeypatch) -> None:
    response = _Response(b"")
    response.status = 503
    monkeypatch.setattr(updater_module, "build_opener", lambda *_: _Opener(response))
    target = tmp_path / "partial"
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=2
        )
    assert error.value.code == "bundle_download_invalid"
    assert not target.exists()


def test_production_download_write_failure_cleans_partial_destination(
    tmp_path: Path, monkeypatch
) -> None:
    response = _Response(b"x")
    monkeypatch.setattr(updater_module, "build_opener", lambda *_: _Opener(response))
    target = tmp_path / "partial"
    real_open = Path.open

    class FailingWriter:
        def __init__(self, handle) -> None:  # type: ignore[no-untyped-def]
            self._handle = handle

        def __enter__(self):  # type: ignore[no-untyped-def]
            self._handle.__enter__()
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return self._handle.__exit__(*args)

        def write(self, value: bytes) -> int:
            raise OSError("write failure")

    def open_destination(path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        handle = real_open(path, *args, **kwargs)
        return FailingWriter(handle) if path == target else handle

    monkeypatch.setattr(Path, "open", open_destination)
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=2
        )
    assert error.value.code == "bundle_request_failed"
    assert not target.exists()


def test_production_download_cleanup_failure_is_safe(tmp_path: Path, monkeypatch) -> None:
    response = _Response(b"xx")
    monkeypatch.setattr(updater_module, "build_opener", lambda *_: _Opener(response))
    target = tmp_path / "partial"
    real_unlink = Path.unlink

    def fail_target_unlink(path: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if path == target:
            raise OSError("CANARY-C:/private/partial")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_target_unlink)
    with pytest.raises(BundleUpdateError) as error:
        UrllibBundleTransport(allowed_hosts=frozenset({"example.test"})).download_to(
            "https://example.test/b", headers={}, destination=target, max_bytes=1
        )
    assert error.value.code == "bundle_staging_cleanup_failed"
    assert str(error.value) == "bundle update failed"
    assert "CANARY" not in str(error.value)
    assert str(target) not in str(error.value)


def _updater(tmp_path: Path, transport: FixtureTransport):
    bundle, provider = _bundle(tmp_path / "bundle")
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    updater = BundleUpdater(
        manifest_url="https://example.test/stable-manifest.json",
        transport=transport,
        manager=manager,
        runtime_database=runtime,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
        allowed_hosts=frozenset({"example.test"}),
        data_directory=tmp_path / "data",
    )
    return bundle, runtime, manager, updater


def test_etag_poll_activates_once_then_304_does_not_download_again(tmp_path: Path) -> None:
    seed_bundle, provider = _bundle(tmp_path / "seed")
    stable = StableManifest(
        bundle_id=seed_bundle.manifest.bundle_id,
        release_tag="index-fixture",
        asset_url="https://example.test/reponpc-index.tar.zst",
        asset_size=seed_bundle.archive_size,
        asset_sha256=seed_bundle.archive_sha256,
        published_at="2026-08-10T12:01:00Z",
    )
    transport = FixtureTransport(
        [
            HttpResponse(200, {"ETag": '"v1"'}, stable.canonical_bytes()),
            HttpResponse(200, {}, seed_bundle.archive_path.read_bytes()),
            HttpResponse(304, {}, b""),
        ]
    )
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    updater = BundleUpdater(
        manifest_url="https://example.test/stable-manifest.json",
        transport=transport,
        manager=manager,
        runtime_database=runtime,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
        allowed_hosts=frozenset({"example.test"}),
        data_directory=tmp_path / "data",
    )

    assert updater.poll_once() == "activated"
    active = manager.status().active_bundle_id
    assert active == stable.bundle_id
    assert updater.poll_once() == "not_modified"
    assert manager.status().active_bundle_id == active
    assert transport.calls[2][1]["If-None-Match"] == '"v1"'


def test_untrusted_asset_url_is_rejected_without_replacing_active_bundle(tmp_path: Path) -> None:
    bundle, provider = _bundle(tmp_path / "bundle")
    invalid = StableManifest(
        bundle_id=bundle.manifest.bundle_id,
        release_tag="index-fixture",
        asset_url="https://untrusted.example/reponpc-index.tar.zst",
        asset_size=bundle.archive_size,
        asset_sha256=bundle.archive_sha256,
        published_at="2026-08-10T12:01:00Z",
    )
    transport = FixtureTransport([HttpResponse(200, {"ETag": '"bad"'}, invalid.canonical_bytes())])
    runtime = RuntimeDatabase(tmp_path / "runtime")
    runtime.initialize()
    manager = BundleManager(
        data_directory=tmp_path / "data",
        runtime_database=runtime,
        expected_embedding=provider.identity(),
    )
    updater = BundleUpdater(
        manifest_url="https://example.test/stable-manifest.json",
        transport=transport,
        manager=manager,
        runtime_database=runtime,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
        allowed_hosts=frozenset({"example.test"}),
        data_directory=tmp_path / "data",
    )

    assert updater.poll_once() == "rejected"
    assert manager.status().active_bundle_id is None


def test_manifest_size_mismatch_cleans_streamed_candidate(tmp_path: Path) -> None:
    bundle, runtime, manager, updater = _updater(tmp_path, FixtureTransport([]))
    stable = StableManifest(
        bundle.manifest.bundle_id,
        "index-fixture",
        "https://example.test/a",
        bundle.archive_size + 1,
        bundle.archive_sha256,
        "2026-08-10T12:01:00Z",
    )
    updater._transport = FixtureTransport(
        [
            HttpResponse(200, {}, stable.canonical_bytes()),
            HttpResponse(200, {}, bundle.archive_path.read_bytes()),
        ]
    )
    assert updater.poll_once() == "rejected"
    assert manager.status().active_bundle_id is None
    assert runtime.bundle_state().safe_update_error == "bundle_download_invalid"
    assert not list(updater._staging_root.iterdir())


def test_manifest_hash_mismatch_cleans_streamed_candidate(tmp_path: Path) -> None:
    bundle, runtime, manager, updater = _updater(tmp_path, FixtureTransport([]))
    stable = StableManifest(
        bundle.manifest.bundle_id,
        "index-fixture",
        "https://example.test/a",
        bundle.archive_size,
        "0" * 64,
        "2026-08-10T12:01:00Z",
    )
    updater._transport = FixtureTransport(
        [
            HttpResponse(200, {}, stable.canonical_bytes()),
            HttpResponse(200, {}, bundle.archive_path.read_bytes()),
        ]
    )
    assert updater.poll_once() == "rejected"
    assert manager.status().active_bundle_id is None
    assert runtime.bundle_state().safe_update_error == "bundle_outer_checksum_invalid"
    assert not list(updater._staging_root.iterdir())


def test_verified_bundle_id_mismatch_closes_and_removes_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    bundle, runtime, manager, updater = _updater(tmp_path, FixtureTransport([]))
    stable = StableManifest(
        bundle.manifest.bundle_id,
        "index-fixture",
        "https://example.test/a",
        bundle.archive_size,
        bundle.archive_sha256,
        "2026-08-10T12:01:00Z",
    )
    updater._transport = FixtureTransport(
        [
            HttpResponse(200, {}, stable.canonical_bytes()),
            HttpResponse(200, {}, bundle.archive_path.read_bytes()),
        ]
    )
    directory = updater._staging_root / "verified-mismatch"
    directory.mkdir()
    (directory / "marker").write_text("x")

    class Candidate:
        def __init__(self) -> None:
            self.directory = directory
            self.manifest = type("Manifest", (), {"bundle_id": "different"})()
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    candidate = Candidate()
    monkeypatch.setattr(updater_module, "verify_bundle_archive", lambda **_: candidate)
    assert updater.poll_once() == "rejected"
    assert runtime.bundle_state().safe_update_error == "stable_bundle_id_mismatch"
    assert manager.status().active_bundle_id is None
    assert candidate.closed == 1
    assert not directory.exists()
    assert not list(updater._staging_root.iterdir())
