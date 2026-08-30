import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  initialGuidedOnboardingState,
  type ContributionProposal,
  type GuidedOnboardingState,
  type GuidedOnboardingViewProps,
  type GuidedProfile,
  type GuidedRepository,
  type RepositoryAnalysis,
  type RepositoryMetadata,
} from "./guidedOnboarding";
import { GuidedOnboardingView } from "./GuidedOnboardingView";

const metadata: RepositoryMetadata = {
  slug: "octocat/demo",
  name: "demo",
  description: "A public demonstration repository.",
  primary_language: "TypeScript",
  default_branch: "main",
  is_fork: false,
  is_archived: false,
  updated_at: "2026-08-14T00:00:00Z",
  html_url: "https://github.com/octocat/demo",
};

const profile: GuidedProfile = {
  displayName: "Ada Lovelace",
  headline: { "zh-TW": "證據導向的建造者", en: "Evidence-led builder" },
  bio: {
    "zh-TW": "用清楚的證據分享作品。",
    en: "Sharing work with clear evidence.",
  },
  greeting: { "zh-TW": "歡迎探索我的作品。", en: "Welcome to my projects." },
};

const proposal: ContributionProposal = {
  role: { "zh-TW": "共同維護者", en: "Co-maintainer" },
  summary: { "zh-TW": "維護公開 parser", en: "Maintained the public parser" },
  claims: [
    {
      id: "parser-work",
      kind: "responsibility",
      statement: { "zh-TW": "維護 parser", en: "Maintained the parser" },
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
  facts: [
    {
      evidence_class: "REPOSITORY_FACT",
      evidence_id: "E_fact_1",
      path: "src/parser.ts",
      start_line: 4,
      end_line: 12,
      text: "export function parse(input: string)",
    },
  ],
  inferences: [
    {
      evidence_class: "MODEL_INFERENCE",
      statement: {
        "zh-TW": "這個 repository 可能提供可重用的 parser。",
        en: "The repository may provide a reusable parser.",
      },
      supporting_evidence_ids: ["E_fact_1"],
    },
  ],
  skipped_summary: { count: 1, reasons: ["binary"] },
};

function repository(
  overrides: Partial<GuidedRepository> = {},
): GuidedRepository {
  return {
    metadata,
    ref: null,
    include: [],
    exclude: [],
    selected: true,
    analysisStatus: "complete",
    analysis,
    ownerStatement: "I maintained the parser with another contributor.",
    proposal,
    confirmedContribution: null,
    ...overrides,
  };
}

function state(
  overrides: Partial<GuidedOnboardingState> = {},
): GuidedOnboardingState {
  return {
    ...initialGuidedOnboardingState(),
    repositories: [repository()],
    selectionConfirmed: true,
    ...overrides,
  };
}

function props(
  overrides: Partial<GuidedOnboardingViewProps> = {},
): GuidedOnboardingViewProps {
  return {
    locale: "en",
    state: initialGuidedOnboardingState(),
    busy: false,
    errorCode: "",
    providerStatus: null,
    providerStatusPending: false,
    onAction: vi.fn(),
    onDiscover: vi.fn(),
    onResolve: vi.fn(),
    onAnalyze: vi.fn(),
    onRefreshProviderStatus: vi.fn(),
    onSuggestContribution: vi.fn(),
    onCreateDraft: vi.fn(),
    onCopyDraft: vi.fn(),
    onDownloadDraft: vi.fn(),
    ...overrides,
  };
}

describe("GuidedOnboardingView", () => {
  it("renders the welcome outcome, semantic progress, and advanced path", () => {
    const markup = renderToStaticMarkup(<GuidedOnboardingView {...props()} />);

    expect(markup).toContain("Guided portfolio setup");
    expect(markup).toContain("Let RepoNPC understand your work");
    expect(markup).toContain('aria-label="Guided setup progress"');
    expect(markup).toContain("Start guided setup");
    expect(markup).toContain("Use advanced raw YAML");
    expect(markup).toContain('data-step="intro"');
  });

  it("renders keyboard-operable repository checkboxes and visible disabled reasons", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "repositories", selectionConfirmed: false }),
        })}
      />,
    );

    expect(markup).toContain('type="checkbox"');
    expect(markup).toContain("octocat/demo");
    expect(markup).toContain("Confirm selection and continue to analysis");
    expect(markup).toContain("1 selected of 1");
    expect(markup).toContain("Use the keyboard to check");

    const emptySelection = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "repositories",
            selectionConfirmed: false,
            repositories: [repository({ selected: false })],
          }),
        })}
      />,
    );
    expect(emptySelection).toContain(
      "Select at least one repository before continuing.",
    );
  });

  it("offers local search and bounded pagination feedback", () => {
    const moreMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "repositories",
            selectionConfirmed: false,
            discoveryPage: 1,
            discoveryHasMore: true,
          }),
        })}
      />,
    );
    expect(moreMarkup).toContain('id="guided-repository-search"');
    expect(moreMarkup).toContain("Load next page");

    const finishedMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "repositories",
            selectionConfirmed: false,
            discoveryPage: 5,
            discoveryHasMore: true,
          }),
        })}
      />,
    );
    expect(finishedMarkup).toContain(
      "Discovery reached five pages or GitHub has no more public repositories.",
    );
  });

  it("keeps repository facts and model inferences in distinct evidence groups", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "analysis" }) })}
      />,
    );

    expect(markup).toContain('data-evidence-class="REPOSITORY_FACT"');
    expect(markup).toContain('data-evidence-class="MODEL_INFERENCE"');
    expect(markup).toContain("REPOSITORY_FACT | Repository facts");
    expect(markup).toContain("MODEL_INFERENCE | Model inferences");
    expect(markup).toContain("E_fact_1");
    expect(markup).toContain("The repository may provide a reusable parser.");
  });

  it("shows a server-owned provider preflight without exposing connection details", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "analysis" }),
          providerStatus: {
            ready: false,
            provider: "openai_compatible",
            lastCheckedAt: "2026-08-15T01:02:03Z",
          },
        })}
      />,
    );

    expect(markup).toContain("Model connection");
    expect(markup).toContain(
      "OpenAI-compatible (including vLLM) is not ready.",
    );
    expect(markup).toContain("OpenAI-compatible connection details");
    expect(markup).toContain("Recheck");
    expect(markup).toContain('dateTime="2026-08-15T01:02:03Z"');
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain("base_url");
  });

  it("allows an unavailable analysis to continue to manual contribution", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "analysis",
            repositories: [
              repository({ analysisStatus: "unavailable", analysis: null }),
            ],
          }),
        })}
      />,
    );

    expect(markup).toContain("Review facts and describe contribution");
    expect(markup).not.toContain(
      "Complete analysis for every selected repository before continuing.",
    );
  });

  it("uses the durable batch seam in place of serial analysis and gates continuation on terminal state", () => {
    const activeMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "analysis" }),
          batchAnalysisView: (
            <section id="batch-analysis-fixture">
              Batch progress fixture
            </section>
          ),
          batchCanCreate: true,
          onCreateBatch: vi.fn(),
        })}
      />,
    );

    expect(activeMarkup).toContain('id="batch-analysis-fixture"');
    expect(activeMarkup).toContain("Start batch analysis");
    expect(activeMarkup).not.toContain("Model connection");
    expect(activeMarkup).toMatch(
      /<button[^>]*disabled[^>]*>Review facts and describe contribution<\/button>/,
    );

    const terminalMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "analysis" }),
          batchAnalysisView: <section>Batch complete</section>,
          batchAnalysisTerminal: true,
          onCreateBatch: vi.fn(),
        })}
      />,
    );
    expect(terminalMarkup).toMatch(
      /<button[^>]*>Review facts and describe contribution<\/button>/,
    );
    expect(terminalMarkup).not.toMatch(
      /<button[^>]*disabled[^>]*>Review facts and describe contribution<\/button>/,
    );
  });

  it("renders explicit proposal edit, accept, and reject controls", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "contributions" }) })}
      />,
    );

    expect(markup).toContain("Your original statement");
    expect(markup).toContain('data-evidence-class="OWNER_ASSERTION"');
    expect(markup).toContain("Proposed owner assertions");
    expect(markup).toContain('id="guided-role-octocat-demo-zh-TW"');
    expect(markup).toContain('id="guided-role-octocat-demo-en"');
    expect(markup).toContain('id="guided-summary-octocat-demo-zh-TW"');
    expect(markup).toContain('id="guided-summary-octocat-demo-en"');
    expect(markup).toContain("Accept proposal");
    expect(markup).toContain("Save edits and accept");
    expect(markup).toContain("Reject proposal");
    expect(markup).toContain(
      "Only explicit acceptance creates OWNER_ASSERTION",
    );
  });

  it("keeps contribution entry usable after unavailable analysis", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "contributions",
            repositories: [
              repository({
                analysisStatus: "unavailable",
                analysis: null,
                proposal: null,
              }),
            ],
          }),
        })}
      />,
    );
    expect(markup).toContain("Enter contribution manually");
    expect(markup).not.toContain(
      "Complete analysis for every selected repository",
    );

    const incompleteMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "contributions",
            repositories: [
              repository({
                analysisStatus: "unavailable",
                analysis: null,
                proposal: {
                  role: { "zh-TW": "", en: "" },
                  summary: { "zh-TW": "", en: "" },
                  claims: [],
                },
              }),
            ],
          }),
        })}
      />,
    );
    expect(incompleteMarkup).toContain(
      "Complete both Traditional Chinese and English role and summary fields before accepting.",
    );
  });

  it("renders all bilingual basic profile fields and blocks incomplete confirmation visibly", () => {
    const empty = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "profile",
            profile: initialGuidedOnboardingState().profile,
          }),
        })}
      />,
    );
    expect(empty).toContain('id="guided-profile-display-name"');
    expect(empty).toContain('id="guided-profile-headline-zh-TW"');
    expect(empty).toContain('id="guided-profile-headline-en"');
    expect(empty).toContain('id="guided-profile-bio-zh-TW"');
    expect(empty).toContain('id="guided-profile-bio-en"');
    expect(empty).toContain('id="guided-profile-greeting-zh-TW"');
    expect(empty).toContain('id="guided-profile-greeting-en"');
    expect(empty).toContain(
      "Complete every bilingual profile field before continuing.",
    );

    const complete = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "profile", profile }) })}
      />,
    );
    expect(complete).toContain("Confirm profile and review draft");
    expect(complete).not.toContain(
      "Complete every bilingual profile field before continuing.",
    );
  });

  it("renders review and draft-ready actions without owning persistence", () => {
    const reviewMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({
            step: "review",
            profile,
            profileConfirmed: true,
            repositories: [
              repository({
                confirmedContribution: {
                  ...proposal,
                  evidence_class: "OWNER_ASSERTION",
                },
              }),
            ],
          }),
        })}
      />,
    );
    expect(reviewMarkup).toContain("Review confirmed content");
    expect(reviewMarkup).toContain("Create complete YAML draft");
    expect(reviewMarkup).toContain("Confirmed");

    const draftMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "draft", profile, profileConfirmed: true }),
        })}
      />,
    );
    expect(draftMarkup).toContain(
      "The YAML draft is ready to inspect in advanced mode.",
    );
    expect(draftMarkup).toContain("Copy YAML");
    expect(draftMarkup).toContain("Download YAML");
  });

  it("keeps the bilingual surface and safe operation error visible", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ locale: "zh-TW", errorCode: "RATE_LIMITED" })}
      />,
    );

    expect(markup).toContain("引導式作品集設定");
    expect(markup).toContain("開始引導設定");
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("引導設定錯誤");
  });
});
