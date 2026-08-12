"""Deterministic composition of RepoNPC's built-in character sheet.

The built-in character is intentionally drawn here instead of loading image
files.  Keeping the masks and primitives in this module makes composition
pure, reproducible, and safe to run while building an immutable bundle.  The
result uses the same canonical sheet contract as uploaded characters: four
``32 x 32`` RGBA frames for each of the seven ordered states.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from io import BytesIO
from typing import Any, Final, NamedTuple

from PIL import Image, ImageDraw

from reponpc.config.models import BuiltinCharacterConfig

CANVAS_WIDTH: Final = 128
CANVAS_HEIGHT: Final = 224
FRAME_WIDTH: Final = 32
FRAME_HEIGHT: Final = 32
FRAME_COLUMNS: Final = 4
FRAME_ROWS: Final = 7
STATE_NAMES: Final[tuple[str, ...]] = (
    "idle",
    "walk",
    "listen",
    "think",
    "talk",
    "success",
    "offline",
)
LAYER_ORDER: Final[tuple[str, ...]] = ("body", "outfit", "hair", "accessory")

BODY_IDS: Final[frozenset[str]] = frozenset({"standard"})
SKIN_IDS: Final[frozenset[str]] = frozenset({"light", "medium", "dark"})
HAIR_IDS: Final[frozenset[str]] = frozenset({"none", "short", "long"})
OUTFIT_IDS: Final[frozenset[str]] = frozenset({"adventurer", "engineer", "mage"})
ACCESSORY_IDS: Final[frozenset[str]] = frozenset({"none", "glasses", "headphones"})

_HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$")
_SKIN_PALETTE: Final[dict[str, tuple[int, int, int, int]]] = {
    "light": (244, 194, 157, 255),
    "medium": (198, 137, 94, 255),
    "dark": (117, 73, 48, 255),
}
_OUTLINE: Final[tuple[int, int, int, int]] = (34, 27, 42, 255)
_SHADOW: Final[tuple[int, int, int, int]] = (44, 36, 56, 180)
_WHITE: Final[tuple[int, int, int, int]] = (255, 255, 255, 255)
_GLASS: Final[tuple[int, int, int, int]] = (177, 225, 246, 235)


class SpriteComposerError(ValueError):
    """Stable, safe failure raised for invalid composition input/registries."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.error_code = code
        super().__init__(
            f"{code}: {message or _ERROR_MESSAGES.get(code, 'sprite composition failed')}"
        )


_ERROR_MESSAGES: Final[dict[str, str]] = {
    "INVALID_CONFIG": "built-in character configuration is invalid",
    "MISSING_LAYER": "built-in character layer is missing",
    "UNKNOWN_ID": "built-in character ID is not allowlisted",
    "INVALID_COLOR": "built-in character color is invalid",
    "INVALID_REGISTRY": "built-in character registry is invalid",
    "RENDER_ERROR": "built-in character could not be rendered",
}


class _RenderSpec(NamedTuple):
    state_index: int
    frame_index: int
    x: int
    y: int
    skin: tuple[int, int, int, int]
    hair: tuple[int, int, int, int]
    primary: tuple[int, int, int, int]
    secondary: tuple[int, int, int, int]
    outfit: str
    hair_style: str
    accessory: str


