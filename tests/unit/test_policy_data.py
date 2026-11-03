"""Registry-wide policy contracts, fail-closed loading and generated-data drift."""

# ruff: noqa: RUF001 -- Regression anchors preserve the original Traditional Chinese copy.

from __future__ import annotations

import shutil
import unicodedata
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from reponpc.chat import policy_data
from reponpc.chat.answers import _contains_person_reference, _render_v2_segment, no_match_answer
from reponpc.i18n.convert import convert
from reponpc.i18n.languages import LANGUAGES
from scripts.generate_zh_cn_policy import generate

POLICY_DIR = policy_data.POLICY_DIR
OLD_MESSAGES = {
    "no_match": {
        "zh-TW": "這個問題我在作品集裡找不到相關內容，可以試試下面這些問題。",
        "en": "I couldn't find anything about that in this portfolio. Try one of these questions.",
    },
    "no_match_without_suggestions": {
        "zh-TW": "這個問題我在作品集裡找不到相關內容。",
        "en": "I couldn't find anything about that in this portfolio.",
    },
    "temporary_no_match": {
        "zh-TW": "這次沒能整理出可靠的回答，請再問一次。",
        "en": "I couldn't put together a reliable answer this time. Please ask again.",
    },
    "owner_prefix": {
        "zh-TW": "{owner} 自述：{text}",
        "en": "In {owner}'s own words: {text}",
    },
}


@pytest.fixture
def policy_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "policy"
    shutil.copytree(POLICY_DIR, directory)
    monkeypatch.setattr(policy_data, "POLICY_DIR", directory)
    return directory


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, value: object) -> None:
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n"
    )


def snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in directory.glob("*.yml")}


def test_every_registered_language_has_complete_trust_data() -> None:
    policy_data.validate_policy_data()
    groups = read_yaml(POLICY_DIR / "inflation_terms.yml")["groups"]
    for language in LANGUAGES:
        policy = policy_data.person_policy(language.tag)
        assert policy is policy_data.person_policy(language.tag)
        assert policy.references
        assert all(term.strip() for term in (*policy.references, *policy.exclusions))
        assert len(policy.references) == len(set(policy.references))
        for locales in groups.values():
            terms = locales[language.tag]
            assert terms and all(isinstance(term, str) and term.strip() for term in terms)
            normalized = [unicodedata.normalize("NFKC", term).casefold() for term in terms]
            assert len(normalized) == len(set(normalized))


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_missing_person_policy_fails_closed(policy_copy: Path, language) -> None:
    (policy_copy / f"person_reference.{language.tag}.yml").unlink()
    with pytest.raises(policy_data.PolicyDataError, match=f"person_reference.{language.tag}"):
        policy_data.validate_policy_data()


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
@pytest.mark.parametrize("references", [[], [" ", "\t"], "not a list", [123]])
def test_invalid_person_references_fail_closed(policy_copy: Path, language, references) -> None:
    write_yaml(
        policy_copy / f"person_reference.{language.tag}.yml",
        {"references": references, "exclusions": []},
    )
    with pytest.raises(policy_data.PolicyDataError):
        policy_data.person_policy(language.tag)


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
@pytest.mark.parametrize("problem", ["missing", "empty", "wrong_type"])
def test_every_inflation_group_requires_each_language(
    policy_copy: Path, language, problem: str
) -> None:
    path = policy_copy / "inflation_terms.yml"
    raw = read_yaml(path)
    for locales in raw["groups"].values():
        if problem == "missing":
            locales.pop(language.tag)
        else:
            locales[language.tag] = [] if problem == "empty" else "not a list"
    write_yaml(path, raw)
    with pytest.raises(policy_data.PolicyDataError):
        policy_data.validate_policy_data()


@pytest.mark.parametrize("key", OLD_MESSAGES)
def test_every_visitor_message_needs_english(policy_copy: Path, key: str) -> None:
    path = policy_copy / "visitor_messages.yml"
    raw = read_yaml(path)
    raw["messages"][key].pop("en")
    write_yaml(path, raw)
    with pytest.raises(policy_data.PolicyDataError, match="English"):
        policy_data.validate_policy_data()


@pytest.mark.parametrize(
    "filename",
    [
        *(f"person_reference.{language.tag}.yml" for language in LANGUAGES),
        "inflation_terms.yml",
        "visitor_messages.yml",
    ],
)
@pytest.mark.parametrize("content", ["[invalid YAML", "- not a mapping\n"])
def test_invalid_yaml_or_document_shape_fails_closed(
    policy_copy: Path, filename: str, content: str
) -> None:
    (policy_copy / filename).write_text(content, encoding="utf-8", newline="\n")
    with pytest.raises(policy_data.PolicyDataError, match=filename):
        policy_data.validate_policy_data()


@pytest.mark.parametrize("filename", ["inflation_terms.yml", "visitor_messages.yml"])
def test_missing_shared_policy_fails_closed(policy_copy: Path, filename: str) -> None:
    (policy_copy / filename).unlink()
    with pytest.raises(policy_data.PolicyDataError, match=filename):
        policy_data.validate_policy_data()


def test_inflation_groups_are_the_normalized_longest_first_union(policy_copy: Path) -> None:
    path = policy_copy / "inflation_terms.yml"
    raw = read_yaml(path)
    group = next(iter(raw["groups"]))
    raw["groups"][group][LANGUAGES[0].tag].extend(["ＦＯＯ", "foo", "A longer term"])
    write_yaml(path, raw)
    groups = policy_data.inflation_groups()
    for key, locales in raw["groups"].items():
        expected = {
            unicodedata.normalize("NFKC", term).casefold()
            for terms in locales.values()
            for term in terms
        }
        assert set(groups[key]) == expected
        assert list(map(len, groups[key])) == sorted(map(len, expected), reverse=True)
    assert groups[group].count("foo") == 1


