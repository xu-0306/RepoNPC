# RepoNPC v1 Sprite-Sheet Format

**Status:** Approved format contract through Technical Specification 0.3.8
**Format version:** 1  
**Related requirements:** FR-015, FR-016; AC-020–AC-022

## 1. Canonical sheet

A custom RepoNPC character is one non-animated PNG with:

- canvas: exactly **256 x 448 pixels**;
- grid: **4 columns x 7 rows**;
- frame: exactly **64 x 64 pixels**;
- one facing direction; the UI may mirror it horizontally;
- transparent RGBA or indexed color that decodes to RGBA;
- rows and columns in the fixed order below.

```text
             column 0   column 1   column 2   column 3
row 0 idle      0,0        64,0       128,0      192,0
row 1 walk      0,64       64,64      128,64     192,64
row 2 listen    0,128      64,128     128,128    192,128
row 3 think     0,192      64,192     128,192    192,192
row 4 talk      0,256      64,256     128,256    192,256
row 5 success   0,320      64,320     128,320    192,320
row 6 offline   0,384      64,384     128,384    192,384
```

Each coordinate is the top-left pixel of a `64 x 64` frame. Pixel coordinates are zero-based; no gutters, margins, padding, or resolution metadata affects the canonical grid.

## 2. State meanings

| Row | State | When used | Recommended motion |
| ---: | --- | --- | --- |
| 0 | `idle` | Page ready, no active interaction | breathing/blink, minimal movement |
| 1 | `walk` | Decorative entrance/short repositioning | alternating feet/body bob |
| 2 | `listen` | Input focused or visitor composing | attentive pose, small reaction |
| 3 | `think` | Retrieval/provider/answer validation | visible thinking loop |
| 4 | `talk` | Validated SSE answer chunks rendering | mouth/gesture loop |
| 5 | `success` | Answer completed normally | short positive reaction |
| 6 | `offline` | Setup/model/service error | calm unavailable pose, not alarming |

All four frames must be present and every one of the 28 cells must contain at least one non-transparent pixel. Frames may intentionally repeat for a quiet state.

## 3. Pixel-art authoring rules

- Prefer drawing at native `64 x 64`. Larger or smaller source material should use the converter and must be reviewed at canonical size.
- Use hard pixel edges and no fractional coordinates.
- Keep important features within each frame. Pixels do not bleed into adjacent cells.
- Prefer a consistent ground/baseline (recommended y=29 within each frame) so state changes do not jump.
- Leave transparency around the silhouette where practical.
- Avoid tiny text, logos that become unreadable, flashing frames, and rapid high-contrast changes.
- Use nearest-neighbor scaling in previews and cards; smoothing must be disabled.
- The sheet may use any palette, but the final UI/card contrast and non-color state cues must remain accessible.

## 4. Validation contract

Admin preview/writeback and the index build perform the same validation:

1. enforce the configured byte limit (default 1 MiB, hard maximum 2 MiB) before decode;
2. verify PNG signature and decode successfully with bounded pixel/memory work;
3. reject APNG/multiple-frame data, malformed/trailing polyglot content, and unsupported color/depth modes;
4. require exact decoded dimensions `256 x 448`;
5. convert to canonical 8-bit RGBA;
6. require at least one transparent pixel in the sheet and every one of the 28 frames to be non-empty;
7. strip text, ICC, EXIF, timestamps, and other ancillary metadata;
8. re-encode deterministically to a normal non-interlaced PNG;
9. calculate content SHA-256 and use only the re-encoded bytes for preview, GitHub writeback, and bundle generation.

MIME type and filename extension alone are never trusted. Valid writeback paths match exactly `assets/character/*.png`; filenames are lowercase ASCII matching `^[a-z][a-z0-9_-]{0,63}\.png$`.

Stable validation codes should include `WRONG_DIMENSIONS`, `FILE_TOO_LARGE`, `NOT_PNG`, `ANIMATED_PNG`, `UNSUPPORTED_COLOR_MODE`, `MISSING_TRANSPARENCY`, `EMPTY_FRAME`, `UNSAFE_PNG`, and `INVALID_FILENAME` with localized safe messages.

### 4.1 Material conversion

Conversion is separate from canonical validation and never weakens it. The authenticated admin input may be:

1. one static PNG with exactly four columns and seven rows of equal square cells at any bounded source cell size; or
2. one bounded ZIP with root `sprite-pack.json` schema 1 whose `frames` object contains exactly the seven state keys and exactly four unique PNG member paths per state; or
3. one manifestless bounded ZIP or browser-selected folder containing one or more PNG files plus optional unrelated material.

The converter derives grid size from image dimensions; it does not recognize `237px`, generator filenames, folders such as `Man`, species, or visual content. Manifest paths are explicit POSIX-relative data. Without a root manifest, every bounded PNG is checked for the same square-cell 4-by-7 structure. One candidate converts automatically, multiple candidates return canonical previews for the owner to choose, and none return actionable failure. Candidate IDs hash the normalized relative path and bytes and are recomputed on selection.

