import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  LANGUAGES,
  chromeLocale,
  endonym,
  type LanguageTag,
} from "../../i18n/languages";
import { ClaimEditor } from "./ClaimEditor";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { contributionSuggestionBody } from "./AdminPage";
import {
  requestContributionSuggestion,
  requestOnboardingDraft,
} from "./authoringRequests";
import {
  guidedOnboardingFromConfig,
  guidedOnboardingReducer,
  initialGuidedOnboardingState,
  parseGuidedOnboarding,
  profileIsComplete,
  contributionIsComplete,
  serializeGuidedOnboarding,
} from "./guidedOnboarding";
import { PROFILE_FIELDS } from "./profileTranslation";
import {
  ADMIN_CHROMES,
  SITE_SETS,
  siteState,
} from "./__fixtures__/siteLanguages";

function view(locale: LanguageTag, state: ReturnType<typeof siteState>) {
  return renderToStaticMarkup(
    <GuidedOnboardingView
      locale={locale}
      state={state}
      draft=""
      validation={null}
      busy={false}
      errorCode=""
      analysisSelection={null}
      analysisSelectionPending={false}
      onAction={vi.fn()}
      onDiscover={vi.fn()}
      onResolve={vi.fn()}
      onAnalyze={vi.fn()}
      onRefreshAnalysisSelection={vi.fn()}
      onSuggestContribution={vi.fn()}
      onCreateDraft={vi.fn()}
      onCopyDraft={vi.fn()}
      onDownloadDraft={vi.fn()}
      onOpenPublication={vi.fn()}
    />,
  );
}

describe.each(ADMIN_CHROMES)("site authoring with %s chrome", (locale) => {
  it.each(SITE_SETS.map((supported) => ({ supported })))(
    "renders profile, contribution, claim and review in $supported order",
    ({ supported }) => {
      const state = siteState(supported);
      const profile = view(locale, state);
      for (const field of PROFILE_FIELDS) {
        expect(
          [
            ...profile.matchAll(
              new RegExp(
                `<textarea[^>]*id="guided-profile-${field}-([^"]+)"`,
                "g",
              ),
            ),
          ].map((match) => match[1]),
        ).toEqual(supported);
        for (const tag of supported) expect(profile).toContain(`lang="${tag}"`);
      }
      state.step = "contributions";
      const contributions = view(locale, state);
      for (const field of ["role", "summary"])
        expect(
          [
            ...contributions.matchAll(
              new RegExp(
                `id="guided-${field}-public-owner-another-project-([^"]+)"`,
                "g",
              ),
            ),
          ].map((match) => match[1]),
        ).toEqual(supported);
      const claim = renderToStaticMarkup(
        <ClaimEditor
          locale={locale}
          id="set-claim"
          kind="context"
          statement={state.repositories[0].proposal!.claims[0].statement}
          supported={supported}
          onChange={vi.fn()}
        />,
      );
      expect(
        [...claim.matchAll(/<textarea[^>]*id="set-claim-([^"]+)"/g)].map(
          (match) => match[1],
        ),
      ).toEqual(supported);
      for (const tag of supported) {
        expect(claim).toContain(`(${endonym(tag)})`);
        expect(claim).toContain(`lang="${tag}"`);
      }
      const incomplete = structuredClone(state);
      incomplete.repositories[0].confirmedContribution = null;
      incomplete.repositories[0].proposal!.claims[0].statement[
        supported[supported.length - 1]
      ] = "";
      const incompleteContribution = view(locale, incomplete);
      expect(incompleteContribution).toContain(
        chromeLocale(locale) === "en"
          ? "Complete the role, summary, and contribution descriptions in every site language before accepting."
          : "請完成所有網站語言的角色、摘要及貢獻描述後才能接受。",
      );
      expect(incompleteContribution).toMatch(
        /<button(?=[^>]*aria-describedby="guided-proposal-reason-public-owner-another-project")(?=[^>]*disabled="")[^>]*>/,
      );
      state.step = "review";
      const review = view(locale, state);
      expect(
        [...review.matchAll(/<dt>[^<(]*\(([^)]+)\)<\/dt>/g)].map(
          (match) => match[1],
        ),
      ).toEqual(
        supported.flatMap((tag) => PROFILE_FIELDS.map(() => endonym(tag))),
      );
      expect(
        [...review.matchAll(/class="ux-review-item" lang="([^"]+)"/g)].map(
          (match) => match[1],
        ),
      ).toEqual(supported);
    },
  );
});

it.each(LANGUAGES)(
  "starts new $tag drafts with the resolved locale and English when different",
  ({ tag }) => {
    const state = initialGuidedOnboardingState(false, tag);
    expect(state.locales).toEqual({
      default: tag,
      supported: [...new Set([tag, "en"])],
    });
    for (const field of PROFILE_FIELDS)
      expect(Object.keys(state.profile[field])).toEqual(
        state.locales.supported,
      );
  },
);

