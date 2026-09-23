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
CARD_CHARACTER_SIZE: Final = 128
CARD_CHARACTER_SCALE: Final = CARD_CHARACTER_SIZE // FRAME_SIZE
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


@dataclass(frozen=True, slots=True)
class _TextRegion:
    x: int
    raster_y: int
    svg_y: int
    max_width: int
    font_size: int


@dataclass(frozen=True, slots=True)
class _FittedText:
    value: str
    width: float


@dataclass(frozen=True, slots=True)
class _FittedCardCopy:
    display_name: _FittedText
    headline: _FittedText
    call_to_action: _FittedText
    repository_count: _FittedText | None


_DISPLAY_NAME_REGION: Final = _TextRegion(178, 33, 48, 392, 18)
_HEADLINE_REGION: Final = _TextRegion(178, 67, 80, 392, 13)
_CALL_TO_ACTION_REGION: Final = _TextRegion(192, 125, 138, 214, 14)
_REPOSITORY_COUNT_REGION: Final = _TextRegion(442, 126, 140, 128, 14)
_ELLIPSIS: Final = "…"


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
    fitted_copy = _fit_copy(safe_copy)
    first_frame, frames = _idle_frames(sprite)
    png = _raster_card(fitted_copy, palette, first_frame)
    gif = _gif_card(
        fitted_copy,
        palette,
        frames if animation_enabled else (first_frame,),
        frame_duration_ms,
    )
    svg = _svg_card(
        safe_copy,
        fitted_copy,
        palette,
        first_frame,
        animation_enabled,
        frame_duration_ms,
    )
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
    localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    allowed_scheme = parsed.scheme == "https" or (parsed.scheme == "http" and localhost)
    if not allowed_scheme or not parsed.netloc or parsed.username or parsed.password:
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


def _fit_copy(copy: CardCopy) -> _FittedCardCopy:
    return _FittedCardCopy(
        display_name=_fit_region(copy.display_name, _DISPLAY_NAME_REGION),
        headline=_fit_region(copy.headline, _HEADLINE_REGION),
        call_to_action=_fit_region(copy.call_to_action, _CALL_TO_ACTION_REGION),
        repository_count=(
            None
            if copy.repository_count is None
            else _fit_region(
                f"{copy.repository_count} repos",
                _REPOSITORY_COUNT_REGION,
            )
        ),
    )


def _fit_region(value: str, region: _TextRegion) -> _FittedText:
    font = _card_font(region.font_size)
    fitted = _fit_text(value, font, region.max_width)
    return _FittedText(value=fitted, width=float(font.getlength(fitted)))


