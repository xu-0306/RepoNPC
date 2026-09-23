from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from reponpc.cards.sprite_composer import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FRAME_HEIGHT,
    FRAME_ROWS,
    FRAME_WIDTH,
    STATE_NAMES,
    CharacterPack,
    CharacterPackOption,
    SpriteComposerError,
    compose_builtin,
)
from reponpc.config.models import BuiltinCharacterPackConfig


def _config(**updates: object) -> BuiltinCharacterPackConfig:
    data: dict[str, object] = {
        "pack_id": "core/humanoid",
        "pack_version": 1,
        "options": {
            "tone": "medium",
            "hairstyle": "short",
            "attire": "adventurer",
            "hair_color": "#2b1d14",
            "primary_color": "#6d5dfc",
            "secondary_color": "#f2c14e",
            "accessory": "glasses",
        },
    }
    data.update(updates)
    return BuiltinCharacterPackConfig.model_validate(data)


def test_composer_returns_canonical_rgba_sheet_with_all_frames_visible() -> None:
    raw = compose_builtin(_config())
    with Image.open(BytesIO(raw)) as sheet:
        assert sheet.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
        assert sheet.mode == "RGBA"
        pixels = sheet.load()
        assert any(pixels[x, y][3] == 0 for x in range(CANVAS_WIDTH) for y in range(CANVAS_HEIGHT))
        for row in range(FRAME_ROWS):
            for column in range(4):
                assert any(
                    pixels[x, y][3] > 0
                    for x in range(column * FRAME_WIDTH, (column + 1) * FRAME_WIDTH)
                    for y in range(row * FRAME_HEIGHT, (row + 1) * FRAME_HEIGHT)
                )


def test_composition_is_byte_for_byte_deterministic() -> None:
    config = _config()
    assert compose_builtin(config) == compose_builtin(config)


def test_pack_local_palette_options_are_visible_in_output() -> None:
    options = dict(_config().options)
    options.update(hair_color="#010203", primary_color="#040506", secondary_color="#070809")
    raw = compose_builtin(_config(options=options))
    with Image.open(BytesIO(raw)) as sheet:
        pixels = sheet.load()
        colors = {pixels[x, y] for x in range(CANVAS_WIDTH) for y in range(CANVAS_HEIGHT)}
    assert (1, 2, 3, 255) in colors
    assert (4, 5, 6, 255) in colors
    assert (7, 8, 9, 255) in colors


def test_unknown_missing_and_invalid_pack_options_have_stable_errors() -> None:
    options = dict(_config().options)
    options["cape"] = "yes"
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(_config(options=options))
    assert captured.value.code == "UNKNOWN_OPTION"
    assert captured.value.field == "cape"

    options = dict(_config().options)
    del options["hairstyle"]
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(_config(options=options))
    assert captured.value.code == "MISSING_OPTION"
    assert captured.value.field == "hairstyle"

    options = dict(_config().options)
    options["attire"] = "spacesuit"
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(_config(options=options))
    assert captured.value.code == "INVALID_OPTION"
    assert captured.value.field == "attire"


def test_unknown_pack_and_version_never_fall_back() -> None:
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(_config(pack_id="community/unknown"))
    assert captured.value.code == "UNKNOWN_PACK"

    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(_config(pack_version=2))
    assert captured.value.code == "PACK_VERSION_UNSUPPORTED"


def test_legacy_humanoid_fields_are_not_part_of_the_core_schema() -> None:
    with pytest.raises(ValidationError):
        BuiltinCharacterPackConfig.model_validate(
            {
                "pack_id": "core/humanoid",
                "pack_version": 1,
                "options": {},
                "body": "standard",
            }
        )


def _render_orb(options: Mapping[str, str]) -> bytes:
    palette = {"cyan": (0, 255, 255, 255), "magenta": (255, 0, 255, 255)}
    image = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(FRAME_ROWS):
        for column in range(4):
            left = column * FRAME_WIDTH + 12
            top = row * FRAME_HEIGHT + 12
            draw.ellipse((left, top, left + 7, top + 7), fill=palette[options["glow"]])
    output = BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def test_generic_pack_compiler_accepts_non_humanoid_pack_without_core_changes() -> None:
    pack = CharacterPack(
        pack_id="fixture/floating-orb",
        version=3,
        options={"glow": CharacterPackOption("choice", frozenset({"cyan", "magenta"}))},
        renderer=_render_orb,
    )
    config = BuiltinCharacterPackConfig.model_validate(
        {
            "pack_id": "fixture/floating-orb",
            "pack_version": 3,
            "options": {"glow": "cyan"},
        }
    )

    raw = compose_builtin(config, registry={(pack.pack_id, pack.version): pack})

    with Image.open(BytesIO(raw)) as sheet:
        assert sheet.size == (CANVAS_WIDTH, CANVAS_HEIGHT)
        pixels = sheet.load()
        assert any(
            pixels[x, y] == (0, 255, 255, 255)
            for x in range(CANVAS_WIDTH)
            for y in range(CANVAS_HEIGHT)
        )


def test_pack_registry_and_renderer_fail_closed() -> None:
    invalid_pack = CharacterPack(
        pack_id="Fixture/invalid",
        version=1,
        options={},
        renderer=lambda _options: b"not a sprite",
    )
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(
            {
                "pack_id": "Fixture/invalid",
                "pack_version": 1,
                "options": {},
            },
            registry={(invalid_pack.pack_id, invalid_pack.version): invalid_pack},
        )
    assert captured.value.code == "INVALID_REGISTRY"

    noncanonical_pack = CharacterPack(
        pack_id="fixture/noncanonical",
        version=1,
        options={},
        renderer=lambda _options: b"not a sprite",
    )
    with pytest.raises(SpriteComposerError) as captured:
        compose_builtin(
            BuiltinCharacterPackConfig(pack_id="fixture/noncanonical", pack_version=1, options={}),
            registry={(noncanonical_pack.pack_id, noncanonical_pack.version): noncanonical_pack},
        )
    assert captured.value.code == "RENDER_ERROR"


def test_state_rows_remain_the_closed_animation_protocol() -> None:
    assert STATE_NAMES == ("idle", "walk", "listen", "think", "talk", "success", "offline")
