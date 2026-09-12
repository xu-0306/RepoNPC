import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ADMIN_UI_SCALE_STORAGE_KEY,
  DEFAULT_ADMIN_UI_SCALE,
  parseAdminUiScale,
  persistAdminUiScale,
} from "./adminUiScale";

describe("admin UI scale preference", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("uses the larger comfortable scale by default", () => {
    expect(DEFAULT_ADMIN_UI_SCALE).toBe("comfortable");
    expect(parseAdminUiScale(null)).toBe("comfortable");
    expect(parseAdminUiScale("unexpected")).toBe("comfortable");
  });

  it("accepts only supported display scales", () => {
    expect(parseAdminUiScale("standard")).toBe("standard");
    expect(parseAdminUiScale("comfortable")).toBe("comfortable");
    expect(parseAdminUiScale("large")).toBe("large");
  });

  it("persists only the non-sensitive display preference", () => {
    const setItem = vi.fn();
    vi.stubGlobal("window", { localStorage: { setItem } });

    persistAdminUiScale("large");

    expect(setItem).toHaveBeenCalledWith(ADMIN_UI_SCALE_STORAGE_KEY, "large");
  });
});
