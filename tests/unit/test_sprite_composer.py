from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from reponpc.cards.sprite_composer import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    FRAME_HEIGHT,
    FRAME_ROWS,
    FRAME_WIDTH,
    LAYER_ORDER,
    STATE_NAMES,
    SpriteComposerError,
    compose_builtin,
)
from reponpc.config.models import BuiltinCharacterConfig


def _config(**updates: object) -> BuiltinCharacterConfig:
    data: dict[str, object] = {
        "body": "standard",
        "skin": "medium",
        "hair": "short",
        "hair_color": "#2b1d14",
        "outfit": "adventurer",
        "primary_color": "#6d5dfc",
        "secondary_color": "#f2c14e",
        "accessory": "glasses",
    }
    data.update(updates)
    return BuiltinCharacterConfig.model_validate(data)


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


def test_palette_substitution_is_visible_in_output() -> None:
    raw = compose_builtin(
        _config(hair_color="#010203", primary_color="#040506", secondary_color="#070809")
    )
    with Image.open(BytesIO(raw)) as sheet:
        pixels = sheet.load()
        colors = {pixels[x, y] for x in range(CANVAS_WIDTH) for y in range(CANVAS_HEIGHT)}
    assert (1, 2, 3, 255) in colors
    assert (4, 5, 6, 255) in colors
    assert (7, 8, 9, 255) in colors


def test_mapping_input_uses_exact_contract_and_rejects_unknown_id() -> None:
    values = _config().model_dump()
    values["accessory"] = "cape"
    with pytest.raises(SpriteComposerError) as exc_info:
        compose_builtin(values)
    assert exc_info.value.code == "UNKNOWN_ID"


def test_malformed_colors_and_missing_layers_have_stable_errors() -> None:
    values = _config().model_dump()
    values["hair_color"] = "#ABCDEF"
    with pytest.raises(SpriteComposerError) as exc_info:
        compose_builtin(values)
    assert exc_info.value.code == "INVALID_COLOR"

    del values["hair"]
    with pytest.raises(SpriteComposerError) as exc_info:
        compose_builtin(values)
    assert exc_info.value.code == "MISSING_LAYER"


def test_layer_order_is_frozen() -> None:
    assert LAYER_ORDER == ("body", "outfit", "hair", "accessory")
    assert STATE_NAMES == ("idle", "walk", "listen", "think", "talk", "success", "offline")
