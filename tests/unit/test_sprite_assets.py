from __future__ import annotations

import io
import struct

import pytest
from PIL import Image, PngImagePlugin

from reponpc.cards.assets import SpriteValidationError, validate_sprite, validate_sprite_filename


def _sheet(*, metadata: bool = False) -> bytes:
    image = Image.new("RGBA", (128, 224), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 32 + 4, row * 32 + 4), (20 + row, 40 + column, 60, 255))
    info = None
    if metadata:
        info = PngImagePlugin.PngInfo()
        info.add_text("canary", "must-not-survive")
    output = io.BytesIO()
    image.save(output, "PNG", pnginfo=info)
    return output.getvalue()


def test_valid_sprite_is_metadata_free_and_deterministic() -> None:
    first = validate_sprite(_sheet(metadata=True))
    second = validate_sprite(_sheet(metadata=True))

    assert first == second
    assert b"must-not-survive" not in first.content
    assert len(first.sha256) == 64
    with Image.open(io.BytesIO(first.content)) as image:
        assert image.mode == "RGBA"
        assert image.size == (128, 224)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"not-png", "NOT_PNG"),
        (_sheet() + b"<script>", "UNSAFE_PNG"),
        (_sheet() + struct.pack(">I", 0), "UNSAFE_PNG"),
    ],
)
def test_unsafe_framing_is_rejected(payload: bytes, code: str) -> None:
    with pytest.raises(SpriteValidationError) as error:
        validate_sprite(payload)
    assert error.value.code == code


def test_rejects_ihdr_dimensions_before_pillow_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = bytearray(_sheet())
    payload[16:20] = (4096).to_bytes(4, "big")

    def unexpected_decode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Pillow decode must not run for rejected IHDR dimensions")

    monkeypatch.setattr(Image, "open", unexpected_decode)
    with pytest.raises(SpriteValidationError) as error:
        validate_sprite(bytes(payload))

    assert error.value.code == "WRONG_DIMENSIONS"


def test_missing_transparency_and_empty_state_are_rejected() -> None:
    opaque = Image.new("RGBA", (128, 224), "red")
    output = io.BytesIO()
    opaque.save(output, "PNG")
    with pytest.raises(SpriteValidationError, match="character asset is invalid") as error:
        validate_sprite(output.getvalue())
    assert error.value.code == "MISSING_TRANSPARENCY"

    empty = Image.new("RGBA", (128, 224), (0, 0, 0, 0))
    empty.putpixel((1, 1), (1, 2, 3, 255))
    output = io.BytesIO()
    empty.save(output, "PNG")
    with pytest.raises(SpriteValidationError) as error:
        validate_sprite(output.getvalue())
    assert error.value.code == "EMPTY_STATE"


@pytest.mark.parametrize("filename", ["../hero.png", "nested/hero.png", "Hero.png", "hero.jpg"])
def test_filename_allowlist_rejects_unsafe_values(filename: str) -> None:
    with pytest.raises(SpriteValidationError) as error:
        validate_sprite_filename(filename)
    assert error.value.code == "INVALID_FILENAME"
