import type { CSSProperties } from "react";

import "./CharacterRenderer.css";

export const CHARACTER_STATES = [
  "idle",
  "walk",
  "listen",
  "think",
  "talk",
  "success",
  "offline",
] as const;

export type CharacterState = (typeof CHARACTER_STATES)[number];

export const CHARACTER_FRAME_SIZE = 32;
export const CHARACTER_FRAME_COUNT = 4;
export const DEFAULT_CHARACTER_FRAME_DURATION_MS = 160;
export const MIN_CHARACTER_FRAME_DURATION_MS = 80;
export const MAX_CHARACTER_FRAME_DURATION_MS = 1000;

const CHARACTER_STATE_ROWS: Record<CharacterState, number> = {
  idle: 0,
  walk: 1,
  listen: 2,
  think: 3,
  talk: 4,
  success: 5,
  offline: 6,
};

export interface CharacterRendererProps {
  assetUrl: string;
  state: CharacterState;
  stateLabel: string;
  reducedMotion: boolean;
  frame?: number;
  frameDurationMs?: number;
  className?: string;
}

/** Returns a valid sheet column for any runtime frame value. */
export function normalizeCharacterFrame(frame?: number): number {
  if (typeof frame !== "number" || !Number.isFinite(frame)) {
    return 0;
  }

  return Math.min(CHARACTER_FRAME_COUNT - 1, Math.max(0, Math.trunc(frame)));
}

/** Returns a configuration-bounded animation duration in whole milliseconds. */
export function normalizeFrameDurationMs(frameDurationMs?: number): number {
  if (
    typeof frameDurationMs !== "number" ||
    !Number.isFinite(frameDurationMs)
  ) {
    return DEFAULT_CHARACTER_FRAME_DURATION_MS;
  }

  return Math.min(
    MAX_CHARACTER_FRAME_DURATION_MS,
    Math.max(MIN_CHARACTER_FRAME_DURATION_MS, Math.round(frameDurationMs)),
  );
}

export function getCharacterStateRow(state: CharacterState): number {
  return CHARACTER_STATE_ROWS[state];
}

export function CharacterRenderer({
  assetUrl,
  state,
  stateLabel,
  reducedMotion,
  frame,
  frameDurationMs,
  className,
}: CharacterRendererProps) {
  const initialFrame = reducedMotion ? 0 : normalizeCharacterFrame(frame);
  const row = getCharacterStateRow(state);
  const frameDuration = normalizeFrameDurationMs(frameDurationMs);
  const rendererClassName = ["character-renderer", className]
    .filter(Boolean)
    .join(" ");
  const spriteStyle = {
    "--character-animation-duration": `${
      frameDuration * CHARACTER_FRAME_COUNT
    }ms`,
    "--character-frame-end-x": `${
      -(initialFrame + CHARACTER_FRAME_COUNT) * CHARACTER_FRAME_SIZE
    }px`,
    "--character-frame-start-x": `${-initialFrame * CHARACTER_FRAME_SIZE}px`,
    "--character-row-offset-y": `${-row * CHARACTER_FRAME_SIZE}px`,
  } as CSSProperties;

  return (
    <span
      aria-label={stateLabel}
      className={rendererClassName}
      data-character-state={state}
      data-reduced-motion={reducedMotion ? "true" : "false"}
      role="img"
    >
      <span aria-hidden="true" className="character-renderer__viewport">
        <span className="character-renderer__sheet" style={spriteStyle}>
          <img
            alt=""
            className="character-renderer__sheet-image"
            draggable={false}
            height={224}
            src={assetUrl}
            width={128}
          />
          <img
            alt=""
            className="character-renderer__sheet-image"
            draggable={false}
            height={224}
            src={assetUrl}
            width={128}
          />
        </span>
      </span>
    </span>
  );
}
