import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const script = readFileSync(
  new URL("../../public/scene-mode.js", import.meta.url),
  "utf8",
);
const key = "reponpc.visitor.scheme";
const defaultId = "fixture_default";
const otherId = "fixture_other";

function bootstrap({
  saved = otherId,
  allowed = true,
  failure,
  pathname = "/",
} = {}) {
  const attributes = new Map([
    ["data-owner-mode", "system"],
    ["data-visitor-toggle", "true"],
    ["data-default-scheme", defaultId],
    ["data-visitor-scheme-choice", String(allowed)],
  ]);
  const storage = new Map(saved === null ? [] : [[key, saved]]);
  const events = [];
  const cookie = vi.fn(() => {
    throw new Error("cookie access");
  });
  const network = vi.fn(() => {
    throw new Error("network access");
  });
  const document = {
    documentElement: {
      getAttribute: (name) => attributes.get(name) ?? null,
      setAttribute: (name, value) => attributes.set(name, value),
      removeAttribute: (name) => attributes.delete(name),
    },
  };
  Object.defineProperty(document, "cookie", { get: cookie, set: cookie });
  const localStorage = Object.fromEntries(
    ["getItem", "setItem", "removeItem"].map((method) => [
      method,
      vi.fn((name, value) => {
        if (failure === method) throw new Error("storage unavailable");
        if (method === "getItem") return storage.get(name) ?? null;
        if (method === "setItem") storage.set(name, value);
        if (method === "removeItem") storage.delete(name);
      }),
    ]),
  );
  const window = {
    location: { pathname, search: "?scheme=untrusted_url_choice" },
    localStorage,
    fetch: network,
    XMLHttpRequest: network,
    dispatchEvent: (event) =>
      events.push({ type: event.type, detail: event.detail }),
  };
  runInNewContext(script, {
    window,
    document,
    fetch: network,
    XMLHttpRequest: network,
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options.detail;
      }
    },
  });
  const api = window.RepoNPCSceneMode;
  const configure = (choice = allowed, ids = [defaultId, otherId]) =>
    api.configure("system", true, defaultId, choice, ids);
  return {
    api,
    attributes,
    configure,
    storage,
    events,
    cookie,
    network,
    localStorage,
  };
}

describe("P1 visitor scheme bootstrap", () => {
  it("applies a saved scheme before React and exposes a frozen API without sending it", () => {
    const view = bootstrap();
    expect(view.attributes.get("data-visitor-scheme")).toBe(otherId);
    expect(view.api.getScheme()).toBe(otherId);
    expect(Object.isFrozen(view.api)).toBe(true);
    view.configure();
    view.api.setScheme(defaultId);
    view.api.setScheme(otherId);
    expect(view.cookie).not.toHaveBeenCalled();
    expect(view.network).not.toHaveBeenCalled();
    expect([...view.attributes.values()]).not.toContain("untrusted_url_choice");
    expect([...view.storage.keys()]).toEqual([key]);
  });

  it.each([
    "",
    "UPPER",
    "with-hyphen",
    "../escape",
    "x".repeat(65),
    "url(attack)",
  ])("ignores malformed/oversized id %s", (saved) => {
    const view = bootstrap({ saved });
    expect(view.attributes.get("data-visitor-scheme")).toBe(defaultId);
    expect(view.api.getScheme()).toBe(defaultId);
  });

  it("accepts the bounded id syntax, then ignores unknown ids without deleting storage", () => {
    const saved = "a".repeat(64);
    const view = bootstrap({ saved });
    expect(view.api.getScheme()).toBe(saved);
    view.configure();
    expect(view.api.getScheme()).toBe(defaultId);
    expect(view.attributes.get("data-visitor-scheme")).toBe(defaultId);
    expect(view.storage.get(key)).toBe(saved);
    expect(view.api.setScheme(saved)).toBe(false);
    view.configure(true, [defaultId, otherId, saved]);
    expect(view.api.getScheme()).toBe(saved);
  });

  it("ignores storage and setters while choice is off, then restores an allowed choice", () => {
    const view = bootstrap({ allowed: false });
    expect(view.api.getScheme()).toBe(defaultId);
    expect(view.attributes.get("data-visitor-scheme")).toBe(defaultId);
    expect(view.localStorage.getItem).not.toHaveBeenCalledWith(key);
    expect(view.api.setScheme(otherId)).toBe(false);
    expect(view.api.setScheme(null)).toBe(false);
    view.configure(true);
    expect(view.api.getScheme()).toBe(otherId);
    expect(view.attributes.get("data-visitor-scheme-choice")).toBe("true");
    view.configure(false);
    expect(view.api.getScheme()).toBe(defaultId);
    expect(view.attributes.get("data-visitor-scheme-choice")).toBe("false");
    expect(view.storage.get(key)).toBe(otherId);
  });

  it.each([null, defaultId])(
    "clears storage for %s and emits the effective default",
    (id) => {
      const view = bootstrap();
      view.configure();
      expect(view.api.setScheme(id)).toBe(true);
      expect(view.storage.has(key)).toBe(false);
      expect(view.api.getScheme()).toBe(defaultId);
      expect(view.attributes.get("data-visitor-scheme")).toBe(defaultId);
      expect(view.events.at(-1)).toEqual({
        type: "reponpc:visitor-scheme-change",
        detail: defaultId,
      });
      expect(view.api.setScheme(otherId)).toBe(true);
      expect(view.events.at(-1)).toEqual({
        type: "reponpc:visitor-scheme-change",
        detail: otherId,
      });
    },
  );

  it.each(["getItem", "setItem", "removeItem"])(
    "keeps choices usable when %s throws",
    (failure) => {
      const view = bootstrap({ failure });
      expect(view.api.getScheme()).toBe(
        failure === "getItem" ? defaultId : otherId,
      );
      view.configure();
      expect(view.api.setScheme(otherId)).toBe(true);
      expect(view.api.getScheme()).toBe(otherId);
      expect(view.api.setScheme(null)).toBe(true);
      expect(view.api.getScheme()).toBe(defaultId);
      expect(view.events.at(-1).detail).toBe(defaultId);
    },
  );

  it("preserves two-argument configure calls and rejects unknown setters", () => {
    const view = bootstrap();
    view.configure();
    expect(view.api.configure("dark", false)).toBe("dark");
    expect(view.api.getScheme()).toBe(otherId);
    expect(view.attributes.get("data-default-scheme")).toBe(defaultId);
    expect(view.api.setScheme("fixture_unknown")).toBe(false);
    expect(view.api.setScheme("x".repeat(65))).toBe(false);
    expect(view.storage.get(key)).toBe(otherId);
  });

  it.each(["/admin", "/admin/appearance"])(
    "leaves %s unchanged",
    (pathname) => {
      const view = bootstrap({ pathname });
      expect(view.api).toBeUndefined();
      expect(view.localStorage.getItem).not.toHaveBeenCalled();
      expect(view.localStorage.setItem).not.toHaveBeenCalled();
      expect(view.localStorage.removeItem).not.toHaveBeenCalled();
      expect(view.attributes.has("data-visitor-scheme")).toBe(false);
      expect(view.cookie).not.toHaveBeenCalled();
      expect(view.network).not.toHaveBeenCalled();
    },
  );
});
