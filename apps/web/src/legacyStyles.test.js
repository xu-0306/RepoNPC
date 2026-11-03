import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const SRC = fileURLToPath(new URL(".", import.meta.url));
const ADMIN_CSS = [
  "styles.css",
  "p4-w1.css",
  "p4-w2.css",
  "p4-w3.css",
  "p4-w4.css",
  "features/admin/scene.css",
  "features/admin/guidedAnalysis.css",
];
const walk = (directory) =>
  readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });

function legacyTokens(source) {
  return [...source.matchAll(/--(?:ui|admin)-[a-z0-9-]+/g)]
    .map(([token]) => token)
    .filter((token) => token !== "--admin-progress");
}

function styleIssues(source) {
  const css = source.replace(/\/\*[\s\S]*?\*\//g, " ");
  const issues = legacyTokens(css).map((token) => `legacy token: ${token}`);
  const colorSyntax = new Set(
    "transparent currentcolor none inherit initial unset revert revert-layer solid dashed dotted double inset outset groove ridge hidden to top right bottom left linear-gradient repeating-linear-gradient color-mix in srgb".split(
      " ",
    ),
  );
  for (const [, property, raw] of css.matchAll(
    /(?:^|[;{])\s*([\w-]+)\s*:\s*([^;{}]*)(?=[;}])/g,
  )) {
    const value = raw.trim();
    if (/^border(?:-[a-z]+){0,2}-radius$/.test(property)) {
      const zero = value
        .split(/[\s/]+/)
        .every((part) => /^0(?:px|rem|em|%)?$/.test(part));
      if (!zero && !/^(inherit|initial|unset)$/.test(value))
        issues.push(`radius: ${value}`);
    }
    if (property === "box-shadow") {
      for (const layer of value.split(/,(?![^(]*\))/)) {
        const lengths = layer
          .replace(/var\([^)]*\)|rgba?\([^)]*\)|#[\da-f]+/gi, "")
          .match(/-?\d*\.?\d+(?:px|rem|em)?/g);
        if (lengths?.length >= 3 && parseFloat(lengths[2]) !== 0)
          issues.push(`soft shadow: ${layer.trim()}`);
      }
    }
    if (/(?:repeating-)?(?:radial|conic)-gradient\s*\(/.test(value))
      issues.push(`gradient: ${value}`);
    for (const [, repeating, body] of value.matchAll(
      /\b(repeating-)?linear-gradient\(((?:[^()]|\([^()]*\))*)\)/g,
    )) {
      const grid = /^(?:90deg,\s*)?var\(--px-grid\) 1px,\s*transparent 1px$/;
      const stops = body
        .split(/,(?![^(]*\))/)
        .map((stop) => stop.trim())
        .filter((stop) => !/^(?:to |\d+deg$)/.test(stop));
      const stripe =
        stops.length >= 2 &&
        stops.every((stop) =>
          /^var\(--px-[a-z0-9-]+\)(?:\s+(?:0|\d*\.?\d+(?:px|rem|%))){1,2}$/.test(
            stop,
          ),
        );
      if (repeating ? !stripe : !grid.test(body.trim()))
        issues.push(`gradient: ${body}`);
    }
    if (property.startsWith("--px-")) continue;
    let literal =
      /#[\da-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\s*\(/i.test(
        value,
      );
    if (
      /^(?:color|background(?:-color|-image)?|(?:border(?:-(?:top|right|bottom|left))?|outline)(?:-color)?|box-shadow|text-shadow|fill|stroke|accent-color|caret-color|text-decoration-color)$/.test(
        property,
      )
    ) {
      const syntax = value
        .replace(/var\([^)]*\)|url\([^)]*\)/g, "")
        .match(/(?<![\w-])[a-z][a-z-]*(?![\w-])/gi);
      literal ||= syntax?.some((word) => !colorSyntax.has(word.toLowerCase()));
    }
    if (literal) issues.push(`colour literal: ${property}: ${value}`);
  }
  return issues;
}

it("removes legacy tokens from every non-test source, retaining the progress data variable", () => {
  for (const path of walk(SRC)) {
    if (!/\.(?:css|ts|tsx|js|mjs)$/.test(path) || /\.test\./.test(path))
      continue;
    expect(legacyTokens(readFileSync(path, "utf8")), path).toEqual([]);
  }
});

it.each(ADMIN_CSS)("keeps %s square, hard-shadowed and token-only", (file) => {
  expect(styleIssues(readFileSync(join(SRC, file), "utf8"))).toEqual([]);
});

it.each([
  ["border-radius: 0.5rem", "radius"],
  ["border-top-left-radius: 2px", "radius"],
  ["box-shadow: 0 4px 16px var(--px-shadow)", "soft shadow"],
  ["box-shadow: inset -2px 4px 0.5em var(--px-shadow)", "soft shadow"],
  ["color: #fff", "colour literal"],
  ["background: rgb(255, 255, 255)", "colour literal"],
  ["border: 2px solid rebeccapurple", "colour literal"],
  ["background: radial-gradient(circle, red, blue)", "gradient"],
  ["background: repeating-conic-gradient(red 0deg, blue 90deg)", "gradient"],
  [
    "background: linear-gradient(135deg, var(--px-surface), var(--px-surface-alt))",
    "gradient",
  ],
  [
    "background: repeating-linear-gradient(90deg, var(--px-surface), var(--px-surface-alt))",
    "gradient",
  ],
  ["color: var(--ui-primary)", "legacy token"],
  ["color: var(--admin-progress-colour)", "legacy token"],
])("detects a legacy mutation: %s", (declaration, issue) => {
  expect(styleIssues(`.sample { ${declaration}; }`)).toEqual(
    expect.arrayContaining([expect.stringContaining(issue)]),
  );
});

it("accepts pixel tokens, hard shadows, hard grid/stripe stops and the progress data variable", () => {
  expect(
    styleIssues(`
      :root { --px-surface: #fff9ed; }
      .sample {
        --admin-progress: 50%;
        border: 2px solid var(--px-line);
        border-radius: 0;
        color: var(--px-ink);
        box-shadow: inset 3px 3px 0 var(--px-surface-alt), -4px 4px 0 var(--px-shadow);
        background: color-mix(in srgb, var(--px-ink) 55%, transparent);
        background-image: linear-gradient(var(--px-grid) 1px, transparent 1px),
          linear-gradient(90deg, var(--px-grid) 1px, transparent 1px),
          repeating-linear-gradient(90deg, var(--px-accent) 0 1.5rem, var(--px-ink) 1.5rem 3rem);
      }
    `),
  ).toEqual([]);
  expect(legacyTokens('style={{ "--admin-progress": progress }}')).toEqual([]);
});
