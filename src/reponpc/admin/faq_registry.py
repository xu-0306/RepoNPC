"""Finite bilingual standard questions and claim editor defaults."""

# ruff: noqa: RUF001 -- Traditional Chinese product copy uses native punctuation.

from typing import Literal

Locale = Literal["zh-TW", "en"]
ClaimKind = Literal["role", "responsibility", "achievement", "context"]

# This finite product registry is shared by queue creation and claim shortcuts.
STANDARD_QUESTIONS: tuple[tuple[str, ClaimKind, dict[Locale, str]], ...] = (
    (
        "responsibility",
        "responsibility",
        {
            "zh-TW": "作者在這些專案中負責什麼？",
            "en": "What was the owner's responsibility in these projects?",
        },
    ),
    (
        "built_work",
        "responsibility",
        {
            "zh-TW": "作者實作了哪些功能或作品？",
            "en": "What did the owner build in these projects?",
        },
    ),
    (
        "duration",
        "context",
        {
            "zh-TW": "作者參與這些專案的期間是多久？",
            "en": "When and for how long did the owner participate in these projects?",
        },
    ),
    (
        "team_context",
        "context",
        {
            "zh-TW": "這些專案的團隊與合作背景是什麼？",
            "en": "What was the team and collaboration context of these projects?",
        },
    ),
    (
        "outcome",
        "achievement",
        {
            "zh-TW": "這些專案有哪些可確認的成果？",
            "en": "What outcomes are supported by evidence for these projects?",
        },
    ),
    (
        "technologies",
        "context",
        {"zh-TW": "這些專案使用哪些技術？", "en": "Which technologies do these projects use?"},
    ),
)
