from __future__ import annotations

import io
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

import reponpc.cards.render as card_render
from reponpc.cards.assets import (
    FRAME_COLUMNS,
    FRAME_ROWS,
    FRAME_SIZE,
    HEIGHT,
    WIDTH,
    validate_sprite,
)
from reponpc.cards.render import (
    CardCopy,
    CardPalette,
    CardRenderError,
    render_card_assets,
    render_readme_snippet,
)


def _sprite() -> bytes:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for row in range(FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            image.putpixel(
                (column * FRAME_SIZE + 4, row * FRAME_SIZE + 4),
                (80, 90, 100, 255),
            )
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


@pytest.mark.parametrize(
    ("value", "region"),
    [
        ("超長繁體中文角色名稱" * 8, card_render._DISPLAY_NAME_REGION),
        ("以可驗證證據打造可靠又清楚的開源專案導覽" * 8, card_render._HEADLINE_REGION),
        ("A very long English display name " * 8, card_render._DISPLAY_NAME_REGION),
        ("https://example.invalid/" + "unbroken-path/" * 20, card_render._HEADLINE_REGION),
        ("立即閱讀所有可驗證的專案內容" * 8, card_render._CALL_TO_ACTION_REGION),
        ("RepoNPC混合CJKandLatinText" * 10, card_render._HEADLINE_REGION),
    ],
)
def test_long_card_text_is_fitted_by_measured_width(
    value: str, region: card_render._TextRegion
) -> None:
    font = card_render._card_font(region.font_size)

    fitted = card_render._fit_text(value, font, region.max_width)

    assert fitted
    assert fitted.endswith("…")
    assert font.getlength(fitted) <= region.max_width


def test_short_card_text_is_not_changed_by_fitting() -> None:
    region = card_render._DISPLAY_NAME_REGION
    font = card_render._card_font(region.font_size)

    assert card_render._fit_text("RepoNPC", font, region.max_width) == "RepoNPC"


def test_all_formats_reuse_the_same_fitted_strings_and_regions() -> None:
    copy = CardCopy(
        display_name="超長繁體中文角色名稱" * 8,
        headline="https://example.invalid/" + "unbroken-path/" * 20,
        call_to_action="Read every verified repository detail " * 8,
        repository_count=int("9" * 80),
    )
    safe_copy = card_render._bounded_copy(copy)
    fitted = card_render._fit_copy(safe_copy)
    assert fitted.repository_count is not None
    assets = render_card_assets(
        copy=copy,
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
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    visible = [element.text for element in root.findall("svg:text", namespace)]
    expected = [
        fitted.display_name.value,
        fitted.headline.value,
        fitted.call_to_action.value,
        fitted.repository_count.value,
    ]
    assert visible == expected
    assert all(value and value.endswith("…") for value in expected)
    regions = (
        card_render._DISPLAY_NAME_REGION,
        card_render._HEADLINE_REGION,
        card_render._CALL_TO_ACTION_REGION,
        card_render._REPOSITORY_COUNT_REGION,
    )
    for element, region in zip(root.findall("svg:text", namespace), regions, strict=True):
        assert float(element.attrib["textLength"]) <= region.max_width
    title = root.find("svg:title", namespace)
    description = root.find("svg:desc", namespace)
    assert title is not None
    assert description is not None
    assert title.text == safe_copy.display_name
    assert description.text == safe_copy.headline
    for payload, expected_format in ((assets.png, "PNG"), (assets.gif, "GIF")):
        with Image.open(io.BytesIO(payload)) as image:
            assert image.format == expected_format
            assert image.size == (600, 180)

    repeated = render_card_assets(
        copy=copy,
        palette=CardPalette(
            background="#ffffff",
            panel="#eeeeee",
            text="#111111",
            accent="#6633ff",
            border="#222222",
        ),
        sprite=validate_sprite(_sprite()),
    )
    assert repeated == assets


def test_hostile_long_text_remains_inert_after_fitting() -> None:
    assets = render_card_assets(
        copy=CardCopy(
            display_name='<svg onload="alert(1)"><script>' * 5,
            headline='</text><foreignObject href="https://evil.invalid">' * 5,
            call_to_action='<a xlink:href="https://evil.invalid">' * 5,
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
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert b"<script" not in assets.svg
    assert b"<foreignObject" not in assets.svg
    forbidden_attributes = {
        "onload",
        "href",
        "{http://www.w3.org/1999/xlink}href",
    }
    assert all(forbidden_attributes.isdisjoint(element.attrib) for element in root.iter())
