"""Resolve a validated scene against one canonical character sheet."""

from __future__ import annotations

import io
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, cast

from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from reponpc.cards.assets import FRAME_COLUMNS, FRAME_ROWS, FRAME_SIZE, validate_sprite
from reponpc.config.models import SceneConfig, SceneFocusConfig
from reponpc.scene.dim import DIM_OPACITY
from reponpc.scene.images import SceneImageError, validate_scene_image
from reponpc.scene.registry import (
    SCENE_ROLES,
    SceneRegistry,
    contrast_pairs,
    contrast_ratio,
    default_scene_registry,
)


class SceneResolutionError(ValueError):
    """Safe resolver failure without user-supplied values or asset data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("visitor scene could not be resolved")


class _StrictSceneModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SceneScheme(_StrictSceneModel):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)]
    version: Annotated[int, Field(ge=1)]


class SceneTokens(_StrictSceneModel):
    background: str
    surface: str
    surface_alt: str
    ink: str
    muted_ink: str
    accent: str
    accent_ink: str
    border: str
    stage: str
    focus: str

    @field_validator(*SCENE_ROLES)
    @classmethod
    def validate_hex(cls, value: str) -> str:
        if re.fullmatch(r"#[0-9a-f]{6}", value) is None:
            raise ValueError("scene colors must be lowercase six-digit hexadecimal values")
        return value

    @model_validator(mode="after")
    def validate_contrast(self) -> SceneTokens:
        roles = self.model_dump()
        for foreground, background, minimum in contrast_pairs():
            if contrast_ratio(roles[foreground], roles[background]) + 1e-9 < minimum:
                raise ValueError(f"contrast pair {foreground}/{background} fails")
        return self


class SceneThemes(_StrictSceneModel):
    light: SceneTokens
    dark: SceneTokens


class PublicScene(_StrictSceneModel):
    revision: Annotated[int, Field(ge=0)]
    scheme: SceneScheme
    color_mode: Literal["system", "light", "dark"]
    visitor_mode_toggle: bool
    themes: SceneThemes
    background_url: str | None
    background_scaling: Literal["smooth", "pixelated"]
    background_focus: SceneFocusConfig
    background_dim: Literal["auto", "none", "low", "medium", "high"]

    @field_validator("background_url")
    @classmethod
    def validate_background_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("/api/public/scene-background?rev="):
            raise ValueError("background URL must use the same-origin scene asset route")
        return value

    @model_validator(mode="after")
    def validate_background_revision(self) -> PublicScene:
        if self.background_url is not None:
            expected = f"/api/public/scene-background?rev={self.revision}"
            if self.background_url != expected:
                raise ValueError("background URL revision must match scene revision")
        return self


@dataclass(frozen=True, slots=True)
class SceneNotice:
    kind: Literal[
        "accent_adjusted",
        "stage_adjusted",
        "stage_plate",
        "background_dim_adjusted",
    ]
    variant: Literal["light", "dark"]
    adjusted_value: str
    reason: str


@dataclass(frozen=True, slots=True)
class SceneResolution:
    public: PublicScene
    notices: tuple[SceneNotice, ...]


def resolve_scene(
    settings: SceneConfig | Mapping[str, object],
    *,
    sprite_content: bytes,
    revision: int,
    registry: SceneRegistry | None = None,
    background_content: bytes | None = None,
) -> SceneResolution:
    """Resolve all public tokens; the canonical sheet may affect only ``stage``."""

    selected_registry = registry or default_scene_registry()
    try:
        parsed_settings = (
            settings
            if isinstance(settings, SceneConfig)
            else SceneConfig.model_validate(settings, context={"scene_registry": selected_registry})
        )
    except ValidationError:
        raise SceneResolutionError("scene_settings_invalid") from None
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise SceneResolutionError("scene_revision_invalid")
    if not isinstance(sprite_content, bytes):
        raise SceneResolutionError("character_sprite_invalid")
    try:
        sprite = validate_sprite(sprite_content)
        with Image.open(io.BytesIO(sprite.content)) as image:
            image.load()
            edge = _average_edge_color(image.convert("RGBA"))
    except Exception as exc:
        raise SceneResolutionError("character_sprite_invalid") from exc

    try:
        scheme = selected_registry.scheme(parsed_settings.color_scheme)
    except KeyError:
        raise SceneResolutionError("scene_scheme_unknown") from None

    notices: list[SceneNotice] = []
    resolved_variants: dict[str, dict[str, str]] = {}
    for variant in ("light", "dark"):
        roles = dict(scheme.variant(variant))
        if parsed_settings.accent is not None:
            accent, accent_ink = _resolve_accent(parsed_settings.accent, roles)
            if accent != parsed_settings.accent.lower():
                notices.append(
                    SceneNotice(
                        "accent_adjusted",
                        variant,
                        accent,
                        "The accent was adjusted in lightness to meet contrast requirements.",
                    )
                )
            roles["accent"] = accent
            roles["accent_ink"] = accent_ink

        stage = roles["stage"]
        if contrast_ratio(edge, stage) < 3.0 or stage == roles["surface"]:
            surface = roles["surface"]

            def acceptable_stage(candidate: str, fixed_surface: str = surface) -> bool:
                return candidate != fixed_surface and contrast_ratio(edge, candidate) >= 3.0

            adjusted = _nearest_lightness(stage, acceptable_stage)
            if adjusted is None:
                stage = max(
                    (
                        color
                        for color in (_from_oklch(0, 0, 0), _from_oklch(1, 0, 0))
                        if color != roles["surface"]
                    ),
                    key=lambda color: contrast_ratio(edge, color),
                )
                notices.append(
                    SceneNotice(
                        "stage_plate",
                        variant,
                        stage,
                        "A solid stage plate is needed because hue-preserving lightness "
                        "cannot meet 3:1.",
                    )
                )
            else:
                stage = adjusted
                notices.append(
                    SceneNotice(
                        "stage_adjusted",
                        variant,
                        stage,
                        "Stage lightness was adjusted to separate the character edge at 3:1.",
                    )
                )
        roles["stage"] = stage
        resolved_variants[variant] = roles

    resolved_dim: Literal["auto", "none", "low", "medium", "high"] = parsed_settings.background_dim
    if background_content is not None:
        if parsed_settings.background_path is None:
            raise SceneResolutionError("scene_background_invalid")
        resolved_dim, dim_notices = _resolve_background_dim(
            parsed_settings,
            background_content,
            edge_color=edge,
            themes=resolved_variants,
        )
        notices.extend(dim_notices)

    background_url = (
        f"/api/public/scene-background?rev={revision}"
        if parsed_settings.background_path is not None
        else None
    )
    try:
        public = PublicScene(
            revision=revision,
            scheme=SceneScheme(id=scheme.id, version=scheme.version),
            color_mode=parsed_settings.color_mode,
            visitor_mode_toggle=parsed_settings.visitor_mode_toggle,
            themes=SceneThemes(
                light=SceneTokens(**resolved_variants["light"]),
                dark=SceneTokens(**resolved_variants["dark"]),
            ),
            background_url=background_url,
            background_scaling=parsed_settings.background_scaling,
            background_focus=parsed_settings.background_focus,
            background_dim=resolved_dim,
        )
    except ValidationError:
        raise SceneResolutionError("scene_resolution_invalid") from None
    return SceneResolution(public=public, notices=tuple(notices))


def _resolve_background_dim(
    settings: SceneConfig,
    content: bytes,
    *,
    edge_color: str,
    themes: Mapping[str, Mapping[str, str]],
) -> tuple[Literal["none", "low", "medium", "high"], list[SceneNotice]]:
    """Choose the least dim that separates every bounded crop sample from the NPC edge.

    Sampling is deliberately capped at two 9x9 images (desktop and portrait), across both
    themes. The full source image is decoded only after the shared image guard validates it.
    """

    if settings.background_dim != "auto":
        return settings.background_dim, []
    try:
        filename = "background.webp" if content.startswith(b"RIFF") else "background.png"
        image = validate_scene_image(content, filename=filename)
        with Image.open(io.BytesIO(image.content)) as source:
            source.load()
            rgba = source.convert("RGBA")
            centering = (settings.background_focus.x / 100, settings.background_focus.y / 100)
            crops = (
                ImageOps.fit(rgba, (32, 18), centering=centering),
                ImageOps.fit(rgba, (18, 32), centering=centering),
            )
            # ponytail: two 9x9 crops bound preview work; raise density for finer image detail.
            samples = [tuple(crop.resize((9, 9)).convert("RGBA").getdata()) for crop in crops]
    except (OSError, ValueError, SceneImageError) as exc:
        raise SceneResolutionError("scene_background_invalid") from exc

    selected: Literal["none", "low", "medium", "high"] | None = None
    failed_variants: set[str] = set()
    for level, opacity in DIM_OPACITY.items():
        passing_variants: set[str] = set()
        for variant in ("light", "dark"):
            surface = _rgb(themes[variant]["surface"])
            if all(
                contrast_ratio(edge_color, _dim_sample(pixel, surface, opacity)) >= 3.0
                for crop in samples
                for pixel in crop
            ):
                passing_variants.add(variant)
        if passing_variants == {"light", "dark"}:
            selected = cast(Literal["none", "low", "medium", "high"], level)
            break
        failed_variants = {"light", "dark"} - passing_variants

    if selected is None:
        selected = "high"
        return selected, [
            SceneNotice(
                "stage_plate",
                variant,  # type: ignore[arg-type]
                selected,
                "The image remains busy at the strongest dim setting; "
                "the opaque NPC ring stays visible.",
            )
            for variant in sorted(failed_variants)
        ]
    if selected == "none":
        return selected, []
    opacity = DIM_OPACITY[selected]
    return selected, [
        SceneNotice(
            "background_dim_adjusted",
            variant,  # type: ignore[arg-type]
            selected,
            f"Background dim was set to {opacity:.0%} for NPC separation.",
        )
        for variant in ("light", "dark")
    ]


def _dim_sample(
    pixel: tuple[int, int, int, int], surface: tuple[int, int, int], opacity: float
) -> str:
    red, green, blue, alpha = pixel
    channels = tuple(
        round(channel * alpha / 255 + surface[index] * (255 - alpha) / 255)
        for index, channel in enumerate((red, green, blue))
    )
    channels = tuple(
        round(channels[index] * (1 - opacity) + surface[index] * opacity) for index in range(3)
    )
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]


def _resolve_accent(requested: str, roles: dict[str, str]) -> tuple[str, str]:
    normalized = requested.lower()

    def valid(candidate: str) -> str | None:
        if any(
            contrast_ratio(candidate, roles[surface]) < 3.0
            for surface in ("background", "surface", "surface_alt")
        ):
            return None
        for foreground in (roles["ink"], roles["background"]):
            if contrast_ratio(foreground, candidate) >= 4.5:
                return foreground
        return None

    foreground = valid(normalized)
    if foreground is not None:
        return normalized, foreground
    adjusted = _nearest_lightness(normalized, lambda candidate: valid(candidate) is not None)
    if adjusted is None:
        raise SceneResolutionError("accent_contrast_unresolvable")
    resolved_foreground = valid(adjusted)
    if resolved_foreground is None:
        raise SceneResolutionError("accent_contrast_unresolvable")
    return adjusted, resolved_foreground


def _average_edge_color(image: Image.Image) -> str:
    """Average visible boundary pixels across the 28 cells, never across seams."""

    rgba = image.convert("RGBA")
    weighted = [0.0, 0.0, 0.0]
    weight_total = 0
    for state in range(FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            left, top = column * FRAME_SIZE, state * FRAME_SIZE
            frame = rgba.crop((left, top, left + FRAME_SIZE, top + FRAME_SIZE))
            pixels = frame.load()
            if pixels is None:
                raise ValueError("sprite frame cannot be read")
            for y in range(FRAME_SIZE):
                for x in range(FRAME_SIZE):
                    red, green, blue, alpha = cast(tuple[int, int, int, int], pixels[x, y])
                    if alpha == 0:
                        continue
                    if any(
                        nx < 0
                        or ny < 0
                        or nx >= FRAME_SIZE
                        or ny >= FRAME_SIZE
                        or cast(tuple[int, int, int, int], pixels[nx, ny])[3] == 0
                        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                    ):
                        for index, channel in enumerate((red, green, blue)):
                            weighted[index] += channel * alpha
                        weight_total += alpha
    if weight_total == 0:
        raise ValueError("sprite has no visible edge")
    return "#" + "".join(f"{round(channel / weight_total):02x}" for channel in weighted)


def _nearest_lightness(color: str, acceptable: Callable[[str], bool]) -> str | None:
    lightness, chroma, hue = _to_oklch(color)
    candidates = sorted(range(1001), key=lambda value: (abs(value / 1000 - lightness), value))
    for step in candidates:
        candidate = _from_oklch(step / 1000, chroma, hue)
        if acceptable(candidate):
            return candidate
    return None


def _to_oklch(color: str) -> tuple[float, float, float]:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    red, green, blue = (
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    )
    l_root = (0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue) ** (1 / 3)
    m_root = (0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue) ** (1 / 3)
    s_root = (0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue) ** (1 / 3)
    lightness = 0.2104542553 * l_root + 0.7936177850 * m_root - 0.0040720468 * s_root
    a = 1.9779984951 * l_root - 2.4285922050 * m_root + 0.4505937099 * s_root
    b = 0.0259040371 * l_root + 0.7827717662 * m_root - 0.8086757660 * s_root
    return lightness, math.hypot(a, b), math.atan2(b, a)


def _from_oklch(lightness: float, chroma: float, hue: float) -> str:
    def linear_rgb(candidate_chroma: float) -> tuple[float, float, float]:
        a = candidate_chroma * math.cos(hue)
        b = candidate_chroma * math.sin(hue)
        l_root = lightness + 0.3963377774 * a + 0.2158037573 * b
        m_root = lightness - 0.1055613458 * a - 0.0638541728 * b
        s_root = lightness - 0.0894841775 * a - 1.2914855480 * b
        l_value, m_value, s_value = l_root**3, m_root**3, s_root**3
        return (
            4.0767416621 * l_value - 3.3077115913 * m_value + 0.2309699292 * s_value,
            -1.2684380046 * l_value + 2.6097574011 * m_value - 0.3413193965 * s_value,
            -0.0041960863 * l_value - 0.7034186147 * m_value + 1.7076147010 * s_value,
        )

    rgb = linear_rgb(chroma)
    if not all(-1e-9 <= channel <= 1 + 1e-9 for channel in rgb):
        low, high = 0.0, chroma
        for _ in range(24):
            middle = (low + high) / 2
            if all(-1e-9 <= channel <= 1 + 1e-9 for channel in linear_rgb(middle)):
                low = middle
            else:
                high = middle
        rgb = linear_rgb(low)
    encoded = tuple(
        12.92 * min(1.0, max(0.0, channel))
        if channel <= 0.0031308
        else 1.055 * min(1.0, max(0.0, channel)) ** (1 / 2.4) - 0.055
        for channel in rgb
    )
    return "#" + "".join(f"{int(channel * 255 + 0.5):02x}" for channel in encoded)
