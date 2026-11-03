// Mirror of src/reponpc/i18n/languages.json (ADR-078). languages.test.ts fails when they differ.
export interface Language {
  readonly tag: string;
  readonly endonym: string;
  readonly scripts: readonly string[];
  readonly direction: "ltr" | "rtl";
  readonly match: readonly string[];
}

export const LANGUAGES = [
  {
    tag: "zh-TW",
    endonym: "繁體中文",
    scripts: ["BOPOMOFO", "CJK", "LATIN"],
    direction: "ltr",
    match: ["zh", "zh-hant", "zh-hk", "zh-mo", "zh-tw"],
  },
  {
    tag: "en",
    endonym: "English",
    scripts: ["LATIN"],
    direction: "ltr",
    match: ["en"],
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
