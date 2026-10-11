"""Focused checks for the centralized answer policy data."""

from __future__ import annotations

from pathlib import Path

import yaml

POLICY_DIR = Path(__file__).parents[2] / "src" / "reponpc" / "chat" / "policy"


def test_inflation_policy_is_cross_locale_and_has_no_duplicate_variants() -> None:
    policy = yaml.safe_load((POLICY_DIR / "inflation_terms.yml").read_text(encoding="utf-8"))

    groups = policy["groups"]
    assert groups
    for terms_by_locale in groups.values():
        assert set(terms_by_locale) >= {"en", "zh-TW"}
        terms = [term for values in terms_by_locale.values() for term in values]
        assert terms
        assert len(terms) == len({term.casefold() for term in terms})


def test_person_reference_policy_preserves_cjk_project_phrases() -> None:
    from reponpc.chat.answers import _contains_person_reference

    for text in ("開發工具", "這個專案實作了 API", "我們使用 API", "他們使用 API"):
        assert not _contains_person_reference(text, "zh-TW", ())
