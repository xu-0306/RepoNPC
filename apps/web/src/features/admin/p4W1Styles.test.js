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

it("shows an opened project as a pressed outline with one contained body", () => {
  const css = readFileSync(new URL("../../p4-w1.css", import.meta.url), "utf8");
  // The shared .px-info[open] fill turns the icon cell into a solid block.
  expect(css).toMatch(
    /\.p4-w1-repositories \.p4-w1-repository__details\[open\] > summary\s*\{[^}]*background: var\(--px-surface-alt\);[^}]*border: 2px solid var\(--px-line\)/s,
  );
  expect(css).toMatch(
    /\.p4-w1-repository__details > summary\s*\{[^}]*align-self: start;[^}]*justify-content: center/s,
  );
  expect(css).toMatch(
    /\.p4-w1-repository__details::details-content\s*\{[^}]*grid-column: 1 \/ -1/s,
  );
  expect(css).toMatch(
    /\.p4-w1-repository__id\s*\{[^}]*display: flex;[^}]*flex-wrap: wrap/s,
  );
});

it("pins only step-level actions in equal cells and keeps each project's action on its row", () => {
  const bar = readFileSync(new URL("../../p4-w1.css", import.meta.url), "utf8");
  expect(bar).toMatch(
    /\.guided-analysis > \.guided-analysis__actions\s*\{[^}]*display: grid;[^}]*repeat\(auto-fill, minmax\(min\(100%, 17rem\), 1fr\)\)/s,
  );
  expect(bar).toMatch(
    /\.guided-analysis__actions > p\s*\{\s*grid-column: 1 \/ -1/,
  );
  const rows = readFileSync(
    new URL("guidedAnalysis.css", import.meta.url),
    "utf8",
  );
  expect(rows).toMatch(
    /\.guided-analysis__repository-row\s*\{[^}]*justify-content: space-between/s,
  );
  expect(rows).toMatch(
    /\.guided-analysis__repository-row > \.px-button\s*\{[^}]*min-width: 8rem/s,
  );
  expect(rows).not.toContain("guided-analysis__retry");
});
