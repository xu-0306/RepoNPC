"""Host-only, reproducible private character drafts; never publishes or changes sources.

Example (the destination must not exist):
  uv run --locked python tools/prepare_character_assets.py --source PixelNPC/Man \
    --draft-dir release-evidence/a9/drafts/man --strategy pixelize

Discovery, normalization, cleanup suggestions and validation use the existing
converter. This script only exports review artifacts, not an animation engine.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import stat
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from reponpc.cards.assets import (
    FRAME_COLUMNS,
    FRAME_ROWS,
    FRAME_SIZE,
    HEIGHT,
    STATE_ROWS,
    WIDTH,
    validate_sprite,
)
from reponpc.cards.conversion import (
    MAX_PACK_ENTRIES,
    MAX_SOURCE_BYTES,
    MAX_SOURCE_MEMBER_BYTES,
    MAX_SOURCE_UNCOMPRESSED_BYTES,
    ConversionStrategy,
    MaterialEntry,
    SpriteConversion,
    SpriteConversionError,
    SpriteSelection,
    prepare_sprite_entries,
    prepare_sprite_material,
)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_path(path: Path) -> Path:
    if ".." in path.parts:
        raise ValueError("parent traversal is not allowed")
    absolute = path.absolute()
    for component in (*reversed(absolute.parents), absolute):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("symlinks and reparse points are not allowed")
    return absolute


def _read_file(path: Path, limit: int) -> bytes:
    _safe_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("source must contain only regular files and directories")
    if before.st_size > limit:
        raise SpriteConversionError("SOURCE_FILE_TOO_LARGE")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("source changed during preparation")
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise SpriteConversionError("SOURCE_FILE_TOO_LARGE")
    return content


def _folder_entries(source: Path) -> tuple[MaterialEntry, ...]:
    entries: list[MaterialEntry] = []
    pending = [source]
    count = total = 0
    while pending:
        directory = pending.pop()
        _safe_path(directory)
        with os.scandir(directory) as iterator:
            for item in iterator:
                count += 1
                if count > MAX_PACK_ENTRIES:
                    raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
                path = _safe_path(Path(item.path))
                if path.is_dir():
                    pending.append(path)
                    continue
                content = _read_file(path, MAX_SOURCE_MEMBER_BYTES)
                total += len(content)
                if total > MAX_SOURCE_UNCOMPRESSED_BYTES:
                    raise SpriteConversionError("PACK_LIMIT_EXCEEDED")
                entries.append(MaterialEntry(path.relative_to(source).as_posix(), content))
    return tuple(sorted(entries, key=lambda entry: entry.path))


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9, interlace=False)
    return buffer.getvalue()


def _frame(image: Image.Image, row: int, column: int, scale: int) -> Image.Image:
    return image.crop(
        (
            column * FRAME_SIZE,
            row * FRAME_SIZE,
            (column + 1) * FRAME_SIZE,
            (row + 1) * FRAME_SIZE,
        )
    ).resize((FRAME_SIZE * scale, FRAME_SIZE * scale), Image.Resampling.NEAREST)


def _contact_sheet(image: Image.Image) -> bytes:
    side, label_height, margin = FRAME_SIZE * 2, 20, 8
    panel_width = FRAME_COLUMNS * (side + margin)
    output = Image.new("RGB", (panel_width * 2, FRAME_ROWS * (side + label_height) + 24))
    draw = ImageDraw.Draw(output)
    for panel, (background, foreground, title) in enumerate(
        (((245, 245, 245), (20, 20, 20), "LIGHT"), ((25, 25, 25), (245, 245, 245), "DARK"))
    ):
        left = panel * panel_width
        draw.rectangle((left, 0, left + panel_width - 1, output.height), fill=background)
        draw.text((left + margin, 4), f"DRAFT / UNAPPROVED - {title}", fill=foreground)
        for row, state in enumerate(STATE_ROWS):
            for column in range(FRAME_COLUMNS):
                x, y = left + column * (side + margin), 24 + row * (side + label_height)
                draw.text((x + margin, y), f"{state}:{column}", fill=foreground)
                frame = _frame(image, row, column, 2)
                output.paste(frame, (x, y + label_height), frame)
    return _png(output)


def _animation(image: Image.Image, row: int) -> bytes:
    frames = []
    for column in range(FRAME_COLUMNS):
        output = Image.new("RGB", (FRAME_SIZE * 3, FRAME_SIZE * 3 + 24), (245, 245, 245))
        ImageDraw.Draw(output).text((4, 4), f"DRAFT {STATE_ROWS[row]}:{column}", fill=(20, 20, 20))
        frame = _frame(image, row, column, 3)
        output.paste(frame, (0, 24), frame)
        frames.append(output.quantize(colors=256, dither=Image.Dither.NONE))
    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=160,
        loop=0,
        disposal=2,
        optimize=False,
    )
    return buffer.getvalue()


def prepare_drafts(
    source: Path,
    draft_dir: Path,
    *,
    strategy: ConversionStrategy = "pixelize",
) -> dict[str, object]:
    """Export all candidates into a fresh, explicitly chosen private directory.

    Existing destinations (even empty ones) are rejected. A failed write may
    leave a partial private directory; rerun with a new destination, never
    overwrite it. Source and destination trees must not overlap.
    """
    source, draft_dir = _safe_path(source), _safe_path(draft_dir)
    if source == draft_dir or source in draft_dir.parents or draft_dir in source.parents:
        raise ValueError("source and draft directory must not overlap")
    if draft_dir.exists():
        raise FileExistsError("draft directory already exists; choose a fresh directory")
    entries = _folder_entries(source) if source.is_dir() else None
    if entries is not None:
        prepared = prepare_sprite_entries(entries, strategy=strategy)
        source_records = [
            {"path": entry.path, "sha256": _sha(entry.content), "bytes": len(entry.content)}
            for entry in entries
        ]
    else:
        content = _read_file(source, MAX_SOURCE_BYTES)
        prepared = prepare_sprite_material(content, strategy=strategy)
        source_records = [{"path": source.name, "sha256": _sha(content), "bytes": len(content)}]
        if zipfile.is_zipfile(io.BytesIO(content)):
            # The converter has already enforced archive path, size and type limits.
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                source_records.extend(
                    {
                        "path": info.filename,
                        "sha256": _sha(archive.read(info)),
                        "bytes": info.file_size,
                    }
                    for info in sorted(archive.infolist(), key=lambda info: info.filename)
                    if not info.is_dir()
                )

    if isinstance(prepared, SpriteSelection):
        conversions = []
        for candidate in prepared.candidates:
            # Discovery only computes cleanup for its first candidate. Selecting
            # each structural ID runs the same cleanup primitive for every one.
            selected = (
                prepare_sprite_entries(
                    entries, strategy=strategy, candidate_id=candidate.candidate_id
                )
                if entries is not None
                else prepare_sprite_material(
                    content, strategy=strategy, candidate_id=candidate.candidate_id
                )
            )
            assert isinstance(selected, SpriteConversion)
            conversions.append(selected)
    else:
        conversions = [prepared]

    outputs: dict[str, bytes] = {}
    candidates: list[dict[str, object]] = []
    review = [
        "# Private character drafts — unapproved",
        "",
        "Art and licensing are unconfirmed. These files are not production packs.",
        "Inspect all 28 cells, seven animations, light/dark edges, baseline and motion.",
        "Original and cleaned alternatives remain separate; no choice is made for you.",
        "The blank template is truly empty and is NOT a valid NPC sheet.",
        "",
    ]
    for conversion in conversions:
        source_path = conversion.source_path or source.name
        identifier = conversion.candidate_id or _sha(source_path.encode("utf-8") + b"\0" + content)
        alternatives = [("original", conversion.sprite)]
        if conversion.cleanup is not None:
            alternatives.append(("cleaned", conversion.cleanup.sprite))
        record: dict[str, object] = {
            "candidate_id": identifier,
            "source_path": source_path,
            "source_kind": conversion.source_kind,
            "source_frame_sizes": conversion.source_frame_sizes,
            "warnings": [{"code": item.code, "items": item.items} for item in conversion.warnings],
            "variants": [],
            "selected_variant": None,
        }
        if conversion.cleanup is not None:
            record["cleanup"] = {
                "affected_frames": conversion.cleanup.affected_frames,
                "removed_source_pixels": conversion.cleanup.removed_source_pixels,
                "requires_owner_choice": True,
            }
        review.extend(
            [
                f"## Candidate {identifier}",
                "",
                f"Source: <code>{html.escape(source_path)}</code>",
                "",
            ]
        )
        variants = []
        for name, sprite in alternatives:
            canonical = validate_sprite(sprite.content)
            prefix = f"candidate-{identifier}/{name}"
            outputs[f"{prefix}/character.png"] = canonical.content
            image = Image.open(io.BytesIO(canonical.content)).convert("RGBA")
            outputs[f"{prefix}/contact-sheet.png"] = _contact_sheet(image)
            for row, state in enumerate(STATE_ROWS):
                outputs[f"{prefix}/{state}.gif"] = _animation(image, row)
            variants.append(
                {"name": name, "png": f"{prefix}/character.png", "sha256": canonical.sha256}
            )
            review.extend(
                [
                    f"### {name} (draft)",
                    "",
                    f"![All 28 cells, light and dark]({prefix}/contact-sheet.png)",
                    "",
                    " | ".join(f"[{state}]({prefix}/{state}.gif)" for state in STATE_ROWS),
                    "",
                ]
            )
        record["variants"] = variants
        candidates.append(record)

    outputs["blank-template-invalid-npc.png"] = _png(
        Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    )
    outputs["REVIEW.md"] = ("\n".join(review) + "\n").encode("utf-8")
    outputs["SOURCE_PROVENANCE.md"] = (
        b"# Source provenance facts (draft)\n\n"
        b"The manifest records relative source paths, byte sizes and SHA-256 hashes.\n"
        b"All sources were read only. Conversion uses RepoNPC's existing pixel converter.\n"
        b"Names, metadata or graphics stating MIT are not evidence of redistribution rights.\n"
        b"The owner must confirm origin, generation rights, reference/photo permissions,\n"
        b"and final license before any asset can become a production pack or example.\n"
        b"No source artwork was redrawn; alignment was not applied by this export tool.\n"
    )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "draft": True,
        "approved": False,
        "art_license_confirmed": False,
        "strategy": strategy,
        "canonical_dimensions": [WIDTH, HEIGHT],
        "frame_dimensions": [FRAME_SIZE, FRAME_SIZE],
        "state_order": STATE_ROWS,
        "frame_order": list(range(FRAME_COLUMNS)),
        "animation_frame_duration_ms": 160,
        "source_files": source_records,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "blank_template": {"path": "blank-template-invalid-npc.png", "valid_npc_sheet": False},
        "output_files": [
            {"path": name, "sha256": _sha(value), "bytes": len(value)}
            for name, value in sorted(outputs.items())
        ],
    }
    outputs["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    _safe_path(draft_dir.parent)
    draft_dir.parent.mkdir(parents=True, exist_ok=True)
    draft_dir.mkdir()  # Exclusive creation: even a concurrent empty destination fails closed.
    for name, value in sorted(outputs.items()):
        target = draft_dir / name
        _safe_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(value)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--draft-dir", required=True, type=Path, help="fresh private review directory"
    )
    parser.add_argument("--strategy", choices=("pixel_exact", "pixelize"), default="pixelize")
    arguments = parser.parse_args()
    try:
        manifest = prepare_drafts(
            arguments.source, arguments.draft_dir, strategy=arguments.strategy
        )
    except (OSError, ValueError) as exc:
        reason = exc.code if isinstance(exc, SpriteConversionError) else str(exc)
        parser.exit(1, f"Draft preparation failed: {reason}\n")
    print(f"Prepared {manifest['candidate_count']} unapproved candidates; inspect REVIEW.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
