"""Fail-closed validation and deterministic re-encoding for character sheets."""

from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass
from typing import Final

from PIL import Image, UnidentifiedImageError

PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
WIDTH: Final = 128
HEIGHT: Final = 224
FRAME_SIZE: Final = 32
STATE_ROWS: Final = ("idle", "walk", "listen", "think", "talk", "success", "offline")
DEFAULT_MAX_BYTES: Final = 1024 * 1024
HARD_MAX_BYTES: Final = 2 * 1024 * 1024


class SpriteValidationError(ValueError):
    """Stable public-safe asset validation failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("character asset is invalid")


@dataclass(frozen=True, slots=True)
class CanonicalSprite:
    content: bytes
    sha256: str
    width: int = WIDTH
    height: int = HEIGHT


def validate_sprite(
    content: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> CanonicalSprite:
    """Validate untrusted PNG bytes and return canonical metadata-free RGBA bytes."""

    if max_bytes <= 0 or max_bytes > HARD_MAX_BYTES:
        raise ValueError("max_bytes must be within the supported asset limit")
    if len(content) > max_bytes:
        raise SpriteValidationError("FILE_TOO_LARGE")
    chunks, dimensions = _png_chunks(content)
    if b"acTL" in chunks or b"fcTL" in chunks or b"fdAT" in chunks:
        raise SpriteValidationError("ANIMATED_PNG")
    if dimensions != (WIDTH, HEIGHT):
        raise SpriteValidationError("WRONG_DIMENSIONS")
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.load()
            if source.format != "PNG":
                raise SpriteValidationError("NOT_PNG")
            if getattr(source, "n_frames", 1) != 1 or bool(source.info.get("default_image")):
                raise SpriteValidationError("ANIMATED_PNG")
            if source.size != (WIDTH, HEIGHT):
                raise SpriteValidationError("WRONG_DIMENSIONS")
            if source.mode not in {"RGBA", "LA", "P"}:
                raise SpriteValidationError("UNSUPPORTED_COLOR_MODE")
            image = source.convert("RGBA")
    except SpriteValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise SpriteValidationError("NOT_PNG") from exc

    alpha = image.getchannel("A")
    minimum, _maximum = alpha.getextrema()
    if minimum == 255:
        raise SpriteValidationError("MISSING_TRANSPARENCY")
    for row, _state in enumerate(STATE_ROWS):
        first_frame = image.crop((0, row * FRAME_SIZE, FRAME_SIZE, (row + 1) * FRAME_SIZE))
        if first_frame.getbbox() is None:
            raise SpriteValidationError("EMPTY_STATE")

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9, interlace=False)
    canonical = output.getvalue()
    return CanonicalSprite(content=canonical, sha256=hashlib.sha256(canonical).hexdigest())


def validate_sprite_filename(filename: str) -> str:
    """Normalize no path data; accept one exact lowercase ASCII PNG filename."""

    import re

    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}\.png", filename):
        raise SpriteValidationError("INVALID_FILENAME")
    return filename


def _png_chunks(content: bytes) -> tuple[frozenset[bytes], tuple[int, int]]:
    """Parse the complete PNG framing and reject truncation or trailing polyglot bytes."""

    if not content.startswith(PNG_SIGNATURE):
        raise SpriteValidationError("NOT_PNG")
    offset = len(PNG_SIGNATURE)
    chunks: set[bytes] = set()
    saw_iend = False
    dimensions: tuple[int, int] | None = None
    while offset < len(content):
        if len(content) - offset < 12:
            raise SpriteValidationError("UNSAFE_PNG")
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        chunk_type = content[offset + 4 : offset + 8]
        chunk_data = content[offset + 8 : offset + 8 + length]
        end = offset + 12 + length
        if end > len(content):
            raise SpriteValidationError("UNSAFE_PNG")
        if saw_iend:
            raise SpriteValidationError("UNSAFE_PNG")
        if not chunks and chunk_type != b"IHDR":
            raise SpriteValidationError("UNSAFE_PNG")
        if chunk_type == b"IHDR":
            if dimensions is not None or length != 13:
                raise SpriteValidationError("UNSAFE_PNG")
            dimensions = struct.unpack(">II", chunk_data[:8])
        chunks.add(chunk_type)
        offset = end
        if chunk_type == b"IEND":
            if length != 0 or offset != len(content):
                raise SpriteValidationError("UNSAFE_PNG")
            saw_iend = True
    if not saw_iend or dimensions is None or b"IDAT" not in chunks:
        raise SpriteValidationError("UNSAFE_PNG")
    return frozenset(chunks), dimensions
