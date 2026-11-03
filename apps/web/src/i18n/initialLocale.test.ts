import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../app/App";
import { VisitorApp } from "../app/VisitorApp";
import {
  resolveInitialLocale,
  resolveLocaleIn,
  storeLocale,
} from "./initialLocale";
import { LEGACY_LANGUAGES, type PairTag } from "./languages";
import { LANGUAGES, matchLocale } from "./languages";
import {
  languageProfile,
  legacyTags,
  siteSets,
} from "../app/siteLanguages.test-cases";

// Exercise the real state owners with the existing Node hook-harness pattern.
const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as (() => unknown)[],
}));
vi.mock("react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react")>()),
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values))
      hooks.values[index] = typeof initial === "function" ? initial() : initial;
    return [
      hooks.values[index],
      (next: unknown) => {
        hooks.values[index] =
          typeof next === "function" ? next(hooks.values[index]) : next;
      },
    ];
  },
  useRef: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = { current: initial };
    return hooks.values[index];
  },
  useCallback: (callback: unknown) => callback,
  useEffect: (effect: () => unknown, dependencies?: unknown[]) => {
    const index = hooks.cursor++;
    const previous = hooks.values[index] as unknown[] | undefined;
    if (
      !dependencies ||
      !previous ||
      dependencies.some(
        (value, position) => !Object.is(value, previous[position]),
      )
    ) {
      hooks.effects.push(() => {
        hooks.values[index] = dependencies;
        return effect();
      });
    }
  },
}));
vi.mock("../app/visitorData", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/visitorData")>()),
  fetchPublicProfile: async (locale?: PairTag) =>
    languageProfile(locale ?? legacyTags[0]!, legacyTags),
  fetchPublicFaq: () => new Promise(() => undefined),
  fetchPublicStatus: () => new Promise(() => undefined),
}));

const stored = new Map<string, string>();
const storage = {
  getItem: vi.fn((key: string) => stored.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => stored.set(key, value)),
};
const cleanups: (() => void)[] = [];

beforeEach(() => {
  hooks.values = [];
  stored.clear();
  storage.getItem
    .mockReset()
    .mockImplementation((key) => stored.get(key) ?? null);
  storage.setItem
    .mockReset()
    .mockImplementation((key, value) => stored.set(key, value));
  vi.stubGlobal("navigator", { languages: ["en-US"], language: "en-US" });
  vi.stubGlobal("document", { documentElement: { lang: "", dataset: {} } });
  vi.stubGlobal("window", {
    location: { pathname: "/admin" },
    localStorage: storage,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    setTimeout: vi.fn(() => 1),
    clearTimeout: vi.fn(),
    matchMedia: () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
});
afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  vi.unstubAllGlobals();
});

describe("initial locale", () => {
  it.each(LEGACY_LANGUAGES)(
    "prefers the stored $tag to the browser",
    ({ tag }) => {
      stored.set("reponpc.locale", tag);
      vi.stubGlobal("navigator", {
        languages: LEGACY_LANGUAGES.filter((entry) => entry.tag !== tag).map(
          (entry) => entry.tag,
        ),
      });
      expect(resolveInitialLocale()).toBe(tag);
    },
  );

  it.each(
    [
      "",
      "null",
      "__proto__",
      ...LEGACY_LANGUAGES.flatMap(({ tag }) => [
        tag.toUpperCase(),
        `${tag}-x-stored`,
      ]),
    ].flatMap((value) => LEGACY_LANGUAGES.map(({ tag }) => ({ value, tag }))),
  )("ignores invalid stored $value with browser $tag", ({ value, tag }) => {
    stored.set("reponpc.locale", value);
    vi.stubGlobal("navigator", { languages: [tag] });
    expect(resolveInitialLocale()).toBe(tag);
  });

  it.each([
    { languages: ["fr", "en-GB"], expected: "en" },
    { languages: ["zh-HK", "en"], expected: "zh-TW" },
    { languages: ["en-US", "zh-TW"], expected: "en" },
    { languages: ["de-DE", "fr-FR"], expected: "zh-TW" },
  ])("matches $languages in order", ({ languages, expected }) => {
    vi.stubGlobal("navigator", { languages });
    expect(resolveInitialLocale()).toBe(expected);
  });

  it.each(
    LEGACY_LANGUAGES.flatMap(({ tag, match }) =>
      match.map((prefix) => ({ tag, prefix })),
    ),
  )("matches registry prefix $prefix to $tag", ({ tag, prefix }) => {
    for (const browserTag of [prefix, `${prefix.toUpperCase()}-x-browser`]) {
      vi.stubGlobal("navigator", { languages: [browserTag] });
      expect(resolveInitialLocale()).toBe(tag);
    }
  });

  it.each(LEGACY_LANGUAGES)(
    "uses navigator.language for $tag when languages is empty",
    ({ tag }) => {
      vi.stubGlobal("navigator", { languages: [], language: tag });
      expect(resolveInitialLocale()).toBe(tag);
    },
  );

  it("keeps zh-TW when navigator is unavailable", () => {
    vi.stubGlobal("navigator", undefined);
    expect(resolveInitialLocale()).toBe("zh-TW");
  });

  it("falls back to the browser when accessing storage throws", () => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("Storage disabled");
      },
    });
    expect(resolveInitialLocale()).toBe("en");
    expect(() => storeLocale("zh-TW")).not.toThrow();
  });

  it.each(LEGACY_LANGUAGES)("stores the exact registry tag $tag", ({ tag }) => {
    storeLocale(tag);
    expect(storage.setItem).toHaveBeenCalledWith("reponpc.locale", tag);
    expect(stored.get("reponpc.locale")).toBe(tag);
  });
});

