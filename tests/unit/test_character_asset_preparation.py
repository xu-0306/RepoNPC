from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, PngImagePlugin

from reponpc.cards.assets import STATE_ROWS, SpriteValidationError, validate_sprite
from reponpc.cards.conversion import (
    MAX_PACK_ENTRIES,
    MAX_SOURCE_MEMBER_BYTES,
    SpriteConversionError,
)
from tools.prepare_character_assets import prepare_drafts


def _grid(side: int, *, metadata: bool = False, cleanup: bool = False) -> bytes:
    image = Image.new("RGBA", (side * 4, side * 7), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for row in range(7):
        for column in range(4):
            left, top = column * side + side // 4, row * side + side // 4
            draw.rectangle(
                (left, top, left + side // 2, top + side // 2),
                fill=(30 + row * 20, 40 + column * 30, 70, 255),
            )
    if cleanup:
        for x in range(side // 3, side // 2):
            image.putpixel((x, side - 1), (90, 45, 25, 255))
            image.putpixel((x, side), (90, 45, 25, 255))
    output = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("description", "untrusted metadata must not survive")
    image.save(output, format="PNG", pnginfo=info)
    return output.getvalue()


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "side,strategy", [(32, "pixel_exact"), (128, "pixel_exact"), (73, "pixelize")]
)
def test_unseen_cell_sizes_canonical_validation_metadata_and_source_unchanged(
    tmp_path: Path, side: int, strategy: str
) -> None:
    source = tmp_path / "unfamiliar-name.png"
    original = _grid(side, metadata=True)
    source.write_bytes(original)
    destination = tmp_path / "private-draft"
    manifest = prepare_drafts(source, destination, strategy=strategy)
    assert manifest["candidate_count"] == 1
    assert manifest["draft"] is True
    assert manifest["approved"] is False
    assert manifest["art_license_confirmed"] is False
    candidates = manifest["candidates"]
    canonical = destination / candidates[0]["variants"][0]["png"]
    assert validate_sprite(canonical.read_bytes()).content == canonical.read_bytes()
    with Image.open(canonical) as image:
        assert image.size == (256, 448)
        assert image.mode == "RGBA"
        assert not image.info
        assert image.getchannel("A").getextrema() == (0, 255)
    assert source.read_bytes() == original
    assert manifest["source_files"][0]["sha256"] == hashlib.sha256(original).hexdigest()


def test_ambiguity_retains_every_candidate_and_cleanup_alternative(tmp_path: Path) -> None:
    source = tmp_path / "arbitrary-form"
    source.mkdir()
    (source / "zebra.png").write_bytes(_grid(64, cleanup=True))
    (source / "tiny-concept.png").write_bytes(_grid(32, cleanup=True))
    (source / "notes.txt").write_text("not a grid", encoding="utf-8")
    manifest = prepare_drafts(source, tmp_path / "draft")
    assert manifest["candidate_count"] == 2
    assert [candidate["source_path"] for candidate in manifest["candidates"]] == [
        "tiny-concept.png",
        "zebra.png",
    ]
    for candidate in manifest["candidates"]:
        assert candidate["selected_variant"] is None
        assert {variant["name"] for variant in candidate["variants"]} == {"original", "cleaned"}
        assert candidate["cleanup"]["requires_owner_choice"] is True
        assert candidate["cleanup"]["affected_frames"] == (("walk", 0),)
        assert any(warning["code"] == "BUNDLE_MEMBERS_IGNORED" for warning in candidate["warnings"])


def test_manifest_and_all_outputs_repeat_identically_and_template_is_exactly_blank(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "b.png").write_bytes(_grid(73))
    (source / "a.png").write_bytes(_grid(64))
    before = _files(source)
    first, second = tmp_path / "private-one", tmp_path / "private-two"
    prepare_drafts(source, first)
    prepare_drafts(source, second)
    assert _files(first) == _files(second)
    assert _files(source) == before
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    for record in manifest["output_files"]:
        output = (first / record["path"]).read_bytes()
        assert len(output) == record["bytes"]
        assert hashlib.sha256(output).hexdigest() == record["sha256"]
    with Image.open(first / "blank-template-invalid-npc.png") as image:
        assert image.size == (256, 448)
        assert image.tobytes() == bytes(256 * 448 * 4)
        assert not image.info
    with pytest.raises(SpriteValidationError, match="character asset is invalid") as failure:
        validate_sprite((first / "blank-template-invalid-npc.png").read_bytes())
    assert failure.value.code == "EMPTY_FRAME"
    assert manifest["blank_template"]["valid_npc_sheet"] is False
    assert str(tmp_path) not in (first / "manifest.json").read_text(encoding="utf-8")


def test_contact_labels_and_seven_animation_frame_order(tmp_path: Path) -> None:
    source = tmp_path / "material.png"
    source.write_bytes(_grid(64))
    destination = tmp_path / "draft"
    manifest = prepare_drafts(source, destination, strategy="pixel_exact")
    prefix = Path(manifest["candidates"][0]["variants"][0]["png"]).parent
    review = (destination / "REVIEW.md").read_text(encoding="utf-8")
    assert "All 28 cells" in review
    with Image.open(destination / prefix / "contact-sheet.png") as contact:
        assert contact.width > 256 * 2
        assert contact.height > 448 * 2
    for row, state in enumerate(STATE_ROWS):
        with Image.open(destination / prefix / f"{state}.gif") as animation:
            assert animation.n_frames == 4
            assert animation.info["duration"] == 160
            assert animation.info["loop"] == 0
            for column in range(4):
                animation.seek(column)
                assert animation.convert("RGB").getpixel((96, 120)) == (
                    30 + row * 20,
                    40 + column * 30,
                    70,
                )


def test_zip_discovery_hashes_archive_and_members(tmp_path: Path) -> None:
    source = tmp_path / "input.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("unknown/a.png", _grid(73))
        archive.writestr("unknown/b.png", _grid(32))
    original = source.read_bytes()
    manifest = prepare_drafts(source, tmp_path / "draft")
    assert manifest["candidate_count"] == 2
    assert {record["path"] for record in manifest["source_files"]} == {
        "input.zip",
        "unknown/a.png",
        "unknown/b.png",
    }
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "unsafe", ["../escape.png", "/absolute.png", "bad\\path.png", "bad\x00path.png"]
)
def test_unsafe_zip_paths_fail_without_output(tmp_path: Path, unsafe: str) -> None:
    source = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(source, "w") as archive:
        info = zipfile.ZipInfo("placeholder.png")
        info.filename = unsafe  # ZipInfo's Windows constructor normalizes backslashes.
        archive.writestr(info, _grid(64))
    destination = tmp_path / "draft"
    with pytest.raises(SpriteConversionError) as failure:
        prepare_drafts(source, destination)
    assert failure.value.code == "PACK_UNSAFE"
    assert not destination.exists()


def test_archive_symlink_rejected(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.zip"
    info = zipfile.ZipInfo("linked.png")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(info, "../../elsewhere")
    with pytest.raises(SpriteConversionError) as failure:
        prepare_drafts(source, tmp_path / "draft")
    assert failure.value.code == "PACK_UNSAFE"


def test_folder_symlink_rejected_without_following(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(_grid(64))
    try:
        (source / "linked.png").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"host cannot create symlinks: {exc}")
    with pytest.raises(ValueError, match="symlinks"):
        prepare_drafts(source, tmp_path / "draft")


def test_output_symlink_is_rejected_and_target_untouched(tmp_path: Path) -> None:
    source = tmp_path / "material.png"
    source.write_bytes(_grid(64))
    target = tmp_path / "owner-directory"
    target.mkdir()
    sentinel = target / "preserve.txt"
    sentinel.write_text("owner file", encoding="utf-8")
    linked = tmp_path / "linked-directory"
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"host cannot create symlinks: {exc}")
    with pytest.raises(ValueError, match="symlinks"):
        prepare_drafts(source, linked / "draft")
    assert sentinel.read_text(encoding="utf-8") == "owner file"
    assert not (target / "draft").exists()


def test_folder_total_byte_budget_rejected_before_conversion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import prepare_character_assets

    monkeypatch.setattr(prepare_character_assets, "MAX_SOURCE_UNCOMPRESSED_BYTES", 10)
    source = tmp_path / "material"
    source.mkdir()
    (source / "one.txt").write_bytes(b"012345")
    (source / "two.txt").write_bytes(b"012345")
    with pytest.raises(SpriteConversionError) as failure:
        prepare_drafts(source, tmp_path / "draft")
    assert failure.value.code == "PACK_LIMIT_EXCEEDED"
    assert not (tmp_path / "draft").exists()


def test_excess_candidates_fail_without_a_partial_selection(tmp_path: Path) -> None:
    source = tmp_path / "material"
    source.mkdir()
    for index in range(17):
        (source / f"art-{index}.png").write_bytes(_grid(16))
    with pytest.raises(SpriteConversionError) as failure:
        prepare_drafts(source, tmp_path / "draft")
    assert failure.value.code == "TOO_MANY_CANDIDATES"
    assert not (tmp_path / "draft").exists()


@pytest.mark.parametrize("kind", ["member", "count", "invalid-png", "traversal", "overlap"])
def test_input_bounds_invalid_png_and_path_rejection(tmp_path: Path, kind: str) -> None:
    source = tmp_path / "source"
    source.mkdir()
    destination = tmp_path / "draft"
    if kind == "member":
        with (source / "large.dat").open("wb") as stream:
            stream.truncate(MAX_SOURCE_MEMBER_BYTES + 1)
    elif kind == "count":
        for index in range(MAX_PACK_ENTRIES + 1):
            (source / f"{index}.txt").touch()
    elif kind == "invalid-png":
        source = source / "bad.png"
        source.write_bytes(_grid(64) + b"trailing-polyglot")
    elif kind == "traversal":
        source = source / ".." / "source"
    else:
        destination = source / "draft"
    with pytest.raises((ValueError, SpriteConversionError)):
        prepare_drafts(source, destination)
    assert not destination.exists()


def test_destination_is_never_overwritten_even_empty_or_after_partial_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_grid(64))
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        prepare_drafts(source, existing)
    sentinel = existing / "owner-file.txt"
    sentinel.write_text("preserve this", encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare_drafts(source, existing)
    assert sentinel.read_text(encoding="utf-8") == "preserve this"
    destination = tmp_path / "partial"
    real_open = Path.open

    def fail_write(path: Path, *args: object, **kwargs: object) -> object:
        if path.name == "SOURCE_PROVENANCE.md" and args and args[0] == "xb":
            raise OSError("simulated storage failure")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_write)
    with pytest.raises(OSError, match="simulated"):
        prepare_drafts(source, destination)
    partial = _files(destination)
    assert partial
    with pytest.raises(FileExistsError):
        prepare_drafts(source, destination)
    assert _files(destination) == partial
