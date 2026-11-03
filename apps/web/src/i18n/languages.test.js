import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import {
  endonym,
  isLanguageTag,
  languageByTag,
  LANGUAGES,
  matchLocale,
} from "./languages";

const REGISTRY = JSON.parse(
  readFileSync(
    join(
      dirname(fileURLToPath(import.meta.url)),
      "../../../../src/reponpc/i18n/languages.json",
    ),
    "utf8",
  ),
);
const TAGS = LANGUAGES.map((language) => language.tag);

describe("language registry mirror", () => {
  it("equals src/reponpc/i18n/languages.json entry by entry", () => {
    expect(REGISTRY.version).toBe(1);
    expect(JSON.parse(JSON.stringify(LANGUAGES))).toEqual(REGISTRY.languages);
  });

  it("claims every match prefix once and includes each tag itself", () => {
    const prefixes = LANGUAGES.flatMap((language) => language.match);
    expect(new Set(prefixes).size).toBe(prefixes.length);
    for (const language of LANGUAGES) {
      expect(language.match).toContain(language.tag.toLowerCase());
    }
  });

  it("labels languages with their own name and falls back to the tag", () => {
    for (const language of LANGUAGES) {
      expect(endonym(language.tag)).toBe(language.endonym);
    }
    expect(endonym("xx")).toBe("xx");
    expect(isLanguageTag("xx")).toBe(false);
    expect(languageByTag(TAGS[0])?.tag).toBe(TAGS[0]);
  });
});

describe("matchLocale", () => {
  // every entry's own prefixes, upper-cased, and with underscores, must find that entry
  const own = LANGUAGES.flatMap((language) =>
    language.match.flatMap((prefix) => [
      [prefix, language.tag],
      [prefix.toUpperCase(), language.tag],
      [prefix.replaceAll("-", "_"), language.tag],
    ]),
  );
  it.each(own)("%s matches its registry entry %s", (browserTag, tag) => {
    expect(matchLocale([browserTag], TAGS, "fallback")).toBe(tag);
  });

  it("returns the first browser tag that matches, not the best-ranked language", () => {
    expect(matchLocale(["fr", "en-GB"], TAGS, "zh-TW")).toBe("en");
    expect(matchLocale(["zh-HK", "en"], TAGS, "zh-TW")).toBe("zh-TW");
    expect(matchLocale(["en-US", "zh-TW"], TAGS, "zh-TW")).toBe("en");
    expect(matchLocale(["zh-CN"], TAGS, "en")).toBe("zh-TW");
  });

  it("normalises case, spaces and underscores", () => {
    expect(matchLocale([" EN_us "], TAGS, "zh-TW")).toBe("en");
    expect(matchLocale(["ZH_Hant_TW"], TAGS, "en")).toBe("zh-TW");
  });

  it("returns the fallback when nothing matches or the list is empty", () => {
    expect(matchLocale(["fr", "de-CH"], TAGS, "zh-TW")).toBe("zh-TW");
    expect(matchLocale([], TAGS, "en")).toBe("en");
  });

  it("ignores languages the page does not support", () => {
    expect(matchLocale(["zh-TW", "en"], ["en"], "zh-TW")).toBe("en");
    expect(matchLocale(["zh-TW"], ["en"], "en")).toBe("en");
    expect(matchLocale(["zh-TW"], [], "en")).toBe("en");
  });

  it("does not confuse a tag with a longer unrelated language code", () => {
    expect(matchLocale(["eng"], TAGS, "zh-TW")).toBe("zh-TW");
    expect(matchLocale(["zhx"], TAGS, "en")).toBe("en");
  });
});
