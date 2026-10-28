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

    it("falls back to a plain message for unknown or non-Error failures", () => {
      for (const error of [new TypeError("Failed to fetch"), "oops", null]) {
        expect(pagesShareErrorMessage(locale, error)).toBe(fallback);
      }
      expect(fallback).not.toMatch(/[A-Z]{3,}_[A-Z_]+/);
    });
  },
);
