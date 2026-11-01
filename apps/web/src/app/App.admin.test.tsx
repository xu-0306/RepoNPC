import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, expect, it, vi } from "vitest";

import type { Locale } from "../i18n/messages";
import { App } from "./App";

// Reuse the Node hook harness to render the real locale owner and flush its effects.
const hooks = vi.hoisted(() => ({
  locale: "zh-TW" as Locale,
  effects: [] as (() => unknown)[],
}));
vi.mock("react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react")>()),
  useState: () => [
    hooks.locale,
    (locale: Locale) => {
      hooks.locale = locale;
    },
  ],
  useEffect: (effect: () => unknown) => hooks.effects.push(effect),
}));

afterEach(() => vi.unstubAllGlobals());

it("syncs the admin document language on loading and zh-TW → en → zh-TW changes", () => {
  vi.stubGlobal("window", { location: { pathname: "/admin" } });
  vi.stubGlobal("document", { documentElement: { lang: "en" } });
  hooks.locale = "zh-TW";
  const Router = App().type as () => ReactElement<{
    fallback: ReactElement;
    children: ReactElement<{
      locale: Locale;
      onLocaleChange: (locale: Locale) => void;
    }>;
  }>;
  function render() {
    hooks.effects = [];
    const view = Router();
    for (const effect of hooks.effects) effect();
    return view;
  }

  let view = render();
  expect(renderToStaticMarkup(view.props.fallback)).toContain(
    "正在載入管理介面…",
  );
  expect(document.documentElement.lang).toBe("zh-TW");
  for (const locale of ["en", "zh-TW"] as const) {
    view.props.children.props.onLocaleChange(locale);
    view = render();
    expect(view.props.children.props.locale).toBe(locale);
    expect(document.documentElement.lang).toBe(locale);
    expect(renderToStaticMarkup(view.props.fallback)).toContain(
      `lang="${locale}"`,
    );
  }
});
