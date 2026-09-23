import { describe, expect, it } from "vitest";

import {
  analyzeFrameAlignment,
  automaticFrameAlignment,
  canShiftFrame,
  emptyFrameOffsets,
  parseFramePixelOffset,
} from "./characterFrameAlignment";

const SHEET_WIDTH = 256;
const SHEET_HEIGHT = 448;
const FRAME_SIZE = 64;

function sheetWithPositions(positionsByRow: number[][]): Uint8ClampedArray {
  const rgba = new Uint8ClampedArray(SHEET_WIDTH * SHEET_HEIGHT * 4);
  for (let row = 0; row < 7; row += 1) {
    for (let frame = 0; frame < 4; frame += 1) {
      const left = positionsByRow[row]?.[frame] ?? 20;
      for (let y = 18; y < 44; y += 1) {
        for (let x = left; x < left + 12; x += 1) {
          rgba[
            ((row * FRAME_SIZE + y) * SHEET_WIDTH + frame * FRAME_SIZE + x) *
              4 +
              3
          ] = 255;
        }
      }
    }
  }
  return rgba;
}

describe("character frame alignment", () => {
  it("suggests safe shifts for an unseen shape drifting in more than one state", () => {
    const rgba = sheetWithPositions([
      [18, 14, 10, 6],
      [4, 10, 16, 22],
    ]);
    const analysis = analyzeFrameAlignment(rgba, SHEET_WIDTH, SHEET_HEIGHT);

    for (const row of [0, 1]) {
      const starts = Array.from({ length: 4 }, (_, frame) => {
        const index = row * 4 + frame;
        expect(
          canShiftFrame(
            analysis.bounds[index]!,
            analysis.suggestedOffsets[index]!,
          ),
        ).toBe(true);
        return (
          analysis.bounds[index]!.left + analysis.suggestedOffsets[index]!.x
        );
      });
      expect(new Set(starts).size).toBe(1);
      expect(analysis.horizontalDrift[row]).toBeGreaterThan(0);
    }
    expect(analysis.suggestedOffsets.every((offset) => offset.y === 0)).toBe(
      true,
    );
  });

  it("does not invent movement for already aligned frames", () => {
    const analysis = analyzeFrameAlignment(
      sheetWithPositions([]),
      SHEET_WIDTH,
      SHEET_HEIGHT,
    );
    expect(analysis.suggestedOffsets).toEqual(emptyFrameOffsets());
    expect(analysis.horizontalDrift.every((drift) => drift === 0)).toBe(true);
    expect(automaticFrameAlignment(analysis)).toEqual({
      offsets: emptyFrameOffsets(),
      alignedStates: 0,
    });
  });

  it("automatically corrects repeated grid-column displacement across unrelated states", () => {
    const rgba = sheetWithPositions([
      [37, 30, 23, 17],
      [36, 29, 22, 16],
      [38, 31, 24, 18],
      [35, 28, 21, 15],
      [39, 32, 25, 19],
      [37, 30, 23, 17],
      [36, 29, 22, 16],
    ]);
    const analysis = analyzeFrameAlignment(rgba, SHEET_WIDTH, SHEET_HEIGHT);
    const automatic = automaticFrameAlignment(analysis);
    expect(automatic.alignedStates).toBe(7);
    for (let row = 0; row < 7; row += 1) {
      const adjusted = Array.from({ length: 4 }, (_, frame) => {
        const index = row * 4 + frame;
        expect(
          canShiftFrame(analysis.bounds[index]!, automatic.offsets[index]!),
        ).toBe(true);
        return analysis.anchors[index]! + automatic.offsets[index]!.x;
      });
      expect(Math.max(...adjusted) - Math.min(...adjusted)).toBeLessThanOrEqual(
        1,
      );
    }
  });

  it("leaves a single expressive moving state untouched", () => {
    const analysis = analyzeFrameAlignment(
      sheetWithPositions([
        [20, 20, 20, 20],
        [8, 15, 22, 29],
      ]),
      SHEET_WIDTH,
      SHEET_HEIGHT,
    );
    expect(analysis.suggestedOffsets.some((offset) => offset.x !== 0)).toBe(
      true,
    );
    expect(automaticFrameAlignment(analysis).offsets).toEqual(
      emptyFrameOffsets(),
    );
  });

  it("does not choose between competing column patterns", () => {
    const analysis = analyzeFrameAlignment(
      sheetWithPositions([
        [8, 13, 18, 23],
        [9, 14, 19, 24],
        [10, 15, 20, 25],
        [30, 25, 20, 15],
        [31, 26, 21, 16],
        [32, 27, 22, 17],
      ]),
      SHEET_WIDTH,
      SHEET_HEIGHT,
    );
    expect(automaticFrameAlignment(analysis)).toEqual({
      offsets: emptyFrameOffsets(),
      alignedStates: 0,
    });
  });

  it("keeps unusually large translations as review-only suggestions", () => {
    const analysis = analyzeFrameAlignment(
      sheetWithPositions(Array.from({ length: 7 }, () => [4, 20, 36, 48])),
      SHEET_WIDTH,
      SHEET_HEIGHT,
    );
    expect(analysis.suggestedOffsets.some((offset) => offset.x !== 0)).toBe(
      true,
    );
    expect(automaticFrameAlignment(analysis).offsets).toEqual(
      emptyFrameOffsets(),
    );
  });

  it("never suggests or permits a shift that would crop opaque edge pixels", () => {
    const rgba = sheetWithPositions([[0, 10, 20, 30]]);
    for (let y = 18; y < 44; y += 1) {
      for (let x = 0; x < FRAME_SIZE; x += 1) {
        rgba[(y * SHEET_WIDTH + x) * 4 + 3] = 255;
      }
    }
    const analysis = analyzeFrameAlignment(rgba, SHEET_WIDTH, SHEET_HEIGHT);
    expect(analysis.suggestedOffsets[0]).toEqual({ x: 0, y: 0 });
    expect(
      analysis.suggestedOffsets.every((offset, index) =>
        canShiftFrame(analysis.bounds[index]!, offset),
      ),
    ).toBe(true);
    expect(canShiftFrame(analysis.bounds[0]!, { x: 1, y: 0 })).toBe(false);
    expect(canShiftFrame(analysis.bounds[0]!, { x: 0, y: -19 })).toBe(false);
  });

  it("rejects malformed sheet dimensions and empty frames", () => {
    const valid = sheetWithPositions([]);
    expect(() => analyzeFrameAlignment(valid, 128, SHEET_HEIGHT)).toThrow();
    valid.fill(0, 3, valid.length);
    expect(() =>
      analyzeFrameAlignment(valid, SHEET_WIDTH, SHEET_HEIGHT),
    ).toThrow("Empty character frame");
  });

  it("accepts bounded integer X/Y entries and rejects clipping or partial text", () => {
    const bounds = { left: 5, top: 7, right: 54, bottom: 61 };
    expect(parseFramePixelOffset({ x: "-5", y: "3" }, bounds)).toEqual({
      x: -5,
      y: 3,
    });
    expect(parseFramePixelOffset({ x: "11", y: "0" }, bounds)).toBeNull();
    expect(parseFramePixelOffset({ x: "2.5", y: "0" }, bounds)).toBeNull();
    expect(parseFramePixelOffset({ x: "", y: "-" }, bounds)).toBeNull();
  });
});
