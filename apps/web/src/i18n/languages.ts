// Mirror of src/reponpc/i18n/languages.json (ADR-079). languages.test.js fails when they differ.
export interface Language {
  readonly tag: string;
  readonly endonym: string;
  readonly english_name: string;
  readonly scripts: readonly string[];
  readonly direction: "ltr" | "rtl";
  readonly match: readonly string[];
  readonly title_max: number;
  readonly chrome: "zh-TW" | "en";
  readonly derive?: { readonly from: string; readonly converter: string };
}

export const LANGUAGES = [
  {
    tag: "zh-TW",
    endonym: "繁體中文",
    english_name: "Traditional Chinese",
    scripts: ["BOPOMOFO", "CJK", "LATIN"],
    direction: "ltr",
    match: ["zh", "zh-hant", "zh-hk", "zh-mo", "zh-tw"],
    title_max: 24,
    chrome: "zh-TW",
    derive: { from: "zh-CN", converter: "s2twp" },
  },
  {
    tag: "zh-CN",
    endonym: "简体中文",
    english_name: "Simplified Chinese",
    scripts: ["CJK", "LATIN"],
    direction: "ltr",
    match: ["zh-cn", "zh-hans", "zh-sg"],
    title_max: 24,
    chrome: "zh-TW",
    derive: { from: "zh-TW", converter: "tw2sp" },
  },
  {
    tag: "en",
    endonym: "English",
    english_name: "English",
    scripts: ["LATIN"],
    direction: "ltr",
    match: ["en"],
    title_max: 80,
    chrome: "en",
  },
  {
    tag: "es",
    endonym: "Español",
    english_name: "Spanish",
    scripts: ["LATIN"],
    direction: "ltr",
    match: ["es"],
    title_max: 80,
    chrome: "en",
  },
] as const satisfies readonly Language[];

export type LanguageTag = (typeof LANGUAGES)[number]["tag"];

export function languageByTag(tag: string): Language | undefined {
  return LANGUAGES.find((language) => language.tag === tag);
}

export function isLanguageTag(value: unknown): value is LanguageTag {
  return typeof value === "string" && languageByTag(value) !== undefined;
}

/** A language is labelled in its own language, whatever the viewer reads. */
export function endonym(tag: string): string {
  return languageByTag(tag)?.endonym ?? tag;
}

export function chromeLocale(tag: string): "zh-TW" | "en" {
  return languageByTag(tag)?.chrome ?? "en";
}

export function englishName(tag: string): string {
  return languageByTag(tag)?.english_name ?? tag;
}

export function titleMax(tag: string): number | undefined {
  return languageByTag(tag)?.title_max;
}

export function deriveConverter(
  source: string,
  target: string,
): string | undefined {
  const derive = languageByTag(target)?.derive;
  return derive?.from === source ? derive.converter : undefined;
}

function prefixLength(browserTag: string, language: Language): number {
  return language.match.reduce(
    (best, prefix) =>
      browserTag === prefix || browserTag.startsWith(`${prefix}-`)
        ? Math.max(best, prefix.length)
        : best,
    0,
  );
}

/**
 * First browser tag that matches a supported language wins; within one browser tag the
 * longest matching registry prefix wins. Returns `fallback` when nothing matches.
 */
export function matchLocale<Fallback extends string>(
  browserTags: readonly string[],
  supported: readonly string[],
  fallback: Fallback,
): LanguageTag | Fallback {
  const candidates = LANGUAGES.filter((language) =>
    supported.includes(language.tag),
  );
  for (const raw of browserTags) {
    const browserTag = raw.trim().toLowerCase().replaceAll("_", "-");
    let winner: Language | undefined;
    let winnerLength = 0;
    for (const language of candidates) {
      const length = prefixLength(browserTag, language);
      if (length > winnerLength) {
        winner = language;
        winnerLength = length;
      }
    }
    if (winner !== undefined) return winner.tag as LanguageTag;
  }
  return fallback;
}
