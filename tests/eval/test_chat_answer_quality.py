"""Deterministic Phase 3 answer-quality evaluation for the production validator.

The fixture records reviewed material claims and their immutable supporting
evidence.  This scorer does not ask a model to decide entailment: it checks
only exact reviewed claim lines, their server-built citations, and fail-closed
behavior.  Every emitted citation is counted in the resolution denominator,
while every scenario must also exactly match its reviewed citation set.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from reponpc.bundles.index_reader import IndexedEvidence
from reponpc.chat.answers import Citation, ValidatedAnswer, validate_answer

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "chat" / "answer_quality_scenarios.json"
_SOURCE_MARKER_RE = re.compile(r"\[(S[1-9][0-9]*)\]")


@dataclass(frozen=True, slots=True)
class CitationScore:
    """Citation results with an emitted-citation denominator."""

    resolved_emitted: int
    emitted: int
    exact_reviewed_match: bool


@dataclass(frozen=True, slots=True)
class FactualScore:
    """Reviewed supported material-claim entailment results."""

    entailed_reviewed_claims: int
    reviewed_claims: int
    exact_reviewed_match: bool


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _evidence(raw: dict[str, Any]) -> IndexedEvidence:
    return IndexedEvidence(
        evidence_id=str(raw["evidence_id"]),
        evidence_class=str(raw["evidence_class"]),
        repository_slug=str(raw["repository_slug"]),
        commit_sha=str(raw["commit_sha"]),
        path=str(raw["path"]),
        start_line=int(raw["start_line"]),
        end_line=int(raw["end_line"]),
        title=str(raw["title"]) if raw["title"] is not None else None,
        symbol=str(raw["symbol"]) if raw["symbol"] is not None else None,
        content=str(raw["content"]),
        language=str(raw["language"]) if raw["language"] is not None else None,
        metadata=dict(raw["metadata"]),
    )


def _selected(
    by_source_id: dict[str, IndexedEvidence], scenario: dict[str, Any]
) -> dict[str, IndexedEvidence]:
    return {source_id: by_source_id[source_id] for source_id in scenario["selected_source_ids"]}


def _citation_matches_evidence(citation: Citation, evidence: IndexedEvidence) -> bool:
    return (
        citation.evidence_id == evidence.evidence_id
        and citation.evidence_class == evidence.evidence_class
        and citation.repository == evidence.repository_slug
        and citation.commit_sha == evidence.commit_sha
        and citation.path == evidence.path
        and citation.start_line == evidence.start_line
        and citation.end_line == evidence.end_line
        and citation.url == evidence.github_permalink
    )


def _score_citations(
    result: ValidatedAnswer,
    expected_evidence_ids: list[str],
    by_evidence_id: dict[str, IndexedEvidence],
) -> CitationScore:
    """Score every emitted citation and require an exact reviewed result set."""

    expected = [by_evidence_id[evidence_id] for evidence_id in expected_evidence_ids]
    resolved_emitted = sum(
        any(_citation_matches_evidence(citation, evidence) for evidence in expected)
        for citation in result.citations
    )
    actual_ids = [citation.evidence_id for citation in result.citations]
    exact_reviewed_match = (
        actual_ids == expected_evidence_ids
        and len(result.citations) == len(expected)
        and all(
            _citation_matches_evidence(citation, evidence)
            for citation, evidence in zip(result.citations, expected, strict=True)
        )
    )
    return CitationScore(resolved_emitted, len(result.citations), exact_reviewed_match)


def _material_claim_lines(answer_markdown: str) -> list[tuple[str, tuple[str, ...]]]:
    """Return non-empty answer lines and their source markers without NLP."""

    claims: list[tuple[str, tuple[str, ...]]] = []
    for line in answer_markdown.splitlines():
        text = _SOURCE_MARKER_RE.sub("", line).strip()
        if text:
            claims.append((text, tuple(_SOURCE_MARKER_RE.findall(line))))
    return claims


def _score_factual_entailment(
    result: ValidatedAnswer, reviewed_claims: list[dict[str, Any]]
) -> FactualScore:
    """Compare only fixture-reviewed supported material claim lines and IDs."""

    actual_claims = _material_claim_lines(result.answer_markdown)
    citation_by_source = {citation.id: citation.evidence_id for citation in result.citations}
    entailed = 0
    exact_reviewed_match = not result.insufficient_evidence and len(actual_claims) == len(
        reviewed_claims
    )

    for index, expected in enumerate(reviewed_claims):
        if index >= len(actual_claims):
            continue
        actual_text, source_ids = actual_claims[index]
        expected_text = str(expected["text"])
        supporting_ids = [str(value) for value in expected["supporting_evidence_ids"]]
        actual_evidence_ids = [citation_by_source.get(source_id) for source_id in source_ids]
        claim_is_entailed = actual_text == expected_text and actual_evidence_ids == supporting_ids
        entailed += int(claim_is_entailed)
        exact_reviewed_match = exact_reviewed_match and claim_is_entailed

    return FactualScore(entailed, len(reviewed_claims), exact_reviewed_match)


def _output_text(result: ValidatedAnswer) -> str:
    citation_text = " ".join(
        f"{citation.title} {citation.excerpt} {citation.url}" for citation in result.citations
    )
    return f"{result.answer_markdown} {citation_text}"


def _fails_closed(result: ValidatedAnswer) -> bool:
    return result.insufficient_evidence and not result.citations


def test_answer_quality_gate_uses_reviewed_expectations_and_fails_closed() -> None:
    fixture = _load_fixture()
    assert fixture["schema_version"] == 2
    canary = str(fixture["canary"])
    evidence_by_source = {item["source_id"]: _evidence(item) for item in fixture["evidence"]}
    evidence_by_id = {item.evidence_id: item for item in evidence_by_source.values()}
    scenarios = list(fixture["scenarios"])

    citation_emitted = citation_resolved = 0
    factual_total = factual_entailed = 0
    unsupported_total = unsupported_correct = 0
    safety_total = safety_fail_closed = 0

    for scenario in scenarios:
        expected = scenario["expected"]
        expected_ids = [str(value) for value in expected["citation_evidence_ids"]]
        reviewed_claims = expected["reviewed_claims"]
        assert len(expected_ids) == len(set(expected_ids)), scenario["id"]
        assert isinstance(reviewed_claims, list), scenario["id"]
        result = validate_answer(
            scenario["raw"],
            _selected(evidence_by_source, scenario),
            scenario["locale"],
        )

        citation_score = _score_citations(result, expected_ids, evidence_by_id)
        citation_resolved += citation_score.resolved_emitted
        citation_emitted += citation_score.emitted
        assert citation_score.exact_reviewed_match, scenario["id"]
        assert canary not in _output_text(result), scenario["id"]

        if scenario["kind"] == "supported":
            assert expected["factual_policy"] == "accept", scenario["id"]
            assert reviewed_claims, scenario["id"]
            factual_score = _score_factual_entailment(result, reviewed_claims)
            factual_entailed += factual_score.entailed_reviewed_claims
            factual_total += factual_score.reviewed_claims
            assert factual_score.exact_reviewed_match, scenario["id"]

        if scenario["kind"] == "unsupported":
            assert expected["factual_policy"] == "abstain", scenario["id"]
            unsupported_total += 1
            unsupported_correct += int(_fails_closed(result))

        if scenario["kind"] == "safety":
            assert expected.get("fail_closed") is True, scenario["id"]
            safety_total += 1
            safety_fail_closed += int(_fails_closed(result))
            assert _fails_closed(result), scenario["id"]

    citation_rate = citation_resolved / citation_emitted if citation_emitted else 1.0
    factual_rate = factual_entailed / factual_total if factual_total else 1.0
    unsupported_rate = unsupported_correct / unsupported_total if unsupported_total else 1.0
    safety_rate = safety_fail_closed / safety_total if safety_total else 1.0

    assert factual_total > 0
    assert citation_rate >= 0.95, (citation_resolved, citation_emitted, citation_rate)
    assert factual_rate >= 0.90, (factual_entailed, factual_total, factual_rate)
    assert unsupported_rate >= 0.90, (
        unsupported_correct,
        unsupported_total,
        unsupported_rate,
    )
    assert safety_rate == 1.0, (safety_fail_closed, safety_total, safety_rate)


def test_quality_scorer_self_falsifies_extra_emitted_citation() -> None:
    """An extra otherwise-valid citation cannot hide behind a perfect rate."""

    fixture = _load_fixture()
    evidence_by_source = {item["source_id"]: _evidence(item) for item in fixture["evidence"]}
    evidence_by_id = {item.evidence_id: item for item in evidence_by_source.values()}
    scenario = next(
        item for item in fixture["scenarios"] if item["id"] == "supported_repository_fact"
    )
    result = validate_answer(
        scenario["raw"],
        _selected(evidence_by_source, scenario),
        scenario["locale"],
    )
    assert result.citations

    duplicated = replace(result, citations=(*result.citations, result.citations[0]))
    score = _score_citations(
        duplicated,
        [str(value) for value in scenario["expected"]["citation_evidence_ids"]],
        evidence_by_id,
    )

    assert score.resolved_emitted == 2
    assert score.emitted == 2
    assert not score.exact_reviewed_match