def _fit_text(value: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Fit one already-clean string without wrapping or environment-dependent fonts."""

    if font.getlength(value) <= max_width:
        return value
    for end in range(len(value) - 1, 0, -1):
        candidate = f"{value[:end].rstrip()}{_ELLIPSIS}"
        if font.getlength(candidate) <= max_width:
            return candidate
    if font.getlength(_ELLIPSIS) <= max_width:
        return _ELLIPSIS
    raise CardRenderError("TEXT_REGION_TOO_NARROW")


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


def _background(copy: _FittedCardCopy, palette: CardPalette, frame: Image.Image) -> Image.Image:
    image = Image.new("RGBA", CARD_SIZE, palette.background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (12, 12, 587, 167),
        radius=12,
        fill=palette.panel,
        outline=palette.border,
        width=3,
    )
    enlarged = frame.resize((CARD_CHARACTER_SIZE, CARD_CHARACTER_SIZE), Image.Resampling.NEAREST)
    image.alpha_composite(enlarged, (28, 26))
    draw.text(
        (_DISPLAY_NAME_REGION.x, _DISPLAY_NAME_REGION.raster_y),
        copy.display_name.value,
        fill=palette.text,
        font=_card_font(_DISPLAY_NAME_REGION.font_size),
    )
    draw.text(
        (_HEADLINE_REGION.x, _HEADLINE_REGION.raster_y),
        copy.headline.value,
        fill=palette.text,
        font=_card_font(_HEADLINE_REGION.font_size),
    )
    draw.rounded_rectangle((178, 116, 420, 149), radius=7, fill=palette.accent)
    draw.text(
        (_CALL_TO_ACTION_REGION.x, _CALL_TO_ACTION_REGION.raster_y),
        copy.call_to_action.value,
        fill=palette.panel,
        font=_card_font(_CALL_TO_ACTION_REGION.font_size),
    )
    if copy.repository_count is not None:
        draw.text(
            (_REPOSITORY_COUNT_REGION.x, _REPOSITORY_COUNT_REGION.raster_y),
            copy.repository_count.value,
            fill=palette.text,
            font=_card_font(_REPOSITORY_COUNT_REGION.font_size),
        )
    return image


def _card_font(size: int = 16) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except OSError as exc:
        raise CardRenderError("FONT_UNAVAILABLE") from exc


def _raster_card(copy: _FittedCardCopy, palette: CardPalette, frame: Image.Image) -> bytes:
    output = io.BytesIO()
    _background(copy, palette, frame).convert("RGB").save(
        output, "PNG", optimize=False, compress_level=9
    )
    return output.getvalue()


def _gif_card(
    copy: _FittedCardCopy,
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
    fitted_copy: _FittedCardCopy,
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
                    f'<rect x="{28 + x * CARD_CHARACTER_SCALE}" '
                    f'y="{26 + y * CARD_CHARACTER_SCALE}" '
                    f'width="{CARD_CHARACTER_SCALE}" height="{CARD_CHARACTER_SCALE}" '
                    f'fill="#{red:02x}{green:02x}{blue:02x}"{opacity}/>'
                )
    motion = ""
    if animate:
        motion = (
            "@keyframes pulse{0%,100%{transform:translateY(0)}"
            "50%{transform:translateY(-2px)}}"
            f".npc{{animation:pulse {duration * 4}ms steps(1,end) infinite}}"
        )
    repo = ""
    if fitted_copy.repository_count is not None:
        repo = _svg_text(
            fitted_copy.repository_count,
            _REPOSITORY_COUNT_REGION,
            css_class="repo-count",
        )
    xml = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" '
        'viewBox="0 0 600 180" role="img" aria-labelledby="title desc">'
        f'<title id="title">{html.escape(copy.display_name)}</title>'
        f'<desc id="desc">{html.escape(copy.headline)}</desc>'
        f"<style>text{{font-family:'Noto Sans CJK TC',sans-serif;fill:{palette.text}}}"
        f".cta{{fill:{palette.panel}}}{motion}</style>"
        f'<rect width="600" height="180" fill="{palette.background}"/>'
        f'<rect x="12" y="12" width="575" height="155" rx="12" '
        f'fill="{palette.panel}" stroke="{palette.border}" stroke-width="3"/>'
        f'<g class="npc">{"".join(rectangles)}</g>'
        f"{_svg_text(fitted_copy.display_name, _DISPLAY_NAME_REGION, font_weight='700')}"
        f"{_svg_text(fitted_copy.headline, _HEADLINE_REGION)}"
        f'<rect x="178" y="116" width="242" height="33" rx="7" fill="{palette.accent}"/>'
        f"{_svg_text(fitted_copy.call_to_action, _CALL_TO_ACTION_REGION, css_class='cta')}"
        f"{repo}"
        "</svg>"
    )
    return xml.encode("utf-8")


def _svg_text(
    text: _FittedText,
    region: _TextRegion,
    *,
    css_class: str | None = None,
    font_weight: str | None = None,
) -> str:
    attributes = [
        f'x="{region.x}"',
        f'y="{region.svg_y}"',
        f'font-size="{region.font_size}"',
        f'textLength="{text.width:.3f}"',
        'lengthAdjust="spacingAndGlyphs"',
    ]
    if css_class is not None:
        attributes.append(f'class="{css_class}"')
    if font_weight is not None:
        attributes.append(f'font-weight="{font_weight}"')
    return f"<text {' '.join(attributes)}>{html.escape(text.value)}</text>"
