"""Scene card regressions using the shipped configuration and canonical sprite."""

from __future__ import annotations

import hashlib
import io
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from PIL import Image, ImageColor, ImageDraw, ImageFont

from reponpc.cards import render as renderer
from reponpc.cards.assets import CanonicalSprite, validate_sprite
from reponpc.cards.render import CardCopy, CardPalette, CardRenderError, render_card_assets
from reponpc.cards.sprite_composer import compose_builtin
from reponpc.config.models import load_public_config

FIXTURE = Path("tests/fixtures/phase2/reponpc.yml")
FONTS = Path(renderer.__file__).with_name("fonts")
NAMESPACE = "{http://www.w3.org/2000/svg}"
RECTANGLE = r"M(\d+) (\d+)h(\d+)v(\d+)h-\3z"


def svg_to_image(payload: bytes) -> Image.Image:
    """Rebuild every path rectangle, rejecting anything beyond static pixel geometry."""
    root = ET.fromstring(payload)
    assert root.tag == NAMESPACE + "svg"
    assert root.attrib["width"] == "600" and root.attrib["height"] == "180"
    assert root.attrib["viewBox"] == "0 0 600 180"
    assert root.attrib["role"] == "img" and root.attrib["aria-labelledby"] == "title desc"
    assert root.attrib["shape-rendering"] == "crispEdges"
    assert {element.tag for element in root.iter()} == {
        NAMESPACE + tag for tag in ("svg", "title", "desc", "rect", "path")
    }
    assert all(
        not (key.lower().startswith("on") or "href" in key)
        for element in root.iter()
        for key in element.attrib
    )
    assert len(root.findall(NAMESPACE + "rect")) == 1
    background = root.find(NAMESPACE + "rect")
    assert background is not None
    assert set(background.attrib) == {"width", "height", "fill"}
    assert background.attrib["width"] == "600" and background.attrib["height"] == "180"
    image = Image.new("RGB", (600, 180), background.attrib["fill"])
    for path in root.findall(NAMESPACE + "path"):
        assert set(path.attrib) == {"fill", "d"}
        assert re.fullmatch(r"#[0-9a-f]{6}", path.attrib["fill"])
        commands = list(re.finditer(RECTANGLE, path.attrib["d"]))
        assert commands and "".join(match[0] for match in commands) == path.attrib["d"]
        for match in commands:
            x, y, width, height = map(int, match.groups())
            assert width > 0 and height > 0 and x + width <= 600 and y + height <= 180
            image.paste(path.attrib["fill"], (x, y, x + width, y + height))
    return image


@pytest.fixture(scope="module")
def sprite() -> CanonicalSprite:
    builtin = load_public_config(FIXTURE).character.builtin
    assert builtin is not None
    return validate_sprite(compose_builtin(builtin))


def _palette(theme: str) -> CardPalette:
    return CardPalette(**getattr(load_public_config(FIXTURE).card.themes, theme).model_dump())


def _copy(locale: str) -> CardCopy:
    config = load_public_config(FIXTURE)
    return CardCopy(
        config.profile.display_name,
        config.profile.headline[locale],
        config.card.call_to_action[locale],
        sum(repository.enabled for repository in config.repositories),
    )


