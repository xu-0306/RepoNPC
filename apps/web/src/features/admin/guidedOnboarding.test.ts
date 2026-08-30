import { describe, expect, it } from "vitest";

import {
  guidedErrorMessage,
  guidedOnboardingReducer,
  initialGuidedOnboardingState,
  parseGuidedOnboarding,
  serializeGuidedOnboarding,
  type ContributionProposal,
  type RepositoryAnalysis,
  type RepositoryMetadata,
} from "./guidedOnboarding";

describe("guided onboarding errors", () => {
  it("explains GitHub connectivity and input failures without a generic fallback", () => {
    expect(guidedErrorMessage("zh-TW", "GITHUB_ERROR")).toContain(
      "無法連線 GitHub",
    );
    expect(guidedErrorMessage("en", "GITHUB_ERROR")).toContain(
      "GitHub could not be reached",
    );
    expect(guidedErrorMessage("zh-TW", "VALIDATION_ERROR")).toContain(
      "格式無效",
    );
  });
});

const metadata: RepositoryMetadata = {
  slug: "octocat/demo",
  name: "demo",
  description: "Public demo",
  primary_language: "TypeScript",
  default_branch: "main",
  is_fork: false,
  is_archived: false,
  updated_at: "2026-08-14T00:00:00Z",
  html_url: "https://github.com/octocat/demo",
};

const proposal: ContributionProposal = {
  role: { "zh-TW": "共同維護者", en: "Co-maintainer" },
  summary: { "zh-TW": "維護公開模組", en: "Maintained public modules" },
  claims: [
    {
      id: "parser_work",
      kind: "responsibility",
      statement: { "zh-TW": "維護解析器", en: "Maintained the parser" },
    },
  ],
};

const analysis: RepositoryAnalysis = {
  repository: {
    slug: metadata.slug,
    commit_sha: "a".repeat(40),
    default_branch: "main",
    html_url: metadata.html_url,
  },
  facts: [],
  inferences: [],
  skipped_summary: { count: 0, reasons: [] },
};

const profile = {
  displayName: "Example Developer",
  headline: { "zh-TW": "打造可靠系統", en: "Building reliable systems" },
  bio: { "zh-TW": "專注於開發者工具。", en: "Focused on developer tooling." },
  greeting: {
    "zh-TW": "嗨，我是你的 RepoNPC。",
    en: "Hi, I am your RepoNPC.",
  },
};

function selectedState() {
  let state = guidedOnboardingReducer(initialGuidedOnboardingState(), {
    type: "START",
  });
  state = guidedOnboardingReducer(state, {
    type: "MERGE_REPOSITORIES",
    repositories: [metadata],
    page: 1,
    hasMore: false,
  });
  state = guidedOnboardingReducer(state, {
    type: "TOGGLE_REPOSITORY",
    slug: metadata.slug,
  });
  return state;
}

