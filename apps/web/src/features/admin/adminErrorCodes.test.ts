import { describe, expect, it } from "vitest";

import codes from "./__fixtures__/adminErrorCodes.json";
import { embeddingProfileErrorMessage } from "./embeddingProfileError";
import { guidedErrorMessage } from "./guidedOnboarding";

// The fixture lists the provider HTTP family once as a template.
function expand(code: string): string[] {
  return code.includes("{status}")
    ? Array.from({ length: 500 }, (_, index) =>
        code.replace("{status}", String(100 + index)),
      )
    : [code];
}

describe.each(["zh-TW", "en"] as const)(
  "admin error code coverage in %s",
  (locale) => {
    it("classifies every embedding profile envelope code", () => {
      const fallback = embeddingProfileErrorMessage(
        locale,
        new Error("UNKNOWN_CODE"),
      );
      for (const code of codes.embedding_profile.mapped.flatMap(expand)) {
        expect(
          embeddingProfileErrorMessage(locale, new Error(code)),
          code,
        ).not.toBe(fallback);
      }
      for (const code of Object.keys(codes.embedding_profile.generic)) {
        expect(
          embeddingProfileErrorMessage(locale, new Error(code)),
          code,
        ).toBe(fallback);
      }
    });

    it("classifies every guided onboarding envelope code", () => {
      const fallback = guidedErrorMessage(locale, "UNKNOWN_CODE");
      for (const code of codes.guided_onboarding.mapped) {
        expect(guidedErrorMessage(locale, code), code).not.toBe(fallback);
      }
      for (const code of Object.keys(codes.guided_onboarding.generic)) {
        expect(guidedErrorMessage(locale, code), code).toBe(fallback);
      }
    });
  },
);
