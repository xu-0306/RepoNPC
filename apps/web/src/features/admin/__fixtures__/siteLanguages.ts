import {
  LANGUAGES,
  matchLocale,
  type LanguageTag,
} from "../../../i18n/languages";
import {
  initialGuidedOnboardingState,
  localizedFor,
  type GuidedStep,
  type LocalizedText,
} from "../guidedOnboarding";

const tags = LANGUAGES.map(({ tag }) => tag);
const matched = (browser: string) => matchLocale([browser], tags, tags[0]);
const traditional = matched("zh-Hant");
const simplified = matched("zh-Hans");
const english = matched("en");
const spanish = matched("es");

export const SITE_SETS: LanguageTag[][] = [
  ...new Map(
    [
      initialGuidedOnboardingState(false, traditional).locales.supported,
      [english],
      [spanish],
      [simplified, english],
      tags,
      [...tags.slice(2), ...tags.slice(0, 2)],
      ...tags.map((tag) => [tag]),
    ].map((site) => [site.join(","), site]),
  ).values(),
];

export const ADMIN_CHROMES = [
  ...new Set(LANGUAGES.map((language) => language.chrome)),
];

export function textFor(
  supported: readonly LanguageTag[],
  field: string,
): LocalizedText {
  return Object.fromEntries(
    supported.map((tag) => [tag, `${field} ${tag}`]),
  ) as LocalizedText;
}

export function siteState(
  supported: LanguageTag[],
  step: GuidedStep = "profile",
) {
  const state = initialGuidedOnboardingState(false, supported[0]);
  state.locales = {
    default: supported[supported.length - 1],
    supported: [...supported],
  };
  state.step = step;
  state.selectionConfirmed = true;
  state.profile = {
    displayName: "Public owner",
    githubLogin: "public-owner",
    aliasesText: "",
    headline: textFor(supported, "headline"),
    bio: textFor(supported, "bio"),
    greeting: textFor(supported, "greeting"),
  };
  const contribution = {
    role: textFor(supported, "role"),
    summary: textFor(supported, "summary"),
    claims: [
      {
        id: "other_claim",
        kind: "context" as const,
        statement: textFor(supported, "statement"),
      },
    ],
  };
  state.repositories = [
    {
      metadata: {
        slug: "public-owner/another-project",
        name: "another-project",
        description: null,
        primary_language: null,
        default_branch: "main",
        is_fork: false,
        is_archived: false,
        updated_at: null,
        html_url: "https://github.com/public-owner/another-project",
      },
      ref: null,
      include: [],
      exclude: [],
      selected: true,
      confirmedSelectionFingerprint: null,
      analysisStatus: "idle",
      analysis: null,
      ownerStatement: "Owner's original text",
      proposal: contribution,
      proposalSource: "manual",
      previousContribution: null,
      confirmedContribution: {
        ...contribution,
        evidence_class: "OWNER_ASSERTION",
      },
    },
  ];
  return state;
}

export function blankSiteState(supported: LanguageTag[]) {
  const state = siteState(supported);
  for (const field of ["headline", "bio", "greeting"] as const)
    state.profile[field] = localizedFor(supported);
  state.repositories = [];
  return state;
}
