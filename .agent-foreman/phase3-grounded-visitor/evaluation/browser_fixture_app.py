"""Evaluation-only real-app fixture for Phase 3 browser falsification."""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reponpc.api.public import SetupState
from reponpc.chat.answers import Citation
from reponpc.chat.service import ChatDelivery
from reponpc.main import create_app
from reponpc.providers import ProviderUsage

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / ".pytest-tmp" / "phase3-browser-public"
PUBLIC.mkdir(parents=True, exist_ok=True)


def localized_profile(locale: str) -> dict[str, object]:
    chinese = locale == "zh-TW"
    return {
        "profile": {
            "display_name": "Fixture Owner",
            "headline": "可驗證的工程作品集" if chinese else "Verifiable engineering portfolio",
            "bio": "以固定證據介紹專案。"
            if chinese
            else "Projects explained with immutable evidence.",
            "location": "Taipei",
            "avatar_url": None,
            "links": [{"label": "GitHub", "url": "https://github.com/example"}],
        },
        "repositories": [
            {
                "slug": "owner/repo",
                "summary": "混合檢索專案" if chinese else "Hybrid retrieval project",
                "role": "作品集聲明" if chinese else "Portfolio assertion",
                "tags": ["Python", "TypeScript"],
                "demo_url": "https://example.com/demo",
            }
        ],
        "suggested_questions": ["這個專案如何使用檢索？"]
        if chinese
        else ["How does this project use retrieval?"],
    }


profile_document = {
    "schema_version": 1,
    "locales": {locale: localized_profile(locale) for locale in ("zh-TW", "en")},
    "character": {"mode": "builtin", "asset_url": "/api/public/character.png", "revision": 1},
    "index": {
        "version": "fixture-index",
        "built_at": datetime(2026, 8, 12, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "repository_count": 1,
    },
}
(PUBLIC / "profile.json").write_text(json.dumps(profile_document), encoding="utf-8")


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def fixture_sprite() -> bytes:
    width, height = 128, 224
    rows = []
    colors = (
        (91, 75, 255, 255),
        (46, 125, 50, 255),
        (0, 121, 107, 255),
        (245, 124, 0, 255),
        (198, 40, 40, 255),
        (123, 31, 162, 255),
        (84, 110, 122, 255),
    )
    for y in range(height):
        row_color = colors[y // 32]
        pixels = bytearray()
        for x in range(width):
            frame = x // 32
            border = x % 32 in {0, 31} or y % 32 in {0, 31}
            color = (
                (31, 31, 31, 255)
                if border
                else tuple(max(0, channel - frame * 12) for channel in row_color[:3]) + (255,)
            )
            pixels.extend(color)
        rows.append(b"\0" + bytes(pixels))
    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        signature
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + png_chunk(b"IEND", b"")
    )


(PUBLIC / "character.png").write_bytes(fixture_sprite())


@dataclass
class BrowserChatService:
    def answer(self, **kwargs: object) -> ChatDelivery:
        locale = str(kwargs["locale"])
        answer = (
            "檢索由固定證據支持。[S1]"
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
        return ChatDelivery(
            "fixture-index",  # type: ignore[arg-type]
            locale,  # type: ignore[arg-type]
            1,
            answer,
            (citation,),
            "stop",
            ProviderUsage(10, 5),
            False,
        )


app = create_app(
    setup_state=SetupState(
        index_ready=True,
        index_version="fixture-index",
        model_ready=True,
        model_provider="ollama",
        model_last_checked_at="2026-08-12T00:00:00Z",
        public_directory=PUBLIC,
    ),
    chat_service=BrowserChatService(),  # type: ignore[arg-type]
    web_dist=ROOT / "apps" / "web" / "dist",
)
