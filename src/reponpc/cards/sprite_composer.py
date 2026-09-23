"""Compile versioned built-in character packs to the canonical sprite sheet.

The compiler is deliberately species-agnostic. Pack-local option names and
rendering live behind the registry boundary; the public core contract knows
only a pack ID/version, bounded string options, and the canonical four-by-seven
sprite output shared with uploaded characters.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
from types import MappingProxyType
from typing import Any, Final, NamedTuple

from PIL import Image, ImageDraw

from reponpc.cards.assets import (
    FRAME_COLUMNS,
    FRAME_ROWS,
    FRAME_SIZE,
    HEIGHT,
    STATE_ROWS,
    WIDTH,
    validate_sprite,
)
from reponpc.config.models import (
    CHARACTER_OPTION_ID_RE,
    CHARACTER_PACK_ID_RE,
    BuiltinCharacterPackConfig,
)

CANVAS_WIDTH: Final = WIDTH
CANVAS_HEIGHT: Final = HEIGHT
FRAME_WIDTH: Final = FRAME_SIZE
FRAME_HEIGHT: Final = FRAME_SIZE
STATE_NAMES: Final[tuple[str, ...]] = STATE_ROWS
_HUMANOID_SOURCE_FRAME_SIZE: Final = 32
_HUMANOID_LAYER_ORDER: Final[tuple[str, ...]] = ("body", "outfit", "hair", "accessory")
_HUMANOID_BODY_IDS: Final[frozenset[str]] = frozenset({"standard"})
_HUMANOID_TONE_IDS: Final[frozenset[str]] = frozenset({"light", "medium", "dark"})
_HUMANOID_HAIRSTYLE_IDS: Final[frozenset[str]] = frozenset({"none", "short", "long"})
_HUMANOID_ATTIRE_IDS: Final[frozenset[str]] = frozenset({"adventurer", "engineer", "mage"})
_HUMANOID_ACCESSORY_IDS: Final[frozenset[str]] = frozenset({"none", "glasses", "headphones"})

_HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$")
_HUMANOID_TONE_PALETTE: Final[dict[str, tuple[int, int, int, int]]] = {
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

    def __init__(self, code: str, message: str | None = None, *, field: str | None = None) -> None:
        self.code = code
        self.error_code = code
        self.field = field
        super().__init__(
            f"{code}: {message or _ERROR_MESSAGES.get(code, 'sprite composition failed')}"
        )


_ERROR_MESSAGES: Final[dict[str, str]] = {
    "INVALID_CONFIG": "built-in character pack configuration is invalid",
    "MISSING_LAYER": "built-in character layer is missing",
    "UNKNOWN_ID": "built-in pack option is not allowlisted",
    "INVALID_COLOR": "built-in pack color is invalid",
    "INVALID_REGISTRY": "built-in character pack registry is invalid",
    "UNKNOWN_PACK": "built-in character pack is not registered",
    "PACK_VERSION_UNSUPPORTED": "built-in character pack version is unsupported",
    "MISSING_OPTION": "required built-in pack option is missing",
    "UNKNOWN_OPTION": "built-in pack option is unknown",
    "INVALID_OPTION": "built-in pack option is invalid",
    "RENDER_ERROR": "built-in character pack could not be rendered",
}


@dataclass(frozen=True, slots=True)
class CharacterPackOption:
    """One pack-owned option contract; core code does not interpret its name."""

    kind: str
    choices: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class CharacterPack:
    """Trusted built-in pack manifest plus its deterministic renderer."""

    pack_id: str
    version: int
    options: Mapping[str, CharacterPackOption]
    renderer: Callable[[Mapping[str, str]], bytes]


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
        raise SpriteComposerError("INVALID_COLOR", field, field=field)
    try:
        return (*bytes.fromhex(value[1:]), 255)
    except ValueError:
        raise SpriteComposerError("INVALID_COLOR", field, field=field) from None


def _pack_config_values(
    config: BuiltinCharacterPackConfig | Mapping[str, Any],
) -> tuple[str, int, Mapping[str, str]]:
    if isinstance(config, BuiltinCharacterPackConfig):
        return config.pack_id, config.pack_version, config.options
    if not isinstance(config, Mapping) or set(config) != {
        "pack_id",
        "pack_version",
        "options",
    }:
        raise SpriteComposerError("INVALID_CONFIG")
    pack_id = config["pack_id"]
    pack_version = config["pack_version"]
    options = config["options"]
    if (
        not isinstance(pack_id, str)
        or not isinstance(pack_version, int)
        or isinstance(pack_version, bool)
        or not isinstance(options, Mapping)
        or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in options.items()
        )
    ):
        raise SpriteComposerError("INVALID_CONFIG")
    return pack_id, pack_version, options


def _resolve_pack(
    pack_id: str,
    pack_version: int,
    registry: Mapping[tuple[str, int], CharacterPack],
) -> CharacterPack:
    pack = registry.get((pack_id, pack_version))
    if pack is not None:
        return pack
    if any(registered_id == pack_id for registered_id, _version in registry):
        raise SpriteComposerError("PACK_VERSION_UNSUPPORTED")
    raise SpriteComposerError("UNKNOWN_PACK")


def _normalize_pack_options(pack: CharacterPack, supplied: Mapping[str, str]) -> Mapping[str, str]:
    expected = set(pack.options)
    actual = set(supplied)
    if actual - expected:
        field = sorted(actual - expected)[0]
        raise SpriteComposerError("UNKNOWN_OPTION", field=field)
    if expected - actual:
        field = sorted(expected - actual)[0]
        raise SpriteComposerError("MISSING_OPTION", field=field)

    normalized: dict[str, str] = {}
    for field, contract in pack.options.items():
        value = supplied[field]
        if contract.kind == "choice":
            if value not in contract.choices:
                raise SpriteComposerError("INVALID_OPTION", field=field)
            normalized[field] = value
        elif contract.kind == "color":
            if _HEX_COLOR.fullmatch(value) is None:
                raise SpriteComposerError("INVALID_COLOR", field=field)
            normalized[field] = value.lower()
        else:
            raise SpriteComposerError("INVALID_REGISTRY")
    return MappingProxyType(normalized)


def _humanoid_render_spec(values: Mapping[str, str]) -> _RenderSpec:
    return _RenderSpec(
        state_index=0,
        frame_index=0,
        x=0,
        y=0,
        skin=_HUMANOID_TONE_PALETTE[values["tone"]],
        hair=_hex(values["hair_color"], "hair_color"),
        primary=_hex(values["primary_color"], "primary_color"),
        secondary=_hex(values["secondary_color"], "secondary_color"),
        outfit=values["attire"],
        hair_style=values["hairstyle"],
        accessory=values["accessory"],
    )


def _pixel(draw: ImageDraw.ImageDraw, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if 0 <= x < _HUMANOID_SOURCE_FRAME_SIZE and 0 <= y < _HUMANOID_SOURCE_FRAME_SIZE:
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


def _humanoid_registry_is_valid() -> bool:
    expected_layers = set(_HUMANOID_LAYER_ORDER)
    if set(_HUMANOID_LAYER_REGISTRY) != expected_layers:
        return False
    expected_ids = {
        "body": _HUMANOID_BODY_IDS,
        "outfit": _HUMANOID_ATTIRE_IDS,
        "hair": _HUMANOID_HAIRSTYLE_IDS,
        "accessory": _HUMANOID_ACCESSORY_IDS,
    }
    for layer, ids in expected_ids.items():
        registry = _HUMANOID_LAYER_REGISTRY.get(layer)
        if not isinstance(registry, Mapping) or set(registry) != set(ids):
            return False
        if any(not callable(drawer) for drawer in registry.values()):
            return False
    return True


# This renderer is local to the humanoid pack. Core pack compilation never
# branches on these layer names, so another pack can expose unrelated options.
_HUMANOID_LAYER_REGISTRY: dict[
    str, dict[str, Callable[[ImageDraw.ImageDraw, _RenderSpec], None]]
] = {
    "body": {"standard": _draw_body},
    "outfit": {name: _draw_outfit for name in _HUMANOID_ATTIRE_IDS},
    "hair": {name: _draw_hair for name in _HUMANOID_HAIRSTYLE_IDS},
    "accessory": {name: _draw_accessory for name in _HUMANOID_ACCESSORY_IDS},
}


def _render_humanoid_pack(options: Mapping[str, str]) -> bytes:
    if not _humanoid_registry_is_valid():
        raise SpriteComposerError("INVALID_REGISTRY")
    base = _humanoid_render_spec(options)
    image = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    try:
        for state_index, _state in enumerate(STATE_NAMES):
            for frame_index in range(FRAME_COLUMNS):
                # Tiny deterministic offsets create readable state animation
                # while keeping the silhouette inside this pack's private
                # 32px source frame before canonical 64px expansion.
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
                # 32px source image. This keeps this pack's clipping/layer
                # order explicit before expansion to the shared 64px format.
                local = Image.new(
                    "RGBA",
                    (_HUMANOID_SOURCE_FRAME_SIZE, _HUMANOID_SOURCE_FRAME_SIZE),
                    (0, 0, 0, 0),
                )
                draw = ImageDraw.Draw(local)
                _HUMANOID_LAYER_REGISTRY["body"]["standard"](draw, spec)
                _HUMANOID_LAYER_REGISTRY["outfit"][spec.outfit](draw, spec)
                _HUMANOID_LAYER_REGISTRY["hair"][spec.hair_style](draw, spec)
                _HUMANOID_LAYER_REGISTRY["accessory"][spec.accessory](draw, spec)
                canonical_frame = local.resize(
                    (FRAME_WIDTH, FRAME_HEIGHT), Image.Resampling.NEAREST
                )
                image.alpha_composite(
                    canonical_frame,
                    (frame_index * FRAME_WIDTH, state_index * FRAME_HEIGHT),
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


_HUMANOID_PACK = CharacterPack(
    pack_id="core/humanoid",
    version=1,
    options=MappingProxyType(
        {
            "tone": CharacterPackOption("choice", _HUMANOID_TONE_IDS),
            "hairstyle": CharacterPackOption("choice", _HUMANOID_HAIRSTYLE_IDS),
            "attire": CharacterPackOption("choice", _HUMANOID_ATTIRE_IDS),
            "accessory": CharacterPackOption("choice", _HUMANOID_ACCESSORY_IDS),
            "hair_color": CharacterPackOption("color"),
            "primary_color": CharacterPackOption("color"),
            "secondary_color": CharacterPackOption("color"),
        }
    ),
    renderer=_render_humanoid_pack,
)

PACK_REGISTRY: Final[Mapping[tuple[str, int], CharacterPack]] = MappingProxyType(
    {(_HUMANOID_PACK.pack_id, _HUMANOID_PACK.version): _HUMANOID_PACK}
)


def _pack_registry_is_valid(registry: Mapping[tuple[str, int], CharacterPack]) -> bool:
    if not registry:
        return False
    for key, pack in registry.items():
        if not isinstance(key, tuple) or len(key) != 2 or not isinstance(pack, CharacterPack):
            return False
        if (
            key != (pack.pack_id, pack.version)
            or not isinstance(pack.pack_id, str)
            or CHARACTER_PACK_ID_RE.fullmatch(pack.pack_id) is None
            or not isinstance(pack.version, int)
            or isinstance(pack.version, bool)
            or pack.version < 1
        ):
            return False
        if (
            not isinstance(pack.options, Mapping)
            or not callable(pack.renderer)
            or len(pack.options) > 32
        ):
            return False
        for option_id, option in pack.options.items():
            if (
                not isinstance(option_id, str)
                or CHARACTER_OPTION_ID_RE.fullmatch(option_id) is None
                or not isinstance(option, CharacterPackOption)
            ):
                return False
            if option.kind == "choice" and (
                not option.choices
                or any(
                    not isinstance(choice, str) or not choice or len(choice) > 128
                    for choice in option.choices
                )
            ):
                return False
            if option.kind == "color" and option.choices:
                return False
            if option.kind not in {"choice", "color"}:
                return False
    return True


def validate_builtin_pack(
    config: BuiltinCharacterPackConfig | Mapping[str, Any],
    *,
    registry: Mapping[tuple[str, int], CharacterPack] = PACK_REGISTRY,
) -> tuple[CharacterPack, Mapping[str, str]]:
    """Resolve and validate a pack config without rendering it."""

    if not _pack_registry_is_valid(registry):
        raise SpriteComposerError("INVALID_REGISTRY")
    pack_id, pack_version, options = _pack_config_values(config)
    pack = _resolve_pack(pack_id, pack_version, registry)
    return pack, _normalize_pack_options(pack, options)


def compose_builtin(
    config: BuiltinCharacterPackConfig | Mapping[str, Any],
    *,
    registry: Mapping[tuple[str, int], CharacterPack] = PACK_REGISTRY,
) -> bytes:
    """Compile a registered built-in pack without knowing its species or slots."""

    pack, options = validate_builtin_pack(config, registry=registry)
    try:
        rendered = pack.renderer(options)
        return validate_sprite(rendered).content
    except SpriteComposerError:
        raise
    except Exception as exc:
        raise SpriteComposerError("RENDER_ERROR") from exc


__all__ = [
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "FRAME_COLUMNS",
    "FRAME_HEIGHT",
    "FRAME_ROWS",
    "FRAME_WIDTH",
    "PACK_REGISTRY",
    "STATE_NAMES",
    "CharacterPack",
    "CharacterPackOption",
    "SpriteComposerError",
    "compose_builtin",
    "validate_builtin_pack",
]
