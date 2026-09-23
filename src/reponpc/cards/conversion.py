"""Convert bounded untrusted character material into the canonical sprite sheet."""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from PIL import Image, ImageDraw, UnidentifiedImageError

from reponpc.cards.assets import (
    FRAME_COLUMNS,
    FRAME_ROWS,
    FRAME_SIZE,
    PNG_SIGNATURE,
    STATE_ROWS,
    CanonicalSprite,
    SpriteValidationError,
    inspect_png,
    validate_sprite,
)

ConversionStrategy = Literal["pixel_exact", "pixelize"]
SourceKind = Literal["grid", "manifest", "bundle"]

MAX_SOURCE_BYTES: Final = 16 * 1024 * 1024
MAX_SOURCE_MEMBER_BYTES: Final = 8 * 1024 * 1024
MAX_SOURCE_UNCOMPRESSED_BYTES: Final = 64 * 1024 * 1024
MAX_SOURCE_PIXELS: Final = 16 * 1024 * 1024
MAX_SOURCE_SIDE: Final = 4096
MAX_PACK_ENTRIES: Final = 64
MAX_DISCOVERY_CANDIDATES: Final = 16
MAX_MANIFEST_BYTES: Final = 64 * 1024
MAX_MEMBER_PATH_CHARS: Final = 256
MAX_PALETTE_COLORS: Final = 64
PACK_MANIFEST_NAME: Final = "sprite-pack.json"
ZIP_SIGNATURES: Final = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


