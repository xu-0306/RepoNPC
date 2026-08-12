"""Deterministic, self-contained card assets and README snippets."""

from __future__ import annotations

import html
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast
from urllib.parse import quote, urlsplit

from PIL import Image, ImageDraw, ImageFont

from reponpc.cards.assets import FRAME_SIZE, CanonicalSprite

Theme = Literal["light", "dark"]
Locale = Literal["zh-TW", "en"]
Extension = Literal["svg", "gif", "png"]
CARD_SIZE: Final = (600, 180)
_FONT_PATH: Final = Path(__file__).with_name("fonts") / "NotoSansCJKtc-Regular.otf"


class CardRenderError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("card output is invalid")


@dataclass(frozen=True, slots=True)
class CardCopy:
    display_name: str
    headline: str
    call_to_action: str
    repository_count: int | None


@dataclass(frozen=True, slots=True)
class CardPalette:
    background: str
    panel: str
    text: str
    accent: str
    border: str


@dataclass(frozen=True, slots=True)
class CardAssets:
    svg: bytes
    gif: bytes
    png: bytes


def render_card_assets(
    *,
    copy: CardCopy,
    palette: CardPalette,
    sprite: CanonicalSprite,
    animation_enabled: bool = True,
    frame_duration_ms: int = 240,
) -> CardAssets:
    """Render matching SVG/GIF/PNG assets from one canonical first frame."""

    if not 80 <= frame_duration_ms <= 1000:
        raise CardRenderError("INVALID_FRAME_DURATION")
    safe_copy = _bounded_copy(copy)
    first_frame, frames = _idle_frames(sprite)
    png = _raster_card(safe_copy, palette, first_frame)
    gif = _gif_card(
        safe_copy,
        palette,
        frames if animation_enabled else (first_frame,),
        frame_duration_ms,
    )
    svg = _svg_card(safe_copy, palette, first_frame, animation_enabled, frame_duration_ms)
    return CardAssets(svg=svg, gif=gif, png=png)


def render_readme_snippet(
    *,
    public_base_url: str,
    locale: Locale,
    theme: Theme,
    extension: Extension,
    revision: int,
) -> str:
    """Return one copy-ready Markdown link with exact revisioned public asset URL."""

    parsed = urlsplit(public_base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CardRenderError("INVALID_PUBLIC_URL")
    if parsed.query or parsed.fragment:
        raise CardRenderError("INVALID_PUBLIC_URL")
    if revision < 0:
        raise CardRenderError("INVALID_REVISION")
    base = public_base_url.rstrip("/")
    query = f"theme={quote(theme)}&locale={quote(locale)}&rev={revision}"
    asset_url = f"{base}/api/public/card.{extension}?{query}"
    return f"[![RepoNPC]({asset_url})]({base})"


def _bounded_copy(copy: CardCopy) -> CardCopy:
    if copy.repository_count is not None and copy.repository_count < 0:
        raise CardRenderError("INVALID_REPOSITORY_COUNT")
    return CardCopy(
        display_name=_clean_text(copy.display_name, 80),
        headline=_clean_text(copy.headline, 160),
        call_to_action=_clean_text(copy.call_to_action, 80),
        repository_count=copy.repository_count,
    )


def _clean_text(value: str, maximum: int) -> str:
    cleaned = " ".join(value.replace("\x00", "").split())
    if not cleaned:
        raise CardRenderError("INVALID_TEXT")
    return cleaned[:maximum]


def _idle_frames(sprite: CanonicalSprite) -> tuple[Image.Image, tuple[Image.Image, ...]]:
    try:
        with Image.open(io.BytesIO(sprite.content)) as sheet:
            rgba = sheet.convert("RGBA")
    except OSError as exc:
        raise CardRenderError("INVALID_SPRITE") from exc
    frames = tuple(
        rgba.crop((column * FRAME_SIZE, 0, (column + 1) * FRAME_SIZE, FRAME_SIZE))
        for column in range(4)
    )
    return frames[0], frames


def _background(copy: CardCopy, palette: CardPalette, frame: Image.Image) -> Image.Image:
    image = Image.new("RGBA", CARD_SIZE, palette.background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (12, 12, 587, 167),
        radius=12,
        fill=palette.panel,
        outline=palette.border,
        width=3,
    )
    enlarged = frame.resize((128, 128), Image.Resampling.NEAREST)
    image.alpha_composite(enlarged, (28, 26))
    font = _card_font()
    draw.text((178, 35), copy.display_name, fill=palette.text, font=font)
    draw.text((178, 68), copy.headline, fill=palette.text, font=font)
    draw.rounded_rectangle((178, 116, 420, 149), radius=7, fill=palette.accent)
    draw.text((192, 127), copy.call_to_action, fill=palette.panel, font=font)
    if copy.repository_count is not None:
        draw.text((442, 129), f"{copy.repository_count} repos", fill=palette.text, font=font)
    return image


def _card_font() -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATH, 16)
    except OSError as exc:
        raise CardRenderError("FONT_UNAVAILABLE") from exc


