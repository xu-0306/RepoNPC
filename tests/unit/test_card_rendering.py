from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

import reponpc.cards.render as card_render
from reponpc.cards.assets import validate_sprite
from reponpc.cards.render import (
    CardCopy,
    CardPalette,
    CardRenderError,
    render_card_assets,
    render_readme_snippet,
)


def _sprite() -> bytes:
    image = Image.new("RGBA", (128, 224), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 32 + 4, row * 32 + 4), (80, 90, 100, 255))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_card_variants_are_valid_static_safe_and_escaped() -> None:
    assets = render_card_assets(
        copy=CardCopy(
            display_name='</text><script>alert("x")</script>',
            headline="Evidence & owner <facts>",
            call_to_action="Ask now",
            repository_count=2,
        ),
        palette=CardPalette(
            background="#ffffff",
            panel="#eeeeee",
            text="#111111",
            accent="#6633ff",
            border="#222222",
        ),
        sprite=validate_sprite(_sprite()),
    )

    root = ET.fromstring(assets.svg)
    assert root.attrib["viewBox"] == "0 0 600 180"
    assert b"<script" not in assets.svg
    assert b"foreignObject" not in assets.svg
    assert b" href=" not in assets.svg
    assert b" xlink:href=" not in assets.svg
    for payload, expected_format in ((assets.png, "PNG"), (assets.gif, "GIF")):
        with Image.open(io.BytesIO(payload)) as image:
            assert image.format == expected_format
            assert image.size == (600, 180)


def test_readme_snippet_uses_exact_https_target() -> None:
    assert render_readme_snippet(
        public_base_url="https://portfolio.example.com/",
        locale="zh-TW",
        theme="dark",
        extension="svg",
        revision=7,
    ) == (
        "[![RepoNPC](https://portfolio.example.com/api/public/card.svg?"
        "theme=dark&locale=zh-TW&rev=7)](https://portfolio.example.com)"
    )


def test_readme_snippet_allows_localhost_http_for_local_acceptance() -> None:
    assert render_readme_snippet(
        public_base_url="http://localhost:8000",
        locale="en",
        theme="light",
        extension="png",
        revision=0,
    ) == (
        "[![RepoNPC](http://localhost:8000/api/public/card.png?"
        "theme=light&locale=en&rev=0)](http://localhost:8000)"
    )


def test_readme_snippet_rejects_nonlocal_plain_http() -> None:
    with pytest.raises(CardRenderError, match="card output is invalid"):
        render_readme_snippet(
            public_base_url="http://portfolio.example.com",
            locale="en",
            theme="light",
            extension="svg",
            revision=0,
        )


def test_traditional_chinese_raster_text_is_real_and_deterministic() -> None:
    common = {
        "palette": CardPalette(
            background="#ffffff",
            panel="#eeeeee",
            text="#111111",
            accent="#6633ff",
            border="#222222",
        ),
        "sprite": validate_sprite(_sprite()),
    }
    first = render_card_assets(
        copy=CardCopy(
            display_name="繁體中文角色",
            headline="探索開源專案",
            call_to_action="開始對話",
            repository_count=2,
        ),
        **common,
    )
    repeated = render_card_assets(
        copy=CardCopy(
            display_name="繁體中文角色",
            headline="探索開源專案",
            call_to_action="開始對話",
            repository_count=2,
        ),
        **common,
    )
    changed = render_card_assets(
        copy=CardCopy(
            display_name="完全不同角色",
            headline="另一個開源專案",
            call_to_action="查看內容",
            repository_count=2,
        ),
        **common,
    )

    assert first.png == repeated.png
    assert first.gif == repeated.gif
    assert first.png != changed.png
    assert first.gif != changed.gif
    assert bytes(card_render._card_font().getmask("繁體中文")) != bytes(
        card_render._card_font().getmask("完全不同")
    )
