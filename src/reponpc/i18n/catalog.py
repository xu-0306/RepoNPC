"""Localized, safe user-facing messages shared by API and UI adapters."""

from __future__ import annotations

from collections.abc import Mapping
from string import Formatter
from types import MappingProxyType
from typing import Final

SUPPORTED_LOCALES: Final[tuple[str, str]] = ("zh-TW", "en")

_MESSAGE_CATALOG: Final[dict[str, dict[str, str]]] = {
    "zh-TW": {
        "index_unavailable": "索引目前無法使用。",
        "service_not_ready": "服務「{service}」尚未就緒。",
        "validation_error": "欄位「{field}」驗證失敗：{reason}。",  # noqa: RUF001
    },
    "en": {
        "index_unavailable": "The index is currently unavailable.",
        "service_not_ready": "The {service} service is not ready.",
        "validation_error": "Validation failed for {field}: {reason}.",
    },
}

MESSAGES: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {locale: MappingProxyType(messages) for locale, messages in _MESSAGE_CATALOG.items()}
)


def _placeholders(template: str) -> frozenset[str]:
    """Return the named replacement fields accepted by a catalog template."""

    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name is not None:
            if not field_name.isidentifier():
                raise ValueError("Catalog placeholders must be simple identifiers.")
            fields.add(field_name)
    return frozenset(fields)


def translate(locale: str, key: str, /, **placeholders: object) -> str:
    """Format a localized catalog message using its declared placeholders only."""

    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"Unsupported locale: {locale!r}")

    messages = MESSAGES[locale]
    if key not in messages:
        raise ValueError(f"Unknown message key: {key!r}")

    template = messages[key]
    expected = _placeholders(template)
    supplied = frozenset(placeholders)
    if missing := expected - supplied:
        raise ValueError(f"Missing placeholders for {key!r}: {sorted(missing)!r}")
    if unexpected := supplied - expected:
        raise ValueError(f"Unexpected placeholders for {key!r}: {sorted(unexpected)!r}")

    return template.format(**placeholders)