def _raster_card(copy: CardCopy, palette: CardPalette, frame: Image.Image) -> bytes:
    output = io.BytesIO()
    _background(copy, palette, frame).convert("RGB").save(
        output, "PNG", optimize=False, compress_level=9
    )
    return output.getvalue()


def _gif_card(
    copy: CardCopy,
    palette: CardPalette,
    frames: tuple[Image.Image, ...],
    duration: int,
) -> bytes:
    rendered = [
        _background(copy, palette, frame).convert("P", palette=Image.Palette.ADAPTIVE)
        for frame in frames
    ]
    output = io.BytesIO()
    rendered[0].save(
        output,
        "GIF",
        save_all=True,
        append_images=rendered[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )
    return output.getvalue()


def _svg_card(
    copy: CardCopy,
    palette: CardPalette,
    frame: Image.Image,
    animate: bool,
    duration: int,
) -> bytes:
    rectangles: list[str] = []
    for y in range(FRAME_SIZE):
        for x in range(FRAME_SIZE):
            red, green, blue, alpha = cast(tuple[int, int, int, int], frame.getpixel((x, y)))
            if alpha:
                opacity = "" if alpha == 255 else f' fill-opacity="{alpha / 255:.3f}"'
                rectangles.append(
                    f'<rect x="{28 + x * 4}" y="{26 + y * 4}" width="4" height="4" '
                    f'fill="#{red:02x}{green:02x}{blue:02x}"{opacity}/>'
                )
    motion = ""
    if animate:
        motion = (
            "@keyframes pulse{0%,100%{transform:translateY(0)}"
            "50%{transform:translateY(-2px)}}"
            f".npc{{animation:pulse {duration * 4}ms steps(1,end) infinite}}"
        )
    repo = (
        ""
        if copy.repository_count is None
        else f'<text x="442" y="140">{copy.repository_count} repos</text>'
    )
    xml = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" '
        'viewBox="0 0 600 180" role="img" aria-labelledby="title desc">'
        f'<title id="title">{html.escape(copy.display_name)}</title>'
        f'<desc id="desc">{html.escape(copy.headline)}</desc>'
        f"<style>text{{font-family:monospace;fill:{palette.text}}}{motion}</style>"
        f'<rect width="600" height="180" fill="{palette.background}"/>'
        f'<rect x="12" y="12" width="575" height="155" rx="12" '
        f'fill="{palette.panel}" stroke="{palette.border}" stroke-width="3"/>'
        f'<g class="npc">{"".join(rectangles)}</g>'
        f'<text x="178" y="48" font-size="18" font-weight="700">'
        f"{html.escape(copy.display_name)}</text>"
        f'<text x="178" y="80" font-size="13">{html.escape(copy.headline)}</text>'
        f'<rect x="178" y="116" width="242" height="33" rx="7" fill="{palette.accent}"/>'
        f'<text x="192" y="138" font-size="14" fill="{palette.panel}">'
        f"{html.escape(copy.call_to_action)}</text>{repo}"
        "</svg>"
    )
    return xml.encode("utf-8")
