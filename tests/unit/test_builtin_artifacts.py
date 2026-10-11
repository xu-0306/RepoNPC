"""Pinned embedding integrity checks have no download or repair side effects."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from reponpc.providers.builtin_artifacts import (
    BuiltinArtifactError,
    BuiltinArtifactFile,
    BuiltinEmbeddingManifest,
    builtin_embedding_identity,
    load_builtin_manifest,
    verify_builtin_artifacts,
)


def _manifest(name: str = "weights.bin", content: bytes = b"fixture") -> BuiltinEmbeddingManifest:
    return load_builtin_manifest().model_copy(
        update={
            "files": (
                BuiltinArtifactFile(
                    name=name, bytes=len(content), sha256=sha256(content).hexdigest()
                ),
            )
        }
    )


def test_pinned_manifest_matches_owner_contract_and_exact_identity() -> None:
    manifest = load_builtin_manifest()
    identity = builtin_embedding_identity()
    assert manifest.revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert len(manifest.files) == 8
    assert manifest.total_bytes == 2_289_765_790
    assert identity.adapter == "builtin_onnx"
    assert identity.model_id == f"BAAI/bge-m3:{manifest.revision}"
    assert identity.dimension == 1024 and identity.normalized
    assert identity.query_prefix == identity.passage_prefix == ""
    assert manifest.source_url.endswith(f"/{manifest.revision}/onnx")


def test_verified_files_are_read_only_and_extra_files_are_not_consumed(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "weights.bin").write_bytes(b"fixture")
    (root / "unrelated.txt").write_bytes(b"leave alone")
    original = {p.name: p.read_bytes() for p in root.iterdir()}
    assert verify_builtin_artifacts(root, _manifest()) == root.resolve()
    assert {p.name: p.read_bytes() for p in root.iterdir()} == original


@pytest.mark.parametrize("content", [b"fixturE", b"short", b"fixture-extra"])
def test_wrong_hash_or_size_fails_without_repair(tmp_path: Path, content: bytes) -> None:
    target = tmp_path / "weights.bin"
    target.write_bytes(content)
    with pytest.raises(BuiltinArtifactError) as failure:
        verify_builtin_artifacts(tmp_path, _manifest())
    assert failure.value.code == "builtin_artifact_invalid"
    assert str(tmp_path) not in str(failure.value)
    assert target.read_bytes() == content


def test_missing_artifacts_do_not_create_directory_or_download(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    with pytest.raises(BuiltinArtifactError):
        verify_builtin_artifacts(root, _manifest())
    assert not root.exists()
    with pytest.raises(BuiltinArtifactError):
        verify_builtin_artifacts(tmp_path, _manifest())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["../weights", "a/b", "a\\b", "/absolute", "C:drive", ".", ".."])
def test_manifest_rejects_path_aliases(name: str) -> None:
    with pytest.raises((ValidationError, ValueError)):
        values = load_builtin_manifest().model_dump()
        values["files"] = [{"name": name, "bytes": 7, "sha256": sha256(b"fixture").hexdigest()}]
        type(load_builtin_manifest()).model_validate(values)


def test_manifest_rejects_duplicate_unknown_fields_and_boolean_sizes() -> None:
    values = load_builtin_manifest().model_dump()
    values["files"] = [values["files"][0], values["files"][0]]
    with pytest.raises(ValidationError):
        type(load_builtin_manifest()).model_validate(values)
    with pytest.raises(ValidationError):
        BuiltinArtifactFile(name="file", bytes=True, sha256="a" * 64)
    values = load_builtin_manifest().model_dump()
    values["download_url"] = "https://alternate.example.test/model"
    with pytest.raises(ValidationError):
        type(load_builtin_manifest()).model_validate(values)


def test_symlink_is_not_a_verified_model_file(tmp_path: Path) -> None:
    source = tmp_path / "outside"
    source.write_bytes(b"fixture")
    root = tmp_path / "model"
    root.mkdir()
    try:
        (root / "weights.bin").symlink_to(source)
    except OSError:
        pytest.skip("host does not permit creating symlinks")
    with pytest.raises(BuiltinArtifactError):
        verify_builtin_artifacts(root, _manifest())
    assert source.read_bytes() == b"fixture"
