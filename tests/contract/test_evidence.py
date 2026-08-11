from __future__ import annotations

import pytest
from pydantic import ValidationError

from reponpc.domain.evidence import EvidenceClass, EvidenceRecord, build_evidence_id

SHA = "a" * 40


def fact(**changes: object) -> EvidenceRecord:
    values: dict[str, object] = {
        "evidence_class": EvidenceClass.REPOSITORY_FACT,
        "repository_slug": "owner/repo",
        "commit_sha": SHA,
        "path": "src/app.py",
        "start_line": 10,
        "end_line": 12,
        "content": "def hello():\n    return 'hi'\n",
    }
    values.update(changes)
    return EvidenceRecord.model_validate(values)


def test_evidence_id_is_stable_and_has_contract_shape() -> None:
    first = fact()
    second = fact()
    assert first.evidence_id == second.evidence_id
    assert first.evidence_id is not None
    assert first.evidence_id.startswith("E_")
    assert len(first.evidence_id) == 26


def test_line_endings_normalize_before_hashing() -> None:
    lf = fact(content="one\ntwo\n")
    crlf = fact(content="one\r\ntwo\r\n")
    assert crlf.content == "one\ntwo\n"
    assert crlf.evidence_id == lf.evidence_id


def test_source_contract_rejects_mutable_or_unsafe_metadata() -> None:
    with pytest.raises(ValidationError):
        fact(commit_sha="main")
    with pytest.raises(ValidationError):
        fact(repository_slug="owner/repo/extra")
    with pytest.raises(ValidationError):
        fact(path="../secret")
    with pytest.raises(ValidationError):
        fact(start_line=0)
    with pytest.raises(ValidationError):
        fact(start_line=12, end_line=10)


def test_owner_assertion_requires_claim_id_and_preserves_class() -> None:
    with pytest.raises(ValidationError):
        fact(evidence_class=EvidenceClass.OWNER_ASSERTION)
    record = fact(evidence_class=EvidenceClass.OWNER_ASSERTION, owner_claim_id="project_role")
    assert record.evidence_class is EvidenceClass.OWNER_ASSERTION
    assert record.owner_claim_id == "project_role"


def test_supplied_forged_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        fact(evidence_id="E_" + "0" * 24)


def test_builder_matches_record_identifier() -> None:
    record = fact()
    assert record.evidence_id == build_evidence_id(
        schema_version=1,
        evidence_class=EvidenceClass.REPOSITORY_FACT,
        repository_slug="owner/repo",
        commit_sha=SHA,
        path="src/app.py",
        start_line=10,
        end_line=12,
        content="def hello():\n    return 'hi'\n",
    )
