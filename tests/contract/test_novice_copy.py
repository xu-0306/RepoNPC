"""Guard the guided onboarding presentation contract while copy evolves."""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[2]
VIEW_PATH = REPOSITORY_ROOT / "apps/web/src/features/admin/GuidedOnboardingView.tsx"


def _source() -> str:
    return VIEW_PATH.read_text(encoding="utf-8")


def _copy_block(source: str, locale: str) -> str:
    match = re.search(rf'  ["\']?{re.escape(locale)}["\']?: \{{', source)
    assert match is not None
    start = match.start()
    end = source.index("\n  },", start) + len("\n  },")
    return source[start:end]


def _copy_strings(block: str) -> list[str]:
    return re.findall(r'"((?:[^"\\]|\\.)*)"', block)


def test_bilingual_copy_uses_plain_evidence_glossary() -> None:
    source = _source()
    chinese = _copy_strings(_copy_block(source, "zh-TW"))
    english = _copy_strings(_copy_block(source, "en"))
    chinese_text = " ".join(chinese)
    english_text = " ".join(english)

    assert "專案中可確認的資訊" in chinese_text
    assert "AI 推論" in chinese_text
    assert "你已確認的個人貢獻" in chinese_text
    assert "一句話介紹自己" in chinese_text
    assert "repository" not in chinese_text.lower()
    assert "facts" not in chinese_text.lower()
    assert "owner assertion" not in chinese_text.lower()
    assert "owner statement" not in chinese_text.lower()
    assert "evidence" not in chinese_text.lower()

    assert "Project information you can verify" in english_text
    assert "AI inferences" in english_text
    assert "your confirmed contribution" in english_text.lower()
    assert "One-line introduction" in english_text
    assert "repository" not in english_text.lower()
    assert "owner assertion" not in english_text.lower()
    assert "owner statement" not in english_text.lower()


def test_copy_preserves_manual_route_confirmation_and_bilingual_warnings() -> None:
    source = _source()
    chinese = " ".join(_copy_strings(_copy_block(source, "zh-TW")))
    english = " ".join(_copy_strings(_copy_block(source, "en")))

    assert "略過分析\uff0c手動填寫貢獻" in chinese
    assert "專案內容無法證明你的身分或角色" in chinese
    assert "不要讓模型替你猜測個人資料" in chinese
    assert "請提供中英文內容" in chinese
    assert "Skip analysis and enter contribution manually" in english
    assert "project content cannot establish your identity or role" in english
    assert "do not ask a model to guess personal profile details" in english
    assert "Supply both languages" in english


def test_view_preserves_props_and_evidence_class_attributes() -> None:
    source = _source()
    match = re.search(
        r"export function GuidedOnboardingView\(\{(?P<props>.*?)\}: GuidedOnboardingViewProps",
        source,
        flags=re.DOTALL,
    )
    assert match is not None

    expected_props = (
        "locale",
        "state",
        "busy",
        "errorCode",
        "batchAnalysisView",
        "batchAnalysisTerminal",
        "batchAnalysisActive",
        "batchCanCreate",
        "batchCreatePending",
        "modelSetupView",
        "providerStatus",
        "providerStatusPending",
        "onAction",
        "onDiscover",
        "onResolve",
        "onAnalyze",
        "onCreateBatch",
        "onRefreshProviderStatus",
        "onSuggestContribution",
        "onCreateDraft",
        "onCopyDraft",
        "onDownloadDraft",
        "workspaceStatus",
    )
    prop_block = match.group("props")
    assert all(re.search(rf"\b{re.escape(prop)}\b", prop_block) for prop in expected_props)

    assert source.count('data-evidence-class="REPOSITORY_FACT"') == 1
    assert source.count('data-evidence-class="MODEL_INFERENCE"') == 1
    assert source.count('data-evidence-class="OWNER_ASSERTION"') == 1