Single PNG/ZIP payloads are capped at 16 MiB. ZIP/folder material is capped at 64 entries, 8 MiB per member, 64 MiB expanded total, 256 path characters, and 16 convertible candidates. Traversal, absolute/backslash paths, symbolic links, encryption, duplicate names, animated/unsafe PNGs and resource-limit violations fail closed. Bounded unrelated/non-candidate material may be ignored and counted, but strict manifest references never degrade to discovery or silently lose frames.

`pixel_exact` uses nearest-neighbor scaling only for integer scale ratios. `pixelize` supports non-integer high-resolution material by deterministic bounded resampling, at most 64 output colors, and binary alpha thresholding. Non-square manifest frames are contained on a transparent bottom-centered square. The report identifies affected frames for partial-alpha removal, palette reduction, padding and edge contact; it also reports mixed source dimensions and bounded unreferenced members.

Conversion output is a draft canonical PNG, not proof of artistic quality. The owner must inspect every state/frame. Conversion never creates a missing pose, writes automatically, preserves source metadata, or treats ZIP content as executable code. Download and GitHub writeback are separate explicit actions; writeback revalidates the canonical bytes.

For structural grid PNGs, a conservative edge-spill check may additionally produce a separately validated cleaned version. It targets only a shallow strip at the top of a cell that continues the preceding row's bottom pixels and is separated from the current character by a transparent gap. This is geometry, not recognition of a species, body part, color or filename. Uncertain, deep, or connected artwork remains untouched; manifest frames are not altered. The normal conversion remains available. The owner compares the same state/frame, then explicitly chooses the cleaned or original version before download or writeback; source bytes are never overwritten. If position alignment is used afterward, it starts with that selected version.

### 4.2 Frame-position repair

After conversion and any original/cleaned choice, the workspace automatically examines each state's four frames. It auto-corrects horizontal drift only when a bounded, non-clipping column pattern agrees across at least half of the seven states, then passes the composed PNG through the protected canonical validator before offering download or writeback. Isolated movement and ambiguous patterns remain unaltered suggestions. The owner can preview all suggestions, enter each frame's X/Y integer-pixel offset, use one-pixel controls, and restore the chosen unaligned version. Invalid or clipping offsets are rejected. Manual edits remain drafts until explicitly applied and validated. The source file is never overwritten; repeated deliberate motion can look like layout drift, so the owner still inspects all states.

## 5. Animation behavior

- `character.animation.frame_duration_ms` accepts 80–1000 ms; the example uses 160 ms.
- Each state loops columns 0 → 1 → 2 → 3 unless the state controller uses a short one-shot `success` sequence followed by idle.
- State changes begin at column 0 to avoid nondeterministic visual jumps.
- `walk` may translate the rendered character a small bounded distance; other states should remain anchored.
- `prefers-reduced-motion: reduce` disables frame cycling, entrance movement, bobbing, and automatic transitions; it shows column 0 of the current semantic state.
- Animation stopping must not hide state text/status available to assistive technology.

## 6. Built-in character packs

Built-ins use a versioned pack contract rather than a universal list of species or humanoid body slots:

```yaml
character:
  mode: builtin
  revision: 1
  builtin:
    pack_id: core/humanoid
    pack_version: 1
    options:
      tone: medium
      hairstyle: short
      attire: adventurer
      hair_color: "#2b1d14"
      primary_color: "#6d5dfc"
      secondary_color: "#f2c14e"
      accessory: glasses
```

Core code understands only the pack identity, bounded string options, and canonical output. Each trusted application pack owns its option names, allowlisted values, internal layers, palette rules, and deterministic renderer. `core/humanoid` version 1 happens to expose the example options above; those names are not required of another pack. A cat, floating orb, vehicle, plant, or other form may expose a completely different manifest without editing the core schema.

The public configuration has no `species` field. Users whose design is not a shipped built-in pack select `mode: custom` and provide the same canonical sheet described in this document. No classification or anatomy metadata is required.

Pack IDs and versions resolve exactly. Unknown packs, unsupported versions, missing or unknown option names, invalid values, renderer failures, and non-canonical output are fatal and never cause substitution or fallback. YAML cannot register renderers or supply code, filesystem paths, URLs, or arbitrary assets to a built-in pack.

The earlier undeployed top-level `body`, `skin`, `hair`, `outfit`, palette, and `accessory` fields are invalid and intentionally have no compatibility aliases. Internal humanoid layer ordering remains a private implementation detail of `core/humanoid`, not a cross-species contract.

## 7. README card rendering

The card scales a chosen frame/state with integer nearest-neighbor scaling. It must not embed the original uploaded PNG as an uncontrolled external link. Generated SVG either uses sanitized embedded pixel data or deterministic vector rectangles/data URLs that pass the SVG allowlist.

- Static PNG uses the first `idle` frame.
- SVG first frame uses the same pose and remains complete if CSS animation is stripped.
- GIF may use a curated subset of idle frames to avoid distracting motion and size growth.
- Character/card revision participates in ETag and README cache-busting URLs.

## 8. Template and licensing

Before v1 release, the repository must include:

- a blank transparent `256x448` template with grid/state guide outside the exported pixels;
- one complete example sheet exercising all states;
- automated golden fixtures for valid/invalid sheets;
- license/provenance for all built-in pixels and example assets compatible with the project MIT distribution.

Contributors must not submit copyrighted game sprites or traced proprietary assets without redistribution rights.