@pytest.mark.parametrize("theme", ["light", "dark", "custom"])
@pytest.mark.parametrize("locale", ["zh-TW", "en"])
def test_scene_pixels_and_all_formats_agree(sprite: CanonicalSprite, theme: str, locale: str):
    palette = (
        CardPalette("#132d47", "#edcba9", "#172339", "#bd5327", "#615243")
        if theme == "custom"
        else _palette(theme)
    )
    copy = _copy(locale)
    assets = render_card_assets(copy=copy, palette=palette, sprite=sprite)
    colors = {key: ImageColor.getrgb(value) for key, value in asdict(palette).items()}
    for role, a, b, amount in (
        ("shade", "background", "border", 0.25),
        ("soft", "panel", "background", 0.5),
        ("tint", "panel", "accent", 0.18),
        ("hill_far", "border", "tint", 0.6),
        ("hill_near", "border", "tint", 0.35),
    ):
        colors[role] = tuple(
            round(x + (y - x) * amount) for x, y in zip(colors[a], colors[b], strict=True)
        )
    with Image.open(io.BytesIO(sprite.content)) as sheet:
        allowed = set(colors.values()) | {
            pixel[:3] for pixel in sheet.crop((0, 0, 256, 64)).getdata() if pixel[3] >= 128
        }
    with Image.open(io.BytesIO(assets.png)) as png, Image.open(io.BytesIO(assets.gif)) as gif:
        assert png.mode == "RGB" and png.size == gif.size == (600, 180)
        assert set(png.getdata()) <= allowed
        assert svg_to_image(assets.svg).tobytes() == png.tobytes()
        assert gif.n_frames == 4 and gif.info["loop"] == 0
        for t in range(4):
            gif.seek(t)
            assert gif.info["duration"] == 240 and gif.disposal_method == 2
            frame = gif.convert("RGB")
            assert set(frame.getdata()) <= allowed
            if t == 0:
                assert frame.tobytes() == png.tobytes()
        for point, role in (
            ((8, 6), "background"),
            ((12, 6), "border"),
            ((8, 10), "border"),
            ((192, 10), "border"),
            ((150, 24), "accent"),
            ((14, 100), "tint"),
            ((14, 120), "hill_far"),
            ((14, 144), "hill_near"),
            ((14, 146), "border"),
        ):
            assert png.getpixel(point) == colors[role]
    static = render_card_assets(copy=copy, palette=palette, sprite=sprite, animation_enabled=False)
    assert static.png == assets.png and static.svg == assets.svg
    with Image.open(io.BytesIO(static.gif)) as gif, Image.open(io.BytesIO(assets.png)) as png:
        assert gif.n_frames == 1 and gif.info["loop"] == 0
        assert gif.convert("RGB").tobytes() == png.tobytes()


def test_repository_count_none_draws_no_repo_text(sprite: CanonicalSprite):
    copy = CardCopy("RepoNPC", "Evidence", "Ask", None)
    assets = render_card_assets(copy=copy, palette=_palette("light"), sprite=sprite)
    counted = render_card_assets(
        copy=replace(copy, repository_count=3), palette=_palette("light"), sprite=sprite
    )
    with Image.open(io.BytesIO(assets.png)) as png, Image.open(io.BytesIO(counted.png)) as other:
        region = (460, 106, 574, 138)
        assert set(png.crop(region).getdata()) == {ImageColor.getrgb(_palette("light").panel)}
        assert png.crop(region).tobytes() != other.crop(region).tobytes()
        assert svg_to_image(assets.svg).tobytes() == png.tobytes()


