import { describe, expect, it } from "vitest";

import { syncDocumentLanguage } from "./App";
import { messages } from "../i18n/messages";

describe("visitor locale contract", () => {
  it("keeps Traditional Chinese and English message keys equivalent", () => {
    expect(Object.keys(messages["zh-TW"]).sort()).toEqual(
      Object.keys(messages.en).sort(),
    );
  });

  it("contains visitor chat and accessibility guidance in both locales", () => {
    for (const locale of ["zh-TW", "en"] as const) {
      expect(messages[locale].chatTitle).not.toEqual("");
      expect(messages[locale].inputLabel).not.toEqual("");
      expect(messages[locale].characterOffline).not.toEqual("");
      expect(messages[locale].suggestionItems).toHaveLength(2);
    }
  });

  it("updates the document language when the visitor changes locale", () => {
    const element = { lang: "zh-TW" };
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: { documentElement: element },
    });
    syncDocumentLanguage("en");
    expect(element.lang).toBe("en");
  });
});
