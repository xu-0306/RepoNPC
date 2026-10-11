from __future__ import annotations

import io
import struct
import zlib

import pytest
from PIL import Image, PngImagePlugin

from reponpc.scene.images import SceneImageError, validate_scene_image


def _image_bytes(
    format: str = "PNG",
    *,
    size: tuple[int, int] = (640, 360),
    color: tuple[int, int, int, int] = (30, 60, 90, 255),
    metadata: bool = False,
) -> bytes:
    image = Image.new("RGBA", size, color)
    output = io.BytesIO()
    if format == "PNG" and metadata:
        info = PngImagePlugin.PngInfo()
        info.add_text("Comment", "owner-private-canary")
        image.save(output, format=format, pnginfo=info)
    elif format == "WEBP":
        image.save(output, format=format, lossless=True)
    else:
        image.save(output, format=format)
    return output.getvalue()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _with_apng_control(content: bytes) -> bytes:
    insertion = content.index(b"IDAT") - 4
    return content[:insertion] + _png_chunk(b"acTL", struct.pack(">II", 2, 0)) + content[insertion:]


def _animated_webp() -> bytes:
    first = Image.new("RGBA", (640, 360), (20, 30, 40, 255))
    second = Image.new("RGBA", (640, 360), (40, 30, 20, 255))
    output = io.BytesIO()
    first.save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
        lossless=True,
    )
    return output.getvalue()


def test_png_is_framed_reencoded_and_metadata_free() -> None:
    original = _image_bytes(metadata=True)
    result = validate_scene_image(original, filename="hero.png")

    assert result.format == "png"
    assert (result.width, result.height) == (640, 360)
    assert result.sha256 == __import__("hashlib").sha256(result.content).hexdigest()
    with Image.open(io.BytesIO(result.content)) as canonical:
        assert canonical.format == "PNG"
        assert canonical.info.get("Comment") is None
        canonical.load()


def test_webp_is_static_canonical_and_deterministic() -> None:
    original = _image_bytes("WEBP")
    first = validate_scene_image(original, filename="hero.webp")
    second = validate_scene_image(original, filename="hero.webp")

    assert first.format == "webp"
    assert first.media_type == "image/webp"
    assert first.content == second.content
    with Image.open(io.BytesIO(first.content)) as canonical:
        assert canonical.format == "WEBP"
        assert canonical.n_frames == 1
        canonical.load()


@pytest.mark.parametrize(
    ("content", "filename", "code"),
    [
        (_image_bytes(), "hero.webp", "IMAGE_FORMAT_MISMATCH"),
        (_image_bytes("WEBP"), "hero.png", "IMAGE_FORMAT_MISMATCH"),
        (_image_bytes(), "hero.PNG", "IMAGE_EXTENSION_INVALID"),
        (_image_bytes(), "..\\hero.png", "IMAGE_FILENAME_INVALID"),
        (_image_bytes() + b"polyglot", "hero.png", "IMAGE_CONTAINER_INVALID"),
        (_image_bytes()[:-4], "hero.png", "IMAGE_CONTAINER_INVALID"),
        (_image_bytes("WEBP") + b"polyglot", "hero.webp", "IMAGE_CONTAINER_INVALID"),
        (_image_bytes("WEBP")[:-2], "hero.webp", "IMAGE_CONTAINER_INVALID"),
        (_with_apng_control(_image_bytes()), "hero.png", "IMAGE_ANIMATED"),
        (_animated_webp(), "hero.webp", "IMAGE_ANIMATED"),
        (_image_bytes(size=(639, 360)), "hero.png", "IMAGE_DIMENSIONS_INVALID"),
        (_image_bytes(size=(2561, 1600)), "hero.png", "IMAGE_DIMENSIONS_INVALID"),
        (b"\x89PNG\r\n\x1a\n", "hero.png", "IMAGE_CONTAINER_INVALID"),
        (b"not an image", "hero.png", "IMAGE_FORMAT_INVALID"),
    ],
    ids=[
        "png-webp-extension-mismatch",
        "webp-png-extension-mismatch",
        "uppercase-extension",
        "path-like-filename",
        "png-polyglot-tail",
        "truncated-png",
        "webp-polyglot-tail",
        "truncated-webp",
        "apng",
        "animated-webp",
        "undersized",
        "oversized",
        "truncated-png-header",
        "unknown-format",
    ],
)
def test_invalid_scene_images_fail_with_safe_errors(
    content: bytes, filename: str, code: str
) -> None:
    with pytest.raises(SceneImageError) as captured:
        validate_scene_image(content, filename=filename)
    assert captured.value.code == code
    assert "polyglot" not in str(captured.value)


def test_png_crc_and_riff_length_are_verified() -> None:
    bad_png = bytearray(_image_bytes())
    bad_png[-5] ^= 0x01
    with pytest.raises(SceneImageError) as captured:
        validate_scene_image(bytes(bad_png), filename="hero.png")
    assert captured.value.code == "IMAGE_CONTAINER_INVALID"

    bad_webp = bytearray(_image_bytes("WEBP"))
    bad_webp[4] ^= 0x01
    with pytest.raises(SceneImageError) as captured:
        validate_scene_image(bytes(bad_webp), filename="hero.webp")
    assert captured.value.code == "IMAGE_CONTAINER_INVALID"


def test_input_and_canonical_output_are_bounded() -> None:
    with pytest.raises(SceneImageError) as captured:
        validate_scene_image(b"x" * (2 * 1024 * 1024 + 1), filename="hero.png")
    assert captured.value.code == "IMAGE_TOO_LARGE"


def test_minimum_and_maximum_dimensions_are_inclusive() -> None:
    minimum = validate_scene_image(_image_bytes(size=(640, 360)), filename="small.png")
    maximum = validate_scene_image(_image_bytes(size=(2560, 1600)), filename="large.png")
    assert (minimum.width, minimum.height) == (640, 360)
    assert (maximum.width, maximum.height) == (2560, 1600)