@pytest.mark.parametrize(
    "name", ["A very long Latin display name " * 8, "超長繁體中文角色名稱" * 8]
)
@pytest.mark.parametrize("locale", ["zh-TW", "en"])
def test_long_text_pixels_match_fitted_glyphs_inside_regions(sprite, name, locale):
    copy = CardCopy(
        name,
        ("專注可驗證的專案證據" if locale == "zh-TW" else "unbroken-verifiable-project/") * 20,
        ("立即詢問所有專案證據" if locale == "zh-TW" else "Ask about every repository ") * 10,
        128,
    )
    palette = _palette("light")
    card = renderer._Card(palette)
    safe = renderer._bounded_copy(copy)
    body = ImageFont.truetype(FONTS / "NotoSansCJKtc-Regular.otf", 14)
    repo_width = int(body.getlength("128 repos"))
    label_max = 570 - repo_width - 20 - 242 - 24
    fitted = []
    for value, role, width in (
        (safe.display_name, "display", 350),
        (safe.headline, "body", 360),
        (safe.call_to_action, "body", label_max),
    ):
        font = card.pick(value, role)
        text = card.fit(value, font, width)
        assert text.endswith("…") and len(text) < len(value)
        assert font.getlength(text) <= width
        fitted.append((font, text))
    name_font, name_text = fitted[0]
    headline_font, headline_text = fitted[1]
    cta_font, cta_text = fitted[2]
    expected = Image.new("RGB", (600, 180), palette.panel)
    draw = ImageDraw.Draw(expected)
    draw.fontmode = "1"
    shade = tuple(
        round(a + (b - a) * 0.25)
        for a, b in zip(
            ImageColor.getrgb(palette.background), ImageColor.getrgb(palette.border), strict=True
        )
    )
    draw.text((216, 56), name_text, font=name_font, fill=shade, anchor="ls")
    draw.text((214, 54), name_text, font=name_font, fill=palette.text, anchor="ls")
    draw.text((214, 88), headline_text, font=headline_font, fill=palette.text, anchor="ls")
    label_width = int(cta_font.getlength(cta_text))
    draw.rectangle((210, 106, 210 + label_width + 47, 137), fill=palette.text)
    draw.text((242, 128), cta_text, font=cta_font, fill=palette.panel, anchor="ls")
    draw.text(
        (570 - body.getlength("128 repos"), 128),
        "128 repos",
        font=body,
        fill=palette.text,
        anchor="ls",
    )
    assets = render_card_assets(copy=copy, palette=palette, sprite=sprite)
    with Image.open(io.BytesIO(assets.png)) as png:
        for region in ((210, 16, 586, 106), (242, 106, 586, 138)):
            assert png.crop(region).tobytes() == expected.crop(region).tobytes()
        assert set(png.crop((210, 100, 586, 106)).getdata()) == {ImageColor.getrgb(palette.panel)}
        bar_right = 210 + label_width + 48
        repo_left = math.floor(570 - body.getlength("128 repos"))
        assert bar_right < repo_left
        assert set(png.crop((bar_right, 106, repo_left, 138)).getdata()) == {
            ImageColor.getrgb(palette.panel)
        }
        assert svg_to_image(assets.svg).tobytes() == png.tobytes()
    with Image.open(io.BytesIO(assets.gif)) as gif:
        assert gif.convert("RGB").tobytes() == svg_to_image(assets.svg).tobytes()


def test_hostile_text_is_inert_and_metadata_preserves_bounded_copy(sprite):
    copy = CardCopy(
        '<script>alert("x")</script>&\'=',
        "]]> <img src=x onerror=alert(1)> &amp;",
        '<a href="https://evil.invalid">go</a>',
        1,
    )
    assets = render_card_assets(copy=copy, palette=_palette("dark"), sprite=sprite)
    root = ET.fromstring(assets.svg)
    assert root.find(NAMESPACE + "title").text == copy.display_name
    assert root.find(NAMESPACE + "desc").text == copy.headline
    markup = re.sub(rb"<(title|desc)\b[^>]*>.*?</\1>", b"", assets.svg)
    assert not re.search(rb"<(?:script|image|text|style)\b|href=|\bon\w+\s*=", markup)
    assert b"<script" not in assets.svg and b"<img" not in assets.svg
    with Image.open(io.BytesIO(assets.png)) as png:
        assert svg_to_image(assets.svg).tobytes() == png.tobytes()


