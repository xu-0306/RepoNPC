"""Deterministic, self-contained card assets and README snippets."""

from __future__ import annotations

import html
import io
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal, cast
from urllib.parse import quote, urlsplit

from PIL import Image, ImageColor, ImageDraw, ImageFont

from reponpc.cards.assets import FRAME_SIZE, CanonicalSprite
from reponpc.i18n.languages import Locale

Theme = Literal["light", "dark"]
Extension = Literal["svg", "gif", "png"]
CARD_SIZE: Final = (600, 180)
CARD_CHARACTER_SIZE: Final = 128
_FONT_PATH: Final = Path(__file__).with_name("fonts") / "NotoSansCJKtc-Regular.otf"
_PIXEL_FONT_PATH: Final = _FONT_PATH.with_name("press-start-2p-latin-400-normal.woff2")
_RGB = tuple[int, int, int]
_FAR: Final = (
    30,
    32,
    36,
    40,
    42,
    44,
    44,
    42,
    40,
    36,
    34,
    32,
    30,
    34,
    38,
    40,
    38,
    34,
    30,
    28,
    26,
    26,
    28,
)
_NEAR: Final = (
    18,
    18,
    20,
    22,
    24,
    24,
    22,
    20,
    18,
    16,
    16,
    18,
    20,
    22,
    22,
    20,
    18,
    16,
    14,
    14,
    16,
    18,
    18,
)


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
    locale: Locale = "en"


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
    frames = _idle_frames(sprite)
    rendered = [
        _scene_card(safe_copy, palette, frame, t)
        for t, frame in enumerate(frames if animation_enabled else frames[:1])
    ]
    return CardAssets(
        svg=_svg_bytes(rendered[0], safe_copy),
        gif=_gif_bytes(rendered, frame_duration_ms),
        png=_png_bytes(rendered[0]),
    )


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
        locale=copy.locale,
    )


def _clean_text(value: str, maximum: int) -> str:
    cleaned = " ".join(value.replace("\x00", "").split())
    if not cleaned:
        raise CardRenderError("INVALID_TEXT")
    return cleaned[:maximum]


