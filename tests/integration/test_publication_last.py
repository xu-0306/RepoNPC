"""Publication order against a mutation-recording GitHub Release boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.indexing.publication import PublicationCoordinator, PublicationError
from tests.integration.test_bundle_producer_consumer import _bundle


class RecordingPublisher:
    def __init__(self, *, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.events: list[str] = []
        self.stable_content: bytes | None = b'{"prior":"stable"}'

    def create_immutable_release(self, *, tag: str, name: str) -> int:
        self.events.append("release")
        self._fail("release")
        return 1

    def upload_immutable_asset(self, *, release_id: int, name: str, content: bytes) -> str:
        self.events.append("upload")
        self._fail("upload")
        assert release_id == 1
        assert name.endswith(".tar.zst")
        assert content
        return "https://github.com/fixture-owner/demo/releases/download/index/asset.tar.zst"

    def verify_asset(self, *, asset_url: str, size: int, sha256: str) -> None:
        self.events.append("verify")
        self._fail("verify")
        assert asset_url.startswith("https://github.com/")
        assert size > 0
        assert len(sha256) == 64

    def update_stable_manifest_last(self, *, content: bytes) -> None:
        self.events.append("stable")
        self._fail("stable")
        self.stable_content = content

    def _fail(self, stage: str) -> None:
        if self.fail_at == stage:
            raise OSError(stage)


def test_publication_advances_stable_manifest_only_after_verified_immutable_asset(
    tmp_path: Path,
) -> None:
    bundle, _ = _bundle(tmp_path)
    publisher = RecordingPublisher()
    coordinator = PublicationCoordinator(publisher)
    result = coordinator.publish_immutable(
        bundle,
        now=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )

    assert publisher.events == ["release", "upload", "verify"]
    assert publisher.stable_content == b'{"prior":"stable"}'

    coordinator.publish_manifest(result.stable_manifest)

    assert publisher.events == ["release", "upload", "verify", "verify", "stable"]
    assert publisher.stable_content == result.stable_manifest.canonical_bytes()


@pytest.mark.parametrize("failure", ["release", "upload", "verify"])
def test_failed_preceding_stage_preserves_prior_stable_manifest(
    tmp_path: Path, failure: str
) -> None:
    bundle, _ = _bundle(tmp_path)
    publisher = RecordingPublisher(fail_at=failure)
    prior = publisher.stable_content

    with pytest.raises(PublicationError) as error:
        PublicationCoordinator(publisher).publish_immutable(
            bundle,
            now=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        )
    assert error.value.code == "bundle_publication_failed"
    assert publisher.stable_content == prior
    assert "stable" not in publisher.events


def test_manifest_step_reverifies_pending_asset_before_pointer_mutation(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    publisher = RecordingPublisher()
    coordinator = PublicationCoordinator(publisher)
    pending = coordinator.publish_immutable(
        bundle,
        now=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    ).stable_manifest
    publisher.fail_at = "verify"

    with pytest.raises(PublicationError):
        coordinator.publish_manifest(pending)

    assert publisher.events == ["release", "upload", "verify", "verify"]
    assert publisher.stable_content == b'{"prior":"stable"}'
