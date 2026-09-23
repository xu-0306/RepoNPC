import {
  CHARACTER_FRAME_COUNT,
  CHARACTER_FRAME_SIZE,
  CHARACTER_SHEET_HEIGHT,
  CHARACTER_SHEET_WIDTH,
  CHARACTER_STATES,
} from "../character/CharacterRenderer";

export interface FrameOffset {
  x: number;
  y: number;
}

export interface FrameBounds {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface FrameAlignmentAnalysis {
  bounds: FrameBounds[];
  anchors: number[];
  suggestedOffsets: FrameOffset[];
  horizontalDrift: number[];
}

export interface AutomaticAlignment {
  offsets: FrameOffset[];
  alignedStates: number;
}

const FRAME_TOTAL = CHARACTER_FRAME_COUNT * CHARACTER_STATES.length;

export function emptyFrameOffsets(): FrameOffset[] {
  return Array.from({ length: FRAME_TOTAL }, () => ({ x: 0, y: 0 }));
}

function median(values: number[]): number {
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? (ordered[middle] ?? 0)
    : ((ordered[middle - 1] ?? 0) + (ordered[middle] ?? 0)) / 2;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

export function canShiftFrame(
  bounds: FrameBounds,
  offset: FrameOffset,
): boolean {
  return (
    Number.isInteger(offset.x) &&
    Number.isInteger(offset.y) &&
    bounds.left + offset.x >= 0 &&
    bounds.right + offset.x <= CHARACTER_FRAME_SIZE &&
    bounds.top + offset.y >= 0 &&
    bounds.bottom + offset.y <= CHARACTER_FRAME_SIZE
  );
}

export function parseFramePixelOffset(
  draft: { x: string; y: string },
  bounds: FrameBounds,
): FrameOffset | null {
  if (!/^-?\d+$/.test(draft.x) || !/^-?\d+$/.test(draft.y)) return null;
  const offset = { x: Number(draft.x), y: Number(draft.y) };
  return canShiftFrame(bounds, offset) ? offset : null;
}

/** Geometry-only suggestions: no species, filenames, poses, or body-part assumptions. */
export function analyzeFrameAlignment(
  rgba: Uint8ClampedArray,
  width: number,
  height: number,
): FrameAlignmentAnalysis {
  if (
    width !== CHARACTER_SHEET_WIDTH ||
    height !== CHARACTER_SHEET_HEIGHT ||
    rgba.length !== width * height * 4
  ) {
    throw new Error("Unexpected character sheet dimensions");
  }

  const bounds: FrameBounds[] = [];
  const anchors: number[] = [];
  for (let row = 0; row < CHARACTER_STATES.length; row += 1) {
    for (let frame = 0; frame < CHARACTER_FRAME_COUNT; frame += 1) {
      const histogram = new Array<number>(CHARACTER_FRAME_SIZE).fill(0);
      let left = CHARACTER_FRAME_SIZE;
      let top = CHARACTER_FRAME_SIZE;
      let right = 0;
      let bottom = 0;
      let opaqueCount = 0;
      for (let y = 0; y < CHARACTER_FRAME_SIZE; y += 1) {
        for (let x = 0; x < CHARACTER_FRAME_SIZE; x += 1) {
          const alphaIndex =
            ((row * CHARACTER_FRAME_SIZE + y) * width +
              frame * CHARACTER_FRAME_SIZE +
              x) *
              4 +
            3;
          if ((rgba[alphaIndex] ?? 0) === 0) continue;
          histogram[x] = (histogram[x] ?? 0) + 1;
          opaqueCount += 1;
          left = Math.min(left, x);
          top = Math.min(top, y);
          right = Math.max(right, x + 1);
          bottom = Math.max(bottom, y + 1);
        }
      }
      if (!opaqueCount) throw new Error("Empty character frame");
      const midpoint = Math.floor((opaqueCount - 1) / 2);
      const nextMidpoint = Math.floor(opaqueCount / 2);
      let count = 0;
      let first = 0;
      let second = 0;
      for (let x = 0; x < CHARACTER_FRAME_SIZE; x += 1) {
        count += histogram[x] ?? 0;
        if (count > midpoint && first === 0) first = x + 1;
        if (count > nextMidpoint) {
          second = x;
          break;
        }
      }
      anchors.push(((first ? first - 1 : 0) + second) / 2);
      bounds.push({ left, top, right, bottom });
    }
  }

  const suggestedOffsets = emptyFrameOffsets();
  const horizontalDrift: number[] = [];
  for (let row = 0; row < CHARACTER_STATES.length; row += 1) {
    const start = row * CHARACTER_FRAME_COUNT;
    const rowAnchors = anchors.slice(start, start + CHARACTER_FRAME_COUNT);
    const rowBounds = bounds.slice(start, start + CHARACTER_FRAME_COUNT);
    horizontalDrift.push(Math.max(...rowAnchors) - Math.min(...rowAnchors));
    const safeTargetMin = Math.max(
      ...rowAnchors.map(
        (anchor, index) => anchor - (rowBounds[index]?.left ?? 0),
      ),
    );
    const safeTargetMax = Math.min(
      ...rowAnchors.map(
        (anchor, index) =>
          anchor + CHARACTER_FRAME_SIZE - (rowBounds[index]?.right ?? 0),
      ),
    );
    const desiredTarget = median(rowAnchors);
    const target =
      safeTargetMin <= safeTargetMax
        ? clamp(desiredTarget, safeTargetMin, safeTargetMax)
        : desiredTarget;
    rowAnchors.forEach((anchor, frame) => {
      const frameBounds = rowBounds[frame];
      if (!frameBounds) return;
      const shift = clamp(
        Math.round(target - anchor),
        -frameBounds.left,
        CHARACTER_FRAME_SIZE - frameBounds.right,
      );
      suggestedOffsets[start + frame] = {
        x: shift === 0 ? 0 : shift,
        y: 0,
      };
    });
  }

  return { bounds, anchors, suggestedOffsets, horizontalDrift };
}

/**
 * A repeated column displacement across independent states is evidence of a
 * sheet-layout problem. A single moving pose is not: leave it for review.
 */
export function automaticFrameAlignment(
  analysis: FrameAlignmentAnalysis,
): AutomaticAlignment {
  const offsets = emptyFrameOffsets();
  const patterns: Array<{ row: number; deltas: number[] }> = [];
  const maximumShift = Math.floor(CHARACTER_FRAME_SIZE / 4);
  const agreementTolerance = Math.max(2, Math.round(CHARACTER_FRAME_SIZE / 16));
  const minimumAgreement = Math.ceil(CHARACTER_STATES.length / 2);

  for (let row = 0; row < CHARACTER_STATES.length; row += 1) {
    const start = row * CHARACTER_FRAME_COUNT;
    const anchors = analysis.anchors.slice(
      start,
      start + CHARACTER_FRAME_COUNT,
    );
    const suggestions = analysis.suggestedOffsets.slice(
      start,
      start + CHARACTER_FRAME_COUNT,
    );
    const bounds = analysis.bounds.slice(start, start + CHARACTER_FRAME_COUNT);
    if (
      anchors.length !== CHARACTER_FRAME_COUNT ||
      suggestions.length !== CHARACTER_FRAME_COUNT ||
      bounds.length !== CHARACTER_FRAME_COUNT ||
      (analysis.horizontalDrift[row] ?? 0) < 2 ||
      suggestions.some(
        (offset, frame) =>
          Math.abs(offset.x) > maximumShift ||
          !canShiftFrame(bounds[frame]!, offset),
      )
    ) {
      continue;
    }
    const alignedAnchors = anchors.map(
      (anchor, frame) => anchor + suggestions[frame]!.x,
    );
    if (Math.max(...alignedAnchors) - Math.min(...alignedAnchors) > 1) {
      continue;
    }
    patterns.push({
      row,
      deltas: anchors.map((anchor) => anchor - anchors[0]!),
    });
  }

  const agrees = (left: number[], right: number[]) =>
    left.every(
      (delta, frame) =>
        Math.abs(delta - (right[frame] ?? Number.POSITIVE_INFINITY)) <=
        agreementTolerance,
    );
  const groups = patterns.map((candidate) =>
    patterns.filter((pattern) => agrees(candidate.deltas, pattern.deltas)),
  );
  const largest = Math.max(0, ...groups.map((group) => group.length));
  if (largest < minimumAgreement) return { offsets, alignedStates: 0 };
  const winners = groups.filter((group) => group.length === largest);
  const signatures = new Set(
    winners.map((group) => group.map((pattern) => pattern.row).join(",")),
  );
  if (signatures.size !== 1) return { offsets, alignedStates: 0 };

  const selected = winners[0]!;
  for (const { row } of selected) {
    const start = row * CHARACTER_FRAME_COUNT;
    for (let frame = 0; frame < CHARACTER_FRAME_COUNT; frame += 1) {
      offsets[start + frame] = analysis.suggestedOffsets[start + frame]!;
    }
  }
  return { offsets, alignedStates: selected.length };
}

async function decodePng(pngBase64: string): Promise<ImageBitmap> {
  const bytes = Uint8Array.from(window.atob(pngBase64), (character) =>
    character.charCodeAt(0),
  );
  const bitmap = await createImageBitmap(
    new Blob([bytes], { type: "image/png" }),
  );
  if (
    bitmap.width !== CHARACTER_SHEET_WIDTH ||
    bitmap.height !== CHARACTER_SHEET_HEIGHT
  ) {
    bitmap.close();
    throw new Error("Unexpected character sheet dimensions");
  }
  return bitmap;
}

function spriteCanvas(bitmap: ImageBitmap): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = CHARACTER_SHEET_WIDTH;
  canvas.height = CHARACTER_SHEET_HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas unavailable");
  context.imageSmoothingEnabled = false;
  context.drawImage(bitmap, 0, 0);
  return canvas;
}

export async function inspectFrameAlignment(
  pngBase64: string,
): Promise<FrameAlignmentAnalysis> {
  const bitmap = await decodePng(pngBase64);
  try {
    const context = spriteCanvas(bitmap).getContext("2d");
    if (!context) throw new Error("Canvas unavailable");
    return analyzeFrameAlignment(
      context.getImageData(0, 0, CHARACTER_SHEET_WIDTH, CHARACTER_SHEET_HEIGHT)
        .data,
      CHARACTER_SHEET_WIDTH,
      CHARACTER_SHEET_HEIGHT,
    );
  } finally {
    bitmap.close();
  }
}

export function drawAlignedFrame(
  context: CanvasRenderingContext2D,
  bitmap: ImageBitmap,
  row: number,
  frame: number,
  offset: FrameOffset,
  destinationX: number,
  destinationY: number,
): void {
  const sourceX = frame * CHARACTER_FRAME_SIZE;
  const sourceY = row * CHARACTER_FRAME_SIZE;
  context.save();
  context.beginPath();
  context.rect(
    destinationX,
    destinationY,
    CHARACTER_FRAME_SIZE,
    CHARACTER_FRAME_SIZE,
  );
  context.clip();
  context.drawImage(
    bitmap,
    sourceX,
    sourceY,
    CHARACTER_FRAME_SIZE,
    CHARACTER_FRAME_SIZE,
    destinationX + offset.x,
    destinationY + offset.y,
    CHARACTER_FRAME_SIZE,
    CHARACTER_FRAME_SIZE,
  );
  context.restore();
}

export async function composeAlignedPng(
  pngBase64: string,
  offsets: FrameOffset[],
): Promise<Blob> {
  if (offsets.length !== FRAME_TOTAL) throw new Error("Invalid frame offsets");
  const bitmap = await decodePng(pngBase64);
  try {
    const source = spriteCanvas(bitmap);
    const sourceContext = source.getContext("2d");
    if (!sourceContext) throw new Error("Canvas unavailable");
    const analysis = analyzeFrameAlignment(
      sourceContext.getImageData(0, 0, source.width, source.height).data,
      source.width,
      source.height,
    );
    if (
      offsets.some(
        (offset, index) => !canShiftFrame(analysis.bounds[index]!, offset),
      )
    ) {
      throw new Error("Frame offset would clip content");
    }
    const output = document.createElement("canvas");
    output.width = CHARACTER_SHEET_WIDTH;
    output.height = CHARACTER_SHEET_HEIGHT;
    const context = output.getContext("2d");
    if (!context) throw new Error("Canvas unavailable");
    context.imageSmoothingEnabled = false;
    for (let row = 0; row < CHARACTER_STATES.length; row += 1) {
      for (let frame = 0; frame < CHARACTER_FRAME_COUNT; frame += 1) {
        drawAlignedFrame(
          context,
          bitmap,
          row,
          frame,
          offsets[row * CHARACTER_FRAME_COUNT + frame]!,
          frame * CHARACTER_FRAME_SIZE,
          row * CHARACTER_FRAME_SIZE,
        );
      }
    }
    return await new Promise<Blob>((resolve, reject) => {
      output.toBlob(
        (blob) =>
          blob ? resolve(blob) : reject(new Error("PNG export failed")),
        "image/png",
      );
    });
  } finally {
    bitmap.close();
  }
}
