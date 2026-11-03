import type { LanguageTag } from "../../i18n/languages";
import {
  selectedRepositories,
  type GuidedOnboardingState,
} from "./guidedOnboarding";

type Request = <T>(path: string, init?: RequestInit) => Promise<T>;

export function requestContributionSuggestion(
  request: Request,
  slug: string,
  ownerStatement: string,
  locales: readonly LanguageTag[],
  signal: AbortSignal,
) {
  return request<unknown>("/api/admin/onboarding/contributions/suggest", {
    method: "POST",
    signal,
    body: JSON.stringify({ slug, owner_statement: ownerStatement, locales }),
  });
}

export function requestOnboardingDraft<T>(
  request: Request,
  state: GuidedOnboardingState,
  baseConfig: Record<string, unknown> | null,
) {
  return request<T>("/api/admin/onboarding/draft", {
    method: "POST",
    body: JSON.stringify({
      locales: state.locales,
      profile: {
        display_name: state.profile.displayName,
        github_login: state.profile.githubLogin.trim(),
        aliases: state.profile.aliasesText
          .split(/\r?\n/)
          .map((alias) => alias.trim())
          .filter(Boolean),
        headline: state.profile.headline,
        bio: state.profile.bio,
        greeting: state.profile.greeting,
      },
      repositories: selectedRepositories(state).map((repository) => ({
        slug: repository.metadata.slug,
        ref: repository.ref,
        include: repository.include,
        exclude: repository.exclude,
        role: repository.confirmedContribution?.role,
        summary: repository.confirmedContribution?.summary,
        claims: repository.confirmedContribution?.claims ?? [],
      })),
      base_config: baseConfig,
      confirmed_assertions: true,
    }),
  });
}
