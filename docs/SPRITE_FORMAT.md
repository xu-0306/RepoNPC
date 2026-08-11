# RepoNPC v1 Sprite-Sheet Format

**Status:** Draft format contract  
**Format version:** 1  
**Related requirements:** FR-015, FR-016; AC-020–AC-022

## 1. Canonical sheet

A custom RepoNPC character is one non-animated PNG with:

- canvas: exactly **128 x 224 pixels**;
- grid: **4 columns x 7 rows**;
- frame: exactly **32 x 32 pixels**;
- one facing direction; the UI may mirror it horizontally;
- transparent RGBA or indexed color that decodes to RGBA;
- rows and columns in the fixed order below.

```text
             column 0   column 1   column 2   column 3
row 0 idle      0,0        32,0       64,0       96,0
row 1 walk      0,32       32,32      64,32      96,32
row 2 listen    0,64       32,64      64,64      96,64
row 3 think     0,96       32,96      64,96      96,96
row 4 talk      0,128      32,128     64,128     96,128
row 5 success   0,160      32,160     64,160     96,160
row 6 offline   0,192      32,192     64,192     96,192
```

Each coordinate is the top-left pixel of a `32 x 32` frame. Pixel coordinates are zero-based; no gutters, margins, padding, or resolution metadata affects the grid.

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

All four frames must be present. Frames may intentionally repeat for a quiet state, but frame 0 of every row must contain at least one non-transparent pixel.

## 3. Pixel-art authoring rules

- Draw at native `32 x 32`; do not submit an upscaled sheet.
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
4. require exact decoded dimensions `128 x 224`;
5. convert to canonical 8-bit RGBA;
6. require at least one transparent pixel in the sheet and non-empty frame 0 for every state row;
7. strip text, ICC, EXIF, timestamps, and other ancillary metadata;
8. re-encode deterministically to a normal non-interlaced PNG;
9. calculate content SHA-256 and use only the re-encoded bytes for preview, GitHub writeback, and bundle generation.

MIME type and filename extension alone are never trusted. Valid writeback paths match exactly `assets/character/*.png`; filenames are lowercase ASCII matching `^[a-z][a-z0-9_-]{0,63}\.png$`.

Stable validation codes should include `WRONG_DIMENSIONS`, `FILE_TOO_LARGE`, `NOT_PNG`, `ANIMATED_PNG`, `UNSUPPORTED_COLOR_MODE`, `MISSING_TRANSPARENCY`, `EMPTY_STATE`, `UNSAFE_PNG`, and `INVALID_FILENAME` with localized safe messages.

## 5. Animation behavior

- `character.animation.frame_duration_ms` accepts 80–1000 ms; the example uses 160 ms.
- Each state loops columns 0 → 1 → 2 → 3 unless the state controller uses a short one-shot `success` sequence followed by idle.
- State changes begin at column 0 to avoid nondeterministic visual jumps.
- `walk` may translate the rendered character a small bounded distance; other states should remain anchored.
- `prefers-reduced-motion: reduce` disables frame cycling, entrance movement, bobbing, and automatic transitions; it shows column 0 of the current semantic state.
- Animation stopping must not hide state text/status available to assistive technology.

## 6. Built-in character composition

Built-in parts are registered by stable IDs in a versioned asset manifest. At minimum v1 supports the IDs used by `reponpc.example.yml`:

- body: `standard`;
- skin: `light`, `medium`, `dark`;
- hair: `none`, `short`, `long`;
- outfit: `adventurer`, `engineer`, `mage`;
- accessory: `none`, `glasses`, `headphones`;
- hexadecimal hair/primary/secondary colors.

Each layer uses the same 4x7 grid and alignment. The composer orders layers deterministically (body/skin, outfit, hair, accessory), applies only allowlisted palette substitutions, and outputs the canonical re-encoded sheet. Unknown IDs/colors fail configuration validation rather than silently selecting an option.

Additional built-in IDs are backward-compatible. Removing/renaming an ID requires a schema migration and upgrade note.

## 7. README card rendering

The card scales a chosen frame/state with integer nearest-neighbor scaling. It must not embed the original uploaded PNG as an uncontrolled external link. Generated SVG either uses sanitized embedded pixel data or deterministic vector rectangles/data URLs that pass the SVG allowlist.

- Static PNG uses the first `idle` frame.
- SVG first frame uses the same pose and remains complete if CSS animation is stripped.
- GIF may use a curated subset of idle frames to avoid distracting motion and size growth.
- Character/card revision participates in ETag and README cache-busting URLs.

## 8. Template and licensing

Before v1 release, the repository must include:

- a blank transparent `128x224` template with grid/state guide outside the exported pixels;
- one complete example sheet exercising all states;
- automated golden fixtures for valid/invalid sheets;
- license/provenance for all built-in pixels and example assets compatible with the project MIT distribution.

Contributors must not submit copyrighted game sprites or traced proprietary assets without redistribution rights.

