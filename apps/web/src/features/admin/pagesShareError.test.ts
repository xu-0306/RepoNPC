import { describe, expect, it } from "vitest";

import { pagesShareErrorMessage } from "./pagesShareError";

// Codes the Pages sharing routes can return (src/reponpc/api/admin.py pages_sharing_error).
const MAPPED = [
  "SHARING_VERIFICATION_FAILED",
  "SHARING_VERIFICATION_UNAVAILABLE",
  "SHARING_CONFIGURATION_INVALID",
  "SHARING_CONFLICT",
  "SHARING_EXPORT_UNAVAILABLE",
  "SHARING_EXPORT_INVALID",
];

describe.each(["zh-TW", "en"] as const)(
  "Pages share errors in %s",
  (locale) => {
    const fallback = pagesShareErrorMessage(locale, new Error("UNKNOWN_CODE"));

    it.each(MAPPED)("explains %s without showing the code", (code) => {
      const message = pagesShareErrorMessage(locale, new Error(code));
      expect(message).not.toBe(fallback);
      expect(message).not.toContain(code);
    });

    it("points an invalid Pages URL at live chat, not at a removed step", () => {
      const message = pagesShareErrorMessage(
        locale,
        new Error("SHARING_CONFIGURATION_INVALID"),
      );
      expect(message).toContain(locale === "zh-TW" ? "第 4 段" : "section 4");
      expect(message).toContain("Funnel URL");
      expect(message).not.toMatch(
        /Pages 網域|Pages domain|上一步|previous step/,
      );
    });

    it("falls back to a plain message for unknown or non-Error failures", () => {
      for (const error of [new TypeError("Failed to fetch"), "oops", null]) {
        expect(pagesShareErrorMessage(locale, error)).toBe(fallback);
      }
      expect(fallback).not.toMatch(/[A-Z]{3,}_[A-Z_]+/);
    });
  },
);
