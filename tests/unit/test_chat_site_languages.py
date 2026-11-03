"""Chat trust checks and prompts follow the registry and the active site set."""

from __future__ import annotations

from itertools import product

import pytest

from reponpc.admin.faq_registry import STANDARD_QUESTIONS
from reponpc.chat import answers
from reponpc.chat.policy_data import PolicyDataError, person_policy, visitor_message
from reponpc.chat.service import _provider_messages
from reponpc.i18n.convert import convert
from reponpc.i18n.languages import LANGUAGES, english_name, language_tags
from tests.unit.test_answer_validation import evidence


def _envelope(*segments):
    return {"segments": list(segments), "insufficient_evidence": False}


def _segment(text, kind="project", source="S1"):
    return {"kind": kind, "text": text, "source_ids": [source]}


@pytest.mark.parametrize("tag", language_tags())
def test_site_policy_order_and_prompt_language(tag):
    site = language_tags()[1:] + language_tags()[:1]
    expected = tuple(dict.fromkeys((tag, "en", *site)))
    assert answers._policy_locales(tag, site) == expected
    assert answers._policy_locales(tag, (tag,)) == tuple(dict.fromkeys((tag, "en")))
    for system_role in (True, False):
        messages = _provider_messages("Python?", tag, (), "", system_role=system_role)
        assert f"Respond in {english_name(tag)}." in messages[0].content


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_standard_faq_covers_registry_and_derived_copy_does_not_drift(language):
    for _key, _kind, texts in STANDARD_QUESTIONS:
        assert set(texts) == set(language_tags())
        assert texts[language.tag].strip()
        if language.derive is not None:
            source = language.derive.source
            assert texts[language.tag] == convert(texts[source], source, language.tag)


@pytest.mark.parametrize("tag", language_tags())
def test_project_wording_survives_while_owner_claims_and_inflation_drop(tag):
    neutral = {
        "zh-TW": ("開發工具提供其他功能。", "這個專案實作了 API。"),
        "zh-CN": ("开发工具提供其他功能。", "这个项目实现了 API。"),
        "en": ("The tool implements an API.", "Built with FastAPI."),
        "es": ("El proyecto implementa una API.", "Estas herramientas usan FastAPI."),
    }.get(tag, ("Python API.", "FastAPI."))
    selected = dict(
        [evidence("S1"), evidence("S2", evidence_class="OWNER_ASSERTION", content="Python API")]
    )
    for text in neutral:
        result = answers.validate_v2_answer(
            _envelope(_segment(text)), selected, tag, owner_name="Fixture", site_locales=(tag,)
        )
        assert not result.insufficient_evidence
        assert result.answer_markdown == text + " [S1]"
        assert result.discarded_segments == ()
    for reference in person_policy(tag).references:
        result = answers.validate_v2_answer(
            _envelope(_segment(neutral[0]), _segment(reference + " API.")),
            selected,
            tag,
            owner_name="Fixture",
            site_locales=(tag,),
        )
        assert result.answer_markdown == neutral[0] + " [S1]"
        assert "OWNER_ASSERTION_MISSING" in result.discarded_reason_codes
    from reponpc.chat.policy_data import POLICY_DIR, _inflation_policy

    groups = _inflation_policy(POLICY_DIR / "inflation_terms.yml")
    for locales in groups.values():
        for term in locales[tag]:
            result = answers.validate_v2_answer(
                _envelope(_segment(neutral[0]), _segment("{{owner}} " + term, "person", "S2")),
                selected,
                tag,
                owner_name="Fixture",
                site_locales=(tag,),
            )
            assert result.answer_markdown == neutral[0] + " [S1]"
            assert "INFLATION_UNSUPPORTED" in result.discarded_reason_codes


@pytest.mark.parametrize("visitor,source", tuple(product(language_tags(), repeat=2)))
def test_person_reference_in_another_site_language_is_reclassified(visitor, source):
    site = tuple(dict.fromkeys((visitor, source)))
    for reference in person_policy(source).references:
        result = answers.validate_v2_answer(
            _envelope(_segment("Python API."), _segment(reference + " API.")),
            dict([evidence("S1")]),
            visitor,
            owner_name="Fixture",
            site_locales=site,
        )
        assert result.answer_markdown == "Python API. [S1]"
        assert result.discarded_segments == (
            (1, ("OWNER_REFERENCE_MISSING", "OWNER_ASSERTION_MISSING")),
        )


@pytest.mark.parametrize("broken", language_tags())
def test_invalid_policy_fails_closed_even_for_explicit_owner_anchor(monkeypatch, broken):
    original = answers._load_locale_policy

    def load(tag):
        if tag == broken:
            raise PolicyDataError("invalid policy")
        return original(tag)

    monkeypatch.setattr(answers, "_load_locale_policy", load)
    visitor = language_tags()[-1]
    result = answers.validate_v2_answer(
        _envelope(_segment("{{owner}} uses Python.", "person")),
        dict([evidence("S1", evidence_class="OWNER_ASSERTION", content="Python")]),
        visitor,
        owner_name="Fixture",
        site_locales=language_tags(),
    )
    assert result.no_match_reason == "VALIDATION_UNEXPECTED"
    assert result.answer_markdown == visitor_message(visitor, "temporary_no_match")
    assert result.citations == result.suggested_questions == ()
