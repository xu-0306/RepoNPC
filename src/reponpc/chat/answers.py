"""Fail-closed grounded answer and server-owned citation validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from reponpc.bundles.index_reader import IndexedEvidence

_SOURCE_MARKER_RE = re.compile(r"\[(S[1-9][0-9]*)\]")
_SOURCE_ID_RE = re.compile(r"S[1-9][0-9]*")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"(?i)(?:https?|ftp|file|javascript):\S+")
_HTML_RE = re.compile(r"<[^>]*>")
_PERSON_CLAIM_RE = re.compile(
    r"(?i)(?:\b(?:I|he|she|they|owner|maintainer|author|employee|engineer|lead|senior|"
    r"responsible|created|built|implemented|achieved|led|worked|founded|founder|"
    r"maintained|maintains|authored)\b|"
    r"我|他|她|作者|創辦人|維護者|員工|工程師|主管|資深|負責|建立|開發|實作|達成|"
    r"領導|創辦|維護|撰寫|任職)"
)
_WORD_RE = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+", re.IGNORECASE)
_CLAIM_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "he",
        "her",
        "hers",
        "him",
        "his",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "owner",
        "she",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "we",
    }
)
_ABSTENTIONS = {
    "zh-TW": "目前可用的作品集證據不足以確認這個問題。",
    "en": "The available portfolio evidence is insufficient to confirm this.",
}


class Inference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=4000)
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("inference source IDs must be unique")
        return value


class AnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_markdown: str = Field(min_length=1, max_length=20000)
    used_source_ids: tuple[str, ...] = Field(max_length=8)
    inferences: tuple[Inference, ...] = Field(default=(), max_length=16)
    insufficient_evidence: bool

    @field_validator("used_source_ids")
    @classmethod
    def unique_used_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("used source IDs must be unique")
        return value


@dataclass(frozen=True, slots=True)
class Citation:
    id: str
    evidence_id: str
    evidence_class: str
    repository: str
    commit_sha: str
    path: str
    start_line: int
    end_line: int
    title: str
    excerpt: str
    url: str


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    answer_markdown: str
    citations: tuple[Citation, ...]
    insufficient_evidence: bool


def validate_answer(
    raw: str | dict[str, Any],
    selected_evidence: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
) -> ValidatedAnswer:
    """Validate complete provider output or return a localized safe abstention."""

    try:
        envelope = (
            AnswerEnvelope.model_validate_json(raw)
            if isinstance(raw, str)
            else AnswerEnvelope.model_validate(raw)
        )
        return _validate_envelope(envelope, selected_evidence, locale)
    except (ValidationError, ValueError, TypeError):
        return _abstention(locale)


def _validate_envelope(
    envelope: AnswerEnvelope,
    selected: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
) -> ValidatedAnswer:
    if not selected or any(not _SOURCE_ID_RE.fullmatch(source_id) for source_id in selected):
        raise ValueError("invalid selected source map")
    answer = envelope.answer_markdown
    if _URL_RE.search(answer) or _HTML_RE.search(answer):
        raise ValueError("model-authored links or HTML are forbidden")
    answer = _LINK_RE.sub(lambda match: match.group(1), answer)
    markers = tuple(dict.fromkeys(_SOURCE_MARKER_RE.findall(answer)))
    if any(source_id not in selected for source_id in markers):
        raise ValueError("unknown source marker")
    if set(markers) != set(envelope.used_source_ids):
        raise ValueError("source markers and envelope differ")
    if any(source_id not in selected for source_id in envelope.used_source_ids):
        raise ValueError("unselected source ID")
    if envelope.insufficient_evidence:
        if envelope.used_source_ids or envelope.inferences:
            raise ValueError("abstention must not assert evidence")
        return _abstention(locale)
    if not markers or not _all_material_lines_are_cited(answer):
        raise ValueError("uncited material claim")
    for line in answer.splitlines():
        if _PERSON_CLAIM_RE.search(line):
            cited = _SOURCE_MARKER_RE.findall(line)
            if not cited or not any(
                _owner_assertion_supports(line, selected[source_id]) for source_id in cited
            ):
                raise ValueError("unsupported person claim")
    for inference in envelope.inferences:
        if any(source_id not in selected for source_id in inference.source_ids):
            raise ValueError("unknown inference source")
        if any(
            selected[source_id].evidence_class == "MODEL_INFERENCE"
            for source_id in inference.source_ids
        ):
            raise ValueError("inference cycle")
    citations = tuple(_citation(source_id, selected[source_id]) for source_id in markers)
    return ValidatedAnswer(answer, citations, False)


def _all_material_lines_are_cited(answer: str) -> bool:
    for line in answer.splitlines():
        material = line.strip().lstrip("#>*-0123456789. ").strip()
        if material and len(material) > 2 and not _SOURCE_MARKER_RE.search(line):
            return False
    return True


def _owner_assertion_supports(line: str, evidence: IndexedEvidence) -> bool:
    if evidence.evidence_class != "OWNER_ASSERTION":
        return False
    claim_terms = _claim_terms(_SOURCE_MARKER_RE.sub("", line))
    evidence_terms = _claim_terms(evidence.content)
    if not claim_terms or not evidence_terms:
        return False
    if all(term in evidence_terms for term in claim_terms):
        return True
    claim_cjk = "".join(term for term in claim_terms if _contains_cjk(term))
    evidence_cjk = "".join(term for term in evidence_terms if _contains_cjk(term))
    return len(claim_cjk) >= 4 and claim_cjk in evidence_cjk


def _claim_terms(value: str) -> tuple[str, ...]:
    return tuple(
        term
        for token in _WORD_RE.findall(value.casefold())
        for term in ([token] if _contains_cjk(token) else token.split())
        if term not in _CLAIM_STOPWORDS
    )


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)


def _citation(source_id: str, evidence: IndexedEvidence) -> Citation:
    return Citation(
        id=source_id,
        evidence_id=evidence.evidence_id,
        evidence_class=evidence.evidence_class,
        repository=evidence.repository_slug,
        commit_sha=evidence.commit_sha,
        path=evidence.path,
        start_line=evidence.start_line,
        end_line=evidence.end_line,
        title=evidence.title or evidence.symbol or evidence.path,
        excerpt=evidence.content[:500],
        url=evidence.github_permalink,
    )


def _abstention(locale: Literal["zh-TW", "en"]) -> ValidatedAnswer:
    return ValidatedAnswer(_ABSTENTIONS[locale], (), True)
