import { matchLocale, type LanguageTag } from "./languages";

/**
 * The stored manual choice wins when the set still offers it; otherwise the first browser
 * language that matches the set; otherwise `fallback`.
 */
export function resolveLocaleIn<Fallback extends string>(
  supported: readonly string[],
  fallback: Fallback,
): LanguageTag | Fallback {
  try {
    const stored = window.localStorage.getItem("reponpc.locale");
    if (stored !== null && supported.includes(stored))
      return stored as LanguageTag;
  } catch {
    // Browser storage can be unavailable even when the page is usable.
  }

  return matchLocale(
    typeof navigator === "undefined"
      ? []
      : navigator.languages.length
        ? navigator.languages
        : [navigator.language],
    supported,
    fallback,
  );
}

export function storeLocale(tag: string): void {
  try {
    window.localStorage.setItem("reponpc.locale", tag);
  } catch {
    // A manual choice still applies when browser storage is unavailable.
  }
}
