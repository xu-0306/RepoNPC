// Build guard for the dedicated visitor runtime dependency closure.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "apps/web/package.json"));
const ts = require("typescript");
const fallback = "scene-fallback.generated.css";
const retired = new Set([
  "template",
  "source",
  "glow",
  "pack",
  "pack_id",
  "species",
  "css",
]);
const color =
  /#[\da-f]{3,8}\b|\b(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color|device-cmyk)a?\s*\(/i;

function unwrapped(node) {
  while (ts.isAsExpression(node) || ts.isParenthesizedExpression(node))
    node = node.expression;
  return node;
}

function check(entry, { schemes, roles }) {
  const seen = new Set();
  let mappers = 0;
  const allowedKeys = new Set(
    roles.flatMap((role) => [`--scene-light-${role}`, `--scene-dark-${role}`]),
  );
  function fail(file, reason) {
    throw new Error(`${path.relative(root, file)}: ${reason}`);
  }
  function visit(file) {
    if (seen.has(file)) return;
    seen.add(file);
    if (/[\\/]features[\\/]admin[\\/]/.test(file))
      fail(file, "administration dependency");
    const source = fs.readFileSync(file, "utf8");
    if (file.endsWith(".css")) {
      if (
        path.basename(file) === fallback &&
        file === path.join(root, "apps/web/src/app", fallback)
      )
        return;
      const css = source.replace(/\/\*[\s\S]*?\*\//g, "");
      if (color.test(css)) fail(file, "literal scene colour");
      // Colour-bearing declarations must use tokens; named colours cannot bypass hex checks.
      for (const match of css.matchAll(
        /(?:^|[;{}])\s*(?:color|background(?:-color)?|border(?:-color)?|outline(?:-color)?|box-shadow|text-shadow|fill|stroke)\s*:\s*([^;{}]+)/g,
      )) {
        const value = match[1]
          .replace(/var\([^)]*\)/g, "")
          .replace(/-?(?:\d*\.)?\d+(?:px|rem|em|vh|vw|%)?/g, "")
          .replace(
            /\b(?:transparent|currentColor|inherit|initial|unset|none|solid|dashed|dotted|double|inset|auto|color-mix|in|srgb)\b/g,
            "",
          );
        if (/[a-z]/i.test(value))
          fail(file, "colour declaration outside the closed tokens");
      }
      for (const match of css.matchAll(
        /data-(?:scene-)?scheme\s*=\s*["']?([a-z0-9_]+)/g,
      )) {
        if (schemes.has(match[1])) fail(file, "scheme-specific selector");
      }
      for (const match of css.matchAll(/@import\s+([^;]+);/g)) {
        const target = match[1].match(
          /^(?:"([^"]+)"|'([^']+)'|url\(\s*(?:"([^"]+)"|'([^']+)'|([^\s)]+))\s*\))/,
        );
        const specifier = target?.slice(1).find(Boolean);
        if (!specifier || /^(?:\/|[a-z]+:)/i.test(specifier))
          fail(file, "external or invalid stylesheet import");
        dependency(
          specifier.startsWith(".") ? specifier : "./" + specifier,
          file,
        );
      }
      return;
    }
    const ast = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    function walk(node) {
      if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
        const clause = node.importClause;
        const bindings = clause?.namedBindings;
        const typeOnly =
          node.isTypeOnly ||
          clause?.isTypeOnly ||
          (clause &&
            !clause.name &&
            bindings &&
            ts.isNamedImports(bindings) &&
            bindings.elements.length > 0 &&
            bindings.elements.every((item) => item.isTypeOnly));
        if (
          !typeOnly &&
          node.moduleSpecifier &&
          ts.isStringLiteral(node.moduleSpecifier)
        ) {
          dependency(node.moduleSpecifier.text, file);
        }
      }
      if (
        ts.isCallExpression(node) &&
        node.expression.kind === ts.SyntaxKind.ImportKeyword
      ) {
        const target = node.arguments[0];
        if (!target || !ts.isStringLiteral(target))
          fail(file, "nonliteral dynamic import");
        dependency(target.text, file);
      }
      if (ts.isStringLiteralLike(node)) {
        if (schemes.has(node.text))
          fail(file, "scheme ID in visitor runtime source");
        if (color.test(node.text)) fail(file, "literal scene colour");
      }
      if (
        ts.isPropertyAccessExpression(node) &&
        retired.has(node.name.text) &&
        /(?:^|\.)scene$/.test(node.expression.getText(ast))
      )
        fail(file, "retired scene field");
      if (
        ts.isElementAccessExpression(node) &&
        ts.isStringLiteral(node.argumentExpression) &&
        retired.has(node.argumentExpression.text) &&
        /(?:^|\.)scene$/.test(node.expression.getText(ast))
      )
        fail(file, "retired scene field");
      if (ts.isInterfaceDeclaration(node) && /scene/i.test(node.name.text)) {
        for (const member of node.members) {
          if (
            member.name &&
            retired.has(member.name.getText(ast).replace(/["']/g, ""))
          ) {
            fail(file, "retired scene contract field");
          }
        }
      }
      if (
        ts.isFunctionDeclaration(node) &&
        node.name?.text === "sceneThemeStyle"
      ) {
        mappers += 1;
        const returns =
          node.body?.statements.filter(ts.isReturnStatement) ?? [];
        const object =
          returns.length === 1 &&
          returns[0].expression &&
          unwrapped(returns[0].expression);
        if (!object || !ts.isObjectLiteralExpression(object))
          fail(file, "scene mapper must return closed literal keys");
        const keys = object.properties.map((property) => {
          if (
            !ts.isPropertyAssignment(property) ||
            !ts.isStringLiteral(property.name)
          ) {
            fail(file, "arbitrary scene CSS key");
          }
          return property.name.text;
        });
        if (
          keys.length !== allowedKeys.size ||
          new Set(keys).size !== keys.length ||
          keys.some((key) => !allowedKeys.has(key))
        )
          fail(file, "scene CSS role mapping differs from registry roles");
      }
      ts.forEachChild(node, walk);
    }
    walk(ast);
  }
  function dependency(specifier, parent) {
    if (!specifier.startsWith(".")) {
      if (["react", "react-dom/client"].includes(specifier)) return;
      fail(parent, "unapproved bare or absolute visitor runtime import");
    }
    const candidate = path.resolve(path.dirname(parent), specifier);
    const resolved = [
      candidate,
      ...[".ts", ".tsx", ".js", ".mjs", ".css"].map(
        (suffix) => candidate + suffix,
      ),
      path.join(candidate, "index.ts"),
      path.join(candidate, "index.tsx"),
    ].find((name) => fs.existsSync(name) && fs.statSync(name).isFile());
    if (!resolved) fail(parent, "unresolved runtime import");
    if (!resolved.startsWith(path.dirname(entry) + path.sep))
      fail(parent, "runtime import escapes visitor source");
    visit(resolved);
  }
  visit(entry);
  if (mappers !== 1)
    fail(entry, "one closed sceneThemeStyle mapper is required");
  return seen.size;
}

function selfTest() {
  const directory = fs.mkdtempSync(
    path.join(root, ".test-tmp", "visitor-source-"),
  );
  const roles = ["ink"];
  const options = { schemes: new Set(["test_scheme"]), roles };
  const mapper =
    'export function sceneThemeStyle(scene) { return { "--scene-light-ink": scene.themes.light.ink, "--scene-dark-ink": scene.themes.dark.ink }; }';
  const entry = path.join(directory, "entry.ts");
  const run = (source) => {
    fs.writeFileSync(entry, source);
    return check(entry, options);
  };
  fs.mkdirSync(path.join(directory, "features/admin"), { recursive: true });
  fs.writeFileSync(
    path.join(directory, "features/admin/private.ts"),
    "export const privateValue = 1;",
  );
  assert.equal(
    run(mapper + ' import type { Private } from "./features/admin/private";'),
    1,
  );
  for (const source of [
    mapper + ' import "./features/admin/private";',
    mapper + ' const theme = "test_scheme";',
    mapper + ' const colour = "#abc";',
    mapper + " const old = profile.scene.template;",
    mapper + ' const old = profile.scene["template"];',
    mapper + ' import "/src/features/admin/private";',
    mapper.replace('"--scene-light-ink"', '"--scene-light-css"'),
    mapper.replace(
      '"--scene-light-ink": scene.themes.light.ink',
      "...scene.themes.light",
    ),
  ])
    assert.throws(() => run(source));
  fs.writeFileSync(path.join(directory, "bad.css"), ".a { color: white; }");
  assert.throws(() => run(mapper + ' import "./bad.css";'));
  fs.writeFileSync(
    path.join(directory, "mix.css"),
    ".a { box-shadow: 0 8px 28px color-mix(in srgb, var(--scene-ink) 7%, transparent); }",
  );
  assert.equal(run(mapper + ' import "./mix.css";'), 2);
  fs.writeFileSync(
    path.join(directory, "mix.css"),
    ".a { color: color-mix(in srgb, white 7%, transparent); }",
  );
  assert.throws(() => run(mapper + ' import "./mix.css";'));
  fs.writeFileSync(
    path.join(directory, "nested.css"),
    '@import url("bad.css");',
  );
  assert.throws(() => run(mapper + ' import "./nested.css";'));
  fs.writeFileSync(
    path.join(directory, "nested.css"),
    '@import "https://fixture.test/theme.css";',
  );
  assert.throws(() => run(mapper + ' import "./nested.css";'));
  console.log("Visitor source guard: 14 positive/negative checks passed.");
}

if (process.argv.includes("--self-test")) selfTest();
else {
  // The preceding Python build gate validates this authored registry; this extracts IDs only.
  const registry = fs.readFileSync(
    path.join(root, "src/reponpc/scene/color_schemes.yml"),
    "utf8",
  );
  const schemes = new Set(
    [...registry.matchAll(/^\s*- id:\s*([a-z0-9_]+)\s*$/gm)].map(
      (match) => match[1],
    ),
  );
  const generated = fs.readFileSync(
    path.join(root, "apps/web/src/app", fallback),
    "utf8",
  );
  const roles = [
    ...new Set(
      [...generated.matchAll(/--scene-([a-z_]+):/g)].map((match) => match[1]),
    ),
  ];
  if (schemes.size === 0 || roles.length !== 10)
    throw new Error("invalid generated scene registry identity");
  const count = check(path.join(root, "apps/web/src/visitor-main.tsx"), {
    schemes,
    roles,
  });
  // The head bootstrap is a separate classic script, outside the module import graph.
  const bootstrap = fs.readFileSync(
    path.join(root, "apps/web/public/scene-mode.js"),
    "utf8",
  );
  if (
    color.test(bootstrap) ||
    [...schemes].some((id) => new RegExp(`["']${id}["']`).test(bootstrap))
  ) {
    throw new Error("invalid scene-mode.js colour or scheme literal");
  }
  console.log(`Visitor source guard: ${count} runtime source files checked.`);
}
