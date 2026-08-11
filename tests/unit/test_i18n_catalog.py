from __future__ import annotations

from string import Formatter

import pytest

from reponpc.i18n.catalog import MESSAGES, SUPPORTED_LOCALES, translate


def _placeholders(template: str) -> set[str]:
    return {
        field_name for _, field_name, _, _ in Formatter().parse(template) if field_name is not None
    }


def test_catalog_has_exactly_the_supported_bilingual_locales() -> None:
    assert SUPPORTED_LOCALES == ("zh-TW", "en")
    assert set(MESSAGES) == set(SUPPORTED_LOCALES)


def test_catalog_keys_and_placeholders_are_identical_between_locales() -> None:
    zh_tw_messages = MESSAGES["zh-TW"]
    en_messages = MESSAGES["en"]

    assert set(zh_tw_messages) == {
        "index_unavailable",
        "service_not_ready",
        "validation_error",
    }
    assert set(en_messages) == set(zh_tw_messages)
    assert {key: _placeholders(zh_tw_messages[key]) for key in zh_tw_messages} == {
        key: _placeholders(en_messages[key]) for key in en_messages
    }


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("zh-TW", "服務「chat」尚未就緒。"),
        ("en", "The chat service is not ready."),
    ],
)
def test_translate_formats_declared_placeholders(locale: str, expected: str) -> None:
    assert translate(locale, "service_not_ready", service="chat") == expected


def test_translate_formats_multiple_declared_placeholders() -> None:
    assert translate("en", "validation_error", field="locale", reason="is invalid") == (
        "Validation failed for locale: is invalid."
    )


@pytest.mark.parametrize(
    ("locale", "key"),
    [("fr", "index_unavailable"), ("en", "not_a_message")],
)
def test_translate_rejects_unsupported_locale_and_unknown_key(locale: str, key: str) -> None:
    with pytest.raises(ValueError):
        translate(locale, key)


def test_translate_rejects_missing_or_undeclared_placeholders() -> None:
    with pytest.raises(ValueError, match="Missing placeholders"):
        translate("en", "service_not_ready")

    with pytest.raises(ValueError, match="Unexpected placeholders"):
        translate("en", "index_unavailable", service="chat")
