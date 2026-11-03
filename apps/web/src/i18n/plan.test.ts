import { describe, expect, it } from "vitest";

import { LANGUAGES, deriveConverter } from "./languages";
import { ANALYSIS_LOCALES, planLanguages } from "./plan";

const TAGS: string[] = LANGUAGES.map((language) => language.tag);

/** Every non-empty ordered selection of distinct registry tags. */
function extend(prefix: string[]): string[][] {
  return [
    prefix,
    ...TAGS.filter((tag) => !prefix.includes(tag)).flatMap((tag) =>
      extend([...prefix, tag]),
    ),
  ];
}

const SUBSETS = TAGS.flatMap((tag) => extend([tag])).map(
  (site) => [site.join("|"), site] as const,
);

describe("planLanguages", () => {
  it("matches the documented examples", () => {
    expect(planLanguages(["zh-TW", "zh-CN", "en"])).toEqual({
      written: ["zh-TW", "en"],
      derived: [{ target: "zh-CN", source: "zh-TW" }],
    });
    expect(planLanguages(["en", "zh-CN", "zh-TW"])).toEqual({
      written: ["en", "zh-CN"],
      derived: [{ target: "zh-TW", source: "zh-CN" }],
    });
    expect(planLanguages(["zh-TW", "en"]).derived).toEqual([]);
    expect(planLanguages(["es"])).toEqual({ written: ["es"], derived: [] });
  });

  it.each(SUBSETS)("partitions the ordered set %s", (_name, site) => {
    const plan = planLanguages(site);
    expect(
      [...plan.written, ...plan.derived.map((item) => item.target)].sort(),
    ).toEqual([...site].sort());
    expect(plan.written.length).toBeGreaterThan(0);
    for (const { target, source } of plan.derived) {
      expect(deriveConverter(source, target)).toBeDefined();
      expect(plan.written).toContain(source);
      expect(site.indexOf(source)).toBeLessThan(site.indexOf(target));
    }
  });

  it("rejects an empty set, a repeated tag and an unknown tag", () => {
    expect(() => planLanguages([])).toThrow();
    expect(() => planLanguages(["en", "en"])).toThrow();
    expect(() => planLanguages(["en", "xx"])).toThrow();
  });

  it("keeps the analysis languages written by the model", () => {
    expect(planLanguages(ANALYSIS_LOCALES).derived).toEqual([]);
  });
});
