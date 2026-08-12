"""Fresh evaluator-owned fixture serving the production visitor app."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reponpc.api.public import SetupState
from reponpc.chat.answers import Citation
from reponpc.chat.service import ChatDelivery
from reponpc.main import create_app

ROOT = Path(__file__).resolve().parents[4]
PUBLIC = Path(__file__).with_name("runtime-browser-public")
PUBLIC.mkdir(parents=True, exist_ok=True)


def localized(locale: str) -> dict[str, object]:
    zh = locale == "zh-TW"
    return {
        "profile": {
            "display_name": "Fresh Fixture Owner",
            "headline": "可驗證的工程作品集" if zh else "Verifiable engineering portfolio",
            "bio": "以不可變證據說明專案。" if zh else "Projects explained with immutable evidence.",
            "location": "Taipei",
            "avatar_url": None,
            "links": [{"label": "GitHub", "url": "https://github.com/example"}],
        },
        "repositories": [
            {
                "slug": "owner/repo",
                "summary": "混合檢索專案" if zh else "Hybrid retrieval project",
                "role": "作品集聲明" if zh else "Portfolio assertion",
                "tags": ["Python", "TypeScript"],
                "demo_url": "https://example.com/demo",
            }
        ],
        "suggested_questions": ["這個專案如何使用檢索？"] if zh else ["How does this project use retrieval?"],
    }


document = {
    "schema_version": 1,
    "locales": {locale: localized(locale) for locale in ("zh-TW", "en")},
    "character": {"mode": "builtin", "asset_url": "/api/public/character.png", "revision": 1},
    "index": {
        "version": "fresh-index",
        "built_at": datetime(2026, 8, 12, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "repository_count": 1,
    },
}
(PUBLIC / "profile.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
(PUBLIC / "character.png").write_bytes(
    bytes.fromhex("89504e470d0a1a0a0000000d4948445200000080000000e00806000000")
)


@dataclass
class Chat:
    def answer(self, **kwargs: object) -> ChatDelivery:
        locale = str(kwargs["locale"])
        answer = (
            "檢索由不可變證據支持。[S1]"
            if locale == "zh-TW"
            else "Retrieval is supported by immutable evidence. [S1]"
        )
        citation = Citation(
            "S1",
            "E_" + "a" * 24,
            "REPOSITORY_FACT",
            "owner/repo",
            "b" * 40,
            "src/search.py",
            10,
            12,
            "Retrieval implementation",
            "Hybrid retrieval combines lexical and vector candidates.",
            "https://github.com/owner/repo/blob/" + "b" * 40 + "/src/search.py#L10-L12",
        )
        return ChatDelivery("fresh-index", locale, 1, answer, (citation,), "stop", None, False)  # type: ignore[arg-type]


app = create_app(
    setup_state=SetupState(
        index_ready=True,
        index_version="fresh-index",
        model_ready=True,
        model_provider="ollama",
        model_last_checked_at="2026-08-12T00:00:00Z",
        public_directory=PUBLIC,
    ),
    chat_service=Chat(),  # type: ignore[arg-type]
    web_dist=ROOT / "apps/web/dist",
)