def _hex(value: Any, field: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or _HEX_COLOR.fullmatch(value) is None:
        raise SpriteComposerError("INVALID_COLOR", field)
    try:
        return (*bytes.fromhex(value[1:]), 255)
    except ValueError:
        raise SpriteComposerError("INVALID_COLOR", field) from None


def _value(config: Any, field: str) -> Any:
    """Read a config field without allowing a missing layer to disappear."""

    if isinstance(config, Mapping):
        if field not in config:
            raise SpriteComposerError("MISSING_LAYER", field)
        return config[field]
    try:
        return getattr(config, field)
    except AttributeError:
        raise SpriteComposerError("MISSING_LAYER", field) from None


def _config_values(config: BuiltinCharacterConfig | Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(config, BuiltinCharacterConfig):
        return {field: getattr(config, field) for field in _CONFIG_FIELDS}
    if isinstance(config, Mapping):
        values = dict(config)
    else:
        # A model constructed by pydantic (or a small test double) still has
        # the exact same field contract.  Unknown objects fail safely below.
        values = {}
        for field in _CONFIG_FIELDS:
            values[field] = _value(config, field)
    unknown = set(values) - set(_CONFIG_FIELDS)
    if unknown:
        raise SpriteComposerError("INVALID_CONFIG")
    missing = set(_CONFIG_FIELDS) - set(values)
    if missing:
        raise SpriteComposerError("MISSING_LAYER", sorted(missing)[0])
    return values


_CONFIG_FIELDS: Final[tuple[str, ...]] = (
    "body",
    "skin",
    "hair",
    "hair_color",
    "outfit",
    "primary_color",
    "secondary_color",
    "accessory",
)


def _validate_values(config: BuiltinCharacterConfig | Mapping[str, Any] | Any) -> _RenderSpec:
    values = _config_values(config)
    body = values["body"]
    skin_id = values["skin"]
    hair_style = values["hair"]
    outfit = values["outfit"]
    accessory = values["accessory"]

    def allowlisted(value: Any, choices: frozenset[str]) -> bool:
        return isinstance(value, str) and value in choices

    if not allowlisted(body, BODY_IDS):
        raise SpriteComposerError("UNKNOWN_ID")
    if not allowlisted(skin_id, SKIN_IDS):
        raise SpriteComposerError("UNKNOWN_ID")
    if not allowlisted(hair_style, HAIR_IDS):
        raise SpriteComposerError("UNKNOWN_ID")
    if not allowlisted(outfit, OUTFIT_IDS):
        raise SpriteComposerError("UNKNOWN_ID")
    if not allowlisted(accessory, ACCESSORY_IDS):
        raise SpriteComposerError("UNKNOWN_ID")
    return _RenderSpec(
        state_index=0,
        frame_index=0,
        x=0,
        y=0,
        skin=_SKIN_PALETTE[skin_id],
        hair=_hex(values["hair_color"], "hair_color"),
        primary=_hex(values["primary_color"], "primary_color"),
        secondary=_hex(values["secondary_color"], "secondary_color"),
        outfit=outfit,
        hair_style=hair_style,
        accessory=accessory,
    )


def _pixel(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if 0 <= x < FRAME_WIDTH and 0 <= y < FRAME_HEIGHT:
        draw.point((x, y), fill=color)


def _rect(
    draw: ImageDraw.ImageDraw,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int, int],
) -> None:
    draw.rectangle((x0, y0, x1, y1), fill=color)


def _draw_body(draw: ImageDraw.ImageDraw, spec: _RenderSpec) -> None:
    """Draw body/skin first; outfit and all other layers cover it later."""

    x, y, skin = spec.x, spec.y, spec.skin
    # A one-pixel ground shadow anchors every state while retaining sheet
    # transparency around the character.
    draw.ellipse((x + 7, y + 28, x + 24, y + 31), fill=_SHADOW)
    _rect(draw, x + 10, y + 22, x + 14, y + 29, _OUTLINE)
    _rect(draw, x + 18, y + 22, x + 22, y + 29, _OUTLINE)
    _rect(draw, x + 11, y + 23, x + 13, y + 29, skin)
    _rect(draw, x + 19, y + 23, x + 21, y + 29, skin)
    _rect(draw, x + 9, y + 13, x + 23, y + 24, _OUTLINE)
    _rect(draw, x + 10, y + 14, x + 22, y + 23, skin)
    _rect(draw, x + 9, y + 6, x + 23, y + 15, _OUTLINE)
    _rect(draw, x + 10, y + 7, x + 22, y + 14, skin)
    _rect(draw, x + 8, y + 9, x + 9, y + 12, skin)
    _rect(draw, x + 23, y + 9, x + 24, y + 12, skin)

    # State-specific arm/hand poses are part of the body layer, so the layer
    # order remains body -> outfit -> hair -> accessory for every frame.
    if spec.state_index == 1:  # walk
        _rect(draw, x + 6 + (spec.frame_index % 2), y + 16, x + 9, y + 21, skin)
        _rect(draw, x + 23 - (spec.frame_index % 2), y + 15, x + 26, y + 20, skin)
    elif spec.state_index == 2:  # listen
        _rect(draw, x + 5, y + 14, x + 9, y + 18, skin)
        _pixel(draw, x + 5, y + 13, skin)
    elif spec.state_index == 3:  # think
        _rect(draw, x + 23, y + 13, x + 26, y + 17, skin)
        _rect(draw, x + 25, y + 11, x + 27, y + 14, skin)
    elif spec.state_index == 5:  # success
        _rect(draw, x + 5, y + 11, x + 8, y + 16, skin)
        _rect(draw, x + 24, y + 11, x + 27, y + 16, skin)
        _pixel(draw, x + 5, y + 10, skin)
        _pixel(draw, x + 27, y + 10, skin)
    elif spec.state_index == 6:  # offline
        _rect(draw, x + 6, y + 16, x + 9, y + 20, skin)
        _rect(draw, x + 23, y + 16, x + 26, y + 20, skin)


def _draw_outfit(draw: ImageDraw.ImageDraw, spec: _RenderSpec) -> None:
    x, y, primary, secondary = spec.x, spec.y, spec.primary, spec.secondary
    if spec.outfit == "adventurer":
        _rect(draw, x + 9, y + 14, x + 23, y + 22, primary)
        _rect(draw, x + 8, y + 21, x + 24, y + 23, secondary)
        _rect(draw, x + 11, y + 14, x + 12, y + 19, secondary)
        _rect(draw, x + 20, y + 14, x + 21, y + 19, secondary)
    elif spec.outfit == "engineer":
        _rect(draw, x + 9, y + 14, x + 23, y + 23, primary)
        _rect(draw, x + 12, y + 15, x + 13, y + 22, secondary)
        _rect(draw, x + 19, y + 15, x + 20, y + 22, secondary)
        _rect(draw, x + 9, y + 21, x + 23, y + 23, secondary)
        _pixel(draw, x + 16, y + 18, secondary)
    elif spec.outfit == "mage":
        draw.polygon(
            ((x + 9, y + 14), (x + 23, y + 14), (x + 25, y + 24), (x + 7, y + 24)),
            fill=primary,
        )
        _rect(draw, x + 14, y + 14, x + 18, y + 24, secondary)
        _pixel(draw, x + 16, y + 18, _WHITE)
    else:  # Defensive check for a mutated/invalid registry/config.
        raise SpriteComposerError("UNKNOWN_ID")

    # Mouth and state marks are within the outfit primitive's face/torso
    # palette and make talk/success/offline states visibly distinct.
    if spec.state_index == 4:  # talk
        _rect(draw, x + 15, y + 12, x + 17, y + 13, _OUTLINE)
    elif spec.state_index == 5:  # success
        _rect(draw, x + 14, y + 11, x + 18, y + 12, _WHITE)
    elif spec.state_index == 6:  # offline
        _rect(draw, x + 14, y + 11, x + 18, y + 12, _OUTLINE)


def _draw_hair(draw: ImageDraw.ImageDraw, spec: _RenderSpec) -> None:
    if spec.hair_style == "none":
        return
    x, y, hair = spec.x, spec.y, spec.hair
    if spec.hair_style == "short":
        _rect(draw, x + 9, y + 5, x + 23, y + 8, hair)
        _rect(draw, x + 10, y + 4, x + 20, y + 6, hair)
        _pixel(draw, x + 22, y + 7, hair)
    elif spec.hair_style == "long":
        _rect(draw, x + 9, y + 5, x + 23, y + 8, hair)
        _rect(draw, x + 9, y + 7, x + 11, y + 17, hair)
        _rect(draw, x + 21, y + 7, x + 23, y + 17, hair)
        _pixel(draw, x + 12, y + 5, hair)
    else:
        raise SpriteComposerError("UNKNOWN_ID")


def _draw_accessory(draw: ImageDraw.ImageDraw, spec: _RenderSpec) -> None:
    x, y = spec.x, spec.y
    if spec.accessory == "none":
        return
    if spec.accessory == "glasses":
        _rect(draw, x + 11, y + 9, x + 15, y + 12, _OUTLINE)
        _rect(draw, x + 17, y + 9, x + 21, y + 12, _OUTLINE)
        _rect(draw, x + 12, y + 10, x + 14, y + 11, _GLASS)
        _rect(draw, x + 18, y + 10, x + 20, y + 11, _GLASS)
        _rect(draw, x + 15, y + 10, x + 17, y + 10, _OUTLINE)
    elif spec.accessory == "headphones":
        _rect(draw, x + 8, y + 8, x + 10, y + 14, spec.secondary)
        _rect(draw, x + 22, y + 8, x + 24, y + 14, spec.secondary)
        _rect(draw, x + 9, y + 6, x + 10, y + 9, spec.secondary)
        _rect(draw, x + 22, y + 6, x + 23, y + 9, spec.secondary)
    else:
        raise SpriteComposerError("UNKNOWN_ID")


def _registry_is_valid() -> bool:
    expected_layers = set(LAYER_ORDER)
    if set(LAYER_REGISTRY) != expected_layers:
        return False
    expected_ids = {
        "body": BODY_IDS,
        "outfit": OUTFIT_IDS,
        "hair": HAIR_IDS,
        "accessory": ACCESSORY_IDS,
    }
    for layer, ids in expected_ids.items():
        registry = LAYER_REGISTRY.get(layer)
        if not isinstance(registry, Mapping) or set(registry) != set(ids):
            return False
        if any(not callable(drawer) for drawer in registry.values()):
            return False
    return True


# Public to make the stable module-owned IDs auditable; composition verifies
# its shape every call so accidental edits cannot silently select a fallback.
LAYER_REGISTRY: dict[str, dict[str, Callable[[ImageDraw.ImageDraw, _RenderSpec], None]]] = {
    "body": {"standard": _draw_body},
    "outfit": {name: _draw_outfit for name in OUTFIT_IDS},
    "hair": {name: _draw_hair for name in HAIR_IDS},
    "accessory": {name: _draw_accessory for name in ACCESSORY_IDS},
}


def compose_builtin(config: BuiltinCharacterConfig) -> bytes:
    """Compose one canonical deterministic RGBA PNG from a built-in config.

    ``BuiltinCharacterConfig`` is the supported public input.  A mapping is
    accepted only as a convenience for callers decoding strict YAML; it is
    validated against the exact same field and ID contract and never falls
    back to another character.
    """

    if not _registry_is_valid():
        raise SpriteComposerError("INVALID_REGISTRY")
    base = _validate_values(config)
    image = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    try:
        for state_index, _state in enumerate(STATE_NAMES):
            for frame_index in range(FRAME_COLUMNS):
                # Tiny deterministic offsets create readable state animation
                # while keeping the silhouette inside the 32x32 frame.
                if state_index == 1:
                    x_offset = (0, 1, 0, -1)[frame_index]
                elif state_index == 5:
                    x_offset = (0, 0, 1, 0)[frame_index]
                else:
                    x_offset = 0
                y_offset = (0, 1, 0, 1)[frame_index] if state_index == 0 else 0
                spec = base._replace(
                    state_index=state_index,
                    frame_index=frame_index,
                    x=x_offset,
                    y=y_offset,
                )
                # Draw into absolute sheet coordinates by translating each
                # primitive's local frame coordinates through a temporary
                # 32x32 image.  This keeps clipping and layer order explicit.
                local = Image.new("RGBA", (FRAME_WIDTH, FRAME_HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(local)
                LAYER_REGISTRY["body"]["standard"](draw, spec)
                LAYER_REGISTRY["outfit"][spec.outfit](draw, spec)
                LAYER_REGISTRY["hair"][spec.hair_style](draw, spec)
                LAYER_REGISTRY["accessory"][spec.accessory](draw, spec)
                image.alpha_composite(
                    local, (frame_index * FRAME_WIDTH, state_index * FRAME_HEIGHT)
                )
    except SpriteComposerError:
        raise
    except Exception as exc:
        raise SpriteComposerError("RENDER_ERROR") from exc

    output = BytesIO()
    try:
        image.save(output, format="PNG", optimize=False, compress_level=9)
    except Exception as exc:
        raise SpriteComposerError("RENDER_ERROR") from exc
    return output.getvalue()


__all__ = [
    "ACCESSORY_IDS",
    "BODY_IDS",
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "FRAME_COLUMNS",
    "FRAME_HEIGHT",
    "FRAME_ROWS",
    "FRAME_WIDTH",
    "HAIR_IDS",
    "LAYER_ORDER",
    "LAYER_REGISTRY",
    "OUTFIT_IDS",
    "SKIN_IDS",
    "STATE_NAMES",
    "SpriteComposerError",
    "compose_builtin",
]
