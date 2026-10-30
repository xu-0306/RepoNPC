import { describe, expect, it } from "vitest";

import {
  formatRepositorySize,
  guidedErrorMessage,
  guidedOnboardingFromConfig,
  guidedOnboardingReducer,
  initialGuidedOnboardingState,
  parseGuidedOnboarding,
  serializeGuidedOnboarding,
  type ContributionProposal,
  type GuidedOnboardingState,
  type RepositoryAnalysis,
  type RepositoryMetadata,
} from "./guidedOnboarding";

describe("repository size", () => {
  it.each([
    [0, "0 KB"],
    [1023, "1023 KB"],
    [1024, "1 MB"],
    [1229, "1.2 MB"],
    [1536, "1.5 MB"],
    [2048, "2 MB"],
    [1048575, "1024 MB"],
    [1048576, "1 GB"],
    [1572864, "1.5 GB"],
    [null, null],
    [undefined, null],
  ])("formats %s KB as %s", (size, expected) => {
    expect(formatRepositorySize(size)).toBe(expected);
  });

  it.each([undefined, null, 0, 1536, 1.5])(
    "resumes optional size %s without dropping it",
    (size) => {
      const saved = JSON.parse(serializeGuidedOnboarding(selectedState()));
      if (size !== undefined) saved.repositories[0].metadata.size_kb = size;
      const resumed = parseGuidedOnboarding(JSON.stringify(saved));
      expect(resumed).not.toBeNull();
      expect(resumed?.repositories[0].metadata.size_kb).toBe(size);
    },
  );

  it.each(["1536", true, -1])("rejects invalid saved size %s", (size) => {
    const saved = JSON.parse(serializeGuidedOnboarding(selectedState()));
    saved.repositories[0].metadata.size_kb = size;
    expect(parseGuidedOnboarding(JSON.stringify(saved))).toBeNull();
  });

  it("rejects a non-finite size parsed from a numeric JSON literal", () => {
    const saved = JSON.parse(serializeGuidedOnboarding(selectedState()));
    saved.repositories[0].metadata.size_kb = 1536;
    const content = JSON.stringify(saved).replace(
      '"size_kb":1536',
      '"size_kb":1e400',
    );
    expect(parseGuidedOnboarding(content)).toBeNull();
  });
});

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
    expect(guidedErrorMessage("en", "CONFIG_INVALID")).toContain(
      "configuration is invalid",
    );
    expect(guidedErrorMessage("en", "CONTRIBUTION_CONTEXT_INVALID")).toContain(
      "context space",
    );
  });
});

describe("guided onboarding config hydration", () => {
  it("opens a gap statement without discarding saved claims or unrelated edits", () => {
    const selected = guidedOnboardingReducer(selectedState(), {
      type: "CONFIRM_SELECTION",
    });
    const original: GuidedOnboardingState = {
      ...selected,
      profile: { ...profile, displayName: "Unsaved owner edit" },
      repositories: selected.repositories.map((repository) => ({
        ...repository,
        proposal: {
          ...proposal,
          claims: [
            {
              id: "faq_saved",
              kind: "context" as const,
              statement: {
                "zh-TW": "已保存的新自述",
                en: "Saved rewritten statement",
              },
            },
          ],
        },
      })),
    };
    original.repositories.push({
      ...original.repositories[0],
      metadata: { ...metadata, slug: "octocat/other" },
      proposal: {
        ...proposal,
        summary: { "zh-TW": "未儲存編輯", en: "Unrelated unsaved edit" },
      },
    });
    const next = guidedOnboardingReducer(original, {
      type: "OPEN_CLAIM_EDITOR",
      slug: metadata.slug,
      kind: "achievement",
    });
    expect(next.step).toBe("contributions");
    expect(next.profile).toBe(original.profile);
    expect(next.repositories[1]).toBe(original.repositories[1]);
    expect(next.repositories[0].proposal?.claims[0]).toEqual(
      original.repositories[0].proposal?.claims[0],
    );
    expect(next.repositories[0].proposal?.claims[1].kind).toBe("achievement");
    expect(next.repositories[0].confirmedContribution).toBeNull();
  });
  it("maps an existing validated config into editable profile and contributions", () => {
    const state = guidedOnboardingFromConfig({
      profile: {
        display_name: "Existing owner",
        github_login: "octocat",
        aliases: ["Ada"],
        headline: { "zh-TW": "既有標題", en: "Existing headline" },
        bio: { "zh-TW": "既有簡介", en: "Existing bio" },
        greeting: { "zh-TW": "你好", en: "Hello" },
      },
      repositories: [
        {
          slug: "octocat/demo",
          enabled: true,
          ref: "a".repeat(40),
          include: ["src/**"],
          exclude: ["node_modules/**"],
          role: { "zh-TW": "維護者", en: "Maintainer" },
          summary: { "zh-TW": "維護專案", en: "Maintained project" },
          claims: [],
        },
      ],
    });
    expect(state?.step).toBe("profile");
    expect(state?.profile.greeting.en).toBe("Hello");
    expect(state?.profile.githubLogin).toBe("octocat");
    expect(state?.profile.aliasesText).toBe("Ada");
    expect(state?.repositories[0].confirmedContribution?.role.en).toBe(
      "Maintainer",
    );
    expect(state?.repositories[0].proposal?.role.en).toBe("Maintainer");
    expect(state?.repositories[0].include).toEqual(["src/**"]);
  });
});

