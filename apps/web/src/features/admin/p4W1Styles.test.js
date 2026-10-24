import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

it("keeps w1 styles token-only with square corners and no nested scrolling", () => {
  for (const file of ["../../p4-w1.css", "guidedAnalysis.css"]) {
    const css = readFileSync(new URL(file, import.meta.url), "utf8");
    expect(css).not.toMatch(
      /#[\da-f]{3,8}\b|\b(?:rgb|hsl)a?\s*\(|!important|var\(--admin-/i,
    );
    expect(css).not.toMatch(/overflow(?:-y)?:\s*(?:auto|scroll)/);
    expect(css).not.toMatch(/border-radius:\s*(?!0)[1-9]/);
  }
});
