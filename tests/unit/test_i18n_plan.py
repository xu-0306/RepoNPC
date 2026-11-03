"""ADR-079 site-set planning: written versus derived languages."""

from __future__ import annotations

from itertools import permutations

import pytest

from reponpc.i18n import languages
from reponpc.i18n.plan import (
    ANALYSIS_LOCALES,
    LanguagePlan,
    LocaleNotEnabledError,
    plan_languages,
    require_enabled,
)

ORDERED_SUBSETS = [
    subset
    for size in range(1, len(languages.language_tags()) + 1)
    for subset in permutations(languages.language_tags(), size)
]


def test_documented_examples() -> None:
    assert plan_languages(["zh-TW", "zh-CN", "en"]) == LanguagePlan(
        ("zh-TW", "en"), (("zh-CN", "zh-TW"),)
    )
    assert plan_languages(["en", "zh-CN", "zh-TW"]) == LanguagePlan(
        ("en", "zh-CN"), (("zh-TW", "zh-CN"),)
    )
    assert plan_languages(["zh-TW", "en"]) == LanguagePlan(("zh-TW", "en"), ())
    assert plan_languages(["es"]) == LanguagePlan(("es",), ())


@pytest.mark.parametrize("site", ORDERED_SUBSETS, ids="-".join)
def test_every_ordered_subset_is_partitioned(site: tuple[str, ...]) -> None:
    plan = plan_languages(site)
    assert sorted((*plan.written, *(target for target, _ in plan.derived))) == sorted(site)
    assert plan.written, "the first language is always written"
    for target, source in plan.derived:
        assert languages.converter_for(source, target) is not None
        assert source in plan.written
        assert site.index(source) < site.index(target)


@pytest.mark.parametrize("site", [[], ["en", "en"], ["zh-TW", "zh-TW", "en"]])
def test_an_empty_or_repeating_set_is_rejected(site: list[str]) -> None:
    with pytest.raises(ValueError, match="unique"):
        plan_languages(site)


def test_an_unknown_tag_is_rejected() -> None:
    with pytest.raises(KeyError):
        plan_languages(["en", "xx"])


def test_analysis_locales_are_registry_languages_written_by_the_model() -> None:
    assert set(ANALYSIS_LOCALES) <= set(languages.language_tags())
    assert plan_languages(ANALYSIS_LOCALES).derived == ()


def test_require_enabled_accepts_members_and_names_the_rest() -> None:
    assert require_enabled("es", ("en", "es")) == "es"
    with pytest.raises(LocaleNotEnabledError, match="zh-CN"):
        require_enabled("zh-CN", iter(("en", "es")))
    assert issubclass(LocaleNotEnabledError, ValueError)