it("prefills the confirmed login from the discovered account without replacing an edit", () => {
  const initial = guidedOnboardingReducer(initialGuidedOnboardingState(), {
    type: "START_MANUAL",
  });
  const discovered = guidedOnboardingReducer(initial, {
    type: "SET_ACCOUNT",
    account: "octocat",
  });
  expect(discovered.profile.githubLogin).toBe("octocat");
  const edited = guidedOnboardingReducer(
    {
      ...discovered,
      profile: { ...discovered.profile, githubLogin: "real-owner" },
    },
    { type: "SET_ACCOUNT", account: "someone-else" },
  );
  expect(edited.profile.githubLogin).toBe("real-owner");
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

describe("discovery account changes", () => {
  it("restarts pagination while preserving explicitly collected projects", () => {
    const original = guidedOnboardingReducer(
      {
        ...initialGuidedOnboardingState(),
        step: "repositories",
        githubAccount: "first-account",
      },
      {
        type: "MERGE_REPOSITORIES",
        repositories: [metadata],
        page: 5,
        hasMore: false,
      },
    );
    const next = guidedOnboardingReducer(original, {
      type: "SET_ACCOUNT",
      account: "second-account",
    });
    expect(next.discoveryPage).toBe(0);
    expect(next.discoveryHasMore).toBe(true);
    expect(next.repositories).toBe(original.repositories);
    expect(
      guidedOnboardingReducer(original, {
        type: "SET_ACCOUNT",
        account: "first-account",
      }),
    ).toBe(original);
  });
});

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
  githubLogin: "octocat",
  aliasesText: "",
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
  it.each(["octocat/demo", "somebody/different-project"])(
    "refuses archived repository toggles using metadata for %s",
    (slug) => {
      const initial = selectedState();
      const archived = {
        ...initial,
        repositories: initial.repositories.map((repository) => ({
          ...repository,
          selected: false,
          metadata: { ...repository.metadata, slug, is_archived: true },
        })),
      };
      expect(
        guidedOnboardingReducer(archived, { type: "TOGGLE_REPOSITORY", slug }),
      ).toEqual(archived);
      expect(
        guidedOnboardingReducer(initial, {
          type: "TOGGLE_REPOSITORY",
          slug: metadata.slug,
        }).repositories[0].selected,
      ).toBe(false);
    },
  );

  it("drops archived restored selections on confirm and rejects an archived-only selection", () => {
    const initial = selectedState();
    const archived = {
      ...initial.repositories[0],
      metadata: {
        ...metadata,
        slug: "someone/archived",
        html_url: "https://github.com/someone/archived",
        is_archived: true,
      },
    };
    const restored = {
      ...initial,
      repositories: [...initial.repositories, archived],
    };
    const confirmed = guidedOnboardingReducer(restored, {
      type: "CONFIRM_SELECTION",
    });
    expect(confirmed.selectionConfirmed).toBe(true);
    expect(confirmed.repositories[0].selected).toBe(true);
    expect(confirmed.repositories[1].selected).toBe(false);
    expect(confirmed.repositories[1].confirmedSelectionFingerprint).toBeNull();
    expect(() =>
      guidedOnboardingReducer(
        { ...initial, repositories: [archived] },
        { type: "CONFIRM_SELECTION" },
      ),
    ).toThrow("ONBOARDING_SELECTION_REQUIRED");
    const resumed = guidedOnboardingReducer(initialGuidedOnboardingState(), {
      type: "RESTORE_DRAFT",
      state: restored,
    });
    expect(resumed.repositories[1].selected).toBe(false);
    const legacy = serializeGuidedOnboarding({
      ...restored,
      repositories: restored.repositories.map((repository) => ({
        ...repository,
        metadata: { ...repository.metadata, is_archived: false },
      })),
    });
    const parsed = parseGuidedOnboarding(legacy, [metadata, archived.metadata]);
    expect(parsed?.repositories[1].selected).toBe(false);
    expect(parsed?.repositories[1].confirmedSelectionFingerprint).toBeNull();
  });

  it("drops a selected repository when discovery marks it archived", () => {
    const next = guidedOnboardingReducer(selectedState(), {
      type: "MERGE_REPOSITORIES",
      repositories: [{ ...metadata, is_archived: true }],
      page: 1,
      hasMore: false,
    });
    expect(next.repositories[0].selected).toBe(false);
  });
  it.each([true, false])(
    "restores a draft without overwriting server readiness %s in either response order",
    (modelsConfigured) => {
      const draft = { ...selectedState(), modelsConfigured: !modelsConfigured };
      const initial = initialGuidedOnboardingState();
      const serverUpdate = {
        type: "SET_MODELS_CONFIGURED",
        value: modelsConfigured,
      } as const;
      const restore = { type: "RESTORE_DRAFT", state: draft } as const;
      const serverFirst = guidedOnboardingReducer(
        guidedOnboardingReducer(initial, serverUpdate),
        restore,
      );
      const draftFirst = guidedOnboardingReducer(
        guidedOnboardingReducer(initial, restore),
        serverUpdate,
      );
      expect(serverFirst).toEqual({ ...draft, modelsConfigured });
      expect(draftFirst).toEqual(serverFirst);
    },
  );

  it.each([true, false])(
    "resets the draft while preserving server model readiness %s",
    (modelsConfigured) => {
      const configured = guidedOnboardingReducer(selectedState(), {
        type: "SET_MODELS_CONFIGURED",
        value: modelsConfigured,
      });
      const reset = guidedOnboardingReducer(configured, { type: "RESET" });
      expect(reset).toEqual({
        ...initialGuidedOnboardingState(),
        modelsConfigured,
      });
      const restarted = guidedOnboardingReducer(reset, { type: "START_AI" });
      expect(restarted.step).toBe("models");
      if (modelsConfigured) {
        expect(
          guidedOnboardingReducer(restarted, { type: "COMPLETE_MODEL_SETUP" })
            .step,
        ).toBe("repositories");
      } else {
        expect(() =>
          guidedOnboardingReducer(restarted, { type: "COMPLETE_MODEL_SETUP" }),
        ).toThrow("ONBOARDING_MODELS_REQUIRED");
      }
    },
  );

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
    state = guidedOnboardingReducer(state, {
      type: "SET_CONTRIBUTION_PROPOSAL",
      slug: metadata.slug,
      originalStatement: "I maintained the parser with another contributor.",
      proposal: {
        ...proposal,
        summary: {
          "zh-TW": "再次編輯的摘要",
          en: "An edited summary",
        },
      },
    });
    expect(state.repositories[0].proposal?.summary.en).toBe(
      "An edited summary",
    );
    expect(state.repositories[0].confirmedContribution).toBeNull();
    expect(state.repositories[0].previousContribution?.summary.en).toBe(
      "Co-maintained the public parser",
    );
    state = guidedOnboardingReducer(state, {
      type: "RESTORE_PREVIOUS_CONTRIBUTION",
      slug: metadata.slug,
    });
    expect(state.repositories[0].proposal?.summary.en).toBe(
      "Co-maintained the public parser",
    );
    expect(state.repositories[0].confirmedContribution).toBeNull();
    state = guidedOnboardingReducer(state, {
      type: "SET_CONTRIBUTION_PROPOSAL",
      slug: metadata.slug,
      originalStatement: "I maintained the parser with another contributor.",
      proposal: {
        ...proposal,
        summary: {
          "zh-TW": "再次編輯的摘要",
          en: "An edited summary",
        },
      },
    });
    expect(() =>
      guidedOnboardingReducer(state, { type: "CONTINUE_TO_PROFILE" }),
    ).toThrow("ONBOARDING_CONFIRMATION_REQUIRED");
    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: metadata.slug,
      contribution: state.repositories[0].proposal!,
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: metadata.slug,
      statement: "I assisted with the parser after the scope changed.",
    });
    expect(state.repositories[0].confirmedContribution).toBeNull();
    expect(state.repositories[0].proposal?.summary.en).toBe(
      "An edited summary",
    );
    expect(() =>
      guidedOnboardingReducer(state, { type: "CONTINUE_TO_PROFILE" }),
    ).toThrow("ONBOARDING_CONFIRMATION_REQUIRED");
    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: metadata.slug,
      contribution: state.repositories[0].proposal!,
    });
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

  it("allows manual contribution before preflight or an analysis failure", () => {
    let state = guidedOnboardingReducer(selectedState(), {
      type: "CONFIRM_SELECTION",
    });

    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });

    expect(state.step).toBe("contributions");
    expect(state.repositories[0].analysisStatus).toBe("idle");
  });

  it("unlocks manual repository editing without discarding contribution data", () => {
    let state = guidedOnboardingReducer(
      { ...initialGuidedOnboardingState(), profile },
      { type: "START_MANUAL" },
    );
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
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: metadata.slug,
      statement: "I maintained the parser.",
    });
    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: metadata.slug,
      contribution: proposal,
    });
    const beforeBack = state;

    state = guidedOnboardingReducer(state, { type: "GO_BACK" });

    expect(state.step).toBe("repositories");
    expect(state.selectionConfirmed).toBe(false);
    expect(state.profile).toEqual(beforeBack.profile);
    expect(state.repositories).toEqual(beforeBack.repositories);
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: metadata.slug,
    });
    expect(state.repositories[0].selected).toBe(false);
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: metadata.slug,
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_REPOSITORY_OPTIONS",
      slug: metadata.slug,
      ref: "release",
      include: [],
      exclude: [],
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });

    expect(state.repositories[0].ownerStatement).toBe("");
    expect(state.repositories[0].confirmedContribution).toBeNull();
  });

  it("edits selection without discarding unaffected owner work", () => {
    const other: RepositoryMetadata = {
      ...metadata,
      slug: "octocat/other",
      name: "other",
      html_url: "https://github.com/octocat/other",
    };
    let state = selectedState();
    state = guidedOnboardingReducer(state, {
      type: "ADD_REPOSITORY",
      repository: other,
    });
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: other.slug,
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });
    for (const repository of [metadata, other]) {
      state = guidedOnboardingReducer(state, {
        type: "SET_OWNER_STATEMENT",
        slug: repository.slug,
        statement: `Statement for ${repository.slug}`,
      });
      state = guidedOnboardingReducer(state, {
        type: "CONFIRM_CONTRIBUTION",
        slug: repository.slug,
        contribution: proposal,
      });
    }

    state = guidedOnboardingReducer(state, { type: "EDIT_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "SET_REPOSITORY_OPTIONS",
      slug: other.slug,
      ref: "release",
      include: [],
      exclude: [],
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });

    const unchanged = state.repositories.find(
      (repository) => repository.metadata.slug === metadata.slug,
    );
    const changed = state.repositories.find(
      (repository) => repository.metadata.slug === other.slug,
    );
    expect(unchanged?.ownerStatement).toBe(`Statement for ${metadata.slug}`);
    expect(unchanged?.confirmedContribution).not.toBeNull();
    expect(changed?.ownerStatement).toBe("");
    expect(changed?.confirmedContribution).toBeNull();
    expect(changed?.analysisStatus).toBe("idle");
  });

  it("does not restore stale work after a repository is removed and reselected", () => {
    const other: RepositoryMetadata = {
      ...metadata,
      slug: "octocat/other",
      name: "other",
      html_url: "https://github.com/octocat/other",
    };
    let state = selectedState();
    state = guidedOnboardingReducer(state, {
      type: "ADD_REPOSITORY",
      repository: other,
    });
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: other.slug,
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "CONTINUE_TO_CONTRIBUTIONS",
    });
    state = guidedOnboardingReducer(state, {
      type: "SET_OWNER_STATEMENT",
      slug: other.slug,
      statement: "Stale statement",
    });
    state = guidedOnboardingReducer(state, {
      type: "CONFIRM_CONTRIBUTION",
      slug: other.slug,
      contribution: proposal,
    });

    state = guidedOnboardingReducer(state, { type: "EDIT_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: other.slug,
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });
    state = guidedOnboardingReducer(state, { type: "EDIT_SELECTION" });
    state = guidedOnboardingReducer(state, {
      type: "TOGGLE_REPOSITORY",
      slug: other.slug,
    });
    state = guidedOnboardingReducer(state, { type: "CONFIRM_SELECTION" });

    const reselected = state.repositories.find(
      (repository) => repository.metadata.slug === other.slug,
    );
    expect(reselected?.ownerStatement).toBe("");
    expect(reselected?.confirmedContribution).toBeNull();
    expect(reselected?.analysisStatus).toBe("idle");
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
            url: "https://github.com/octocat/demo/blob/CANARY-RAW-REPOSITORY-BODY/README.md#L1",
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
    expect(resumed?.repositories[0].proposal?.role.en).toBe("Co-maintainer");
    expect(resumed?.repositories[0].previousContribution).toBeNull();
    const editing = guidedOnboardingReducer(
      { ...resumed!, step: "contributions" },
      { type: "EDIT_CONFIRMED_CONTRIBUTION", slug: metadata.slug },
    );
    expect(editing.repositories[0].confirmedContribution).toBeNull();
    expect(editing.repositories[0].proposal?.role.en).toBe("Co-maintainer");
    expect(editing.repositories[0].previousContribution?.role.en).toBe(
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

it("tracks manual/model origin without bypassing confirmation or persisting model drafts", () => {
  let current: GuidedOnboardingState = {
    ...guidedOnboardingReducer(selectedState(), { type: "CONFIRM_SELECTION" }),
    step: "contributions" as const,
  };
  current = guidedOnboardingReducer(current, {
    type: "SET_OWNER_STATEMENT",
    slug: metadata.slug,
    statement: "Original owner statement",
  });
  current = guidedOnboardingReducer(current, {
    type: "BEGIN_MANUAL_CONTRIBUTION",
    slug: metadata.slug,
  });
  expect(current.repositories[0].proposalSource).toBe("manual");
  expect(current.repositories[0].confirmedContribution).toBeNull();
  current = guidedOnboardingReducer(current, {
    type: "SET_CONTRIBUTION_PROPOSAL",
    slug: metadata.slug,
    originalStatement: "Original owner statement",
    proposal,
  });
  expect(current.repositories[0].proposalSource).toBe("model");
  expect(current.repositories[0].confirmedContribution).toBeNull();
  expect(serializeGuidedOnboarding(current)).not.toContain("proposalSource");
  current = guidedOnboardingReducer(current, {
    type: "CONFIRM_CONTRIBUTION",
    slug: metadata.slug,
    contribution: proposal,
  });
  current = guidedOnboardingReducer(current, {
    type: "EDIT_CONFIRMED_CONTRIBUTION",
    slug: metadata.slug,
  });
  expect(current.repositories[0].proposalSource).toBe("manual");
  expect(current.repositories[0].confirmedContribution).toBeNull();
});

it.each(["COMPLETE_MODEL_SETUP", "GO_BACK", "START_MANUAL"] as const)(
  "preserves the prepared draft state through model setup %s",
  (type) => {
    const original: GuidedOnboardingState = {
      ...selectedState(),
      step: "draft",
      route: "manual",
      profile,
      profileConfirmed: true,
    };
    const editing = guidedOnboardingReducer(original, {
      type: "OPEN_PUBLICATION_MODEL_SETUP",
    });
    expect(editing.step).toBe("models");
    expect(editing.route).toBe("ai");
    expect(editing.repositories).toBe(original.repositories);
    expect(editing.profile).toBe(original.profile);
    expect(serializeGuidedOnboarding(editing)).not.toContain(
      "modelSetupReturn",
    );
    expect(
      parseGuidedOnboarding(serializeGuidedOnboarding(editing))?.step,
    ).toBe("draft");
    expect(
      parseGuidedOnboarding(serializeGuidedOnboarding(editing))?.route,
    ).toBe("manual");
    expect(() =>
      guidedOnboardingReducer(editing, { type: "COMPLETE_MODEL_SETUP" }),
    ).toThrow("ONBOARDING_MODELS_REQUIRED");
    const configured = guidedOnboardingReducer(editing, {
      type: "SET_MODELS_CONFIGURED",
      value: true,
    });
    const returned = guidedOnboardingReducer(configured, { type });
    expect(returned).toEqual({
      ...original,
      modelsConfigured: true,
      modelSetupReturn: undefined,
    });
  },
);

describe("guided draft recovery", () => {
  it.each(["zh-TW", "en"] as const)(
    "distinguishes service, input and connection failures in %s",
    (locale) => {
      const zh = locale === "zh-TW";
      const service = guidedErrorMessage(locale, "SERVICE_NOT_READY", "review");
      expect(service).toContain(
        zh ? "草稿建立服務尚未就緒" : "draft creation service is not ready",
      );
      expect(service).toContain(zh ? "維護" : "Maintenance");
      expect(service).not.toContain(zh ? "回報" : "report");
      expect(service).toContain(
        zh ? "重試建立草稿" : "retry creating the draft",
      );
      expect(service).not.toContain(zh ? "設定模型" : "Set up models");
      for (const code of ["VALIDATION_ERROR", "CONFIG_INVALID"]) {
        const message = guidedErrorMessage(locale, code, "review");
        expect(message).toContain(zh ? "確認狀態" : "confirmations");
        expect(message).toContain(zh ? "輸入仍保留" : "input is kept");
        expect(message).not.toContain("https://github.com/username");
      }
      expect(
        guidedErrorMessage(locale, "VALIDATION_ERROR", "repositories"),
      ).toContain("https://github.com/username");
      expect(guidedErrorMessage(locale, "REQUEST_FAILED", "review")).toContain(
        zh ? "網路連線" : "network connection",
      );
      const provider = guidedErrorMessage(locale, "PROVIDER_ERROR");
      expect(provider).not.toContain(zh ? "本機服務" : "local service");
      expect(provider).toContain(
        zh ? "模型沒有回傳可用的結果" : "model did not",
      );
      expect(provider).toContain(zh ? "輸入已保留" : "input is preserved");
      expect(provider).not.toContain(zh ? "無法確認原因" : "cause is unknown");
      const unknown = guidedErrorMessage(
        locale,
        "private-response-canary",
        "review",
      );
      expect(unknown).toContain(zh ? "無法確認原因" : "cause is unknown");
      expect(unknown).not.toContain("private-response-canary");
      expect(unknown).toContain(zh ? "維護" : "Maintenance");
      expect(unknown).not.toContain(zh ? "回報" : "report");
      expect(unknown).not.toContain(zh ? "請檢查內容" : "Review it");
    },
  );
});
