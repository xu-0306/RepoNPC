"""Pinned built-in embedding files and bounded local integrity verification.

This module performs no download, discovers no alternate model and grants no
owner-controlled URL capability. Callers supply a private installation directory.
"""

from __future__ import annotations

import stat
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from reponpc.indexing.sources import EmbeddingIdentity

_HASH_CHUNK_BYTES = 1024 * 1024


class BuiltinArtifactError(RuntimeError):
    """Internal integrity failure that reveals no model path or file content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("built-in embedding artifacts are unavailable")


class BuiltinArtifactFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")]
    bytes: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class BuiltinEmbeddingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    model_id: Literal["BAAI/bge-m3"]
    revision: Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
    license: Literal["MIT"]
    dimension: Literal[1024]
    context_tokens: Literal[8192]
    files: Annotated[tuple[BuiltinArtifactFile, ...], Field(min_length=1, max_length=32)]

    @model_validator(mode="before")
    @classmethod
    def validate_numeric_fields(cls, value: object) -> object:
        if isinstance(value, dict) and any(
            type(value.get(name)) is not int
            for name in ("schema_version", "dimension", "context_tokens")
        ):
            raise ValueError("manifest numeric fields must be integers")
        return value

    @model_validator(mode="after")
    def validate_files(self) -> BuiltinEmbeddingManifest:
        names = [entry.name for entry in self.files]
        if len(names) != len(set(names)) or any(name in {".", ".."} for name in names):
            raise ValueError("artifact names must be unique plain filenames")
        return self

    @property
    def total_bytes(self) -> int:
        return sum(entry.bytes for entry in self.files)

    @property
    def source_url(self) -> str:
        return f"https://huggingface.co/{self.model_id}/tree/{self.revision}/onnx"


def load_builtin_manifest() -> BuiltinEmbeddingManifest:
    """Load only the pinned application resource, without external I/O."""

    try:
        raw = (
            files("reponpc.providers")
            .joinpath("builtin_embedding_manifest.yml")
            .read_text(encoding="utf-8")
        )
        return BuiltinEmbeddingManifest.model_validate(yaml.safe_load(raw))
    except OSError, UnicodeError, yaml.YAMLError, ValidationError:
        raise BuiltinArtifactError("builtin_manifest_invalid") from None


def builtin_embedding_identity() -> EmbeddingIdentity:
    """Include the exact revision in the existing bundle model identity field."""

    manifest = load_builtin_manifest()
    return EmbeddingIdentity(
        "builtin_onnx", f"{manifest.model_id}:{manifest.revision}", manifest.dimension, True, "", ""
    )


def verify_builtin_artifacts(root: Path, manifest: BuiltinEmbeddingManifest | None = None) -> Path:
    """Verify every pinned regular file before any tokenizer/session loads it.

    The optional manifest is an internal test seam, not public configuration.
    Verification streams the large external weights in bounded chunks. Nothing
    is created, deleted, downloaded, repaired or selected on a failure.
    """

    expected = manifest or load_builtin_manifest()
    try:
        # Do not follow a supplied model-root symlink or Windows junction.
        if root.is_symlink() or root.is_junction() or not root.is_dir():
            raise BuiltinArtifactError("builtin_artifacts_missing")
        directory = root.resolve(strict=True)
        for entry in expected.files:
            candidate = directory / entry.name
            if candidate.is_symlink() or candidate.is_junction():
                raise BuiltinArtifactError("builtin_artifact_invalid")
            before = candidate.stat(follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode) or before.st_size != entry.bytes:
                raise BuiltinArtifactError("builtin_artifact_invalid")
            digest = sha256()
            remaining = entry.bytes
            with candidate.open("rb") as stream:
                while remaining:
                    chunk = stream.read(min(remaining, _HASH_CHUNK_BYTES))
                    if not chunk:
                        raise BuiltinArtifactError("builtin_artifact_invalid")
                    remaining -= len(chunk)
                    digest.update(chunk)
                if stream.read(1):
                    raise BuiltinArtifactError("builtin_artifact_invalid")
            after = candidate.stat(follow_symlinks=False)
            if (
                digest.hexdigest() != entry.sha256
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ino != after.st_ino
            ):
                raise BuiltinArtifactError("builtin_artifact_invalid")
        return directory
    except BuiltinArtifactError:
        raise
    except OSError, ValueError:
        raise BuiltinArtifactError("builtin_artifacts_missing") from None
