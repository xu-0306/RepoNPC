import { readFileSync } from "node:fs";
import ts from "typescript";
import { expect, it } from "vitest";

it.each([
  ["AdminWorkspace.tsx", "COPY"],
  ["OnboardingStepper.tsx", "COPY"],
  ["ModelSetupWorkspace.tsx", "COPY"],
  ["CharacterAssetConverter.tsx", "COPY"],
  ["AppearancePanel.tsx", "appearanceCopy"],
  ["AdminStatusCards.tsx", "ADMIN_MODEL_STATES"],
])("keeps every %s copy key equivalent in zh-TW and en", (file, name) => {
  const source = ts.createSourceFile(
    file,
    readFileSync(new URL(file, import.meta.url), "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  let copy;
  function visit(node) {
    if (
      ts.isVariableDeclaration(node) &&
      node.name.getText(source) === name &&
      node.initializer
    ) {
      const value = ts.isAsExpression(node.initializer)
        ? node.initializer.expression
        : node.initializer;
      if (ts.isObjectLiteralExpression(value)) copy = value;
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  expect(copy).toBeDefined();
  const locales = copy.properties.filter(ts.isPropertyAssignment);
  const locale = (id) =>
    locales.find(
      (property) => property.name.getText(source).replaceAll('"', "") === id,
    ).initializer;
  function keys(object) {
    return object.properties
      .filter(ts.isPropertyAssignment)
      .flatMap((property) => {
        const name = property.name.getText(source);
        return [
          name,
          ...(ts.isObjectLiteralExpression(property.initializer)
            ? keys(property.initializer).map((child) => `${name}.${child}`)
            : []),
        ];
      })
      .sort();
  }
  expect(keys(locale("zh-TW"))).toEqual(keys(locale("en")));
});

it("keeps the P3 rules token-only, light-only, responsive and free of retired selectors", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  const rules = css.slice(css.indexOf("/* Set F owner shell;"));
  expect(rules).not.toMatch(
    /#[\da-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color)a?\s*\(/i,
  );
  expect(rules).not.toMatch(/prefers-color-scheme|data-visitor-mode/);
  expect(rules).toContain("--px-night: 0");
  expect(rules).toContain(
    ".admin-workspace__layout:has(> .onboarding-stepper)",
  );
  expect(rules).toContain("max-width: 760px");
  expect(rules).toContain("min-width: 1024px");
  expect(rules.match(/position: sticky/g)).toHaveLength(2);
  for (const old of [
    ".admin-workspace__guide",
    ".admin-workspace__speech",
    ".admin-workspace__npc",
    ".admin-workspace__mode-switch",
    ".model-role-switch",
    ".character-converter__result",
    ".character-converter__steps",
  ])
    expect(css).not.toContain(old);
});

it("lets the equipment and converter content scroll with the page around sticky bottom actions", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  for (const selector of [
    "model-setup-workspace__slots",
    "model-setup-workspace__equipment",
    "character-converter__editor",
    "character-converter__workbench",
  ]) {
    const blocks = [
      ...css.matchAll(new RegExp(`\\.${selector}\\s*\\{([^}]+)\\}`, "g")),
    ];
    expect(blocks.length).toBeGreaterThan(0);
    for (const [, declarations] of blocks)
      expect(declarations).not.toMatch(
        /(?:overflow(?:-y)?\s*:\s*(?:auto|scroll)|(?:^|;)\s*(?:max-)?height\s*:)/,
      );
  }
  for (const selector of [
    "model-setup-workspace__confirm",
    "character-converter__confirm",
  ]) {
    const blocks = [
      ...css.matchAll(new RegExp(`\\.${selector}\\s*\\{([^}]+)\\}`, "g")),
    ];
    expect(blocks[0][1]).toContain("position: sticky");
    expect(blocks[0][1]).toContain("bottom: 0");
    for (const [, declarations] of blocks)
      expect(declarations).not.toMatch(/position\s*:\s*static/);
  }
  expect(css).toMatch(
    /\.model-setup-workspace__slots\s*\{[^}]*padding-bottom: 128px/s,
  );
  expect(css).toMatch(
    /:has\(> \.character-converter__confirm\)[^{]*\{[^}]*padding-bottom: var\(--character-confirm-height, 84px\)/s,
  );
  const converter = readFileSync(
    new URL("CharacterAssetConverter.tsx", import.meta.url),
    "utf8",
  );
  expect(converter).toContain("ref={reserveCharacterConfirmationSpace}");
  expect(converter).toContain('"--character-confirm-height"');
  expect(converter).toContain("new ResizeObserver(reserve)");
});

it("composes a compact phone header and two-row navigation without squeezing desktop chrome", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  const phone = css.slice(css.lastIndexOf("@media (max-width: 760px)"));
  expect(phone).toMatch(/\.admin-workspace__scene\s*\{\s*display: none/);
  expect(phone).toMatch(
    /\.admin-workspace__locale\s*\{[^}]*position: absolute/s,
  );
  expect(phone).toMatch(
    /\.admin-workspace__utilities\s*\{[^}]*flex-wrap: nowrap/s,
  );
  expect(phone).toMatch(
    /\.admin-workspace__modes\s*\{[^}]*repeat\(6, minmax\(0, 1fr\)\)/s,
  );
  expect(phone).toMatch(
    /\.admin-workspace__advanced-tab\s*\{\s*grid-column: span 4/s,
  );
  expect(phone).toMatch(
    /\.character-converter__confirm\s*\{[^}]*grid-template-columns: repeat\(2,/s,
  );
  expect(phone).toMatch(
    /\.model-setup-workspace__confirm \.model-selection\s*\{[^}]*grid-template-columns: minmax\(0, 1fr\) 96px/s,
  );
});

it("stacks full-width phone selections above the action and wraps confirmation feedback", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  const phone = css.slice(css.lastIndexOf("@media (max-width: 760px)"));
  const grid = phone.match(
    /\.model-setup-workspace__confirm \.model-selection\s*\{([^}]+)\}/s,
  )?.[1];
  expect(grid).toBeDefined();
  expect(grid).toContain("grid-template-columns: minmax(0, 1fr) 96px");
  expect(grid).not.toMatch(/repeat\(2,.*96px/s);
  expect(phone).toMatch(
    /\.model-setup-workspace__confirm \.model-selection label\s*\{[^}]*grid-column: 1 \/ -1/s,
  );
  expect(phone).toMatch(
    /\.model-setup-workspace__confirm \.model-selection label \+ label\s*\{[^}]*grid-row: 2/s,
  );
  expect(phone).toMatch(
    /\.model-setup-workspace__confirm \.model-selection button\s*\{[^}]*grid-column: 2;[^}]*grid-row: 3/s,
  );
  const confirmation = css.slice(
    css.indexOf(".model-setup-workspace__confirm {"),
    css.indexOf(".model-setup-workspace__guidance {"),
  );
  expect(confirmation).not.toMatch(
    /ellipsis|line-clamp|overflow:\s*hidden|white-space:\s*nowrap/,
  );
  expect(confirmation).toContain("overflow-wrap: anywhere");
});

it("keeps phone utility and progress names readable to assistive technology without wrapping chrome", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  const phone = css.slice(css.lastIndexOf("@media (max-width: 760px)"));
  expect(phone).toMatch(
    /\.admin-workspace__utilities > \*\s*\{[^}]*flex-shrink: 0;[^}]*white-space: nowrap/s,
  );
  expect(phone).toMatch(
    /\.admin-workspace__modes\s*\{[^}]*overflow-wrap: normal;[^}]*word-break: normal/s,
  );
  const labels = phone.match(
    /\.admin-workspace__utilities \.admin-workspace__utility-label,\s*\.onboarding-stepper__summary-full\s*\{([^}]+)\}/s,
  )?.[1];
  expect(labels).toBeDefined();
  for (const rule of [
    "clip-path: inset(50%)",
    "position: absolute",
    "white-space: nowrap",
    "width: 1px",
    "height: 1em",
  ])
    expect(labels).toContain(rule);
  expect(labels).not.toMatch(/display: none|visibility: hidden/);
  expect(phone).toMatch(/\.admin-workspace__help\s*\{[^}]*min-width: 44px/s);
  expect(css).toMatch(
    /\.onboarding-stepper__summary-compact\s*\{\s*display: none/s,
  );
  expect(phone).toMatch(
    /\.onboarding-stepper__summary-compact\s*\{\s*display: inline/s,
  );
  expect(css).toMatch(
    /\.onboarding-stepper__details > summary\s*\{[^}]*min-height: 44px/s,
  );
});

it("makes phone room above model equipment by tightening gaps and paragraph margins", () => {
  const css = readFileSync(
    new URL("../../styles.css", import.meta.url),
    "utf8",
  );
  const phone = css.slice(css.lastIndexOf("@media (max-width: 760px)"));
  expect(phone).toMatch(
    /\.admin-workspace__layout:has\(> \.onboarding-stepper\)\s*\{[^}]*gap: 12px;[^}]*padding: 12px 16px/s,
  );
  expect(phone).toMatch(
    /\.guided-onboarding\[data-step="models"\][^{]*,[^{]*\.guided-onboarding__header,[^{]*\.guided-onboarding__step--models\s*\{\s*gap: 8px/s,
  );
  expect(phone).toMatch(
    /\.guided-onboarding__step--models > p:first-of-type\s*\{\s*margin: 0/s,
  );
  for (const selector of ["button", "details\\s*>\\s*summary"]) {
    const block = phone.match(
      new RegExp(
        `\\.guided-onboarding__navigation-actions\\s*>\\s*${selector}\\s*\\{([^}]+)\\}`,
        "s",
      ),
    )?.[1];
    expect(block).toBeDefined();
    expect(block).toContain("min-height: 44px");
    expect(block).toContain("white-space: nowrap");
  }
});
