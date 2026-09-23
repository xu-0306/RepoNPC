import { useEffect, useRef, useState } from "react";

import {
  CHARACTER_FRAME_COUNT,
  CHARACTER_FRAME_SIZE,
  CHARACTER_SHEET_HEIGHT,
  CHARACTER_SHEET_WIDTH,
  DEFAULT_CHARACTER_FRAME_DURATION_MS,
  getCharacterStateRow,
  type CharacterState,
} from "../character/CharacterRenderer";
import { drawAlignedFrame, type FrameOffset } from "./characterFrameAlignment";

interface Base64PngCanvasProps {
  pngBase64: string;
  width: number;
  height: number;
  label: string;
  failureText: string;
  className?: string;
  state?: CharacterState;
  frame?: number | null;
  frameOffsets?: FrameOffset[];
}

/** Draws API-provided PNG bytes without a data/blob image URL, preserving img-src 'self'. */
export function Base64PngCanvas({
  pngBase64,
  width,
  height,
  label,
  failureText,
  className,
  state,
  frame,
  frameOffsets,
}: Base64PngCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const failed = failedSource === pngBase64;

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    let cancelled = false;
    let bitmap: ImageBitmap | null = null;
    let timer: number | undefined;
    let activeFrame = frame ?? 0;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");

    const draw = () => {
      if (!bitmap) return;
      context.imageSmoothingEnabled = false;
      context.clearRect(0, 0, width, height);
      if (state) {
        const row = getCharacterStateRow(state);
        drawAlignedFrame(
          context,
          bitmap,
          row,
          activeFrame,
          frameOffsets?.[row * CHARACTER_FRAME_COUNT + activeFrame] ?? {
            x: 0,
            y: 0,
          },
          0,
          0,
        );
      } else if (frameOffsets) {
        for (
          let row = 0;
          row < CHARACTER_SHEET_HEIGHT / CHARACTER_FRAME_SIZE;
          row += 1
        ) {
          for (let column = 0; column < CHARACTER_FRAME_COUNT; column += 1) {
            drawAlignedFrame(
              context,
              bitmap,
              row,
              column,
              frameOffsets[row * CHARACTER_FRAME_COUNT + column] ?? {
                x: 0,
                y: 0,
              },
              column * CHARACTER_FRAME_SIZE,
              row * CHARACTER_FRAME_SIZE,
            );
          }
        }
      } else {
        context.drawImage(bitmap, 0, 0);
      }
    };

    const updateMotion = () => {
      if (timer !== undefined) window.clearInterval(timer);
      activeFrame = frame ?? 0;
      draw();
      if (state && frame == null && !motion.matches) {
        timer = window.setInterval(() => {
          activeFrame = (activeFrame + 1) % CHARACTER_FRAME_COUNT;
          draw();
        }, DEFAULT_CHARACTER_FRAME_DURATION_MS);
      }
    };

    motion.addEventListener("change", updateMotion);
    const decode = async () => {
      const bytes = Uint8Array.from(window.atob(pngBase64), (character) =>
        character.charCodeAt(0),
      );
      const decoded = await createImageBitmap(
        new Blob([bytes], { type: "image/png" }),
      );
      if (cancelled) {
        decoded.close();
        return;
      }
      if (
        decoded.width !== (state ? CHARACTER_SHEET_WIDTH : width) ||
        decoded.height !== (state ? CHARACTER_SHEET_HEIGHT : height)
      ) {
        decoded.close();
        throw new Error("Unexpected PNG dimensions");
      }
      bitmap = decoded;
      updateMotion();
    };
    void decode().catch(() => {
      if (!cancelled) setFailedSource(pngBase64);
    });

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
      motion.removeEventListener("change", updateMotion);
      bitmap?.close();
    };
  }, [pngBase64, width, height, state, frame, frameOffsets]);

  return (
    <>
      <canvas
        aria-label={label}
        className={className}
        data-character-state={state}
        height={height}
        hidden={failed}
        ref={canvasRef}
        role="img"
        width={width}
      />
      {failed && <p role="alert">{failureText}</p>}
    </>
  );
}
