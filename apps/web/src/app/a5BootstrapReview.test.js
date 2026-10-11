import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it } from "vitest";

const script = readFileSync(
  new URL("../../public/scene-mode.js", import.meta.url),
  "utf8",
);

function bootstrap(
  owner,
  toggle,
  saved,
  storageFailure = false,
  pathname = "/",
) {
  const attributes = new Map([
    ["data-owner-mode", owner],
    ["data-visitor-toggle", String(toggle)],
  ]);
  let reads = 0;
  const writes = [];
  const events = [];
  const element = {
    getAttribute: (key) => attributes.get(key) ?? null,
    setAttribute: (key, value) => attributes.set(key, value),
    removeAttribute: (key) => attributes.delete(key),
  };
  const fixtureWindow = {
    location: { pathname },
    dispatchEvent: (event) => events.push(event.detail),
    localStorage: {
      getItem: (key) => {
        reads += 1;
        expect(key).toBe("reponpc.visitor.mode");
        if (storageFailure) throw new Error("fixture storage unavailable");
        return saved;
      },
      setItem: (key, value) => {
        if (storageFailure) throw new Error("fixture storage unavailable");
        writes.push([key, value]);
        saved = value;
      },
      removeItem: (key) => {
        if (storageFailure) throw new Error("fixture storage unavailable");
        writes.push([key, null]);
        saved = null;
      },
    },
    fetch: () => {
      throw new Error("bootstrap must not send a preference");
    },
  };
  runInNewContext(script, {
    document: { documentElement: element },
    window: fixtureWindow,
    CustomEvent: class {
      constructor(type, options) {
        this.type = type;
        this.detail = options.detail;
      }
    },
  });
  expect(writes).toEqual([]);
  const result = () => ({
    mode: attributes.get("data-visitor-mode") ?? "system",
    reads,
  });
  const firstPaint = result();
  Object.defineProperties(firstPaint, {
    api: { value: fixtureWindow.RepoNPCSceneMode },
    result: { value: result },
    writes: { value: writes },
    events: { value: events },
  });
  return firstPaint;
}

describe("Main's independent first-paint mode review", () => {
  it("binds owner defaults and ignores every stored choice when toggling is forbidden", () => {
    for (const owner of ["system", "light", "dark"]) {
      for (const toggle of [true, false]) {
        for (const saved of [null, "light", "dark", "invalid-css-canary"]) {
          const expected =
            toggle && (saved === "light" || saved === "dark") ? saved : owner;
          expect(bootstrap(owner, toggle, saved)).toEqual({
            mode: expected,
            reads: toggle ? 1 : 0,
          });
        }
      }
    }
  });

  it("renders the owner default when storage access fails", () => {
    expect(bootstrap("dark", true, "light", true)).toEqual({
      mode: "dark",
      reads: 1,
    });
    expect(bootstrap("system", true, "dark", true)).toEqual({
      mode: "system",
      reads: 1,
    });
  });

  it("never reads visitor storage while entering the authenticated owner workspace", () => {
    for (const pathname of ["/admin", "/admin/appearance"]) {
      expect(bootstrap("dark", true, "light", true, pathname)).toEqual({
        mode: "system",
        reads: 0,
      });
    }
  });

  it("reconciles newer published policy and immediately ignores a stored override when forbidden", () => {
    const fixture = bootstrap("system", true, "light");
    const reads = fixture.result().reads;
    expect(fixture.api.configure("dark", false)).toBe("dark");
    expect(fixture.result()).toEqual({ mode: "dark", reads });
    expect(fixture.api.set("light")).toBe(false);
    expect(fixture.writes).toEqual([]);
    expect(fixture.api.configure("system", true)).toBe("light");
    expect(fixture.result().mode).toBe("light");
    expect(fixture.events).toEqual(["dark", "light"]);
  });

  it("clears only the visitor preference and returns to each current owner default", () => {
    for (const owner of ["system", "light", "dark"]) {
      const fixture = bootstrap("system", true, "light");
      fixture.api.configure(owner, true);
      expect(fixture.api.set("system")).toBe(true);
      expect(fixture.api.get()).toBe(owner);
      expect(fixture.result().mode).toBe(owner);
      expect(fixture.writes).toEqual([["reponpc.visitor.mode", null]]);
    }
  });

  it("keeps controls usable without storage and rejects unrecognized policy values", () => {
    const fixture = bootstrap("dark", true, null, true);
    expect(fixture.api.set("light")).toBe(true);
    expect(fixture.api.get()).toBe("light");
    expect(fixture.api.set("system")).toBe(true);
    expect(fixture.api.get()).toBe("dark");
    expect(fixture.api.set("url(https://invalid.example)")).toBe(false);
    expect(fixture.api.configure("invalid", false)).toBe("dark");
    expect(fixture.writes).toEqual([]);
  });

  it("binds visitor policy only in the dedicated visitor entry", () => {
    const document = readFileSync(
      new URL("../../visitor.html", import.meta.url),
      "utf8",
    );
    const opening = document.match(/<html\s[^>]*>/)?.[0] ?? "";
    for (const marker of [
      'data-owner-mode="system"',
      'data-visitor-toggle="true"',
    ]) {
      expect(opening).toContain(marker);
      expect(document.split(marker)).toHaveLength(2);
    }
    const tag = '<script src="./scene-mode.js"></script>';
    expect(document.split(tag)).toHaveLength(2);
    expect(document.indexOf(tag)).toBeLessThan(document.indexOf("</head>"));
    const stylesheet = document.search(/<link\b[^>]*rel="stylesheet"/);
    if (stylesheet >= 0) expect(document.indexOf(tag)).toBeLessThan(stylesheet);
    const administrator = readFileSync(
      new URL("../../index.html", import.meta.url),
      "utf8",
    );
    expect(administrator).not.toContain("data-owner-mode");
    expect(administrator).not.toContain("data-visitor-toggle");
    expect(administrator).not.toContain("scene-mode.js");
  });
});
