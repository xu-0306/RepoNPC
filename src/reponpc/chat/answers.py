"""Fail-closed grounded answer and server-owned citation validation."""

from __future__ import annotations

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
    """The sole provider output envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    segments: tuple[AnswerSegment, ...] = Field(max_length=16)
    insufficient_evidence: bool = Field(strict=True)


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
    discarded_segments: tuple[tuple[int, tuple[str, ...]], ...] = ()


def validate_v2_answer(
    raw: str | dict[str, Any],
    selected_evidence: dict[str, IndexedEvidence],
    locale: Literal["zh-TW", "en"],
    *,
    owner_name: str | None = None,
    owner_aliases: Sequence[str] = (),
    suggested_questions: Sequence[str] = (),
) -> ValidatedAnswer:
    """Validate the complete v2 provider output before public delivery."""

    suggestions = _safe_suggestions(suggested_questions)
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
    discarded_segments: list[tuple[int, tuple[str, ...]]] = []
    for segment_index, segment in enumerate(envelope.segments):
        source_ids = segment.source_ids
        evidence = tuple(selected[source_id] for source_id in source_ids)
        person_reference = _contains_person_reference(segment.text, locale, identity_terms)
        kind: str = segment.kind
        if segment.kind in {"project", "inference"} and person_reference:
            kind = "person"
        text = segment.text
        reasons = _segment_drop_reasons(kind, text, evidence, safe_owner=safe_owner)
        if reasons:
            discarded_segments.append((segment_index, reasons))
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
            discarded_segments=tuple(discarded_segments),
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
        tuple(discarded_segments),
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
        if not any(_is_repository_evidence(item) for item in evidence):
            reasons.append("PROJECT_EVIDENCE_MISSING")
        return tuple(reasons)
    return ()


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
    discarded_segments: tuple[tuple[int, tuple[str, ...]], ...] = (),
) -> ValidatedAnswer:
    return ValidatedAnswer(
        _NO_MATCH[locale], (), True, suggestions, discarded_reason_codes, discarded_segments
    )


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
