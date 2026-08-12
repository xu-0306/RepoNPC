"""Adversarial archive and index checks for the immutable bundle boundary."""

from __future__ import annotations

import hashlib
import io
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.bundles.archive import BundleError, build_bundle, verify_bundle_archive
from reponpc.bundles.manifest import bundle_id_for
from tests.integration.test_bundle_producer_consumer import _bundle, _public_files
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _build,
    _configuration_source,
    _fixture_snapshot,
)


def _verify_rejected(archive_path: Path, staging: Path) -> BundleError:
    with pytest.raises(BundleError) as error:
        verify_bundle_archive(
            archive_path=archive_path,
            staging_directory=staging,
            expected_outer_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            expected_embedding=DeterministicEmbeddingProvider().identity(),
            max_bundle_bytes=1024 * 1024,
        )
    assert not staging.exists()
    assert "D:" not in str(error.value)
    assert "runtime.sqlite" not in str(error.value)
    return error.value


@pytest.mark.parametrize(
    ("name", "member_type"),
    (
        ("/absolute.sqlite", tarfile.REGTYPE),
        ("../runtime.sqlite", tarfile.REGTYPE),
        ("C:/outside.sqlite", tarfile.REGTYPE),
        ("C:outside.sqlite", tarfile.REGTYPE),
        ("link", tarfile.SYMTYPE),
        ("hard-link", tarfile.LNKTYPE),
        ("device", tarfile.CHRTYPE),
    ),
)
def test_unsafe_archive_members_are_rejected_before_staging(
    tmp_path: Path,
    name: str,
    member_type: bytes,
) -> None:
    archive_path = tmp_path / "unsafe.tar.zst"
    with tarfile.open(archive_path, "w:zst") as archive:
        member = tarfile.TarInfo(name)
        member.type = member_type
        member.size = 1 if member_type == tarfile.REGTYPE else 0
        if member_type in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
            member.linkname = "index.sqlite"
        archive.addfile(member, io.BytesIO(b"x") if member.size else None)

    error = _verify_rejected(archive_path, tmp_path / "unsafe-stage")
    assert error.code == "bundle_member_unsafe"


def test_duplicate_and_excessive_archive_members_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.tar.zst"
    with tarfile.open(duplicate, "w:zst") as archive:
        for _ in range(2):
            member = tarfile.TarInfo("manifest.json")
            member.size = 2
            archive.addfile(member, io.BytesIO(b"{}"))
    duplicate_error = _verify_rejected(duplicate, tmp_path / "duplicate-stage")
    assert duplicate_error.code == "bundle_member_count_invalid"

    excessive = tmp_path / "excessive.tar.zst"
    with tarfile.open(excessive, "w:zst") as archive:
        for index in range(65):
            member = tarfile.TarInfo(f"member-{index}")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
    excessive_error = _verify_rejected(excessive, tmp_path / "excessive-stage")
    assert excessive_error.code == "bundle_member_count_invalid"


def test_corrupt_sqlite_with_matching_internal_checksums_is_a_safe_bundle_rejection(
    tmp_path: Path,
) -> None:
    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
    index_result.database_path.write_bytes(b"this is not a sqlite database")
    configuration = _configuration_source()
    repository = _fixture_snapshot()
    built_at = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    bundle_id = bundle_id_for(
        built_at=built_at,
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=configuration,
        repositories=(repository,),
        bundle_id=bundle_id,
        built_at=built_at,
        public_files=_public_files(
            bundle_id=bundle_id,
            built_at=built_at,
            repository_count=index_result.repository_count,
        ),
        output_path=tmp_path / f"reponpc-index-{bundle_id}.tar.zst",
    )

    error = _verify_rejected(bundle.archive_path, tmp_path / "corrupt-stage")
    assert error.code == "bundle_index_invalid"


def test_outer_and_embedding_failures_remain_safe_and_leave_no_candidate(tmp_path: Path) -> None:
    bundle, provider = _bundle(tmp_path)
    with pytest.raises(BundleError) as outer_error:
        verify_bundle_archive(
            archive_path=bundle.archive_path,
            staging_directory=tmp_path / "outer-stage",
            expected_outer_sha256="0" * 64,
            expected_embedding=provider.identity(),
            max_bundle_bytes=1024 * 1024,
        )
    assert outer_error.value.code == "bundle_outer_checksum_invalid"
    assert not (tmp_path / "outer-stage").exists()

    wrong_identity = DeterministicEmbeddingProvider(dimension=383).identity()
    with pytest.raises(BundleError) as embedding_error:
        verify_bundle_archive(
            archive_path=bundle.archive_path,
            staging_directory=tmp_path / "embedding-stage",
            expected_outer_sha256=bundle.archive_sha256,
            expected_embedding=wrong_identity,
            max_bundle_bytes=1024 * 1024,
        )
    assert embedding_error.value.code == "bundle_embedding_incompatible"
    assert not (tmp_path / "embedding-stage").exists()
