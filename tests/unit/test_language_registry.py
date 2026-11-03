"""ADR-078 language registry: load rules and agreement with the closed locale pair."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from reponpc.config.models import Locale
from reponpc.i18n import languages
from reponpc.i18n.catalog import SUPPORTED_LOCALES

ENTRY: dict[str, Any] = {
    "tag": "es",
    "endonym": "Español",
    "scripts": ["LATIN"],
    "direction": "ltr",
    "match": ["es"],
}


def write_registry(tmp_path: Path, *entries: dict[str, Any], version: int = 1) -> Path:
    path = tmp_path / "languages.json"
    path.write_text(json.dumps({"version": version, "languages": list(entries)}), encoding="utf-8")
    return path


def test_registry_lists_exactly_the_locales_the_rest_of_the_code_knows() -> None:
    # Phase A (ADR-078): the registry must not drift from the closed locale pair.
    assert set(languages.language_tags()) == set(get_args(Locale)) == set(SUPPORTED_LOCALES)


def test_allowed_scripts_keep_the_values_the_old_hardcoded_table_held() -> None:
    assert languages.allowed_scripts("zh-TW") == {"CJK", "BOPOMOFO", "LATIN"}
    assert languages.allowed_scripts("en") == {"LATIN"}


def test_every_entry_matches_itself_and_prefixes_are_unique() -> None:
    prefixes = [prefix for language in languages.LANGUAGES for prefix in language.match]
    assert len(prefixes) == len(set(prefixes))
    for language in languages.LANGUAGES:
        assert language.tag.lower() in language.match
        assert languages.get_language(language.tag) is language


def test_unknown_tag_raises_key_error() -> None:
    with pytest.raises(KeyError):
        languages.get_language("xx")


def test_a_valid_extra_language_loads_and_the_packaged_file_still_validates(tmp_path: Path) -> None:
    registry = languages.load_language_registry(write_registry(tmp_path, ENTRY))
    assert registry.languages[0].endonym == "Español"
    assert languages.REGISTRY_PATH.is_file()
    assert languages.load_language_registry().languages == languages.LANGUAGES


@pytest.mark.parametrize(
    ("entries", "version", "needle"),
    [
        ([ENTRY, {**ENTRY, "match": ["es", "es-419"]}], 1, "unique"),
        ([ENTRY], 2, "version"),
        ([{**ENTRY, "endonym": ""}], 1, "endonym"),
        ([{**ENTRY, "scripts": ["KLINGON"]}], 1, "KLINGON"),
        ([{**ENTRY, "scripts": []}], 1, "scripts"),
        ([{**ENTRY, "tag": "Spanish!"}], 1, "tag"),
        ([{**ENTRY, "match": ["ES"]}], 1, "match"),
        ([{**ENTRY, "match": ["spa"]}], 1, "match"),
        ([{**ENTRY, "direction": "up"}], 1, "direction"),
        ([{**ENTRY, "unexpected": 1}], 1, "unexpected"),
        (
            [ENTRY, {**ENTRY, "tag": "es-MX", "match": ["es-mx", "es"]}],
            1,
            "claimed by es and es-MX",
        ),
        ([], 1, "languages"),
    ],
)
def test_invalid_registry_is_rejected_and_names_the_problem(
    tmp_path: Path, entries: list[dict[str, Any]], version: int, needle: str
) -> None:
    path = write_registry(tmp_path, *entries, version=version)
    with pytest.raises(ValueError, match=needle):
        languages.load_language_registry(path)


def test_malformed_json_is_a_value_error(tmp_path: Path) -> None:
    path = tmp_path / "languages.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"languages\.json"):
        languages.load_language_registry(path)
