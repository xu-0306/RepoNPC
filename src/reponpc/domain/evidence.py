"""Immutable evidence records and stable content-addressed identifiers."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
EVIDENCE_ID_RE = re.compile(r"^E_[0-9a-f]{24}$")


class EvidenceClass(StrEnum):
    OWNER_ASSERTION = "OWNER_ASSERTION"
    REPOSITORY_FACT = "REPOSITORY_FACT"
    MODEL_INFERENCE = "MODEL_INFERENCE"


def normalize_content(content: str) -> str:
    """Normalize text for stable hashing and safe line-addressable storage."""

    return unicodedata.normalize("NFC", content.replace("\r\n", "\n").replace("\r", "\n"))


def normalize_source_path(path: str) -> str:
    if not path or "\\" in path or path.startswith("/"):
        raise ValueError("source path must be a repository-relative POSIX path")
    normalized = str(PurePosixPath(path))
    if normalized in {"", "."} or ".." in PurePosixPath(normalized).parts:
        raise ValueError("source path must not traverse parent directories")
    return normalized


def build_evidence_id(
    *,
    schema_version: int,
    evidence_class: EvidenceClass,
    repository_slug: str,
    commit_sha: str,
    path: str,
    start_line: int,
    end_line: int,
    content: str,
) -> str:
    """Build the schema-v1 ID using canonical JSON as the field delimiter."""

    normalized_content = normalize_content(content)
    content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
    canonical_fields = [
        schema_version,
        evidence_class.value,
        repository_slug,
        commit_sha,
        normalize_source_path(path),
        start_line,
        end_line,
        content_hash,
    ]
    canonical = json.dumps(canonical_fields, ensure_ascii=False, separators=(",", ":"))
    return "E_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class EvidenceRecord(BaseModel):
    """Validated immutable record suitable for bundle serialization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(default=1, ge=1)
    evidence_id: str | None = None
    evidence_class: EvidenceClass
    repository_slug: str
    commit_sha: str
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content: str = Field(min_length=1)
    owner_claim_id: str | None = None
    title: str | None = None
    symbol: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("commit_sha")
    @classmethod
    def validate_commit(cls, value: str) -> str:
        if not COMMIT_RE.fullmatch(value):
            raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
        return value

    @field_validator("repository_slug")
    @classmethod
    def validate_repository_slug(cls, value: str) -> str:
        parts = value.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise ValueError("repository slug must be owner/name")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_source_path(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = normalize_content(value)
        if not normalized:
            raise ValueError("content must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_record(self) -> EvidenceRecord:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if self.evidence_class is EvidenceClass.OWNER_ASSERTION and not self.owner_claim_id:
            raise ValueError("OWNER_ASSERTION requires owner_claim_id")
        expected = build_evidence_id(
            schema_version=self.schema_version,
            evidence_class=self.evidence_class,
            repository_slug=self.repository_slug,
            commit_sha=self.commit_sha,
            path=self.path,
            start_line=self.start_line,
            end_line=self.end_line,
            content=self.content,
        )
        if self.evidence_id is not None and self.evidence_id != expected:
            raise ValueError("evidence_id does not match record content")
        object.__setattr__(self, "evidence_id", expected)
        return self
