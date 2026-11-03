import { LANGUAGES, endonym, type LanguageTag } from "../i18n/languages";
import type { PublicProfile } from "./publicTypes";

export const legacyTags = LANGUAGES.filter(
  ({ tag, chrome }) => tag === chrome,
).map(({ tag }) => tag);

const tags = LANGUAGES.map(({ tag }) => tag);
export const siteSets: readonly (readonly LanguageTag[])[] = [
  legacyTags,
  ...tags.map((tag) => [tag]),
  tags.filter((tag) => tag === "zh-CN" || tag === "en"),
  tags,
  [...tags.slice(2), ...tags.slice(0, 2)],
];

export function availableLocales(supported: readonly LanguageTag[]) {
  return supported.map((tag) => ({ tag, endonym: endonym(tag) }));
}

export function languageProfile(
  locale: LanguageTag,
  supported: readonly LanguageTag[],
): PublicProfile {
  return {
    schema_version: 1,
    locale,
    available_locales: availableLocales(supported),
    profile: {
      display_name: "Fixture owner",
      headline: `${locale} headline`,
      bio: `${locale} biography`,
      greeting: `${locale} greeting`,
      location: null,
      avatar_url: null,
      links: [],
    },
    repositories: [
      {
        slug: "owner/project",
        summary: `${locale} summary`,
        role: `${locale} role`,
        tags: [],
        demo_url: null,
      },
    ],
    suggested_questions: [`${locale} question?`],
    character: {
      mode: "builtin",
      asset_url: "/api/public/character.png",
      revision: 0,
      frame_duration_ms: 160,
      movement: "none",
    },
    index: {
      version: "fixture-bundle",
      built_at: "2026-11-03T00:00:00Z",
      repository_count: 1,
    },
  };
}