it.each(SITE_SETS.map((supported) => ({ supported })))(
  "requires every value and restores the exact $supported set",
  ({ supported }) => {
    const state = siteState(supported);
    expect(profileIsComplete(state.profile, supported)).toBe(true);
    expect(
      contributionIsComplete(state.repositories[0].proposal!, supported),
    ).toBe(true);
    for (const tag of supported) {
      for (const field of PROFILE_FIELDS) {
        const partial = structuredClone(state);
        partial.profile[field][tag] = " ";
        expect(() =>
          guidedOnboardingReducer(partial, { type: "CONFIRM_PROFILE" }),
        ).toThrow("ONBOARDING_PROFILE_REQUIRED");
      }
      for (const field of ["role", "summary", "claim"] as const) {
        const partial = structuredClone(state);
        const contribution = partial.repositories[0].proposal!;
        if (field === "claim") contribution.claims[0].statement[tag] = "";
        else contribution[field][tag] = "";
        partial.step = "contributions";
        expect(() =>
          guidedOnboardingReducer(partial, {
            type: "CONFIRM_CONTRIBUTION",
            slug: partial.repositories[0].metadata.slug,
            contribution,
          }),
        ).toThrow("ONBOARDING_BILINGUAL_CONTRIBUTION_REQUIRED");
      }
    }
    const restored = parseGuidedOnboarding(serializeGuidedOnboarding(state))!;
    expect(restored.locales).toEqual(state.locales);
    expect(restored.profile).toEqual(state.profile);
    const config = {
      locales: state.locales,
      profile: {
        display_name: state.profile.displayName,
        github_login: state.profile.githubLogin,
        headline: state.profile.headline,
        bio: state.profile.bio,
        greeting: state.profile.greeting,
      },
      repositories: state.repositories.map((repository) => ({
        slug: repository.metadata.slug,
        include: [],
        exclude: [],
        ...repository.confirmedContribution,
      })),
    };
    const loaded = guidedOnboardingFromConfig(config)!;
    expect(loaded.locales).toEqual(state.locales);
    expect(loaded.repositories[0].ownerStatement).toBe(
      state.repositories[0].confirmedContribution!.summary[
        state.locales.default
      ],
    );
    const invalid = structuredClone(config);
    delete (invalid.profile.bio as Partial<typeof invalid.profile.bio>)[
      supported[0]
    ];
    expect(guidedOnboardingFromConfig(invalid)).toBeNull();
  },
);

it.each(SITE_SETS.map((supported) => ({ supported })))(
  "sends exact suggest and draft request keys for $supported",
  async ({ supported }) => {
    const state = siteState(supported);
    const request = vi.fn().mockResolvedValue({});
    const signal = new AbortController().signal;
    await requestContributionSuggestion(
      request,
      state.repositories[0].metadata.slug,
      "A second owner phrasing",
      supported,
      signal,
    );
    expect(request).toHaveBeenLastCalledWith(
      "/api/admin/onboarding/contributions/suggest",
      {
        method: "POST",
        signal,
        body: JSON.stringify({
          slug: state.repositories[0].metadata.slug,
          owner_statement: "A second owner phrasing",
          locales: supported,
        }),
      },
    );
    const base = { retained: "public setting" };
    await requestOnboardingDraft(request, state, base);
    const [path, options] = request.mock.calls[1];
    expect(path).toBe("/api/admin/onboarding/draft");
    const body = JSON.parse(options.body);
    expect(body.locales).toEqual(state.locales);
    for (const field of PROFILE_FIELDS)
      expect(Object.keys(body.profile[field])).toEqual(supported);
    for (const field of ["role", "summary"])
      expect(Object.keys(body.repositories[0][field])).toEqual(supported);
    expect(Object.keys(body.repositories[0].claims[0].statement)).toEqual(
      supported,
    );
    expect(body.base_config).toEqual(base);
    expect(body.confirmed_assertions).toBe(true);
    expect(JSON.stringify(body)).not.toMatch(
      /previousText|translatedText|reviewed|method/,
    );
    const response = {
      slug: state.repositories[0].metadata.slug,
      original_statement: "A second owner phrasing",
      proposal: state.repositories[0].proposal!,
      confirmed: false,
    };
    expect(
      contributionSuggestionBody(
        response,
        response.slug,
        response.original_statement,
        supported,
      ),
    ).toEqual(response);
    const invalid = structuredClone(response);
    delete (
      invalid.proposal.summary as Partial<typeof invalid.proposal.summary>
    )[supported[0]];
    expect(
      contributionSuggestionBody(
        invalid,
        response.slug,
        response.original_statement,
        supported,
      ),
    ).toBeNull();
    const outside = LANGUAGES.find(({ tag }) => !supported.includes(tag));
    if (outside) {
      const extra = structuredClone(response);
      extra.proposal.role[outside.tag] = "Unexpected text";
      expect(
        contributionSuggestionBody(
          extra,
          response.slug,
          response.original_statement,
          supported,
        ),
      ).toBeNull();
    }
  },
);

it("resumes an unchanged phase A draft without a locales property", () => {
  const state = siteState(
    initialGuidedOnboardingState(false, "zh-TW").locales.supported,
  );
  const saved = JSON.parse(serializeGuidedOnboarding(state));
  delete saved.locales;
  const resumed = parseGuidedOnboarding(JSON.stringify(saved))!;
  expect(resumed.locales.supported).toEqual(state.locales.supported);
  expect(resumed.profile).toEqual(state.profile);
  expect(resumed.repositories[0].confirmedContribution).toEqual(
    state.repositories[0].confirmedContribution,
  );
});
