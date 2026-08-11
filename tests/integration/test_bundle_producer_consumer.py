"""Real immutable builder-to-verifier bundle boundary checks."""

from __future__ import annotations

import hashlib
import io
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reponpc.bundles.archive import BundleError, build_bundle, verify_bundle_archive
from reponpc.bundles.manifest import bundle_id_for
from tests.integration.test_index_build import (
    DeterministicEmbeddingProvider,
    _build,
    _configuration_source,
    _fixture_snapshot,
)


def _public_files() -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "public/profile.json": b'{"schema_version":1}',
        "public/character.png": b"\x89PNG\r\n\x1a\nfixture",
    }
    for theme in ("light", "dark"):
        for locale in ("zh-TW", "en"):
            files[f"public/card-{theme}-{locale}.svg"] = (
                b"<svg xmlns='http://www.w3.org/2000/svg'/>"
            )
            files[f"public/card-{theme}-{locale}.gif"] = b"GIF89a"
            files[f"public/card-{theme}-{locale}.png"] = b"\x89PNG\r\n\x1a\nfixture"
    return files


def _bundle(tmp_path: Path):
    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
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
        public_files=_public_files(),
        output_path=tmp_path / f"reponpc-index-{bundle_id}.tar.zst",
    )
    return bundle, provider


def test_production_bundle_bytes_are_accepted_by_the_real_read_only_consumer(
    tmp_path: Path,
) -> None:
    bundle, provider = _bundle(tmp_path)
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=tmp_path / "stage",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    try:
        assert verified.manifest.bundle_id == bundle.manifest.bundle_id
        assert verified.index.lexical_candidates("hybrid retrieval", limit=8)
        assert verified.index.hybrid_candidates(
            "hybrid retrieval",
            query_vector=verified.index.vectors.values[0],
            lexical_limit=8,
            vector_limit=8,
            final_limit=8,
        )
    finally:
        verified.close()


def test_build_streams_index_and_completed_archive_without_read_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
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
    output_path = tmp_path / f"reponpc-index-{bundle_id}.tar.zst"
    original_read_bytes = Path.read_bytes

    def reject_index_or_archive_read(path: Path) -> bytes:
        if path in {index_result.database_path, output_path}:
            raise AssertionError("large bundle files must be streamed")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_index_or_archive_read)
    bundle = build_bundle(
        index_result=index_result,
        configuration_source=configuration,
        repositories=(repository,),
        bundle_id=bundle_id,
        built_at=built_at,
        public_files=_public_files(),
        output_path=output_path,
    )
    verified = verify_bundle_archive(
        archive_path=bundle.archive_path,
        staging_directory=tmp_path / "stage",
        expected_outer_sha256=bundle.archive_sha256,
        expected_embedding=provider.identity(),
        max_bundle_bytes=1024 * 1024,
    )
    verified.close()


@pytest.mark.parametrize(
    "invalid_input",
    ["missing_index", "empty_index", "missing_public", "unexpected_public", "empty_public"],
)
def test_invalid_build_payloads_leave_no_output_or_temporary_archive(
    tmp_path: Path, invalid_input: str
) -> None:
    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
    public_files = _public_files()
    if invalid_input == "missing_index":
        index_result.database_path.unlink()
    elif invalid_input == "empty_index":
        index_result.database_path.write_bytes(b"")
    elif invalid_input == "missing_public":
        public_files.pop("public/profile.json")
    elif invalid_input == "unexpected_public":
        public_files["public/unexpected.txt"] = b"unexpected"
    else:
        public_files["public/profile.json"] = b""
    configuration = _configuration_source()
    repository = _fixture_snapshot()
    bundle_id = bundle_id_for(
        built_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    output_path = tmp_path / f"reponpc-index-{bundle_id}.tar.zst"

    with pytest.raises(BundleError) as error:
        build_bundle(
            index_result=index_result,
            configuration_source=configuration,
            repositories=(repository,),
            bundle_id=bundle_id,
            built_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            public_files=public_files,
            output_path=output_path,
        )

    assert error.value.code in {"bundle_payload_invalid", "bundle_payload_layout_invalid"}
    assert not output_path.exists()
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))


def test_tar_write_failure_removes_the_generated_temporary_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = DeterministicEmbeddingProvider()
    index_result = _build(tmp_path / "index", provider=provider)
    configuration = _configuration_source()
    repository = _fixture_snapshot()
    bundle_id = bundle_id_for(
        built_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        configuration_bytes=configuration.content.encode("utf-8"),
        repositories=((repository.slug, repository.commit_sha),),
        embedding=provider.identity(),
        parser_chunker_version="p2-02-v1",
    )
    output_path = tmp_path / f"reponpc-index-{bundle_id}.tar.zst"

    def fail_addfile(*args: object, **kwargs: object) -> None:
        raise tarfile.TarError("injected tar failure")

    monkeypatch.setattr(tarfile.TarFile, "addfile", fail_addfile)
    with pytest.raises(BundleError) as error:
        build_bundle(
            index_result=index_result,
            configuration_source=configuration,
            repositories=(repository,),
            bundle_id=bundle_id,
            built_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
            public_files=_public_files(),
            output_path=output_path,
        )

    assert error.value.code == "bundle_archive_write_failed"
    assert not output_path.exists()
    assert not list(tmp_path.glob(f".{output_path.name}.*.tmp"))


def test_outer_mismatch_and_embedding_mismatch_never_leave_staging(tmp_path: Path) -> None:
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


def test_archive_traversal_is_rejected_before_any_member_is_written(tmp_path: Path) -> None:
    archive_path = tmp_path / "malicious.tar.zst"
    with tarfile.open(archive_path, "w:zst") as archive:
        member = tarfile.TarInfo("../runtime.sqlite")
        member.size = 3
        archive.addfile(member, io.BytesIO(b"bad"))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    with pytest.raises(BundleError) as error:
        verify_bundle_archive(
            archive_path=archive_path,
            staging_directory=tmp_path / "malicious-stage",
            expected_outer_sha256=digest,
            expected_embedding=DeterministicEmbeddingProvider().identity(),
            max_bundle_bytes=1024 * 1024,
        )
    assert error.value.code == "bundle_member_unsafe"
    assert not (tmp_path / "malicious-stage").exists()


def test_internal_checksum_tampering_is_rejected_even_when_outer_digest_matches(
    tmp_path: Path,
) -> None:
    bundle, provider = _bundle(tmp_path)
    tampered_path = tmp_path / "tampered.tar.zst"
    with (
        tarfile.open(bundle.archive_path, "r:zst") as source,
        tarfile.open(
            tampered_path,
            "w:zst",
        ) as destination,
    ):
        for member in source.getmembers():
            payload = source.extractfile(member)
            assert payload is not None
            content = payload.read()
            if member.name == "public/profile.json":
                content = b'{"tampered":true}'
            copied = tarfile.TarInfo(member.name)
            copied.size = len(content)
            destination.addfile(copied, io.BytesIO(content))
    outer_digest = hashlib.sha256(tampered_path.read_bytes()).hexdigest()

    with pytest.raises(BundleError) as error:
        verify_bundle_archive(
            archive_path=tampered_path,
            staging_directory=tmp_path / "tampered-stage",
            expected_outer_sha256=outer_digest,
            expected_embedding=provider.identity(),
            max_bundle_bytes=1024 * 1024,
        )
    assert error.value.code == "bundle_payload_checksum_invalid"
    assert not (tmp_path / "tampered-stage").exists()
