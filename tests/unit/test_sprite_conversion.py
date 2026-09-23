from __future__ import annotations

import io
import json
import zipfile

import pytest
from PIL import Image

from reponpc.cards.assets import FRAME_COLUMNS, FRAME_ROWS, FRAME_SIZE, HEIGHT, WIDTH
from reponpc.cards.conversion import (
    MaterialEntry,
    SpriteConversion,
    SpriteConversionError,
    SpriteSelection,
    convert_sprite_material,
    prepare_sprite_entries,
    prepare_sprite_material,
)


def _png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _grid(cell_size: int, *, partial_alpha: bool = False) -> bytes:
    image = Image.new(
        "RGBA",
        (FRAME_COLUMNS * cell_size, FRAME_ROWS * cell_size),
        (0, 0, 0, 0),
    )
    inset = max(1, cell_size // 8)
    for row in range(FRAME_ROWS):
        for column in range(FRAME_COLUMNS):
            left = column * cell_size + inset
            top = row * cell_size + inset
            color = (20 + row, 40 + column, 60, 128 if partial_alpha else 255)
            for y in range(top, top + max(1, cell_size // 2)):
                for x in range(left, left + max(1, cell_size // 2)):
                    image.putpixel((x, y), color)
    return _png(image)


def _grid_with_edge_spill(cell_size: int) -> bytes:
    image = Image.open(io.BytesIO(_grid(cell_size))).convert("RGBA")
    left, right = cell_size // 3, cell_size // 2
    for x in range(left, right):
        image.putpixel((x, cell_size - 1), (90, 45, 25, 160))
        for y in range(2):
            image.putpixel((x, cell_size + y), (90, 45, 25, 160))
    return _png(image)


def _frame(width: int, height: int, color: tuple[int, int, int, int]) -> bytes:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y in range(2, max(3, height - 2)):
        for x in range(2, max(3, width - 2)):
            image.putpixel((x, y), color)
    return _png(image)


def _pack(
    *,
    missing_state: str | None = None,
    extra_member: bool = False,
    unsafe_member: str | None = None,
    duplicate_manifest_key: bool = False,
) -> bytes:
    frames: dict[str, list[str]] = {}
    payloads: dict[str, bytes] = {}
    for row, state in enumerate(("idle", "walk", "listen", "think", "talk", "success", "offline")):
        if state == missing_state:
            continue
        paths = []
        for column in range(FRAME_COLUMNS):
            path = f"art/{state}/pose-{column}.png"
            paths.append(path)
            dimensions = (80, 96) if (row + column) % 2 else (96, 96)
            payloads[path] = _frame(
                *dimensions,
                (30 + row, 60 + column, 90, 255),
            )
        frames[state] = paths

    output = io.BytesIO()
    manifest = json.dumps({"schema_version": 1, "frames": frames})
    if duplicate_manifest_key:
        manifest = manifest.replace(
            '{"schema_version": 1,',
            '{"schema_version": 1, "schema_version": 1,',
            1,
        )
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("sprite-pack.json", manifest)
        for path, payload in payloads.items():
            archive.writestr(path, payload)
        if extra_member:
            archive.writestr("notes/provenance.txt", "fixture")
        if unsafe_member:
            archive.writestr(unsafe_member, _frame(32, 32, (1, 2, 3, 255)))
    return output.getvalue()


def _discovery_bundle(*source_sizes: int) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("unfamiliar/notes.txt", "not an image")
        archive.writestr("unfamiliar/reference.png", _frame(41, 59, (1, 2, 3, 255)))
        for index, source_size in enumerate(source_sizes):
            archive.writestr(
                f"unfamiliar/art-{index}.png",
                _grid(source_size, partial_alpha=index % 2 == 0),
            )
    return output.getvalue()


def test_pixelize_converts_unseen_grid_size_without_source_specific_constants() -> None:
    conversion = convert_sprite_material(_grid(73, partial_alpha=True))

    assert conversion.source_kind == "grid"
    assert conversion.strategy == "pixelize"
    assert set(conversion.source_frame_sizes) == {(73, 73)}
    assert conversion.sprite.width == WIDTH
    assert conversion.sprite.height == HEIGHT
    assert any(warning.code == "PARTIAL_ALPHA_REMOVED" for warning in conversion.warnings)
    with Image.open(io.BytesIO(conversion.sprite.content)) as canonical:
        assert canonical.size == (WIDTH, HEIGHT)
        assert canonical.getchannel("A").getextrema() == (0, 255)


@pytest.mark.parametrize("cell_size", [73, 128])
def test_grid_conversion_offers_a_separately_validated_boundary_cleanup(
    cell_size: int,
) -> None:
    source = _grid_with_edge_spill(cell_size)
    conversion = convert_sprite_material(source)

    assert conversion.cleanup is not None
    assert conversion.cleanup.affected_frames == (("walk", 0),)
    assert conversion.cleanup.removed_source_pixels > 0
    assert conversion.cleanup.sprite.sha256 != conversion.sprite.sha256
    with Image.open(io.BytesIO(conversion.sprite.content)) as original:
        assert original.getpixel((FRAME_SIZE // 3, FRAME_SIZE))[3] > 0
    with Image.open(io.BytesIO(conversion.cleanup.sprite.content)) as cleaned:
        assert cleaned.getpixel((FRAME_SIZE // 3, FRAME_SIZE))[3] == 0
        assert cleaned.getpixel((FRAME_SIZE // 3, FRAME_SIZE + FRAME_SIZE // 3))[3] > 0
    with Image.open(io.BytesIO(source)) as unchanged_source:
        assert unchanged_source.getpixel((cell_size // 3, cell_size))[3] == 160


def test_grid_cleanup_preserves_detached_or_connected_intentional_art() -> None:
    cell_size = 96
    detached = Image.open(io.BytesIO(_grid(cell_size))).convert("RGBA")
    for x in range(8, 18):
        detached.putpixel((x, cell_size), (70, 35, 20, 255))
    assert convert_sprite_material(_png(detached)).cleanup is None

    connected = Image.open(io.BytesIO(_grid(cell_size))).convert("RGBA")
    x = cell_size // 3
    for y in range(cell_size - 1, cell_size + cell_size // 4):
        connected.putpixel((x, y), (70, 35, 20, 255))
    assert convert_sprite_material(_png(connected)).cleanup is None

    deep_size = 128
    deep = Image.open(io.BytesIO(_grid(deep_size))).convert("RGBA")
    for y in range(deep_size - 1, deep_size + 10):
        deep.putpixel((deep_size // 3, y), (70, 35, 20, 255))
    assert convert_sprite_material(_png(deep)).cleanup is None


@pytest.mark.parametrize("source_size", [16, 32, 64, 128, 256])
def test_pixel_exact_accepts_integer_source_scales(source_size: int) -> None:
    conversion = convert_sprite_material(_grid(source_size), strategy="pixel_exact")
    assert conversion.sprite.width == FRAME_COLUMNS * FRAME_SIZE
    assert conversion.sprite.height == FRAME_ROWS * FRAME_SIZE


def test_pixel_exact_rejects_non_integer_scale_instead_of_blurring() -> None:
    with pytest.raises(SpriteConversionError) as captured:
        convert_sprite_material(_grid(73), strategy="pixel_exact")
    assert captured.value.code == "NON_INTEGER_SCALE"


def test_manifest_pack_uses_explicit_mapping_and_reports_bounded_variants() -> None:
    conversion = convert_sprite_material(_pack(extra_member=True))

    assert conversion.source_kind == "manifest"
    assert len(conversion.source_frame_sizes) == FRAME_COLUMNS * FRAME_ROWS
    codes = {warning.code for warning in conversion.warnings}
    assert "FRAME_DIMENSIONS_DIFFER" in codes
    assert "SOURCE_FRAME_PADDED" in codes
    assert "UNREFERENCED_MEMBERS" in codes
    assert conversion.sprite.width == WIDTH
    assert conversion.sprite.height == HEIGHT
    assert conversion.cleanup is None


def test_manifest_pack_rejects_missing_state_and_duplicate_json_keys() -> None:
    with pytest.raises(SpriteConversionError) as captured:
        convert_sprite_material(_pack(missing_state="offline"))
    assert captured.value.code == "PACK_MANIFEST_INVALID"

    with pytest.raises(SpriteConversionError) as captured:
        convert_sprite_material(_pack(duplicate_manifest_key=True))
    assert captured.value.code == "PACK_MANIFEST_INVALID"


@pytest.mark.parametrize(
    "unsafe_member",
    ["../escape.png", "art//escape.png", "art/./escape.png", "C:/escape.png"],
)
def test_manifest_pack_rejects_non_normalized_member_paths(unsafe_member: str) -> None:
    with pytest.raises(SpriteConversionError) as captured:
        convert_sprite_material(_pack(unsafe_member=unsafe_member))
    assert captured.value.code == "PACK_UNSAFE"


def test_converter_rejects_shape_that_is_not_a_structural_four_by_seven_grid() -> None:
    image = Image.new("RGBA", (301, 511), (0, 0, 0, 0))
    image.putpixel((10, 10), (1, 2, 3, 255))
    with pytest.raises(SpriteConversionError) as captured:
        convert_sprite_material(_png(image))
    assert captured.value.code == "GRID_LAYOUT_INVALID"


def test_manifestless_bundle_discovers_unseen_candidates_without_filename_rules() -> None:
    preparation = prepare_sprite_material(_discovery_bundle(73, 91))

    assert isinstance(preparation, SpriteSelection)
    assert preparation.ignored_count == 2
    assert len(preparation.candidates) == 2
    assert {candidate.source_path for candidate in preparation.candidates} == {
        "unfamiliar/art-0.png",
        "unfamiliar/art-1.png",
    }
    assert all(len(candidate.candidate_id) == 64 for candidate in preparation.candidates)
    assert all(candidate.conversion.source_kind == "bundle" for candidate in preparation.candidates)

    selected = prepare_sprite_material(
        _discovery_bundle(73, 91),
        candidate_id=preparation.candidates[1].candidate_id,
    )
    assert isinstance(selected, SpriteConversion)
    assert selected.candidate_id == preparation.candidates[1].candidate_id
    assert selected.source_path == "unfamiliar/art-1.png"
    assert any(warning.code == "BUNDLE_MEMBERS_IGNORED" for warning in selected.warnings)


def test_single_bundle_candidate_converts_without_an_extra_selection_step() -> None:
    preparation = prepare_sprite_material(_discovery_bundle(83))

    assert isinstance(preparation, SpriteConversion)
    assert preparation.source_kind == "bundle"
    assert preparation.source_frame_sizes[0] == (83, 83)


def test_selected_bundle_candidate_keeps_its_edge_cleanup_option() -> None:
    entries = (
        MaterialEntry("unfamiliar/plain.png", _grid(79)),
        MaterialEntry("unfamiliar/other.png", _grid_with_edge_spill(91)),
    )
    selection = prepare_sprite_entries(entries)
    assert isinstance(selection, SpriteSelection)
    selected_id = next(
        candidate.candidate_id
        for candidate in selection.candidates
        if candidate.source_path == "unfamiliar/other.png"
    )

    selected = prepare_sprite_entries(entries, candidate_id=selected_id)
    assert isinstance(selected, SpriteConversion)
    assert selected.cleanup is not None
    assert selected.cleanup.affected_frames == (("walk", 0),)


def test_folder_entries_share_bundle_discovery_and_reject_forged_selection() -> None:
    entries = (
        MaterialEntry("custom/one.png", _grid(79)),
        MaterialEntry("custom/two.png", _grid(101)),
        MaterialEntry("custom/readme.md", b"notes"),
    )
    preparation = prepare_sprite_entries(entries)
    assert isinstance(preparation, SpriteSelection)
    assert len(preparation.candidates) == 2

    with pytest.raises(SpriteConversionError) as captured:
        prepare_sprite_entries(entries, candidate_id="0" * 64)
    assert captured.value.code == "CANDIDATE_NOT_FOUND"

    with pytest.raises(SpriteConversionError) as captured:
        prepare_sprite_entries((MaterialEntry("../escape.png", _grid(64)),))
    assert captured.value.code == "PACK_UNSAFE"
