import { describe, expect, it } from "vitest";

import { messages } from "../i18n/messages";

describe("setup shell locale contract", () => {
  it("keeps Traditional Chinese and English message keys equivalent", () => {
    expect(Object.keys(messages["zh-TW"]).sort()).toEqual(
      Object.keys(messages.en).sort(),
    );
  });

  it("contains setup-required and unavailable guidance in both locales", () => {
    for (const locale of ["zh-TW", "en"] as const) {
      expect(messages[locale].statusTitle).not.toEqual("");
      expect(messages[locale].statusDetail).not.toEqual("");
      expect(messages[locale].availabilityDetail).not.toEqual("");
    }
  });
});