describe("guidedOnboardingReducer", () => {
  it("requires explicit selection confirmation before analysis", () => {
    const unconfirmed = selectedState();

    expect(() =>
      guidedOnboardingReducer(unconfirmed, {
        type: "ANALYSIS_STARTED",
        slug: metadata.slug,
      }),
    ).toThrow("ONBOARDING_ILLEGAL_TRANSITION");

    const confirmed = guidedOnboardingReducer(unconfirmed, {
      type: "CONFIRM_SELECTION",
    });
    const running = guidedOnboardingReducer(confirmed, {
      type: "ANALYSIS_STARTED",
      slug: metadata.slug,
    });
    const complete = guidedOnboardingReducer(running, {
      type: "ANALYSIS_COMPLETED",
      slug: metadata.slug,
      analysis,
    });

    expect(complete.repositories[0].analysisStatus).toBe("complete");
    expect(
      complete.repositories[0].analysis?.repository.commit_sha,
    ).toHaveLength(40);
  });

  it("keeps proposals unconfirmed until the owner explicitly confirms edited text", () => {
    let state = guidedOnboardingReducer(selectedState(), {
      type: "CONFIRM_SELECTION",
    });
    state = guidedOnboardingReducer(state, {
      type: "ANALYSIS_UNAVAILABLE",
      slug: metadata.slug,
    });
    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: metadata.slug,
      statement: "I maintained the parser with another contributor.",
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_CONTRIBUTION_PROPOSAL",
      slug: metadata.slug,
      originalStatement: "I maintained the parser with another contributor.",
      proposal,
    });

    expect(state.repositories[0].proposal).toEqual(proposal);
    expect(state.repositories[0].confirmedContribution).toBeNull();
    expect(() =>
      guidedOnboardingReducer(state, { type: "CONTINUE_TO_PROFILE" }),
    ).toThrow("ONBOARDING_CONFIRMATION_REQUIRED");

    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: metadata.slug,
      contribution: {
        ...proposal,
        summary: {
          "zh-TW": "共同維護公開解析器",
          en: "Co-maintained the public parser",
        },
      },
    });

    expect(state.repositories[0].confirmedContribution?.evidence_class).toBe(
      "OWNER_ASSERTION",
    );
    state = guidedOnboardingReducer(state, { type: "CONTINUE_TO_PROFILE" });
    state = guidedOnboardingReducer(state, { type: "SET_PROFILE", profile });
    expect(
      guidedOnboardingReducer(state, { type: "CONFIRM_PROFILE" }).step,
    ).toBe("review");
  });

  it("supports a manual contribution after analysis or model unavailability", () => {
    let state = guidedOnboardingReducer(selectedState(), {
      type: "CONFIRM_SELECTION",
    });
    state = guidedOnboardingReducer(state, {
      type: "ANALYSIS_UNAVAILABLE",
      slug: metadata.slug,
    });
    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: metadata.slug,
      statement: "Public manual statement",
    });
    state = guidedOnboardingReducer(state, {
      type: "BEGIN_MANUAL_CONTRIBUTION",
      slug: metadata.slug,
    });

    expect(state.repositories[0].proposal).toEqual({
      role: { "zh-TW": "", en: "" },
      summary: { "zh-TW": "", en: "" },
      claims: [],
    });
    expect(state.repositories[0].confirmedContribution).toBeNull();
  });

  it("keeps an unmapped raw YAML edit in advanced mode", () => {
    let state = initialGuidedOnboardingState(true);
    state = guidedOnboardingReducer(state, {
      type: "MARK_RAW_YAML_UNMAPPED",
      value: true,
    });

    expect(state.mode).toBe("advanced");
    expect(() =>
      guidedOnboardingReducer(state, { type: "SET_MODE", mode: "guided" }),
    ).toThrow("ONBOARDING_RAW_YAML_UNMAPPED");
  });
});

describe("guided onboarding resume data", () => {
  it("persists only selected public draft fields and confirmed assertions", () => {
    let state = guidedOnboardingReducer(selectedState(), {
      type: "CONFIRM_SELECTION",
    });
    state = guidedOnboardingReducer(state, {
      type: "ANALYSIS_COMPLETED",
      slug: metadata.slug,
      analysis: {
        ...analysis,
        facts: [
          {
            evidence_class: "REPOSITORY_FACT",
            evidence_id: "E_secret",
            path: "README.md",
            start_line: 1,
            end_line: 1,
            text: "CANARY-RAW-REPOSITORY-BODY",
          },
        ],
      },
    });
    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: metadata.slug,
      statement: "Public owner statement",
    });
    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: metadata.slug,
      contribution: proposal,
    });
    state = guidedOnboardingReducer(state, { type: "CONTINUE_TO_PROFILE" });
    state = guidedOnboardingReducer(state, { type: "SET_PROFILE", profile });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_PROFILE" });

    const serialized = serializeGuidedOnboarding(state);

    expect(serialized).toContain("Public owner statement");
    expect(serialized).toContain("OWNER_ASSERTION");
    expect(serialized).not.toContain("CANARY-RAW-REPOSITORY-BODY");
    expect(serialized).not.toContain("facts");
    expect(serialized).not.toContain("proposal");

    const resumed = parseGuidedOnboarding(serialized, [metadata]);
    expect(resumed?.repositories[0].analysis).toBeNull();
    expect(resumed?.repositories[0].confirmedContribution?.role.en).toBe(
      "Co-maintainer",
    );
  });

  it("fails closed for malformed or unknown repository resume payloads", () => {
    expect(parseGuidedOnboarding("not-json", [metadata])).toBeNull();
    expect(
      parseGuidedOnboarding(
        JSON.stringify({
          version: 1,
          step: "draft",
          githubAccount: "octocat",
          discoveryPage: 1,
          discoveryHasMore: false,
          selectionConfirmed: true,
          profile,
          profileConfirmed: true,
          repositories: [
            {
              slug: "unknown/private",
              metadata: {
                ...metadata,
                slug: "unknown/private",
                html_url: "https://github.com/unknown/private",
              },
              ref: null,
              include: [],
              exclude: [],
              ownerStatement: "secret",
              confirmedContribution: null,
            },
          ],
        }),
        [metadata],
      ),
    ).toBeNull();
  });
});
