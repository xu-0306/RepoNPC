"""The single list of languages RepoNPC knows (ADR-078).

Every other module reads languages, endonyms and allowed writing systems from here; none of
them keeps its own list.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

# Unicode script names as `admin.onboarding._letter_script` reports them (the first word of a
# letter's Unicode name, with every CJK ideograph folded into "CJK").
KNOWN_SCRIPTS: Final = frozenset(
    {
        "ARABIC",
        "BOPOMOFO",
        "CJK",
        "CYRILLIC",
        "DEVANAGARI",
        "GREEK",
        "HANGUL",
        "HEBREW",
        "HIRAGANA",
        "KATAKANA",
        "LATIN",
        "THAI",
    }
)
_TAG_RE: Final = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
_MATCH_RE: Final = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})*$")
REGISTRY_PATH: Final = Path(__file__).with_name("languages.json")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Language(_Strict):
    tag: str
    endonym: str = Field(min_length=1, max_length=40)
    scripts: tuple[str, ...] = Field(min_length=1)
    direction: Literal["ltr", "rtl"]
    match: tuple[str, ...] = Field(min_length=1)

    @field_validator("tag")
    @classmethod
    def _tag_shape(cls, value: str) -> str:
        if not _TAG_RE.fullmatch(value):
            raise ValueError("tag must be a BCP-47 language tag")
        return value

    @field_validator("scripts")
    @classmethod
    def _known_scripts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = sorted(set(value) - KNOWN_SCRIPTS)
        if unknown:
            raise ValueError(f"unknown script name {unknown[0]}")
        if len(set(value)) != len(value):
            raise ValueError("scripts must be unique")
        return value

    @field_validator("match")
    @classmethod
    def _match_shape(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _MATCH_RE.fullmatch(prefix) for prefix in value):
            raise ValueError("match prefixes must be lower-case tag prefixes")
        if len(set(value)) != len(value):
            raise ValueError("match prefixes must be unique")
        return value

    @model_validator(mode="after")
    def _tag_matches_itself(self) -> Language:
        if self.tag.lower() not in self.match:
            raise ValueError("match must include the tag itself in lower case")
        return self


class LanguageRegistry(_Strict):
    version: Literal[1]
    languages: tuple[Language, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> LanguageRegistry:
        tags = [language.tag for language in self.languages]
        if len(set(tags)) != len(tags):
            raise ValueError("language tags must be unique")
        owner: dict[str, str] = {}
        for language in self.languages:
            for prefix in language.match:
                if prefix in owner:
                    raise ValueError(
                        f"match prefix {prefix} is claimed by {owner[prefix]} and {language.tag}"
                    )
                owner[prefix] = language.tag
        return self


def load_language_registry(path: Path = REGISTRY_PATH) -> LanguageRegistry:
    """Load and validate a registry file; the error names the offending entry."""

    try:
        return LanguageRegistry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"invalid language registry {path.name}: {exc}") from exc


LANGUAGES: Final[tuple[Language, ...]] = load_language_registry().languages


def language_tags() -> tuple[str, ...]:
    return tuple(language.tag for language in LANGUAGES)


def get_language(tag: str) -> Language:
    for language in LANGUAGES:
        if language.tag == tag:
            return language
    raise KeyError(tag)


def allowed_scripts(tag: str) -> frozenset[str]:
    """Writing systems whose words belong in text written in this language."""

    return frozenset(get_language(tag).scripts)