describe("resolveLocaleIn", () => {
  const SET = LANGUAGES.map(({ tag }) => tag);

  it.each([
    { languages: ["zh-CN"], supported: SET, expected: "zh-CN" },
    { languages: ["zh-SG", "en"], supported: SET, expected: "zh-CN" },
    { languages: ["es-MX"], supported: SET, expected: "es" },
    { languages: ["zh-CN"], supported: ["zh-TW", "en"], expected: "zh-TW" },
    { languages: ["es"], supported: ["en"], expected: "en" },
    { languages: ["fr", "es"], supported: ["en", "es"], expected: "es" },
    { languages: ["fr"], supported: ["es"], expected: "es" },
  ])(
    "matches $languages against $supported",
    ({ languages, supported, expected }) => {
      vi.stubGlobal("navigator", { languages });
      expect(resolveLocaleIn(supported, supported[0]!)).toBe(expected);
    },
  );

  it("uses the stored choice only while the set still offers it", () => {
    stored.set("reponpc.locale", "es");
    vi.stubGlobal("navigator", { languages: ["zh-CN"] });
    expect(resolveLocaleIn(SET, "en")).toBe("es");
    expect(resolveLocaleIn(["zh-CN", "en"], "en")).toBe("zh-CN");
  });

  it("returns the fallback when nothing matches and storage is unusable", () => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("Storage disabled");
      },
    });
    vi.stubGlobal("navigator", { languages: ["de"] });
    expect(resolveLocaleIn(["en", "es"], "es")).toBe("es");
  });

  it("keeps the legacy pair wrapper on the two phase A languages", () => {
    stored.set("reponpc.locale", "es");
    vi.stubGlobal("navigator", { languages: ["es"] });
    expect(resolveInitialLocale()).toBe("zh-TW");
  });

  describe.each(siteSets.map((supported) => ({ supported })))(
    "site set $supported",
    ({ supported }) => {
      it.each(LANGUAGES)(
        "resolves browser and stored choices for $tag only within the set",
        ({ tag }) => {
          const fallback = supported[0]!;
          vi.stubGlobal("navigator", { languages: [tag] });
          const expected = matchLocale([tag], supported, fallback);
          for (const invalid of [undefined, "", "__proto__", "not-a-tag"]) {
            if (invalid !== undefined) stored.set("reponpc.locale", invalid);
            else stored.delete("reponpc.locale");
            expect(resolveLocaleIn(supported, fallback)).toBe(expected);
          }
          stored.set("reponpc.locale", tag);
          expect(resolveLocaleIn(supported, fallback)).toBe(
            supported.includes(tag) ? tag : expected,
          );
          storage.getItem.mockImplementationOnce(() => {
            throw new Error("unavailable");
          });
          expect(resolveLocaleIn(supported, fallback)).toBe(expected);
          vi.stubGlobal("navigator", { languages: [], language: tag });
          stored.clear();
          expect(resolveLocaleIn(supported, fallback)).toBe(expected);
          vi.stubGlobal("navigator", { languages: ["fr-FR"] });
          expect(resolveLocaleIn(supported, fallback)).toBe(fallback);
        },
      );
    },
  );
});

interface LocaleProps {
  locale: PairTag;
  onLocaleChange: (locale: PairTag) => void;
}

function render(app: "admin" | "visitor"): LocaleProps & { profile?: unknown } {
  hooks.cursor = 0;
  hooks.effects = [];
  let props: LocaleProps;
  if (app === "admin") {
    const Router = App().type as () => ReactElement<{
      children: ReactElement<LocaleProps>;
    }>;
    props = Router().props.children.props;
  } else {
    props = VisitorApp().props as LocaleProps;
  }
  for (const effect of hooks.effects) {
    const cleanup = effect();
    if (typeof cleanup === "function") cleanups.push(cleanup as () => void);
  }
  return props;
}

async function settled(app: "admin" | "visitor"): Promise<LocaleProps> {
  let props = render(app);
  if (app === "visitor") {
    await vi.waitFor(() => {
      props = render(app);
      expect(props.profile).toBeTruthy();
    });
  }
  return props;
}

describe.each(["admin", "visitor"] as const)("%s locale owner", (app) => {
  it.each(LEGACY_LANGUAGES)(
    "persists a manual switch to $tag across remounts and syncs html lang",
    async ({ tag }) => {
      const other = LEGACY_LANGUAGES.find((entry) => entry.tag !== tag)!;
      vi.stubGlobal("navigator", { languages: [other.tag] });
      expect((await settled(app)).locale).toBe(other.tag);
      expect(document.documentElement.lang).toBe(other.tag);
      expect(storage.setItem).not.toHaveBeenCalled();
      (await settled(app)).onLocaleChange(tag);
      expect((await settled(app)).locale).toBe(tag);
      expect(document.documentElement.lang).toBe(tag);
      expect(stored.get("reponpc.locale")).toBe(tag);

      hooks.values = [];
      expect((await settled(app)).locale).toBe(tag);
      expect(document.documentElement.lang).toBe(tag);
    },
  );

  it.each(["getItem", "setItem"] as const)(
    "renders and switches when storage %s throws",
    async (method) => {
      storage[method].mockImplementation(() => {
        throw new Error("Storage disabled");
      });
      expect((await settled(app)).locale).toBe("en");
      expect(document.documentElement.lang).toBe("en");
      (await settled(app)).onLocaleChange("zh-TW");
      expect((await settled(app)).locale).toBe("zh-TW");
      expect(document.documentElement.lang).toBe("zh-TW");
    },
  );
});
