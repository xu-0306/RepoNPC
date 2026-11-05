import { chromeLocale } from "../../i18n/languages";

/**
 * The numbered sections of the sharing page, in the order they are shown.
 * Every heading and every "see section N" text derives its number from here,
 * so a reorder cannot leave a stale reference (ADR-081).
 */
export const SHARING_SECTIONS = [
  "prepare",
  "pages",
  "profile",
  "liveChat",
] as const;

export type SharingSection = (typeof SHARING_SECTIONS)[number];

export function sectionNumber(section: SharingSection): number {
  return SHARING_SECTIONS.indexOf(section) + 1;
}

/** A heading such as "2. GitHub Pages". */
export function sectionTitle(section: SharingSection, title: string): string {
  return `${sectionNumber(section)}. ${title}`;
}

/** An in-text reference such as "section 2" or 「第 2 段」. */
export function sectionRef(locale: string, section: SharingSection): string {
  const number = sectionNumber(section);
  return chromeLocale(locale) === "zh-TW"
    ? `第 ${number} 段`
    : `section ${number}`;
}
