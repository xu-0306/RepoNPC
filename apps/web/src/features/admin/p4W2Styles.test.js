import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

it("uses only pixel tokens and keeps form content on the page around pinned actions", () => {
  const css = readFileSync(new URL("../../p4-w2.css", import.meta.url), "utf8");
  expect(css).not.toMatch(
    /#[\da-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\s*\(|!important/i,
  );
  expect(css).not.toMatch(/var\(--(?!px-)/);
  expect(css).toMatch(
    /\.p4-w2 \.p4-w2__confirm\s*\{[^}]*bottom: 0;[^}]*position: sticky/s,
  );
  const bounded = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((rule) =>
    /overflow-y:\s*(auto|scroll)|max-height:/.test(rule[2]),
  );
  expect(bounded.map((rule) => rule[1].trim())).toEqual([".p7-draft-yaml"]);
  expect(bounded[0][2]).toMatch(/max-height:\s*min\(32vh, 18rem\)/);
  expect(bounded[0][2]).toMatch(/min-height:\s*min\(8lh, 24vh\)/);
  expect(bounded[0][2]).toContain("overflow: auto");
  expect(bounded[0][2]).toContain("white-space: pre");
  expect(css).toMatch(
    /\.p4-w2--draft \.p4-w2__tools > \.px-info > summary\s*\{[^}]*min-width: 44px;/s,
  );
  expect(css).toContain("repeat(2, minmax(0, 1fr))");
  expect(css).toContain("grid-template-columns: minmax(0, 1fr)");
  expect(css).toMatch(
    /\.p4-w2--contributions textarea,[^{]*\.p4-w2-claim textarea\s*\{\s*resize: vertical/s,
  );
  expect(css).toMatch(/evidence--proposed-assertions\s*\{[^}]*padding: 0;/s);
  const shared = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  expect(shared).toMatch(
    /#guided-onboarding-heading\s*\{[^}]*border: 0;[^}]*border-radius: 0;[^}]*outline: none;/s,
  );
  expect(shared).toMatch(
    /#guided-onboarding-heading:focus-visible\[data-keyboard-focus="true"\]\s*\{\s*outline: 3px solid var\(--px-focus\);\s*outline-offset: 2px;/s,
  );
  const w1 = readFileSync(new URL("../../p4-w1.css", import.meta.url), "utf8");
  expect(w1).not.toContain("guided-onboarding__header");
});
