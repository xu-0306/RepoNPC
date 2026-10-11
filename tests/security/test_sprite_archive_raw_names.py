"""Raw ZIP names must be rejected before platform normalization hides them."""

from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image

from reponpc.cards.conversion import SpriteConversionError, prepare_sprite_material


def _grid() -> bytes:
    image = Image.new("RGBA", (256, 448), (0, 0, 0, 0))
    for row in range(7):
        for column in range(4):
            image.putpixel((column * 64 + 8, row * 64 + 8), (255, 0, 0, 255))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


@pytest.mark.parametrize("raw_name", ["bad\\path.png", "bad\x00path.png"])
@pytest.mark.parametrize("with_manifest", [False, True])
def test_raw_zip_aliases_fail_in_both_discovery_and_manifest_routes(
    raw_name: str, with_manifest: bool
) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        # Assign after construction: Windows normalizes ZipInfo constructor
        # names, so constructing it with the unsafe name weakens the fixture.
        entry = zipfile.ZipInfo("placeholder.png")
        entry.filename = raw_name
        archive.writestr(entry, _grid())
        if with_manifest:
            archive.writestr("sprite-pack.json", b"{}")
    with pytest.raises(SpriteConversionError) as failure:
        prepare_sprite_material(stream.getvalue())
    assert failure.value.code == "PACK_UNSAFE"
