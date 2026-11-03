import { describe, expect, it } from "vitest";
import source from "../i18n/messages.ts?raw";
import { LANGUAGES, chromeLocale, endonym } from "../i18n/languages";
import { messageLocale, messages } from "../i18n/messages";
import snapshot from "./zhCnCatalog.snapshot.json";

describe("visitor catalogs", () => {
  it("keeps the generated catalog and its source at the converter snapshot", () => {
    expect(source.match(/^ {2}"zh-TW": \{\n.*?^ {2}\},\n/ms)?.[0]).toBe(
      snapshot.source,
    );
    expect(source.match(/^ {2}"zh-CN": \{\n.*?^ {2}\},\n/ms)?.[0]).toBe(
      snapshot.generated,
    );
    expect(source).toContain("// generated, do not edit");
  });

  it.each(LANGUAGES)(
    "resolves all chrome for $tag through the registry",
    ({ tag }) => {
      const catalogTag = messageLocale(tag);
      expect(messages[tag]).toBe(messages[catalogTag]);
      expect(Object.keys(messages[tag]).sort()).toEqual(
        Object.keys(messages.en).sort(),
      );
      expect(messages[tag].languageName).toBe(endonym(catalogTag));
      if (catalogTag !== tag) {
        expect(catalogTag).toBe(chromeLocale(tag));
        expect(messages[tag]).toBe(messages[chromeLocale(tag)]);
      }
      expect(messages[tag].processingDuration(2, 3)).toContain("2");
      expect(messages[tag].processingDuration(0, 3)).toContain("3");
      expect(messages[tag].citationOwner("Owner")).toContain("Owner");
    },
  );

  it("serves the generated Simplified Chinese chrome and the English Spanish chrome", () => {
    expect(messageLocale("zh-CN")).toBe("zh-CN");
    expect(messages["zh-CN"].profileLoading).toBe("正在加载作品集…");
    expect(messages.es).toBe(messages[chromeLocale("es")]);
    expect(messageLocale("es")).toBe("en");
  });
});