def test_gif_accepts_a_sprite_with_more_colours_than_a_gif_palette(sprite):
    with Image.open(io.BytesIO(sprite.content)) as sheet:
        rich = sheet.convert("RGBA")
    pixels = rich.load()
    for y in range(rich.height):
        for x in range(rich.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 255:
                pixels[x, y] = (
                    (red + x * 7) % 256,
                    (green + y * 11) % 256,
                    (blue + (x + y) * 5) % 256,
                    alpha,
                )
    buffer = io.BytesIO()
    rich.save(buffer, "PNG")
    assets = render_card_assets(
        copy=_copy("en"), palette=_palette("light"), sprite=validate_sprite(buffer.getvalue())
    )
    with Image.open(io.BytesIO(assets.png)) as png:
        assert len(png.convert("RGB").getcolors(maxcolors=65536)) > 256
    with Image.open(io.BytesIO(assets.gif)) as gif:
        assert gif.n_frames == 4 and gif.size == (600, 180)
    assert svg_to_image(assets.svg).size == (600, 180)


def test_pixel_font_is_loaded_from_package_with_original_bytes():
    path = FONTS / "press-start-2p-latin-400-normal.woff2"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "afec86997fdaf54af1f59358fa2c1e2a0f1d04146edad18e5cd141d0384a7548"
    )
    card = renderer._Card(_palette("light"))
    for name in ("RepoNPC", "Caf\u00e9", "\u1fff"):
        font = card.pick(name, "display")
        assert Path(font.path) == path and font.size == 16
    for value, role, size in (
        ("名字", "display", 16),
        ("\u2000", "display", 16),
        ("Ask", "body", 14),
    ):
        font = card.pick(value, role)
        assert Path(font.path) == FONTS / "NotoSansCJKtc-Regular.otf" and font.size == size
    assert card.d.fontmode == "1"


def test_missing_pixel_font_raises_existing_error(sprite, tmp_path, monkeypatch):
    monkeypatch.setattr(renderer, "_PIXEL_FONT_PATH", tmp_path / "missing.woff2")
    with pytest.raises(CardRenderError) as failure:
        render_card_assets(
            copy=CardCopy("Latin", "Body", "Ask", 1), palette=_palette("light"), sprite=sprite
        )
    assert failure.value.code == "FONT_UNAVAILABLE"


def test_sprite_edges_use_two_times_nearest_and_alpha_128(sprite):
    with Image.open(io.BytesIO(sprite.content)) as source:
        sheet = source.convert("RGBA")
    for column in range(4):
        sheet.putpixel((column * 64 + 1, 1), (17, 31, 47, 127))
        sheet.putpixel((column * 64 + 2, 1), (51, 67, 83, 128))
    output = io.BytesIO()
    sheet.save(output, "PNG")
    assets = render_card_assets(
        copy=CardCopy("Edge", "Body", "Ask", 1),
        palette=_palette("light"),
        sprite=validate_sprite(output.getvalue()),
    )
    with Image.open(io.BytesIO(assets.png)) as png, Image.open(io.BytesIO(assets.gif)) as gif:
        for t in range(4):
            gif.seek(t)
            frame = gif.convert("RGB")
            y = 28 + 2 * (t % 2) + 2
            assert set(frame.crop((40, y, 42, y + 2)).getdata()) == {
                tuple(
                    round(a + (b - a) * 0.18)
                    for a, b in zip(
                        ImageColor.getrgb(_palette("light").panel),
                        ImageColor.getrgb(_palette("light").accent),
                        strict=True,
                    )
                )
            }
            assert set(frame.crop((42, y, 44, y + 2)).getdata()) == {(51, 67, 83)}
        assert png.getpixel((42, 30)) == (51, 67, 83)


@pytest.mark.parametrize("duration", [80, 1000])
def test_gif_duration_bounds_remain_supported(sprite, duration):
    assets = render_card_assets(
        copy=_copy("en"), palette=_palette("light"), sprite=sprite, frame_duration_ms=duration
    )
    with Image.open(io.BytesIO(assets.gif)) as gif:
        for t in range(4):
            gif.seek(t)
            assert gif.info["duration"] == duration


@pytest.mark.parametrize("duration", [79, 1001])
def test_invalid_gif_duration_keeps_existing_error(sprite, duration):
    with pytest.raises(CardRenderError) as failure:
        render_card_assets(
            copy=_copy("en"), palette=_palette("light"), sprite=sprite, frame_duration_ms=duration
        )
    assert failure.value.code == "INVALID_FRAME_DURATION"
