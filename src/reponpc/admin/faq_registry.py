"""Standard questions and claim editor defaults for every registry language."""

# ruff: noqa: RUF001 -- Traditional Chinese product copy uses native punctuation.

from typing import Literal

from reponpc.i18n.languages import Locale

ClaimKind = Literal["role", "responsibility", "achievement", "context"]

# This finite product registry is shared by queue creation and claim shortcuts.
# Spanish copy is a DRAFT awaiting review by a Spanish speaker.
STANDARD_QUESTIONS: tuple[tuple[str, ClaimKind, dict[Locale, str]], ...] = (
    (
        "responsibility",
        "responsibility",
        {
            "zh-TW": "作者在這些專案中負責什麼？",
            "zh-CN": "作者在这些项目中负责什么？",
            "en": "What was the owner's responsibility in these projects?",
            "es": "¿De qué se encargó el autor en estos proyectos?",
        },
    ),
    (
        "built_work",
        "responsibility",
        {
            "zh-TW": "作者實作了哪些功能或作品？",
            "zh-CN": "作者实作了哪些功能或作品？",
            "en": "What did the owner build in these projects?",
            "es": "¿Qué funciones u obras implementó el autor en estos proyectos?",
        },
    ),
    (
        "duration",
        "context",
        {
            "zh-TW": "作者參與這些專案的期間是多久？",
            "zh-CN": "作者参与这些项目的期间是多久？",
            "en": "When and for how long did the owner participate in these projects?",
            "es": "¿Cuándo y durante cuánto tiempo participó el autor en estos proyectos?",
        },
    ),
    (
        "team_context",
        "context",
        {
            "zh-TW": "這些專案的團隊與合作背景是什麼？",
            "zh-CN": "这些项目的团队与合作背景是什么？",
            "en": "What was the team and collaboration context of these projects?",
            "es": "¿Cuál fue el contexto del equipo y la colaboración en estos proyectos?",
        },
    ),
    (
        "outcome",
        "achievement",
        {
            "zh-TW": "這些專案有哪些可確認的成果？",
            "zh-CN": "这些项目有哪些可确认的成果？",
            "en": "What outcomes are supported by evidence for these projects?",
            "es": "¿Qué resultados de estos proyectos están respaldados por evidencia?",
        },
    ),
    (
        "technologies",
        "context",
        {
            "zh-TW": "這些專案使用哪些技術？",
            "zh-CN": "这些项目使用哪些技术？",
            "en": "Which technologies do these projects use?",
            "es": "¿Qué tecnologías utilizan estos proyectos?",
        },
    ),
)
