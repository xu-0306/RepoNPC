"""Adversarial answer envelope and citation policy tests."""

from __future__ import annotations

import pytest

from reponpc.bundles.index_reader import IndexedEvidence
from reponpc.chat.answers import validate_answer


def evidence(
    source_id: str,
    *,
    evidence_class: str = "REPOSITORY_FACT",
    content: str = "bounded fixture content",
) -> tuple[str, IndexedEvidence]:
    return (
        source_id,
        IndexedEvidence(
            evidence_id="E_" + "a" * 24,
            evidence_class=evidence_class,
            repository_slug="owner/repo",
            commit_sha="b" * 40,
            path="src/app.py",
            start_line=10,
            end_line=12,
            title="Fixture",
            symbol=None,
            content=content,
            language="python",
            metadata={},
        ),
    )


def test_validated_answer_builds_server_owned_immutable_citation() -> None:
    selected = dict([evidence("S1")])
    result = validate_answer(
        {
            "answer_markdown": "The repository implements retrieval. [S1]",
            "used_source_ids": ["S1"],
            "inferences": [],
            "insufficient_evidence": False,
        },
        selected,
        "en",
    )

    assert result.insufficient_evidence is False
    assert result.citations[0].url == (
        "https://github.com/owner/repo/blob/" + "b" * 40 + "/src/app.py#L10-L12"
    )


@pytest.mark.parametrize(
    "answer,used",
    [
        ("Unknown source. [S9]", ["S9"]),
        ("Uncited material claim.", []),
        ("Unsafe [citation](https://evil.test). [S1]", ["S1"]),
        ("<script>alert(1)</script> [S1]", ["S1"]),
    ],
)
def test_unknown_uncited_or_active_content_becomes_abstention(answer: str, used: list[str]) -> None:
    result = validate_answer(
        {
            "answer_markdown": answer,
            "used_source_ids": used,
            "inferences": [],
            "insufficient_evidence": False,
        },
        dict([evidence("S1")]),
        "en",
    )

    assert result.insufficient_evidence is True
    assert result.citations == ()


def test_person_claim_requires_matching_owner_assertion() -> None:
    raw = {
        "answer_markdown": "She implemented the system. [S1]",
        "used_source_ids": ["S1"],
        "inferences": [],
        "insufficient_evidence": False,
    }

    rejected = validate_answer(raw, dict([evidence("S1")]), "en")
    accepted = validate_answer(
        raw,
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="She implemented the system.",
                )
            ]
        ),
        "en",
    )

    assert rejected.insufficient_evidence is True
    assert accepted.insufficient_evidence is False


def test_person_claim_requires_semantically_matching_owner_assertion() -> None:
    raw = {
        "answer_markdown": "Alice founded the company. [S1]",
        "used_source_ids": ["S1"],
        "inferences": [],
        "insufficient_evidence": False,
    }

    mismatched = validate_answer(
        raw,
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="Alice maintains the documentation.",
                )
            ]
        ),
        "en",
    )
    matched = validate_answer(
        raw,
        dict(
            [
                evidence(
                    "S1",
                    evidence_class="OWNER_ASSERTION",
                    content="Alice founded the company.",
                )
            ]
        ),
        "en",
    )

    assert mismatched.insufficient_evidence is True
    assert matched.insufficient_evidence is False


def test_inference_cannot_depend_on_model_inference_or_unknown_source() -> None:
    raw = {
        "answer_markdown": "A bounded inference is shown. [S1]",
        "used_source_ids": ["S1"],
        "inferences": [{"statement": "derived", "source_ids": ["S1"]}],
        "insufficient_evidence": False,
    }

    result = validate_answer(raw, dict([evidence("S1", evidence_class="MODEL_INFERENCE")]), "zh-TW")

    assert result.insufficient_evidence is True
    assert result.answer_markdown == "目前可用的作品集證據不足以確認這個問題。"
