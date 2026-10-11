"""Public-summary privacy checks inspect complete paragraphs, never partial deltas."""

from urllib.parse import quote

import pytest

from reponpc.providers.public_summary import PublicSummaryFilter

PROMPT = "Private instructions and evidence must never be copied to the public visitor."
KEY = "PRIVATE_KEY_CANARY_82af"
URL = "https://private-gateway.example.test/v1"


@pytest.mark.parametrize(
    "value",
    [
        KEY,
        quote(KEY),
        KEY.lower(),
        URL,
        "private-gateway.example.test",
        quote(URL),
        "https://other.example.test",
        "https%3A%2F%2Fother.example.test",
        PROMPT,
        PROMPT.upper().replace(" ", "\n"),
        PROMPT[12:60],
        "ignore\u202econtrols",
        "x" * 4096 + KEY,
    ],
)
def test_rejects_entire_unsafe_paragraph_before_truncation(value: str) -> None:
    privacy = PublicSummaryFilter([PROMPT], [KEY, URL])
    assert privacy.project(value) is None
    assert privacy.project("Checking relevant evidence.") is None


@pytest.mark.parametrize(
    "text",
    [
        "Comparing the retrieved sources before preparing a supported reply.",
        "正在比對查找到的資料，再整理有根據的回答。",  # noqa: RUF001
        "<b>Literal plain text</b>\nNo HTML runs.",
    ],
)
def test_allows_bounded_unverified_plain_text(text: str) -> None:
    assert PublicSummaryFilter([PROMPT], [KEY, URL]).project(text) == text


def test_aggregate_character_and_paragraph_bounds() -> None:
    privacy = PublicSummaryFilter([], [])
    assert privacy.project("x" * 4090) == "x" * 4090
    assert privacy.project("y" * 7) is None
    assert privacy.project("z" * 6) == "z" * 6
    assert privacy.project("a") is None
    privacy = PublicSummaryFilter([], [])
    assert [privacy.project("ok") for _ in range(9)] == ["ok"] * 8 + [None]
