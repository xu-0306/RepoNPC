"""ADR-079 registry validation and the shared locale contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from reponpc.config.models import Locale
from reponpc.i18n import languages
from reponpc.i18n.catalog import SUPPORTED_LOCALES

ENTRY: dict[str, Any] = languages.get_language("es").model_dump(
    mode="json", by_alias=True, exclude_none=True
)


def write_registry(tmp_path: Path, *entries: dict[str, Any], version: int = 1) -> Path:
    path = tmp_path / "languages.json"
    path.write_text(json.dumps({"version": version, "languages": list(entries)}), encoding="utf-8")
    return path


def test_registry_lists_exactly_the_locales_the_rest_of_the_code_knows() -> None:
    assert Locale is languages.Locale
    adapter = TypeAdapter(Locale)
    for tag in languages.language_tags():
        assert adapter.validate_python(tag) == tag
    with pytest.raises(ValidationError, match="unknown language tag"):
        adapter.validate_python("not-a-registry-tag")


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
        ([{**ENTRY, "english_name": ""}], 1, "english_name"),
        ([{**ENTRY, "english_name": "x" * 41}], 1, "english_name"),
        ([{**ENTRY, "title_max": 0}], 1, "title_max"),
        ([{**ENTRY, "title_max": 201}], 1, "title_max"),
        ([{**ENTRY, "chrome": "es"}], 1, "chrome"),
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


@pytest.mark.parametrize(
    ("derive", "needle"),
    [
        ({"from": "xx", "converter": "tw2sp"}, "unknown derive source"),
        ({"from": ENTRY["tag"], "converter": "tw2sp"}, "itself"),
        ({"from": ENTRY["tag"], "converter": "unknown"}, "unknown converter"),
        ({"from": ENTRY["tag"], "converter": "tw2sp", "extra": 1}, "extra"),
        ({"source": ENTRY["tag"], "converter": "tw2sp"}, "from"),
    ],
)
def test_invalid_derivation_is_rejected(
    tmp_path: Path, derive: dict[str, Any], needle: str
) -> None:
    with pytest.raises(ValueError, match=needle):
        languages.load_language_registry(write_registry(tmp_path, {**ENTRY, "derive": derive}))


def test_registry_helpers_follow_every_entry() -> None:
    for language in languages.LANGUAGES:
        assert languages.is_language_tag(language.tag)
        assert languages.english_name(language.tag) == language.english_name
        assert languages.title_max(language.tag) == language.title_max > 0
        assert languages.chrome_locale(language.tag) == language.chrome
        assert language.chrome in SUPPORTED_LOCALES
        for source in languages.LANGUAGES:
            expected = (
                language.derive.converter
                if language.derive is not None and language.derive.source == source.tag
                else None
            )
            assert languages.converter_for(source.tag, language.tag) == expected
    assert not languages.is_language_tag("not-a-registry-tag")
    assert not languages.is_language_tag(None)


def test_derivation_alias_and_frozen_models() -> None:
    for language in languages.LANGUAGES:
        if language.derive is not None:
            assert language.derive.model_dump(by_alias=True)["from"] == language.derive.source
            with pytest.raises(ValidationError, match="frozen"):
                language.derive.converter = "tw2sp"
        with pytest.raises(ValidationError, match="frozen"):
            language.title_max = 1


def test_config_site_set_is_one_to_n_unique_registry_tags_with_the_default_inside() -> None:
    from reponpc.config.models import LocalesConfig

    tags = languages.language_tags()
    for language in languages.LANGUAGES:
        single = LocalesConfig(default=language.tag, supported=(language.tag,))
        assert single.supported == (language.tag,)
    full = LocalesConfig(default=tags[-1], supported=tags)
    assert full.supported == tags
    rotated = (*tags[1:], tags[0])
    assert LocalesConfig(default=tags[0], supported=rotated).supported == rotated

    with pytest.raises(ValidationError, match="empty"):
        LocalesConfig(default=tags[0], supported=())
    with pytest.raises(ValidationError, match="unique"):
        LocalesConfig(default=tags[0], supported=(tags[0], tags[0]))
    with pytest.raises(ValidationError, match="default"):
        LocalesConfig(default=tags[0], supported=tags[1:])
    with pytest.raises(ValidationError):
        LocalesConfig(default="xx", supported=("xx",))
    with pytest.raises(ValidationError):
        LocalesConfig(default=tags[0], supported=(tags[0], "xx"))


def test_api_models_keep_their_phase_a_language_boundary() -> None:
    from reponpc.api.admin import FaqQueueRequest
    from reponpc.api.public import PublicChatRequest

    for language in languages.LANGUAGES:
        assert FaqQueueRequest(locale=language.tag).locale == language.tag
        if language.tag not in SUPPORTED_LOCALES:
            with pytest.raises(ValidationError):
                PublicChatRequest(message="Project?", locale=language.tag)
    for unknown in ("unknown", " " + languages.LANGUAGES[0].tag):
        with pytest.raises(ValidationError):
            FaqQueueRequest(locale=unknown)
