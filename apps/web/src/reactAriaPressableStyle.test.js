import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  claimReactAriaPressableStyle,
  REACT_ARIA_PRESSABLE_STYLE_ID,
} from "./reactAriaPressableStyle";

function fakeDocument(existing = false) {
  const appended = [];
  const doc = {
    head: { append: (node) => appended.push(node) },
    getElementById: (id) =>
      existing && id === REACT_ARIA_PRESSABLE_STYLE_ID ? {} : null,
    createElement: () => {
      const node = {
        id: "",
        attrs: {},
        setAttribute(key, value) {
          node.attrs[key] = value;
        },
      };
      return node;
    },
  };
  return { doc, appended };
}

describe("React Aria pressable style marker", () => {
  it("adds one marker element and does not add a second", () => {
    const { doc, appended } = fakeDocument();
    claimReactAriaPressableStyle(doc);
    expect(appended).toHaveLength(1);
    expect(appended[0].id).toBe("react-aria-pressable-style");
    const again = fakeDocument(true);
    claimReactAriaPressableStyle(again.doc);
    expect(again.appended).toHaveLength(0);
  });

  it("matches what the installed usePress checks before injecting a style", () => {
    const fromComponents = createRequire(
      createRequire(import.meta.url).resolve(
        "react-aria-components/package.json",
      ),
    );
    const root = dirname(fromComponents.resolve("react-aria/package.json"));
    const source = readFileSync(
      join(root, "dist/private/interactions/usePress.mjs"),
      "utf8",
    );
    expect(source).toContain(`'${REACT_ARIA_PRESSABLE_STYLE_ID}'`);
    expect(source).toMatch(/getElementById\([^)]*STYLE_ID\)\) return;/);
  });

  it("keeps the equivalent rule in the shipped stylesheet", () => {
    const css = readFileSync(join(__dirname, "styles.css"), "utf8");
    expect(css).toMatch(
      /\[data-react-aria-pressable\]\s*\{\s*touch-action:\s*pan-x pan-y pinch-zoom;/,
    );
  });
});