def test_visitor_messages_preserve_old_copy_and_fall_back_to_english(policy_copy: Path) -> None:
    path = policy_copy / "visitor_messages.yml"
    raw = read_yaml(path)
    for key in OLD_MESSAGES:
        raw["messages"][key] = {"en": OLD_MESSAGES[key]["en"]}
    write_yaml(path, raw)
    for language in LANGUAGES:
        for key in OLD_MESSAGES:
            assert policy_data.visitor_message(language.tag, key) == OLD_MESSAGES[key]["en"]
    assert policy_data.visitor_message("not-a-tag", "no_match") == OLD_MESSAGES["no_match"]["en"]
    with pytest.raises(policy_data.PolicyDataError):
        policy_data.visitor_message("en", "missing")


def test_original_visitor_copy_is_byte_identical() -> None:
    for key, locales in OLD_MESSAGES.items():
        for tag, text in locales.items():
            assert policy_data.visitor_message(tag, key).encode() == text.encode()


def test_zh_cn_data_matches_fresh_conversion() -> None:
    person = read_yaml(POLICY_DIR / "person_reference.zh-TW.yml")
    simplified = read_yaml(POLICY_DIR / "person_reference.zh-CN.yml")
    assert simplified == {
        key: [convert(term, "zh-TW", "zh-CN") for term in terms] for key, terms in person.items()
    }
    for filename, root_key in (
        ("inflation_terms.yml", "groups"),
        ("visitor_messages.yml", "messages"),
    ):
        entries = read_yaml(POLICY_DIR / filename)[root_key]
        for locales in entries.values():
            source = locales["zh-TW"]
            assert locales["zh-CN"] == (
                convert(source, "zh-TW", "zh-CN")
                if isinstance(source, str)
                else [convert(term, "zh-TW", "zh-CN") for term in source]
            )


def test_generator_is_idempotent_and_preserves_every_other_byte(policy_copy: Path) -> None:
    before = snapshot(policy_copy)
    generate(policy_copy)
    assert snapshot(policy_copy) == before
    generate(policy_copy)
    assert snapshot(policy_copy) == before


def test_generator_converts_updated_sources_without_changing_other_languages(
    policy_copy: Path,
) -> None:
    path = policy_copy / "inflation_terms.yml"
    raw = read_yaml(path)
    group = next(iter(raw["groups"]))
    raw["groups"][group]["zh-TW"].append("網路程式維護")
    write_yaml(path, raw)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("# Keep this unrelated comment.\n")
    generate(policy_copy)
    after = read_yaml(path)
    assert after["groups"][group]["zh-CN"][-1] == "网络程序维护"
    for key, locales in raw["groups"].items():
        for tag, values in locales.items():
            if tag != "zh-CN":
                assert after["groups"][key][tag] == values
    assert "# Keep this unrelated comment.\n" in path.read_text(encoding="utf-8")


def test_spanish_data_keeps_its_draft_review_notice() -> None:
    for filename in ("person_reference.es.yml", "inflation_terms.yml", "visitor_messages.yml"):
        comments = (POLICY_DIR / filename).read_text(encoding="utf-8").splitlines()[:2]
        assert any(line.startswith("# DRAFT:") and "Spanish speaker" in line for line in comments)


@pytest.mark.parametrize(
    ("tag", "personal", "neutral"),
    [
        ("zh-CN", "我维护这个项目", "这个项目使用 Python"),
        ("es", "yo mantengo este proyecto", "El proyecto usa Python"),
        ("zh-CN", "作者是工程师", "项目提供网络工具"),
        ("es", "La autora es ingeniera", "Este proyecto ofrece herramientas"),
    ],
)
def test_person_reference_smoke(tag: str, personal: str, neutral: str) -> None:
    assert _contains_person_reference(personal, tag, ())
    assert not _contains_person_reference(neutral, tag, ())


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_answer_copy_uses_the_language_policy(language) -> None:
    tag = language.tag
    assert no_match_answer(
        tag, reason="NO_EVIDENCE_SELECTED"
    ).answer_markdown == policy_data.visitor_message(tag, "no_match_without_suggestions")
    assert no_match_answer(
        tag, ("Python?",), reason="NO_EVIDENCE_SELECTED"
    ).answer_markdown == policy_data.visitor_message(tag, "no_match")
    assert no_match_answer(
        tag, reason="ENVELOPE_SCHEMA_INVALID"
    ).answer_markdown == policy_data.visitor_message(tag, "temporary_no_match")
    assert _render_v2_segment("person", "A project", ("S1",), tag, "Owner") == (
        policy_data.visitor_message(tag, "owner_prefix").format(owner="Owner", text="A project")
        + " [S1]"
    )


@pytest.mark.parametrize("language", LANGUAGES, ids=lambda language: language.tag)
def test_app_factory_aborts_when_any_language_policy_is_missing(
    policy_copy: Path, language
) -> None:
    from reponpc.main import create_app

    (policy_copy / f"person_reference.{language.tag}.yml").unlink()
    with pytest.raises(policy_data.PolicyDataError, match=f"person_reference.{language.tag}"):
        create_app()


def test_normal_app_factory_starts() -> None:
    from reponpc.main import create_app

    with TestClient(create_app()) as client:
        assert client.get("/healthz").json() == {"status": "alive"}
