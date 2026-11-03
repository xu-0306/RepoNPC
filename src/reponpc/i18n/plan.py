"""Which languages of a site set are written and which are derived (ADR-079)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from reponpc.i18n.languages import get_language

# The durable repository analysis writes inference text in these languages whatever the site set
# is, so its cache never depends on the set. Other site languages of an inference come from
# conversion or from profile translation.
ANALYSIS_LOCALES: Final = ("zh-TW", "en")


class LocaleNotEnabledError(ValueError):
    """A registry language that the active site set does not include."""


@dataclass(frozen=True, slots=True)
class LanguagePlan:
    written: tuple[str, ...]
    # (target, source) pairs in site order; the source is always in `written`.
    derived: tuple[tuple[str, str], ...]


def plan_languages(site: Sequence[str]) -> LanguagePlan:
    """Split a site set into written languages and ones converted from an earlier written one."""

    if not site or len(set(site)) != len(site):
        raise ValueError("a site set is a non-empty list of unique language tags")
    written: list[str] = []
    derived: list[tuple[str, str]] = []
    for tag in site:
        derive = get_language(tag).derive
        if derive is not None and derive.source in written:
            derived.append((tag, derive.source))
        else:
            written.append(tag)
    return LanguagePlan(tuple(written), tuple(derived))


def require_enabled(locale: str, enabled: Iterable[str]) -> str:
    """Return `locale` when the site set includes it; API layers map the error to a 4xx."""

    if locale not in tuple(enabled):
        raise LocaleNotEnabledError(f"language {locale} is not enabled for this site")
    return locale
