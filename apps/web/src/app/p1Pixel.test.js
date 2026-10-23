import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../pixel.css", import.meta.url), "utf8");

describe("P1 pixel CSS contract", () => {
  it("self-hosts exactly one unmodified Latin font with swap and the closed unicode range", () => {
    expect(css.match(/@font-face\s*\{/g)).toHaveLength(1);
    expect(css).toContain(
      'url("./assets/fonts/press-start-2p-latin-400-normal.woff2")',
    );
    expect(css).toMatch(/font-display:\s*swap/);
    expect(css).toMatch(/font-weight:\s*400/);
    expect(
      css.match(/unicode-range:\s*([^;]+);/)?.[1].replace(/\s+/g, ""),
    ).toBe(
      "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
    );
    const font = readFileSync(
      new URL(
        "../assets/fonts/press-start-2p-latin-400-normal.woff2",
        import.meta.url,
      ),
    );
    expect(font.length).toBe(12512);
    expect(createHash("sha256").update(font).digest("hex")).toBe(
      "afec86997fdaf54af1f59358fa2c1e2a0f1d04146edad18e5cd141d0384a7548",
    );
  });

  it("keeps every colour tokenized, every class prefixed and all pixel sizes readable", () => {
    expect(css).not.toMatch(
      /#[\da-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\s*\(/i,
    );
    const declarations = [
      ...css.matchAll(
        /(?:^|[;{}])\s*(?:color|background(?:-color)?|border(?:-color)?|outline(?:-color)?|box-shadow|text-shadow|fill|stroke)\s*:\s*([^;{}]+)/g,
      ),
    ];
    expect(declarations.length).toBeGreaterThan(20);
    for (const [, value] of declarations) {
      expect(/var\(/.test(value) || /^(?:none|0)$/.test(value.trim())).toBe(
        true,
      );
    }
    const sizes = [...css.matchAll(/font-size:\s*(\d+(?:\.\d+)?)px/g)].map(
      (match) => Number(match[1]),
    );
    expect(sizes.length).toBeGreaterThan(0);
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(13);
    const classes = [...css.matchAll(/\.([a-z][\w-]*)/g)].map(
      (match) => match[1],
    );
    expect(
      classes.filter((name) => !name.startsWith("px-") && name !== "woff2"),
    ).toEqual([]);
    const registry = readFileSync(
      new URL(
        "../../../../src/reponpc/scene/color_schemes.yml",
        import.meta.url,
      ),
      "utf8",
    );
    for (const [, id] of registry.matchAll(/^\s*- id:\s*([a-z0-9_]+)\s*$/gm)) {
      expect(css).not.toContain(id);
    }
  });

  it("provides the primitives, keyboard and pressed states, reduced motion and a token-only scene", () => {
    for (const name of [
      "panel",
      "panel--raised",
      "panel--inset",
      "button",
      "button--primary",
      "button--secondary",
      "button--quiet",
      "button--danger",
      "field",
      "chip",
      "tab",
      "dialog",
      "progress",
      "badge",
      "scene",
      "display",
    ]) {
      expect(css).toContain(`.px-${name}`);
    }
    expect(css).toContain('content: "▼" / ""');
    expect(css).toContain('data-npc-plate="true"');
    expect(css).toContain("var(--px-progress, 0%)");
    expect(css).toMatch(/outline:\s*3px solid var\(--px-focus\)/);
    expect(css).toContain("transform: translate(2px, 2px)");
    expect(css).toContain('[aria-disabled="true"]');
    expect(css).toContain('[aria-pressed="true"]');
    expect(css).toContain("prefers-reduced-motion: no-preference");
    expect(css).toContain("prefers-reduced-motion: reduce");
    expect(css.slice(css.indexOf(".px-scene {"))).not.toMatch(/url\(/);
    for (const role of [
      "sky",
      "horizon",
      "hill-far",
      "hill-near",
      "grass",
      "ground",
      "wood",
      "celestial",
    ]) {
      expect(css).toContain(`var(--px-${role})`);
    }
    for (const bundle of ["visitor.css", "styles.css"]) {
      expect(
        readFileSync(new URL(`../${bundle}`, import.meta.url), "utf8"),
      ).toContain('@import "./pixel.css"');
    }
  });
});
