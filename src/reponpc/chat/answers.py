"""Fail-closed grounded answer and server-owned citation validation."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from reponpc.bundles.index_reader import IndexedEvidence

_SOURCE_MARKER_RE = re.compile(r"\[(S[1-9][0-9]*)\]")
_SOURCE_ID_RE = re.compile(r"S[1-9][0-9]*")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL_RE = re.compile(r"(?i)(?:https?|ftp|file|javascript):\S+|(?:www\.)\S+")
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
_NO_MATCH = {
    "zh-TW": "這個問題我在作品集裡找不到相關內容，可以試試下面這些問題。",  # noqa: RUF001
    "en": "I couldn't find anything about that in this portfolio. Try one of these questions.",
}
_OWNER_PLACEHOLDER = "{{owner}}"
_POLICY_DIR = Path(__file__).with_name("policy")
_CJK_NUMERAL_RE = re.compile(r"[零\u3007一二兩三四五六七八九十百千万萬億]+")
_ASCII_NUMERAL_RE = re.compile(r"(?<![A-Za-z0-9_])\d+(?:[.,]\d+)*%?")
_DATE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(\d{4})[-/年](\d{1,2})(?:[-/月](\d{1,2})日?)?(?![A-Za-z0-9_])"
)
_CJK_PERCENT_RE = re.compile(r"百分之([零\u3007一二兩三四五六七八九十百千万萬億]+)")
_ROLE_GROUPS = frozenset({"role", "responsibility", "lead", "founder", "manager", "architect"})
_SEGMENT_DROP_REASON_CODES = frozenset(
    {
        "MODEL_INFERENCE_SOURCE",
        "OWNER_NAME_MISSING",
        "OWNER_REFERENCE_MISSING",
        "OWNER_ASSERTION_MISSING",
        "INFLATION_UNSUPPORTED",
        "NUMBER_UNSUPPORTED",
        "PARTICIPATION_EVIDENCE_MISSING",
        "PARTICIPATION_ROLE_CLAIM",
        "PROJECT_EVIDENCE_MISSING",
        "PROJECT_OWNER_REFERENCE",
        "INFERENCE_EVIDENCE_MISSING",
    }
)


class _EnvelopeIntegrityError(ValueError):
    """An envelope-level failure that must reject the complete answer."""


class AnswerSegment(BaseModel):
    """One typed, structurally cited answer segment from provider output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["person", "participation", "project", "inference"]
    text: str = Field(min_length=1, max_length=4000, strict=True)
    source_ids: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("segment source IDs must be unique")
        return value


