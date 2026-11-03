"""Validated, fail-closed chat trust data for every registered language."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from reponpc.i18n.languages import is_language_tag, language_tags

POLICY_DIR = Path(__file__).with_name("policy")
_MESSAGE_KEYS = frozenset(
    {"no_match", "no_match_without_suggestions", "temporary_no_match", "owner_prefix"}
)


class PolicyDataError(ValueError):
    """Policy data is missing or invalid; messages never include file contents."""


@dataclass(frozen=True, slots=True)
class PersonPolicy:
    references: tuple[str, ...]
    exclusions: tuple[str, ...]


def _mapping(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError, UnicodeError, yaml.YAMLError:
        raise PolicyDataError(f"{path.name}: cannot read valid YAML") from None
    if not isinstance(raw, dict):
        raise PolicyDataError(f"{path.name}: policy must be a mapping")
    return raw


def _terms(value: object, path: Path, *, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(term, str) for term in value):
        raise PolicyDataError(f"{path.name}: terms must be lists of strings")
    result = tuple(term.strip() for term in value if term.strip())
    if required and not result:
        raise PolicyDataError(f"{path.name}: terms must be non-empty")
    return result


@cache
def _person_policy(path: Path) -> PersonPolicy:
    raw = _mapping(path)
    return PersonPolicy(
        _terms(raw.get("references"), path),
        _terms(raw.get("exclusions", []), path, required=False),
    )


def person_policy(tag: str) -> PersonPolicy:
    if not is_language_tag(tag):
        raise PolicyDataError("person policy language is not registered")
    return _person_policy(POLICY_DIR / f"person_reference.{tag}.yml")


@cache
def _inflation_policy(path: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    groups = _mapping(path).get("groups")
    if not isinstance(groups, dict) or not groups:
        raise PolicyDataError(f"{path.name}: groups must be a non-empty mapping")
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for group, locales in groups.items():
        if not isinstance(group, str) or not isinstance(locales, dict) or not locales:
            raise PolicyDataError(f"{path.name}: each group must map languages to terms")
        if any(not isinstance(tag, str) for tag in locales):
            raise PolicyDataError(f"{path.name}: language keys must be strings")
        result[group] = {tag: _terms(values, path) for tag, values in locales.items()}
    return result


@cache
def _inflation_groups(path: Path) -> dict[str, tuple[str, ...]]:
    return {
        group: tuple(
            sorted(
                {
                    unicodedata.normalize("NFKC", term).casefold()
                    for values in locales.values()
                    for term in values
                },
                key=lambda term: (-len(term), term),
            )
        )
        for group, locales in _inflation_policy(path).items()
    }


def inflation_groups() -> dict[str, tuple[str, ...]]:
    return _inflation_groups(POLICY_DIR / "inflation_terms.yml")


@cache
def _visitor_messages(path: Path) -> dict[str, dict[str, str]]:
    messages = _mapping(path).get("messages")
    if not isinstance(messages, dict) or not _MESSAGE_KEYS.issubset(messages):
        raise PolicyDataError(f"{path.name}: required visitor messages are missing")
    for texts in messages.values():
        if not isinstance(texts, dict) or not isinstance(texts.get("en"), str):
            raise PolicyDataError(f"{path.name}: every visitor message needs English text")
        if any(not isinstance(text, str) or not text.strip() for text in texts.values()):
            raise PolicyDataError(f"{path.name}: visitor messages must be non-empty strings")
    return messages


def visitor_message(tag: str, key: str) -> str:
    messages = _visitor_messages(POLICY_DIR / "visitor_messages.yml")
    if key not in messages:
        raise PolicyDataError("visitor message key is missing")
    return messages[key].get(tag, messages[key]["en"])


def validate_policy_data(tags: Iterable[str] | None = None) -> None:
    # Each factory validates current files even if an earlier app populated the caches.
    _person_policy.cache_clear()
    _inflation_policy.cache_clear()
    _inflation_groups.cache_clear()
    _visitor_messages.cache_clear()
    groups = _inflation_policy(POLICY_DIR / "inflation_terms.yml")
    for tag in language_tags() if tags is None else tags:
        person_policy(tag)
        if any(tag not in locales for locales in groups.values()):
            raise PolicyDataError(f"inflation_terms.yml: missing terms for {tag}")
    _visitor_messages(POLICY_DIR / "visitor_messages.yml")
