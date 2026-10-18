"""Strict validation and metadata-free canonicalization for scene images."""

from __future__ import annotations

import hashlib
import io
import struct
import warnings
import zlib
from dataclasses import dataclass
from typing import Final, Literal

from PIL import Image, UnidentifiedImageError

SceneImageFormat = Literal["png", "webp"]
MAX_SCENE_IMAGE_BYTES: Final = 2 * 1024 * 1024
MIN_WIDTH: Final = 640
MIN_HEIGHT: Final = 360
MAX_WIDTH: Final = 2560
MAX_HEIGHT: Final = 1600
_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF: Final = b"RIFF"
_WEBP_MAGIC: Final = b"WEBP"
_ANIMATED_PNG: Final = frozenset({b"acTL", b"fcTL", b"fdAT"})


class SceneImageError(ValueError):
    """Stable, safe image validation error without untrusted input text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("scene image is invalid")


@dataclass(frozen=True, slots=True)
class CanonicalSceneImage:
    """A validated, metadata-free owner image with content identity."""

    content: bytes
    format: SceneImageFormat
    width: int
    height: int
    sha256: str

    @property
    def media_type(self) -> str:
        return "image/png" if self.format == "png" else "image/webp"


def validate_scene_image(content: bytes, *, filename: str) -> CanonicalSceneImage:
    """Validate framing, extension, dimensions and decoding before re-encoding."""

    if not isinstance(content, bytes) or not content:
        raise SceneImageError("IMAGE_INVALID")
    if len(content) > MAX_SCENE_IMAGE_BYTES:
        raise SceneImageError("IMAGE_TOO_LARGE")
    extension = _filename_extension(filename)
    detected = _detect_format(content)
    if detected != extension:
        raise SceneImageError("IMAGE_FORMAT_MISMATCH")
    dimensions = _inspect_png(content) if detected == "png" else _inspect_webp(content)
    if not _dimensions_allowed(*dimensions):
        raise SceneImageError("IMAGE_DIMENSIONS_INVALID")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as probe:
                if probe.format != detected.upper():
                    raise SceneImageError("IMAGE_FORMAT_MISMATCH")
                if getattr(probe, "n_frames", 1) != 1:
                    raise SceneImageError("IMAGE_ANIMATED")
                if probe.size != dimensions or not _dimensions_allowed(*probe.size):
                    raise SceneImageError("IMAGE_DIMENSIONS_INVALID")
                probe.verify()
            with Image.open(io.BytesIO(content)) as source:
                if source.format != detected.upper() or getattr(source, "n_frames", 1) != 1:
                    raise SceneImageError("IMAGE_ANIMATED")
                source.load()
                pixels = source.convert("RGBA").tobytes()
                image = Image.frombytes("RGBA", source.size, pixels)
    except SceneImageError:
        raise
    except Image.DecompressionBombError, Image.DecompressionBombWarning:
        raise SceneImageError("IMAGE_DIMENSIONS_INVALID") from None
    except UnidentifiedImageError, OSError, SyntaxError, ValueError, struct.error:
        raise SceneImageError("IMAGE_INVALID") from None

    output = io.BytesIO()
    try:
        if detected == "png":
            image.save(output, format="PNG", optimize=False, compress_level=9)
        else:
            image.save(output, format="WEBP", lossless=True, quality=100, method=6)
    except OSError, ValueError:
        raise SceneImageError("IMAGE_INVALID") from None
    canonical = output.getvalue()
    if not canonical or len(canonical) > MAX_SCENE_IMAGE_BYTES:
        raise SceneImageError("IMAGE_TOO_LARGE")
    # Re-encoded bytes still have to meet the same complete-container contract.
    if detected == "png":
        _inspect_png(canonical)
    else:
        _inspect_webp(canonical)
    return CanonicalSceneImage(
        content=canonical,
        format=detected,
        width=image.width,
        height=image.height,
        sha256=hashlib.sha256(canonical).hexdigest(),
    )


def _filename_extension(filename: str) -> SceneImageFormat:
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 255
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
    ):
        raise SceneImageError("IMAGE_FILENAME_INVALID")
    if filename.endswith(".png"):
        return "png"
    if filename.endswith(".webp"):
        return "webp"
    raise SceneImageError("IMAGE_EXTENSION_INVALID")


def _detect_format(content: bytes) -> SceneImageFormat:
    if content.startswith(_PNG_SIGNATURE):
        return "png"
    if len(content) >= 12 and content[:4] == _WEBP_RIFF and content[8:12] == _WEBP_MAGIC:
        return "webp"
    raise SceneImageError("IMAGE_FORMAT_INVALID")


def _dimensions_allowed(width: int, height: int) -> bool:
    return MIN_WIDTH <= width <= MAX_WIDTH and MIN_HEIGHT <= height <= MAX_HEIGHT


def _inspect_png(content: bytes) -> tuple[int, int]:
    if not content.startswith(_PNG_SIGNATURE):
        raise SceneImageError("IMAGE_FORMAT_INVALID")
    offset = len(_PNG_SIGNATURE)
    dimensions: tuple[int, int] | None = None
    saw_idat = False
    ended_idat = False
    saw_iend = False
    while offset < len(content):
        if len(content) - offset < 12:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        size = struct.unpack_from(">I", content, offset)[0]
        end = offset + 12 + size
        if size > MAX_SCENE_IMAGE_BYTES or end > len(content) or saw_iend:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        kind = content[offset + 4 : offset + 8]
        payload = content[offset + 8 : offset + 8 + size]
        expected_crc = struct.unpack_from(">I", content, offset + 8 + size)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        if not all(65 <= character <= 90 or 97 <= character <= 122 for character in kind):
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        if offset == len(_PNG_SIGNATURE):
            if kind != b"IHDR" or size != 13:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack_from(">IIBBBBB", payload)
            )
            if (
                width == 0
                or height == 0
                or bit_depth not in {1, 2, 4, 8, 16}
                or color_type not in {0, 2, 3, 4, 6}
                or compression != 0
                or filtering != 0
                or interlace not in {0, 1}
                or (color_type == 0 and bit_depth not in {1, 2, 4, 8, 16})
                or (color_type == 2 and bit_depth not in {8, 16})
                or (color_type == 3 and bit_depth not in {1, 2, 4, 8})
                or (color_type == 4 and bit_depth not in {8, 16})
                or (color_type == 6 and bit_depth not in {8, 16})
            ):
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            dimensions = (width, height)
        elif kind == b"IHDR":
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        if kind in _ANIMATED_PNG:
            raise SceneImageError("IMAGE_ANIMATED")
        if kind == b"IDAT":
            if ended_idat:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            saw_idat = True
        elif saw_idat and kind != b"IEND":
            ended_idat = True
        if kind == b"IEND":
            if size != 0 or not saw_idat or end != len(content):
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            saw_iend = True
        offset = end
    if not saw_iend or dimensions is None:
        raise SceneImageError("IMAGE_CONTAINER_INVALID")
    return dimensions


def _inspect_webp(content: bytes) -> tuple[int, int]:
    if len(content) < 20 or content[:4] != _WEBP_RIFF or content[8:12] != _WEBP_MAGIC:
        raise SceneImageError("IMAGE_FORMAT_INVALID")
    if struct.unpack_from("<I", content, 4)[0] + 8 != len(content):
        raise SceneImageError("IMAGE_CONTAINER_INVALID")
    offset = 12
    dimensions: tuple[int, int] | None = None
    primary_count = 0
    chunk_index = 0
    animation_chunks = {b"ANIM", b"ANMF"}
    while offset < len(content):
        if len(content) - offset < 8:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        kind = content[offset : offset + 4]
        size = struct.unpack_from("<I", content, offset + 4)[0]
        start = offset + 8
        end = start + size
        next_offset = end + (size & 1)
        if end > len(content) or next_offset > len(content):
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        payload = content[start:end]
        if size & 1 and content[end] != 0:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        if kind in animation_chunks:
            raise SceneImageError("IMAGE_ANIMATED")
        if kind == b"VP8X":
            if chunk_index != 0 or size != 10 or dimensions is not None:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            if payload[0] & 0b11000001 or payload[1:4] != b"\x00\x00\x00":
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            if payload[0] & 0x02:
                raise SceneImageError("IMAGE_ANIMATED")
            dimensions = (
                1 + int.from_bytes(payload[4:7], "little"),
                1 + int.from_bytes(payload[7:10], "little"),
            )
        elif kind == b"VP8 ":
            if size < 10 or payload[3:6] != b"\x9d\x01\x2a":
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            primary_count += 1
            frame_size = struct.unpack_from("<HH", payload, 6)
            parsed_dimensions = (frame_size[0] & 0x3FFF, frame_size[1] & 0x3FFF)
            if dimensions is None:
                dimensions = parsed_dimensions
            elif dimensions != parsed_dimensions:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
        elif kind == b"VP8L":
            if size < 5 or payload[0] != 0x2F:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            primary_count += 1
            bits = int.from_bytes(payload[1:5], "little")
            parsed_dimensions = (1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF))
            if (bits >> 29) != 0:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
            if dimensions is None:
                dimensions = parsed_dimensions
            elif dimensions != parsed_dimensions:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
        elif kind == b"ALPH":
            if primary_count or size == 0:
                raise SceneImageError("IMAGE_CONTAINER_INVALID")
        elif kind not in {b"ICCP", b"EXIF", b"XMP ", b"JUNK", b"PAD ", b"ANIM", b"ANMF"}:
            raise SceneImageError("IMAGE_CONTAINER_INVALID")
        offset = next_offset
        chunk_index += 1
    if offset != len(content) or dimensions is None or primary_count != 1:
        raise SceneImageError("IMAGE_CONTAINER_INVALID")
    return dimensions