def _idle_frames(sprite: CanonicalSprite) -> tuple[Image.Image, ...]:
    try:
        with Image.open(io.BytesIO(sprite.content)) as sheet:
            rgba = sheet.convert("RGBA")
    except OSError as exc:
        raise CardRenderError("INVALID_SPRITE") from exc
    frames = []
    for column in range(4):
        frame = rgba.crop((column * FRAME_SIZE, 0, (column + 1) * FRAME_SIZE, FRAME_SIZE))
        frame = frame.resize((CARD_CHARACTER_SIZE, CARD_CHARACTER_SIZE), Image.Resampling.NEAREST)
        frame.putalpha(frame.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
        frames.append(frame)
    return tuple(frames)


@lru_cache
def _card_font(size: int = 16, path: Path = _FONT_PATH) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError as exc:
        raise CardRenderError("FONT_UNAVAILABLE") from exc


def _mix(a: _RGB, b: _RGB, amount: float) -> _RGB:
    return cast(_RGB, tuple(round(a[i] + (b[i] - a[i]) * amount) for i in range(3)))


class _Card:
    def __init__(self, palette: CardPalette) -> None:
        self.c = {
            role: cast(_RGB, ImageColor.getrgb(color)[:3])
            for role, color in asdict(palette).items()
        }
        c = self.c
        c["shade"] = _mix(c["background"], c["border"], 0.25)
        c["soft"] = _mix(c["panel"], c["background"], 0.5)
        c["tint"] = _mix(c["panel"], c["accent"], 0.18)
        c["hill_far"] = _mix(c["border"], c["tint"], 0.6)
        c["hill_near"] = _mix(c["border"], c["tint"], 0.35)
        self.im = Image.new("RGB", CARD_SIZE, c["background"])
        self.d = ImageDraw.Draw(self.im)
        self.d.fontmode = "1"

    def rect(self, x: int, y: int, w: int, h: int, color: str) -> None:
        self.d.rectangle((x, y, x + w - 1, y + h - 1), fill=self.c[color])

    def cut(self, x: int, y: int, w: int, h: int, color: str, n: int) -> None:
        self.rect(x + n, y, w - 2 * n, h, color)
        self.rect(x, y + n, w, h - 2 * n, color)

    def notched(
        self, x: int, y: int, w: int, h: int, line: str, fill: str, bw: int = 4, n: int = 4
    ) -> None:
        self.cut(x, y, w, h, line, n)
        self.cut(x + bw, y + bw, w - 2 * bw, h - 2 * bw, fill, max(n - bw, 0))

    def sprite(self, sprite: Image.Image, x: int, y: int) -> None:
        self.im.paste(sprite, (x, y), sprite)

    def pick(self, value: str, role: str) -> ImageFont.FreeTypeFont:
        if role == "display" and all(ord(character) < 0x2000 for character in value):
            return _card_font(16, _PIXEL_FONT_PATH)
        return _card_font(16 if role == "display" else 14)

    def fit(self, value: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        if font.getlength(value) <= max_width:
            return value
        ellipsis = _ELLIPSIS
        if font.path == _PIXEL_FONT_PATH and bytes(font.getmask(ellipsis)) == bytes(
            font.getmask("\ue000")
        ):
            ellipsis = "..."
        for end in range(len(value) - 1, 0, -1):
            candidate = f"{value[:end].rstrip()}{ellipsis}"
            if font.getlength(candidate) <= max_width:
                return candidate
        if font.getlength(ellipsis) <= max_width:
            return ellipsis
        raise CardRenderError("TEXT_REGION_TOO_NARROW")

    def text(
        self,
        x: int,
        baseline: int,
        value: str,
        color: str,
        role: str,
        max_width: int,
        *,
        right: bool = False,
    ) -> None:
        font = self.pick(value, role)
        value = self.fit(value, font, max_width)
        self.d.text(
            (x - font.getlength(value) if right else x, baseline),
            value,
            fill=self.c[color],
            font=font,
            anchor="ls",
        )

    def measure(self, value: str, role: str, max_width: int) -> int:
        font = self.pick(value, role)
        return int(font.getlength(self.fit(value, font, max_width)))

    def cursor(self, x: int, y: int, color: str) -> None:
        for i, width in enumerate((1, 2, 3, 4, 3, 2, 1)):
            self.rect(x, y + i * 2, width * 2, 2, color)


def _scene_card(copy: CardCopy, palette: CardPalette, frame: Image.Image, t: int) -> Image.Image:
    card = _Card(palette)
    card.notched(8, 6, 584, 168, "border", "panel")
    card.rect(12, 10, 180, 160, "tint")
    card.rect(150, 24, 12, 16, "accent")
    card.rect(148, 26, 16, 12, "accent")
    card.rect(34, 34, 28, 6, "panel")
    card.rect(42, 28, 12, 6, "panel")
    for i, (far, near) in enumerate(zip(_FAR, _NEAR, strict=True)):
        x = 12 + i * 8
        width = min(8, 192 - x)
        card.rect(x, 146 - far, width, far, "hill_far")
        card.rect(x, 146 - near, width, near, "hill_near")
    card.rect(12, 146, 180, 24, "hill_near")
    card.rect(12, 146, 180, 4, "border")
    card.sprite(frame, 38, 28 + (2 if t % 2 else 0))
    card.rect(192, 10, 4, 160, "border")
    card.text(216, 56, copy.display_name, "shade", "display", 350)
    card.text(214, 54, copy.display_name, "text", "display", 350)
    card.text(214, 88, copy.headline, "text", "body", 360)
    repos = repository_count_text(copy.repository_count, copy.locale)
    repo_width = 0 if repos is None else card.measure(repos, "body", 110)
    label_max = 570 - repo_width - 20 - 242 - 24
    label_width = card.measure(copy.call_to_action, "body", label_max)
    card.rect(210, 106, label_width + 48, 32, "text")
    if t % 2 == 0:
        card.cursor(220, 114, "panel")
    card.text(242, 128, copy.call_to_action, "panel", "body", label_max)
    if repos is not None:
        card.text(570, 128, repos, "text", "body", 110, right=True)
    return card.im


@lru_cache
def _repository_count_copy() -> dict[str, dict[str, str]]:
    return cast(
        dict[str, dict[str, str]],
        json.loads(Path(__file__).with_name("copy.json").read_text(encoding="utf-8")),
    )


def repository_count_text(count: int | None, locale: Locale) -> str | None:
    if count is None:
        return None
    template = _repository_count_copy()[locale]["one" if count == 1 else "many"]
    return template.format(count=count)


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _gif_bytes(frames: list[Image.Image], duration: int) -> bytes:
    rendered = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for frame in frames]
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


def _svg_bytes(image: Image.Image, copy: CardCopy) -> bytes:
    width, height = CARD_SIZE
    pixels = image.load()
    assert pixels is not None
    background = cast(_RGB, image.getpixel((0, 0)))
    paths: dict[_RGB, list[str]] = {}
    open_runs: dict[tuple[int, int, _RGB], int] = {}
    for y in range(height + 1):
        current: set[tuple[int, int, _RGB]] = set()
        x = 0
        while y < height and x < width:
            color, end = cast(_RGB, pixels[x, y]), x
            while end < width and pixels[end, y] == color:
                end += 1
            if color != background:
                current.add((x, end - x, color))
            x = end
        for key in [key for key in open_runs if key not in current]:
            y0 = open_runs.pop(key)
            paths.setdefault(key[2], []).append(f"M{key[0]} {y0}h{key[1]}v{y - y0}h-{key[1]}z")
        for key in current:
            open_runs.setdefault(key, y)
    body = "".join(
        f'<path fill="#{color[0]:02x}{color[1]:02x}{color[2]:02x}" d="{"".join(rectangles)}"/>'
        for color, rectangles in paths.items()
    )
    xml = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="180" '
        'viewBox="0 0 600 180" role="img" aria-labelledby="title desc" '
        'shape-rendering="crispEdges">'
        f'<title id="title">{html.escape(copy.display_name)}</title>'
        f'<desc id="desc">{html.escape(copy.headline)}</desc>'
        f'<rect width="600" height="180" '
        f'fill="#{background[0]:02x}{background[1]:02x}{background[2]:02x}"/>{body}</svg>'
    )
    return xml.encode("utf-8")
