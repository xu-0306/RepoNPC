import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  CHARACTER_STATES,
  CharacterRenderer,
  getCharacterStateRow,
  normalizeCharacterFrame,
  normalizeCharacterMovement,
  normalizeFrameDurationMs,
} from "./CharacterRenderer";

describe("CharacterRenderer", () => {
  it("keeps the canonical seven state rows in sheet order", () => {
    expect(CHARACTER_STATES).toEqual([
      "idle",
      "walk",
      "listen",
      "think",
      "talk",
      "success",
      "offline",
    ]);
    expect(getCharacterStateRow("idle")).toBe(0);
    expect(getCharacterStateRow("talk")).toBe(4);
    expect(getCharacterStateRow("offline")).toBe(6);
  });

  it("normalizes runtime frame and duration inputs deterministically", () => {
    expect(normalizeCharacterFrame()).toBe(0);
    expect(normalizeCharacterFrame(-4)).toBe(0);
    expect(normalizeCharacterFrame(1.9)).toBe(1);
    expect(normalizeCharacterFrame(99)).toBe(3);
    expect(normalizeCharacterFrame(Number.NaN)).toBe(0);

    expect(normalizeFrameDurationMs()).toBe(160);
    expect(normalizeFrameDurationMs(79)).toBe(80);
    expect(normalizeFrameDurationMs(160.4)).toBe(160);
    expect(normalizeFrameDurationMs(1001)).toBe(1000);
    expect(normalizeFrameDurationMs(Number.POSITIVE_INFINITY)).toBe(160);
    expect(normalizeCharacterMovement()).toBe("subtle");
    expect(normalizeCharacterMovement("none")).toBe("none");
    expect(normalizeCharacterMovement("unexpected")).toBe("subtle");
  });

  it("renders an accessible label and hides the decorative sheet crop", () => {
    const markup = renderToStaticMarkup(
      <CharacterRenderer
        assetUrl="/assets/character.png"
        className="character-renderer--visitor"
        frame={2}
        frameDurationMs={120}
        reducedMotion={false}
        state="think"
        stateLabel="Thinking"
      />,
    );

    expect(markup).toContain('aria-label="Thinking"');
    expect(markup).toContain('role="img"');
    expect(markup).toContain('data-character-state="think"');
    expect(markup).toContain('data-character-movement="none"');
    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain(
      'class="character-renderer character-renderer--visitor"',
    );
    expect(markup).toMatch(/--character-frame-start-x:-64px/);
    expect(markup).toMatch(/--character-frame-end-x:-192px/);
    expect(markup).toMatch(/--character-row-offset-y:-96px/);
    expect(markup).toMatch(/--character-animation-duration:480ms/);
    expect(markup.match(/<img/g)).toHaveLength(2);
  });

  it("pins reduced motion to the stable first frame", () => {
    const markup = renderToStaticMarkup(
      <CharacterRenderer
        assetUrl="/assets/character.png"
        frame={3}
        frameDurationMs={20}
        reducedMotion
        state="offline"
        stateLabel="Offline"
      />,
    );

    expect(markup).toContain('data-reduced-motion="true"');
    expect(markup).toMatch(/--character-frame-start-x:0px/);
    expect(markup).toMatch(/--character-frame-end-x:-128px/);
    expect(markup).toMatch(/--character-row-offset-y:-192px/);
    expect(markup).toMatch(/--character-animation-duration:320ms/);
  });

  it("marks the walk state for bounded decorative movement", () => {
    const markup = renderToStaticMarkup(
      <CharacterRenderer
        assetUrl="/assets/character.png"
        reducedMotion={false}
        state="walk"
        stateLabel="Walking"
      />,
    );
    expect(markup).toContain('data-character-movement="subtle"');
  });

  it("honors a configured movement mode for walk", () => {
    const markup = renderToStaticMarkup(
      <CharacterRenderer
        assetUrl="/assets/character.png"
        movement="none"
        reducedMotion={false}
        state="walk"
        stateLabel="Walking"
      />,
    );
    expect(markup).toContain('data-character-movement="none"');
  });
});
