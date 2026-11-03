import {
  LANGUAGES,
  isLanguageTag,
  matchLocale,
  type LanguageTag,
} from "./languages";

export function resolveInitialLocale(): LanguageTag {
  try {
    const stored = window.localStorage.getItem("reponpc.locale");
    if (isLanguageTag(stored)) return stored;
  } catch {
    // Browser storage can be unavailable even when the page is usable.
  }

  return matchLocale(
    typeof navigator === "undefined"
      ? []
      : navigator.languages.length
        ? navigator.languages
        : [navigator.language],
    LANGUAGES.map((language) => language.tag),
    "zh-TW",
  );
}

export function storeLocale(tag: LanguageTag): void {
  try {
    window.localStorage.setItem("reponpc.locale", tag);
  } catch {
    // A manual choice still applies when browser storage is unavailable.
  }
}