class AnswerEnvelope(BaseModel):
    """Envelope v2. Legacy output is parsed by the private adapter below."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segments: tuple[AnswerSegment, ...] = Field(max_length=16)
    insufficient_evidence: bool = Field(strict=True)


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


class LegacyAnswerEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_markdown: str = Field(min_length=1, max_length=20000, strict=True)
    used_source_ids: tuple[str, ...] = Field(max_length=8)
    inferences: tuple[Inference, ...] = Field(default=(), max_length=16)
    insufficient_evidence: bool = Field(strict=True)

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
    suggested_questions: tuple[str, ...] = ()
    # Owner-only diagnostics; never serialize this field into public delivery.
    discarded_reason_codes: tuple[str, ...] = ()


def validate_answer(
    raw: str | dict[str, Any],
    selected_evidence: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None = None,
    owner_aliases: Sequence[str] = (),
    suggested_questions: Sequence[str] = (),
    allow_legacy: bool = True,
) -> ValidatedAnswer:
    """Validate one complete provider output before public delivery.

    Envelope v2 is selected by its ``segments`` field.  The v1 parser remains
    available only as the compatibility adapter used by migration fixtures and
    existing tests.  Owner identity is deliberately keyword-only so callers do
    not accidentally bind a display name where a locale was expected.
    """

    suggestions = _safe_suggestions(suggested_questions)
    if _looks_like_v2(raw):
        try:
            envelope = (
                AnswerEnvelope.model_validate_json(raw)
                if isinstance(raw, str)
                else AnswerEnvelope.model_validate(raw)
            )
            return _validate_v2_envelope(
                envelope,
                selected_evidence,
                locale,
                owner_name=owner_name,
                owner_aliases=owner_aliases,
                suggested_questions=suggestions,
            )
        except (ValidationError, ValueError, TypeError, AttributeError, KeyError):
            return _no_match(locale, suggestions)

    if not allow_legacy:
        return _no_match(locale, suggestions)
    try:
        legacy_envelope = (
            LegacyAnswerEnvelope.model_validate_json(raw)
            if isinstance(raw, str)
            else LegacyAnswerEnvelope.model_validate(raw)
        )
        return _validate_legacy_envelope(legacy_envelope, selected_evidence, locale, suggestions)
    except (ValidationError, ValueError, TypeError, AttributeError, KeyError):
        return _abstention(locale, suggestions)


def validate_v2_answer(
    raw: str | dict[str, Any],
    selected_evidence: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None = None,
    owner_aliases: Sequence[str] = (),
    suggested_questions: Sequence[str] = (),
) -> ValidatedAnswer:
    """Validate provider output with the v1 migration adapter disabled."""

    return validate_answer(
        raw,
        selected_evidence,
        locale,
        owner_name=owner_name,
        owner_aliases=owner_aliases,
        suggested_questions=suggested_questions,
        allow_legacy=False,
    )


def _looks_like_v2(raw: str | dict[str, Any]) -> bool:
    if isinstance(raw, dict):
        return "segments" in raw or (
            "insufficient_evidence" in raw
            and "answer_markdown" not in raw
            and "used_source_ids" not in raw
            and "inferences" not in raw
        )
    if not isinstance(raw, str):
        return False
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return '"segments"' in raw
    return isinstance(parsed, dict) and _looks_like_v2(parsed)


def _validate_v2_envelope(
    envelope: AnswerEnvelope,
    selected: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None,
    owner_aliases: Sequence[str],
    suggested_questions: tuple[str, ...],
) -> ValidatedAnswer:
    """Apply envelope integrity checks, then salvage valid typed segments."""

    if envelope.insufficient_evidence:
        return _no_match(locale, suggested_questions)
    if not selected or any(not _SOURCE_ID_RE.fullmatch(source_id) for source_id in selected):
        raise _EnvelopeIntegrityError("invalid selected source map")

    for segment in envelope.segments:
        if (
            _URL_RE.search(segment.text)
            or _HTML_RE.search(segment.text)
            or _LINK_RE.search(segment.text)
            or _SOURCE_MARKER_RE.search(segment.text)
        ):
            raise _EnvelopeIntegrityError("model-authored links, HTML, or source markers")
        if any(
            not _SOURCE_ID_RE.fullmatch(source_id) or source_id not in selected
            for source_id in segment.source_ids
        ):
            raise _EnvelopeIntegrityError("unknown or unselected source ID")
        if segment.kind == "inference" and any(
            selected[source_id].evidence_class == "MODEL_INFERENCE"
            for source_id in segment.source_ids
        ):
            raise _EnvelopeIntegrityError("inference cycle")

    safe_owner = _safe_owner_name(owner_name)
    identity_terms = _identity_terms(owner_name, owner_aliases)
    retained: list[tuple[str, str, tuple[str, ...]]] = []
    discarded_reason_codes: list[str] = []
    for segment in envelope.segments:
        source_ids = segment.source_ids
        evidence = tuple(selected[source_id] for source_id in source_ids)
        person_reference = _contains_person_reference(segment.text, locale, identity_terms)
        kind: str = segment.kind
        if segment.kind in {"project", "inference"} and person_reference:
            kind = "person"
        text = _normalize_owner_references(segment.text, locale, identity_terms)
        reasons = _segment_drop_reasons(kind, text, evidence, safe_owner=safe_owner)
        for reason in reasons:
            if reason not in discarded_reason_codes:
                discarded_reason_codes.append(reason)
        if not reasons:
            retained.append((kind, text, source_ids))

    if not retained:
        return _no_match(
            locale,
            suggested_questions,
            discarded_reason_codes=tuple(discarded_reason_codes),
        )

    rendered: list[str] = []
    citation_ids: list[str] = []
    for kind, text, source_ids in retained:
        rendered.append(_render_v2_segment(kind, text, source_ids, locale, safe_owner))
        for source_id in source_ids:
            if source_id not in citation_ids:
                citation_ids.append(source_id)
    citations = tuple(_citation(source_id, selected[source_id]) for source_id in citation_ids)
    return ValidatedAnswer(
        "\n\n".join(rendered),
        citations,
        False,
        suggested_questions,
        tuple(discarded_reason_codes),
    )


def _segment_drop_reasons(
    kind: str,
    text: str,
    evidence: tuple[IndexedEvidence, ...],
    *,
    safe_owner: str | None,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if any(item.evidence_class == "MODEL_INFERENCE" for item in evidence):
        reasons.append("MODEL_INFERENCE_SOURCE")
        return tuple(reasons)
    if kind == "person":
        owner_evidence = tuple(
            item for item in evidence if item.evidence_class == "OWNER_ASSERTION"
        )
        if safe_owner is None:
            reasons.append("OWNER_NAME_MISSING")
        if _OWNER_PLACEHOLDER not in text:
            reasons.append("OWNER_REFERENCE_MISSING")
        if not owner_evidence:
            reasons.append("OWNER_ASSERTION_MISSING")
        if owner_evidence and not _inflation_supported(text, owner_evidence):
            reasons.append("INFLATION_UNSUPPORTED")
        if owner_evidence and not _numbers_supported(text, owner_evidence):
            reasons.append("NUMBER_UNSUPPORTED")
        return tuple(reasons)
    if kind == "participation":
        participation = tuple(item for item in evidence if item.evidence_class == "PARTICIPATION")
        if safe_owner is None:
            reasons.append("OWNER_NAME_MISSING")
        if not participation:
            reasons.append("PARTICIPATION_EVIDENCE_MISSING")
        if _has_role_claim(text):
            reasons.append("PARTICIPATION_ROLE_CLAIM")
        if participation and not _numbers_supported(text, participation):
            reasons.append("NUMBER_UNSUPPORTED")
        return tuple(reasons)
    if kind == "project":
        if not evidence or not any(_is_repository_evidence(item) for item in evidence):
            reasons.append("PROJECT_EVIDENCE_MISSING")
        if _OWNER_PLACEHOLDER in text or _contains_person_reference(text, "en", ()):
            reasons.append("PROJECT_OWNER_REFERENCE")
        return tuple(reasons)
    if kind == "inference":
        if not evidence:
            reasons.append("INFERENCE_EVIDENCE_MISSING")
        if safe_owner is None and _OWNER_PLACEHOLDER in text:
            reasons.append("OWNER_NAME_MISSING")
        return tuple(reasons)
    return ("INFERENCE_EVIDENCE_MISSING",)


def _valid_v2_segment(
    kind: str,
    text: str,
    evidence: tuple[IndexedEvidence, ...],
    *,
    safe_owner: str | None,
) -> bool:
    """Compatibility predicate for migration callers of the old helper."""

    return not _segment_drop_reasons(kind, text, evidence, safe_owner=safe_owner)


def _is_repository_evidence(evidence: IndexedEvidence) -> bool:
    return evidence.evidence_class in {"REPOSITORY_FACT", "REPOSITORY_METADATA"}


def _render_v2_segment(
    kind: str,
    text: str,
    source_ids: tuple[str, ...],
    locale: Literal["zh-TW", "en"],
    owner_name: str | None,
) -> str:
    rendered_text = text.replace(_OWNER_PLACEHOLDER, owner_name or "")
    if kind == "person":
        if locale == "zh-TW":
            rendered_text = f"{owner_name} 自述：{rendered_text}"  # noqa: RUF001
        else:
            rendered_text = f"In {owner_name}'s own words: {rendered_text}"
    markers = " ".join(f"[{source_id}]" for source_id in source_ids)
    return f"{rendered_text.strip()} {markers}".strip()


def _validate_legacy_envelope(
    envelope: LegacyAnswerEnvelope,
    selected: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    suggested_questions: tuple[str, ...] = (),
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
        return _abstention(locale, suggested_questions)
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
    return ValidatedAnswer(answer, citations, False, suggested_questions)


def validate_legacy_answer(
    raw: str | dict[str, Any],
    selected_evidence: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None = None,
    owner_aliases: Sequence[str] = (),
    suggested_questions: Sequence[str] = (),
) -> ValidatedAnswer:
    """Run the v1 line-by-line adapter for tests and migration only.

    Production provider delivery must use :func:`validate_v2_answer`.  This
    explicit entry point exists so migration fixtures can exercise the v1
    compatibility contract without making v1 an implicit provider fallback.
    """

    suggestions = _safe_suggestions(suggested_questions)
    try:
        envelope = (
            LegacyAnswerEnvelope.model_validate_json(raw)
            if isinstance(raw, str)
            else LegacyAnswerEnvelope.model_validate(raw)
        )
        return _validate_legacy_project_adapter(
            envelope,
            selected_evidence,
            locale,
            owner_name=owner_name,
            owner_aliases=owner_aliases,
            suggested_questions=suggestions,
        )
    except (ValidationError, ValueError, TypeError, AttributeError, KeyError):
        return _no_match(locale, suggestions)


def _validate_legacy_project_adapter(
    envelope: LegacyAnswerEnvelope,
    selected: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None,
    owner_aliases: Sequence[str],
    suggested_questions: tuple[str, ...],
) -> ValidatedAnswer:
    """Treat each v1 answer line as a project segment with recall fallback."""

    if not selected or any(not _SOURCE_ID_RE.fullmatch(source_id) for source_id in selected):
        raise _EnvelopeIntegrityError("invalid selected source map")
    answer = envelope.answer_markdown
    if _URL_RE.search(answer) or _HTML_RE.search(answer) or _LINK_RE.search(answer):
        raise _EnvelopeIntegrityError("model-authored links or HTML are forbidden")
    markers = tuple(dict.fromkeys(_SOURCE_MARKER_RE.findall(answer)))
    if any(source_id not in selected for source_id in markers):
        raise _EnvelopeIntegrityError("unknown source marker")
    if set(markers) != set(envelope.used_source_ids):
        raise _EnvelopeIntegrityError("source markers and envelope differ")
    if any(source_id not in selected for source_id in envelope.used_source_ids):
        raise _EnvelopeIntegrityError("unselected source ID")
    if envelope.insufficient_evidence:
        if envelope.used_source_ids or envelope.inferences:
            raise _EnvelopeIntegrityError("abstention must not assert evidence")
        return _no_match(locale, suggested_questions)
    if not markers or not _all_material_lines_are_cited(answer):
        raise _EnvelopeIntegrityError("uncited material claim")
    for inference in envelope.inferences:
        if any(source_id not in selected for source_id in inference.source_ids):
            raise _EnvelopeIntegrityError("unknown inference source")
        if any(
            selected[source_id].evidence_class == "MODEL_INFERENCE"
            for source_id in inference.source_ids
        ):
            raise _EnvelopeIntegrityError("inference cycle")
        if _URL_RE.search(inference.statement) or _HTML_RE.search(inference.statement):
            raise _EnvelopeIntegrityError("model-authored links or HTML are forbidden")

    safe_owner = _safe_owner_name(owner_name)
    identity_terms = _identity_terms(owner_name, owner_aliases)
    retained: list[tuple[str, str, tuple[str, ...]]] = []
    discarded_reason_codes: list[str] = []
    for line in answer.splitlines():
        source_ids = tuple(dict.fromkeys(_SOURCE_MARKER_RE.findall(line)))
        line_text = _SOURCE_MARKER_RE.sub("", line).strip()
        if not line_text:
            continue
        person_reference = _contains_person_reference(line_text, locale, identity_terms)
        kind = "person" if person_reference else "project"
        normalized = _normalize_owner_references(line_text, locale, identity_terms)
        evidence = tuple(selected[source_id] for source_id in source_ids)
        reasons = _segment_drop_reasons(kind, normalized, evidence, safe_owner=safe_owner)
        for reason in reasons:
            if reason not in discarded_reason_codes:
                discarded_reason_codes.append(reason)
        if not reasons:
            retained.append((kind, normalized, source_ids))

    if not retained:
        return _no_match(
            locale,
            suggested_questions,
            discarded_reason_codes=tuple(discarded_reason_codes),
        )

    rendered: list[str] = []
    citation_ids: list[str] = []
    for kind, text, source_ids in retained:
        rendered.append(_render_v2_segment(kind, text, source_ids, locale, safe_owner))
        for source_id in source_ids:
            if source_id not in citation_ids:
                citation_ids.append(source_id)
    citations = tuple(_citation(source_id, selected[source_id]) for source_id in citation_ids)
    return ValidatedAnswer(
        "\n\n".join(rendered),
        citations,
        False,
        suggested_questions,
        tuple(discarded_reason_codes),
    )


@dataclass(frozen=True, slots=True)
class _LocalePolicy:
    references: tuple[str, ...]
    exclusions: tuple[str, ...]


def _safe_suggestions(values: Sequence[str]) -> tuple[str, ...]:
    """Keep only bounded, display-safe suggestions supplied by the bundle."""

    if not values or isinstance(values, str):
        return ()
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if (
            not candidate
            or len(candidate) > 240
            or _URL_RE.search(candidate)
            or _HTML_RE.search(candidate)
        ):
            continue
        if candidate not in result:
            result.append(candidate)
        if len(result) == 3:
            break
    return tuple(result)


def _no_match(
    locale: Literal["zh-TW", "en"],
    suggestions: tuple[str, ...] = (),
    *,
    discarded_reason_codes: tuple[str, ...] = (),
) -> ValidatedAnswer:
    return ValidatedAnswer(_NO_MATCH[locale], (), True, suggestions, discarded_reason_codes)


def _safe_owner_name(owner_name: str | None) -> str | None:
    if not isinstance(owner_name, str):
        return None
    candidate = owner_name.strip()
    if (
        not candidate
        or len(candidate) > 200
        or any(character in candidate for character in "\r\n")
        or _URL_RE.search(candidate)
        or _HTML_RE.search(candidate)
    ):
        return None
    return candidate


def _identity_terms(owner_name: str | None, owner_aliases: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for value in (owner_name, *owner_aliases):
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate or _safe_owner_name(candidate) is None:
            continue
        normalized = unicodedata.normalize("NFKC", candidate).casefold()
        if normalized not in {unicodedata.normalize("NFKC", item).casefold() for item in values}:
            values.append(candidate)
    return tuple(sorted(values, key=len, reverse=True))


@lru_cache(maxsize=2)
def _load_locale_policy(locale: Literal["zh-TW", "en"]) -> _LocalePolicy:
    path = _POLICY_DIR / f"person_reference.{locale}.yml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("person reference policy must be a mapping")
        references = tuple(
            item.strip()
            for item in raw.get("references", ())
            if isinstance(item, str) and item.strip()
        )
        exclusions = tuple(
            item.strip()
            for item in raw.get("exclusions", ())
            if isinstance(item, str) and item.strip()
        )
        if not references:
            raise ValueError("person reference policy is empty")
        return _LocalePolicy(references, exclusions)
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return _LocalePolicy((), ())


@lru_cache(maxsize=1)
def _load_inflation_terms() -> dict[str, tuple[str, ...]]:
    """Load the cross-locale escalation registry; an invalid file fails closed."""

    path = _POLICY_DIR / "inflation_terms.yml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        groups = raw.get("groups") if isinstance(raw, dict) else None
        if not isinstance(groups, dict):
            return {}
        result: dict[str, tuple[str, ...]] = {}
        for group, locales in groups.items():
            if not isinstance(group, str) or not isinstance(locales, dict):
                return {}
            terms = {
                unicodedata.normalize("NFKC", term).casefold()
                for values in locales.values()
                if isinstance(values, (list, tuple))
                for term in values
                if isinstance(term, str) and term.strip()
            }
            if not terms:
                return {}
            result[group] = tuple(sorted(terms, key=len, reverse=True))
        return result
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return {}


def _term_present(text: str, term: str) -> bool:
    normalized_text = unicodedata.normalize("NFKC", text).casefold()
    normalized_term = unicodedata.normalize("NFKC", term).casefold()
    if not normalized_term:
        return False
    if _contains_cjk(normalized_term):
        return normalized_term in normalized_text
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(normalized_term)}(?![A-Za-z0-9_])"
    return re.search(pattern, normalized_text) is not None


def _contains_person_reference(
    text: str,
    locale: Literal["zh-TW", "en"],
    identities: tuple[str, ...],
) -> bool:
    if _OWNER_PLACEHOLDER in text:
        return True
    policies = tuple(_load_locale_policy(item) for item in _policy_locales(locale))
    exclusions = tuple(exclusion for policy in policies for exclusion in policy.exclusions)
    searchable = _without_exclusions(text, exclusions)
    return any(_term_present(searchable, identity) for identity in identities) or any(
        _term_present(searchable, reference)
        for policy in policies
        for reference in policy.references
    )


def _policy_locales(locale: Literal["zh-TW", "en"]) -> tuple[Literal["zh-TW", "en"], ...]:
    alternate: Literal["zh-TW", "en"] = "en" if locale == "zh-TW" else "zh-TW"
    return (locale, alternate)


def _without_exclusions(text: str, exclusions: Iterable[str]) -> str:
    result = unicodedata.normalize("NFKC", text)
    for exclusion in sorted(exclusions, key=len, reverse=True):
        result = result.replace(unicodedata.normalize("NFKC", exclusion), " ")
    return result


def _normalize_owner_references(
    text: str,
    locale: Literal["zh-TW", "en"],
    identities: tuple[str, ...],
) -> str:
    policies = tuple(_load_locale_policy(item) for item in _policy_locales(locale))
    masked = unicodedata.normalize("NFKC", text)
    saved_exclusions: list[tuple[str, str]] = []
    exclusions = tuple(exclusion for policy in policies for exclusion in policy.exclusions)
    for index, exclusion in enumerate(sorted(exclusions, key=len, reverse=True)):
        token = f"\uf000{index}\uf001"
        normalized_exclusion = unicodedata.normalize("NFKC", exclusion)
        if normalized_exclusion in masked:
            masked = masked.replace(normalized_exclusion, token)
            saved_exclusions.append((token, normalized_exclusion))

    owner_tokens = "\uf002"
    masked = masked.replace(_OWNER_PLACEHOLDER, owner_tokens)
    for identity in identities:
        masked = _replace_reference(masked, identity, _OWNER_PLACEHOLDER)
    masked = masked.replace(_OWNER_PLACEHOLDER, owner_tokens)
    references = tuple(reference for policy in policies for reference in policy.references)
    for reference in sorted(references, key=len, reverse=True):
        masked = _replace_reference(masked, reference, _OWNER_PLACEHOLDER)
    masked = masked.replace(owner_tokens, _OWNER_PLACEHOLDER)
    for token, exclusion in saved_exclusions:
        masked = masked.replace(token, exclusion)
    return masked


def _replace_reference(text: str, reference: str, replacement: str) -> str:
    normalized = unicodedata.normalize("NFKC", reference).casefold()
    if not normalized:
        return text
    if _contains_cjk(normalized):
        return re.sub(re.escape(normalized), replacement, text, flags=re.IGNORECASE)
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(normalized)}(?![A-Za-z0-9_])"
    return re.sub(pattern, replacement, text, flags=re.IGNORECASE)


def _inflation_supported(text: str, owner_evidence: tuple[IndexedEvidence, ...]) -> bool:
    groups = _load_inflation_terms()
    if not groups:
        return False
    for group, terms in groups.items():
        if _has_any_term(text, terms) and not any(
            _has_any_term(evidence.content, groups.get(group, ())) for evidence in owner_evidence
        ):
            return False
    return True


def _has_role_claim(text: str) -> bool:
    groups = _load_inflation_terms()
    if not groups:
        return True
    return any(_has_any_term(text, groups.get(group, ())) for group in _ROLE_GROUPS)


def _has_any_term(text: str, terms: Iterable[str]) -> bool:
    return any(_term_present(text, term) for term in terms)


def _numbers_supported(text: str, evidence: tuple[IndexedEvidence, ...]) -> bool:
    required = _numeric_tokens(text)
    if not required:
        return True
    available = set().union(*(_numeric_tokens(item.content) for item in evidence))
    return required.issubset(available)


def _numeric_tokens(text: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", text)
    values: set[str] = set()
    for match in _DATE_RE.finditer(normalized):
        year, month, day = match.groups()
        values.add(f"date:{year}-{int(month):02d}" + (f"-{int(day):02d}" if day else ""))
    without_dates = _DATE_RE.sub(" ", normalized)
    for match in _CJK_PERCENT_RE.finditer(without_dates):
        value = _parse_cjk_number(match.group(1))
        if value is not None:
            values.add(f"{value}%")
    without_percent = _CJK_PERCENT_RE.sub(" ", without_dates)
    for match in _ASCII_NUMERAL_RE.finditer(without_percent):
        values.add(_canonical_ascii_number(match.group(0)))
    for match in _CJK_NUMERAL_RE.finditer(without_percent):
        value = _parse_cjk_number(match.group(0))
        if value is not None:
            values.add(str(value))
    return frozenset(values)


def _canonical_ascii_number(value: str) -> str:
    suffix = "%" if value.endswith("%") else ""
    stripped = value.replace(",", "").rstrip("%")
    if "." in stripped:
        whole, fraction = stripped.split(".", 1)
        whole = whole.lstrip("0") or "0"
        fraction = fraction.rstrip("0")
        return (f"{whole}.{fraction}" if fraction else whole) + suffix
    return str(int(stripped or "0")) + suffix


def _parse_cjk_number(value: str) -> int | None:
    digits = {
        "零": 0,
        "\u3007": 0,
        "一": 1,
        "二": 2,
        "兩": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000, "萬": 10000, "億": 100000000}
    if all(character in digits for character in value):
        return int("".join(str(digits[character]) for character in value))
    total = 0
    section = 0
    number = 0
    for character in value:
        if character in digits:
            number = digits[character]
            continue
        unit = units.get(character)
        if unit is None:
            return None
        if unit < 10000:
            section += (number or 1) * unit
            number = 0
        else:
            section = (section + number) or 1
            total += section * unit
            section = 0
            number = 0
    return total + section + number


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


def _abstention(
    locale: Literal["zh-TW", "en"], suggestions: tuple[str, ...] = ()
) -> ValidatedAnswer:
    return ValidatedAnswer(_ABSTENTIONS[locale], (), True, suggestions)