class SpriteConversionError(ValueError):
    """Stable, safe conversion failure without rejected source content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("character material could not be converted")


@dataclass(frozen=True, slots=True)
class ConversionWarning:
    code: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SpriteConversion:
    sprite: CanonicalSprite
    source_kind: SourceKind
    strategy: ConversionStrategy
    source_frame_sizes: tuple[tuple[int, int], ...]
    warnings: tuple[ConversionWarning, ...]
    candidate_id: str | None = None
    source_path: str | None = None
    cleanup: SpriteCleanup | None = None


@dataclass(frozen=True, slots=True)
class SpriteCleanup:
    """A separately validated, owner-selectable grid-edge cleanup preview."""

    sprite: CanonicalSprite
    affected_frames: tuple[tuple[str, int], ...]
    removed_source_pixels: int


@dataclass(frozen=True, slots=True)
class MaterialEntry:
    """One bounded relative file supplied by an archive or folder picker."""

    path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class SpriteCandidate:
    """A structurally valid grid which still needs human visual selection."""

    candidate_id: str
    source_path: str
    conversion: SpriteConversion


@dataclass(frozen=True, slots=True)
class SpriteSelection:
    """Multiple valid bundle candidates; no semantic guess is made."""

    strategy: ConversionStrategy
    candidates: tuple[SpriteCandidate, ...]
    ignored_count: int


def convert_sprite_material(
    content: bytes,
    *,
    strategy: ConversionStrategy = "pixelize",
    max_bytes: int = MAX_SOURCE_BYTES,
) -> SpriteConversion:
    """Convert a structural 4x7 PNG grid or manifest-driven ZIP pack."""

    if strategy not in {"pixel_exact", "pixelize"}:
        raise SpriteConversionError("INVALID_STRATEGY")
    if max_bytes <= 0 or max_bytes > MAX_SOURCE_BYTES:
        raise ValueError("max_bytes must be within the supported conversion limit")
    if len(content) > max_bytes:
        raise SpriteConversionError("SOURCE_FILE_TOO_LARGE")

    if content.startswith(PNG_SIGNATURE):
        return _convert_grid(content, strategy=strategy, source_kind="grid")
    elif content.startswith(ZIP_SIGNATURES):
        warnings: dict[str, set[str]] = defaultdict(set)
        frames, source_sizes = _manifest_frames(content, warnings)
        return _convert_frames(
            frames,
            source_sizes,
            strategy=strategy,
            source_kind="manifest",
            warnings=warnings,
        )
    raise SpriteConversionError("UNSUPPORTED_SOURCE")


def prepare_sprite_material(
    content: bytes,
    *,
    strategy: ConversionStrategy = "pixelize",
    candidate_id: str | None = None,
) -> SpriteConversion | SpriteSelection:
    """Prepare a PNG, strict manifest pack, or discovery ZIP for preview."""

    _validate_strategy(strategy)
    if len(content) > MAX_SOURCE_BYTES:
        raise SpriteConversionError("SOURCE_FILE_TOO_LARGE")
    if content.startswith(PNG_SIGNATURE):
        if candidate_id is not None:
            raise SpriteConversionError("CANDIDATE_NOT_FOUND")
        return _convert_grid(content, strategy=strategy, source_kind="grid")
    if not content.startswith(ZIP_SIGNATURES):
        raise SpriteConversionError("UNSUPPORTED_SOURCE")
    if _zip_has_root_manifest(content):
        if candidate_id is not None:
            raise SpriteConversionError("CANDIDATE_NOT_FOUND")
        return convert_sprite_material(content, strategy=strategy)
    return prepare_sprite_entries(
        _archive_entries(content),
        strategy=strategy,
        candidate_id=candidate_id,
    )


def prepare_sprite_entries(
    entries: Sequence[MaterialEntry],
    *,
    strategy: ConversionStrategy = "pixelize",
    candidate_id: str | None = None,
) -> SpriteConversion | SpriteSelection:
    """Discover structural grids from a bounded folder-style file collection."""

    _validate_strategy(strategy)
    if not entries or len(entries) > MAX_PACK_ENTRIES:
        raise SpriteConversionError("PACK_LIMIT_EXCEEDED")

    seen: set[str] = set()
    total_size = 0
    normalized: list[MaterialEntry] = []
    for entry in entries:
        _validate_member_name(entry.path)
        if entry.path in seen:
            raise SpriteConversionError("PACK_UNSAFE")
        seen.add(entry.path)
        if len(entry.content) > MAX_SOURCE_MEMBER_BYTES:
            raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
        total_size += len(entry.content)
        normalized.append(entry)
    if total_size > MAX_SOURCE_UNCOMPRESSED_BYTES:
        raise SpriteConversionError("PACK_LIMIT_EXCEEDED")

    candidates: list[SpriteCandidate] = []
    for entry in sorted(normalized, key=lambda item: item.path):
        if not entry.path.lower().endswith(".png"):
            continue
        identifier = hashlib.sha256(entry.path.encode("utf-8") + b"\0" + entry.content).hexdigest()
        try:
            conversion = _convert_grid(
                entry.content,
                strategy=strategy,
                source_kind="bundle",
                suggest_cleanup=(candidate_id == identifier if candidate_id else not candidates),
            )
        except SpriteConversionError:
            continue
        candidates.append(
            SpriteCandidate(
                candidate_id=identifier,
                source_path=entry.path,
                conversion=SpriteConversion(
                    sprite=conversion.sprite,
                    source_kind="bundle",
                    strategy=conversion.strategy,
                    source_frame_sizes=conversion.source_frame_sizes,
                    warnings=conversion.warnings,
                    candidate_id=identifier,
                    source_path=entry.path,
                    cleanup=conversion.cleanup,
                ),
            )
        )
        if len(candidates) > MAX_DISCOVERY_CANDIDATES:
            raise SpriteConversionError("TOO_MANY_CANDIDATES")

    if not candidates:
        raise SpriteConversionError("NO_CONVERTIBLE_CANDIDATE")
    ignored_count = len(normalized) - len(candidates)
    if candidate_id is not None:
        for candidate in candidates:
            if candidate.candidate_id == candidate_id:
                return _with_ignored_warning(candidate.conversion, ignored_count)
        raise SpriteConversionError("CANDIDATE_NOT_FOUND")
    if len(candidates) == 1:
        return _with_ignored_warning(candidates[0].conversion, ignored_count)
    return SpriteSelection(
        strategy=strategy,
        candidates=tuple(candidates),
        ignored_count=ignored_count,
    )


def _validate_strategy(strategy: ConversionStrategy) -> None:
    if strategy not in {"pixel_exact", "pixelize"}:
        raise SpriteConversionError("INVALID_STRATEGY")


def _convert_grid(
    content: bytes,
    *,
    strategy: ConversionStrategy,
    source_kind: SourceKind,
    suggest_cleanup: bool = True,
) -> SpriteConversion:
    warnings: dict[str, set[str]] = defaultdict(set)
    frames, source_sizes = _grid_frames(content)
    conversion = _convert_frames(
        frames,
        source_sizes,
        strategy=strategy,
        source_kind=source_kind,
        warnings=warnings,
    )
    if not suggest_cleanup:
        return conversion
    cleaned_frames, affected, removed = _suggest_grid_edge_cleanup(frames)
    if not affected:
        return conversion
    try:
        cleaned = _convert_frames(
            cleaned_frames,
            source_sizes,
            strategy=strategy,
            source_kind=source_kind,
            warnings=defaultdict(set),
        )
    except SpriteConversionError:
        return conversion
    if cleaned.sprite.sha256 == conversion.sprite.sha256:
        return conversion
    return replace(
        conversion,
        cleanup=SpriteCleanup(
            sprite=cleaned.sprite,
            affected_frames=affected,
            removed_source_pixels=removed,
        ),
    )


def _suggest_grid_edge_cleanup(
    frames: Sequence[Image.Image],
) -> tuple[list[Image.Image], tuple[tuple[str, int], ...], int]:
    """Remove only a shallow top fragment demonstrably continuing the row above.

    A transparent horizontal gap must separate the fragment from the current
    frame's main artwork. The source and regular conversion are never changed.
    """

    cleaned = list(frames)
    affected: list[tuple[str, int]] = []
    removed_pixels = 0
    for row in range(1, FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            index = row * FRAME_COLUMNS + column
            source = frames[index]
            previous = frames[index - FRAME_COLUMNS]
            side = source.width
            alpha = source.getchannel("A").tobytes()
            previous_alpha = previous.getchannel("A").tobytes()
            prior_edge = previous_alpha[(side - 1) * side : side * side]
            supported = {
                neighbor
                for x, value in enumerate(prior_edge)
                if value >= 64
                for neighbor in (x - 1, x, x + 1)
                if 0 <= neighbor < side
            }
            if not supported:
                continue

            # Both limits scale with the grid cell, not with a species or file.
            max_fragment_height = max(1, side // 16)
            min_gap_height = max(1, side // 64)
            fragment_height = 0
            while fragment_height <= max_fragment_height:
                scan = alpha[fragment_height * side : (fragment_height + 1) * side]
                if not any(value >= 64 for value in scan):
                    break
                fragment_height += 1
            if fragment_height == 0 or fragment_height > max_fragment_height:
                continue
            if fragment_height + min_gap_height >= side:
                continue
            if any(
                value >= 64
                for value in alpha[
                    fragment_height * side : (fragment_height + min_gap_height) * side
                ]
            ):
                continue
            if not any(value >= 64 for value in alpha[(fragment_height + min_gap_height) * side :]):
                continue
            if any(
                value >= 64 and x not in supported
                for y in range(fragment_height)
                for x, value in enumerate(alpha[y * side : (y + 1) * side])
            ):
                continue

            candidate = source.copy()
            draw = ImageDraw.Draw(candidate)
            count = 0
            for y in range(fragment_height):
                for x in supported:
                    if alpha[y * side + x] > 0:
                        draw.point((x, y), fill=(0, 0, 0, 0))
                        count += 1
            if not count:
                continue
            cleaned[index] = candidate
            affected.append((STATE_ROWS[row], column))
            removed_pixels += count
    return cleaned, tuple(affected), removed_pixels


def _convert_frames(
    frames: Sequence[Image.Image],
    source_sizes: Sequence[tuple[int, int]],
    *,
    strategy: ConversionStrategy,
    source_kind: SourceKind,
    warnings: dict[str, set[str]],
) -> SpriteConversion:

    sheet = Image.new(
        "RGBA",
        (FRAME_COLUMNS * FRAME_SIZE, FRAME_ROWS * FRAME_SIZE),
        (0, 0, 0, 0),
    )
    for position, frame in enumerate(frames):
        state_index, frame_index = divmod(position, FRAME_COLUMNS)
        label = f"{STATE_ROWS[state_index]}:{frame_index}"
        normalized = _normalize_frame(frame, strategy, label, warnings)
        sheet.alpha_composite(
            normalized,
            (frame_index * FRAME_SIZE, state_index * FRAME_SIZE),
        )

    output = io.BytesIO()
    sheet.save(output, format="PNG", optimize=False, compress_level=9, interlace=False)
    try:
        canonical = validate_sprite(output.getvalue())
    except SpriteValidationError as exc:
        raise SpriteConversionError(exc.code) from exc
    return SpriteConversion(
        sprite=canonical,
        source_kind=source_kind,
        strategy=strategy,
        source_frame_sizes=tuple(source_sizes),
        warnings=tuple(
            ConversionWarning(code=code, items=tuple(sorted(items)))
            for code, items in sorted(warnings.items())
        ),
    )


def _with_ignored_warning(conversion: SpriteConversion, ignored_count: int) -> SpriteConversion:
    if ignored_count <= 0:
        return conversion
    return SpriteConversion(
        sprite=conversion.sprite,
        source_kind=conversion.source_kind,
        strategy=conversion.strategy,
        source_frame_sizes=conversion.source_frame_sizes,
        warnings=(
            *conversion.warnings,
            ConversionWarning("BUNDLE_MEMBERS_IGNORED", (str(ignored_count),)),
        ),
        candidate_id=conversion.candidate_id,
        source_path=conversion.source_path,
        cleanup=conversion.cleanup,
    )


def _zip_has_root_manifest(content: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return any(info.filename == PACK_MANIFEST_NAME for info in archive.infolist())
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise SpriteConversionError("PACK_UNSAFE") from exc


def _archive_entries(content: bytes) -> tuple[MaterialEntry, ...]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise SpriteConversionError("PACK_UNSAFE") from exc

    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_PACK_ENTRIES:
            raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
        seen: set[str] = set()
        total_size = 0
        entries: list[MaterialEntry] = []
        for info in infos:
            name = info.filename.rstrip("/") if info.is_dir() else info.filename
            _validate_member_name(name)
            if info.filename in seen:
                raise SpriteConversionError("PACK_UNSAFE")
            seen.add(info.filename)
            if info.flag_bits & 0x1 or _is_symlink(info):
                raise SpriteConversionError("PACK_UNSAFE")
            if info.file_size > MAX_SOURCE_MEMBER_BYTES:
                raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
            total_size += info.file_size
            if not info.is_dir():
                try:
                    entries.append(MaterialEntry(info.filename, archive.read(info)))
                except (RuntimeError, zipfile.BadZipFile) as exc:
                    raise SpriteConversionError("PACK_UNSAFE") from exc
        if total_size > MAX_SOURCE_UNCOMPRESSED_BYTES:
            raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
        return tuple(entries)


def _grid_frames(content: bytes) -> tuple[list[Image.Image], list[tuple[int, int]]]:
    image = _decode_source_png(content, max_bytes=MAX_SOURCE_BYTES)
    width, height = image.size
    if width % FRAME_COLUMNS or height % FRAME_ROWS:
        raise SpriteConversionError("GRID_LAYOUT_INVALID")
    frame_width = width // FRAME_COLUMNS
    frame_height = height // FRAME_ROWS
    if frame_width != frame_height or frame_width <= 0:
        raise SpriteConversionError("GRID_LAYOUT_INVALID")
    frames = [
        image.crop(
            (
                column * frame_width,
                row * frame_height,
                (column + 1) * frame_width,
                (row + 1) * frame_height,
            )
        )
        for row in range(FRAME_ROWS)
        for column in range(FRAME_COLUMNS)
    ]
    return frames, [(frame_width, frame_height)] * (FRAME_COLUMNS * FRAME_ROWS)


def _manifest_frames(
    content: bytes, warnings: dict[str, set[str]]
) -> tuple[list[Image.Image], list[tuple[int, int]]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise SpriteConversionError("PACK_UNSAFE") from exc

    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_PACK_ENTRIES:
            raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
        members: dict[str, zipfile.ZipInfo] = {}
        total_size = 0
        for info in infos:
            name = info.filename.rstrip("/") if info.is_dir() else info.filename
            _validate_member_name(name)
            if info.filename in members:
                raise SpriteConversionError("PACK_UNSAFE")
            members[info.filename] = info
            if info.flag_bits & 0x1 or _is_symlink(info):
                raise SpriteConversionError("PACK_UNSAFE")
            if info.file_size > MAX_SOURCE_MEMBER_BYTES:
                raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
            total_size += info.file_size
        if total_size > MAX_SOURCE_UNCOMPRESSED_BYTES:
            raise SpriteConversionError("PACK_LIMIT_EXCEEDED")

        manifest_info = members.get(PACK_MANIFEST_NAME)
        if manifest_info is None or manifest_info.is_dir():
            raise SpriteConversionError("PACK_MANIFEST_INVALID")
        if manifest_info.file_size > MAX_MANIFEST_BYTES:
            raise SpriteConversionError("PACK_MANIFEST_INVALID")
        try:
            manifest = json.loads(
                archive.read(manifest_info).decode("utf-8"),
                object_pairs_hook=_strict_json_object,
            )
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
            raise SpriteConversionError("PACK_MANIFEST_INVALID") from exc
        frame_paths = _manifest_paths(manifest)

        referenced = set(frame_paths)
        extras = {
            name
            for name, info in members.items()
            if not info.is_dir() and name != PACK_MANIFEST_NAME and name not in referenced
        }
        if extras:
            warnings["UNREFERENCED_MEMBERS"].update(extras)

        frames: list[Image.Image] = []
        sizes: list[tuple[int, int]] = []
        for path in frame_paths:
            member_info = members.get(path)
            if member_info is None or member_info.is_dir():
                raise SpriteConversionError("PACK_MEMBER_MISSING")
            try:
                frame = _decode_source_png(
                    archive.read(member_info), max_bytes=MAX_SOURCE_MEMBER_BYTES
                )
            except (KeyError, RuntimeError, zipfile.BadZipFile) as exc:
                raise SpriteConversionError("PACK_UNSAFE") from exc
            frames.append(frame)
            sizes.append(frame.size)
        if len(set(sizes)) > 1:
            warnings["FRAME_DIMENSIONS_DIFFER"].add("pack")
        return frames, sizes


def _manifest_paths(manifest: object) -> list[str]:
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "frames"}:
        raise SpriteConversionError("PACK_MANIFEST_INVALID")
    if manifest["schema_version"] != 1 or isinstance(manifest["schema_version"], bool):
        raise SpriteConversionError("PACK_MANIFEST_INVALID")
    state_frames = manifest["frames"]
    if not isinstance(state_frames, dict) or set(state_frames) != set(STATE_ROWS):
        raise SpriteConversionError("PACK_MANIFEST_INVALID")

    paths: list[str] = []
    for state in STATE_ROWS:
        configured = state_frames[state]
        if (
            not isinstance(configured, list)
            or len(configured) != FRAME_COLUMNS
            or any(not isinstance(path, str) for path in configured)
        ):
            raise SpriteConversionError("PACK_MANIFEST_INVALID")
        for path in configured:
            _validate_member_name(path)
            if path == PACK_MANIFEST_NAME or not path.lower().endswith(".png"):
                raise SpriteConversionError("PACK_MANIFEST_INVALID")
            paths.append(path)
    if len(paths) != len(set(paths)):
        raise SpriteConversionError("PACK_MANIFEST_INVALID")
    return paths


def _validate_member_name(name: str) -> None:
    if (
        not name
        or len(name) > MAX_MEMBER_PATH_CHARS
        or "\\" in name
        or name.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
    ):
        raise SpriteConversionError("PACK_UNSAFE")
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts) or parts[0].endswith(":"):
        raise SpriteConversionError("PACK_UNSAFE")


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SpriteConversionError("PACK_MANIFEST_INVALID")
        result[key] = value
    return result


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _decode_source_png(content: bytes, *, max_bytes: int) -> Image.Image:
    if len(content) > max_bytes:
        raise SpriteConversionError("SOURCE_FILE_TOO_LARGE")
    try:
        chunks, dimensions = inspect_png(content)
    except SpriteValidationError as exc:
        raise SpriteConversionError(exc.code) from exc
    if b"acTL" in chunks or b"fcTL" in chunks or b"fdAT" in chunks:
        raise SpriteConversionError("ANIMATED_PNG")
    width, height = dimensions
    if (
        width <= 0
        or height <= 0
        or width > MAX_SOURCE_SIDE
        or height > MAX_SOURCE_SIDE
        or width * height > MAX_SOURCE_PIXELS
    ):
        raise SpriteConversionError("SOURCE_DIMENSIONS_UNSAFE")
    try:
        with Image.open(io.BytesIO(content)) as source:
            source.load()
            if source.format != "PNG":
                raise SpriteConversionError("NOT_PNG")
            if getattr(source, "n_frames", 1) != 1 or bool(source.info.get("default_image")):
                raise SpriteConversionError("ANIMATED_PNG")
            if source.size != dimensions:
                raise SpriteConversionError("SOURCE_DIMENSIONS_UNSAFE")
            if source.mode not in {"RGBA", "LA", "P"}:
                raise SpriteConversionError("UNSUPPORTED_COLOR_MODE")
            return source.convert("RGBA")
    except SpriteConversionError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise SpriteConversionError("NOT_PNG") from exc


def _normalize_frame(
    source: Image.Image,
    strategy: ConversionStrategy,
    label: str,
    warnings: dict[str, set[str]],
) -> Image.Image:
    alpha = source.getchannel("A")
    if alpha.getbbox() is None:
        raise SpriteConversionError("EMPTY_SOURCE_FRAME")
    histogram = alpha.histogram()
    if any(histogram[value] for value in range(1, 255)):
        warnings["PARTIAL_ALPHA_REMOVED"].add(label)

    source_colors = source.getcolors(maxcolors=MAX_PALETTE_COLORS + 1)
    if source_colors is None:
        warnings["PALETTE_REDUCED"].add(label)

    square = _square_canvas(source, label, warnings)
    if strategy == "pixel_exact":
        if not _integer_scale(square.width, FRAME_SIZE):
            raise SpriteConversionError("NON_INTEGER_SCALE")
        normalized = square.resize((FRAME_SIZE, FRAME_SIZE), Image.Resampling.NEAREST)
    else:
        resampling = Image.Resampling.BOX if square.width > FRAME_SIZE else Image.Resampling.NEAREST
        resized = square.resize((FRAME_SIZE, FRAME_SIZE), resampling)
        alpha_channel = resized.getchannel("A").point(lambda value: 255 if value >= 64 else 0)
        normalized = (
            resized.convert("RGB")
            .quantize(
                colors=MAX_PALETTE_COLORS,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.NONE,
            )
            .convert("RGBA")
        )
        normalized.putalpha(alpha_channel)

    bounds = normalized.getchannel("A").getbbox()
    if bounds is None:
        raise SpriteConversionError("EMPTY_SOURCE_FRAME")
    if bounds[0] == 0 or bounds[1] == 0 or bounds[2] == FRAME_SIZE or bounds[3] == FRAME_SIZE:
        warnings["CONTENT_TOUCHES_EDGE"].add(label)
    return normalized


def _square_canvas(source: Image.Image, label: str, warnings: dict[str, set[str]]) -> Image.Image:
    if source.width == source.height:
        return source
    warnings["SOURCE_FRAME_PADDED"].add(label)
    side = max(source.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(source, ((side - source.width) // 2, side - source.height))
    return square


def _integer_scale(source_size: int, target_size: int) -> bool:
    return source_size % target_size == 0 or target_size % source_size == 0


__all__ = [
    "MAX_PACK_ENTRIES",
    "MAX_SOURCE_BYTES",
    "MAX_SOURCE_MEMBER_BYTES",
    "MAX_SOURCE_UNCOMPRESSED_BYTES",
    "ConversionStrategy",
    "ConversionWarning",
    "MaterialEntry",
    "SourceKind",
    "SpriteCandidate",
    "SpriteConversion",
    "SpriteConversionError",
    "SpriteSelection",
    "convert_sprite_material",
    "prepare_sprite_entries",
    "prepare_sprite_material",
]
