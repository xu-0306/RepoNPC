import { languageByTag, type LanguageTag } from "./languages";

/**
 * Languages in which the durable repository analysis writes inference text, whatever the
 * site set is (mirror of `reponpc.i18n.plan.ANALYSIS_LOCALES`).
 */
export const ANALYSIS_LOCALES = [
  "zh-TW",
  "en",
] as const satisfies readonly LanguageTag[];

export interface LanguagePlan {
  /** Tags whose text the owner or the model writes, in site order. */
  readonly written: readonly LanguageTag[];
  /** Tags produced by conversion from an earlier written tag. */
  readonly derived: readonly {
    readonly target: LanguageTag;
    readonly source: LanguageTag;
  }[];
}

/** Mirror of `reponpc.i18n.plan.plan_languages`. */
export function planLanguages(site: readonly string[]): LanguagePlan {
  if (site.length === 0 || new Set(site).size !== site.length) {
    throw new Error("a site set is a non-empty list of unique language tags");
  }
  const written: LanguageTag[] = [];
  const derived: { target: LanguageTag; source: LanguageTag }[] = [];
  for (const tag of site) {
    const language = languageByTag(tag);
    if (language === undefined) throw new Error(`unknown language tag ${tag}`);
    const source = language.derive?.from;
    if (
      source !== undefined &&
      (written as readonly string[]).includes(source)
    ) {
      derived.push({
        target: language.tag as LanguageTag,
        source: source as LanguageTag,
      });
    } else {
      written.push(language.tag as LanguageTag);
    }
  }
  return { written, derived };
}
