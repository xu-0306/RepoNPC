"""Deterministic conversion follows the registry and preserves authoring tokens."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from reponpc.i18n.convert import _converter, can_convert, convert
from reponpc.i18n.languages import LANGUAGES, converter_for

TRADITIONAL = "就讀中興大學資管系，喜歡將自己的點子作為專案實現。軟體、程式、資訊與網路、記憶體。"  # noqa: RUF001
SIMPLIFIED = "就读中兴大学资管系，喜欢将自己的点子作为项目实现。软件、程序、信息与网络、内存。"  # noqa: RUF001
DERIVED = [language for language in LANGUAGES if language.derive is not None]


def test_known_conversion_in_both_directions() -> None:
    assert convert(TRADITIONAL, "zh-TW", "zh-CN") == SIMPLIFIED
    assert convert(SIMPLIFIED, "zh-CN", "zh-TW") == TRADITIONAL
    assert convert("網路程式", "zh-TW", "zh-CN") == "网络程序"


@pytest.mark.parametrize("language", DERIVED, ids=lambda language: language.tag)
@pytest.mark.parametrize(
    "text",
    [
        "",
        "ASCII only 123 / RepoNPC!",
        "https://example.org/owner/repo?q=Python&lang=en#readme `print('hi')` @handle owner/repo",
    ],
)
def test_every_derive_pair_preserves_ascii_and_tokens(language, text: str) -> None:
    source = language.derive.source
    assert convert(text, source, language.tag) == text
    assert convert(convert(text, source, language.tag), language.tag, source) == text
    assert _converter(language.derive.converter) is _converter(language.derive.converter)


@pytest.mark.parametrize("source", LANGUAGES, ids=lambda language: language.tag)
@pytest.mark.parametrize("target", LANGUAGES, ids=lambda language: language.tag)
def test_converter_capabilities_match_the_registry(source, target) -> None:
    expected = converter_for(source.tag, target.tag) is not None
    assert can_convert(source.tag, target.tag) is expected
    if not expected:
        with pytest.raises(ValueError, match=rf"{source.tag}.*{target.tag}"):
            convert("sample", source.tag, target.tag)


def test_unknown_pairs_are_rejected() -> None:
    assert not can_convert("en", "not-a-registry-tag")
    with pytest.raises(ValueError, match=r"en.*not-a-registry-tag"):
        convert("sample", "en", "not-a-registry-tag")


def test_only_the_conversion_wrapper_imports_opencc() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "reponpc"
    import_pattern = re.compile(r"^\s*(?:from\s+opencc\b|import\s+opencc\b)", re.MULTILINE)
    assert [
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if import_pattern.search(path.read_text(encoding="utf-8"))
    ] == ["i18n/convert.py"]
