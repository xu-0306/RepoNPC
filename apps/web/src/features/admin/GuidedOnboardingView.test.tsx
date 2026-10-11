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
  githubLogin: "octocat",
  aliasesText: "",
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
      excerpt: "export function parse(input: string)",
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
    confirmedSelectionFingerprint: JSON.stringify([null, [], []]),
    analysisStatus: "complete",
    analysis,
    ownerStatement: "I maintained the parser with another contributor.",
    proposal,
    proposalSource: "model",
    previousContribution: null,
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
  it("renders the unnumbered welcome outcome and advanced path", () => {
    const markup = renderToStaticMarkup(<GuidedOnboardingView {...props()} />);

    expect(markup).toContain("Guided portfolio setup");
    expect(markup).toContain("Let RepoNPC understand your work");
    expect(markup).not.toContain('aria-label="Guided setup progress"');
    expect(markup).toContain("Set up AI and begin");
    expect(markup).toContain("Build manually first");
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
    expect(markup).toContain("Use the keyboard to choose");

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
      "Select at least one project before continuing.",
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
      "Discovery reached five pages or GitHub has no more public projects.",
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
    expect(markup).toContain("View project evidence (1 source)");
    expect(markup).toContain("AI inferences");
    expect(markup).toContain("E_fact_1");
    expect(markup).toContain("The repository may provide a reusable parser.");
  });

  it.each(["en", "zh-TW"] as const)(
    "pairs each interpretation with its own collapsed sources in %s",
    (locale) => {
      const extraFact = {
        ...analysis.facts[0],
        evidence_id: "unreferenced",
        path: "docs/notes.md",
        start_line: null,
        end_line: null,
        excerpt: "<script>untrusted()</script>",
      };
      const secondInference = {
        ...analysis.inferences[0],
        statement: {
          en: "Second interpretation. ".repeat(30),
          "zh-TW": "另一份完整的解讀內容。".repeat(40),
        },
        supporting_evidence_ids: ["missing"],
      };
      const markup = renderToStaticMarkup(
        <GuidedOnboardingView
          {...props({
            locale,
            state: state({
              step: "analysis",
              repositories: [
                repository({
                  analysis: {
                    ...analysis,
                    facts: [...analysis.facts, extraFact],
                    inferences: [...analysis.inferences, secondInference],
                  },
                }),
              ],
            }),
          })}
        />,
      );
      const cards = markup
        .split('class="guided-onboarding__interpretation"')
        .slice(1);
      expect(cards).toHaveLength(2);
      expect(cards[0]).toContain("src/parser.ts:4-12");
      expect(cards[0]).not.toContain("docs/notes.md");
      expect(cards[1]).not.toContain("src/parser.ts");
      expect(markup).toContain(
        locale === "en"
          ? "AI interpretation · unconfirmed"
          : "AI 整理・尚未確認",
      );
      expect(markup).toContain(
        locale === "en" ? "Read the full interpretation" : "閱讀完整解讀",
      );
      expect(markup).toContain(
        locale === "en"
          ? "Some supporting evidence is missing"
          : "部分參考依據未包含",
      );
      expect(markup).toContain(
        locale === "en"
          ? "Other verifiable project content"
          : "其他可核對的專案內容",
      );
      expect(markup).toContain("&lt;script&gt;untrusted()&lt;/script&gt;");
      expect(markup).not.toContain("<script>");
      expect(markup).not.toMatch(/<details[^>]*open/);
      expect(markup).toContain(analysis.repository.commit_sha);
      expect(markup).not.toContain('data-evidence-class="OWNER_ASSERTION"');
    },
  );

  it("preserves facts without inferences and allows an empty completed result to continue", () => {
    for (const facts of [analysis.facts, []]) {
      const markup = renderToStaticMarkup(
        <GuidedOnboardingView
          {...props({
            state: state({
              step: "analysis",
              repositories: [
                repository({
                  analysis: { ...analysis, facts, inferences: [] },
                }),
              ],
            }),
          })}
        />,
      );
      expect(markup).toContain("No AI inferences.");
      expect(markup).toMatch(
        /<button[^>]*>Next: describe my contribution<\/button>/,
      );
      expect(markup).toContain(
        facts.length
          ? "Other verifiable project content"
          : "No verifiable project information to display.",
      );
    }
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

    expect(markup).toContain("Next: describe my contribution");
    expect(markup).not.toContain(
      "Complete analysis for every selected project before continuing.",
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
      /<button[^>]*disabled[^>]*>Next: describe my contribution<\/button>/,
    );
    expect(activeMarkup).toMatch(/<button[^>]*disabled[^>]*>Back<\/button>/);
    expect(activeMarkup).toMatch(
      /<button[^>]*disabled[^>]*>Start over<\/button>/,
    );
    expect(activeMarkup).toContain('id="guided-navigation-batch-reason"');
    expect(activeMarkup).toContain("Cancel it below");
    expect(activeMarkup).toContain(
      'aria-describedby="guided-navigation-batch-reason"',
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
      /<button[^>]*>Next: describe my contribution<\/button>/,
    );
    expect(terminalMarkup).not.toMatch(
      /<button[^>]*disabled[^>]*>Next: describe my contribution<\/button>/,
    );
    expect(terminalMarkup).toMatch(/<button[^>]*>Back<\/button>/);
    expect(terminalMarkup).toContain('data-analysis-result="octocat/demo"');
    expect(terminalMarkup).toContain("src/parser.ts");
    expect(terminalMarkup).toContain("export function parse(input: string)");
  });

  it("renders explicit proposal edit, accept, and reject controls", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "contributions" }) })}
      />,
    );

    expect(markup).toContain("Your original contribution description");
    expect(markup).toContain('data-evidence-class="OWNER_ASSERTION"');
    expect(markup).toContain(
      "Personal contribution awaiting your confirmation",
    );
    expect(markup).toContain('id="guided-role-octocat-demo-zh-TW"');
    expect(markup).toContain('id="guided-role-octocat-demo-en"');
    expect(markup).toContain('id="guided-summary-octocat-demo-zh-TW"');
    expect(markup).toContain('id="guided-summary-octocat-demo-en"');
    expect(markup).toContain("Confirm contribution");
    expect(markup).not.toContain(">Save edits and accept<");
    expect(markup).toContain("Reject and rewrite");
    expect(markup).toContain(
      "Only explicit confirmation makes this your confirmed contribution",
    );
  });

  it.each(["zh-TW", "en"] as const)(
    "does not describe confirmed contribution as awaiting confirmation in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <GuidedOnboardingView
          {...props({
            locale,
            state: state({
              step: "contributions",
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
      expect(markup).not.toContain(
        locale === "en"
          ? "Personal contribution awaiting your confirmation"
          : "待你確認的個人貢獻",
      );
      expect(markup).not.toContain(
        locale === "en"
          ? "These are proposals only and are not in YAML yet."
          : "這些內容仍是草稿，尚未進入 YAML。",
      );
      expect(markup).toContain(
        locale === "en" ? "Edit confirmed content" : "編輯已確認內容",
      );
    },
  );

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
      "Complete analysis for every selected project",
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
    expect(empty).toContain('id="guided-profile-github-login"');
    expect(empty).toContain('id="guided-profile-aliases"');
    expect(empty).toContain('id="guided-profile-headline-zh-TW"');
    expect(empty).toContain('id="guided-profile-headline-en"');
    expect(empty).toContain('id="guided-profile-bio-zh-TW"');
    expect(empty).toContain('id="guided-profile-bio-en"');
    expect(empty).toContain('id="guided-profile-greeting-zh-TW"');
    expect(empty).toContain('id="guided-profile-greeting-en"');
    expect(empty).toContain('href="#guided-profile-headline-en"');
    expect(empty).toContain('class="ux-missing-fields"');
    expect(empty).toContain(
      "Complete every bilingual profile field before continuing.",
    );

    const complete = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "profile", profile }) })}
      />,
    );
    expect(complete).toContain("Confirm profile and review draft");
    expect(complete).not.toContain('class="ux-missing-fields"');
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
    expect(reviewMarkup).toContain("Finish content and preview");
    expect(reviewMarkup).toContain("Confirmed");
    expect(reviewMarkup).toContain("共同維護者");
    expect(reviewMarkup).toContain("Co-maintainer");
    expect(reviewMarkup).toContain("維護 parser");
    expect(reviewMarkup).toContain("Maintained the parser");

    const draftMarkup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          state: state({ step: "draft", profile, profileConfirmed: true }),
        })}
      />,
    );
    expect(draftMarkup).toContain(
      "Content is ready. Open Preview &amp; share to prepare the NPC.",
    );
    expect(draftMarkup).toContain("Copy YAML");
    expect(draftMarkup).toContain("Back up settings (YAML)");
  });

  it("keeps the bilingual surface and safe operation error visible", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ locale: "zh-TW", errorCode: "RATE_LIMITED" })}
      />,
    );

    expect(markup).toContain("引導式作品集設定");
    expect(markup).toContain("設定 AI 並開始");
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("引導設定錯誤");
  });
});

it.each(["zh-TW", "en"] as const)(
  "labels manual contributions and selection in %s",
  (locale) => {
    const copy =
      locale === "zh-TW"
        ? ["手動填寫的貢獻", "確認專案並填寫貢獻"]
        : [
            "Manually entered contribution",
            "Confirm projects and enter contributions",
          ];
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          locale,
          state: state({
            step: "contributions",
            route: "manual",
            repositories: [repository({ proposalSource: "manual" })],
          }),
        })}
      />,
    );
    expect(markup).toContain(copy[0]);
    expect(markup).not.toContain(
      locale === "zh-TW"
        ? "AI 建議（尚未確認）"
        : "AI suggestion (unconfirmed)",
    );
    const selection = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({
          locale,
          state: state({ step: "repositories", route: "manual" }),
        })}
      />,
    );
    expect(selection).toContain(copy[1]);
  },
);

it.each(["zh-TW", "en"] as const)(
  "explains both welcome routes beside their accessible controls in %s",
  (locale) => {
    const input = props({ locale });
    const markup = renderToStaticMarkup(<GuidedOnboardingView {...input} />);
    expect(markup).toContain('aria-describedby="guided-start-ai-help"');
    expect(markup).toContain('aria-describedby="guided-start-manual-help"');
    const ai = markup.match(/<p id="guided-start-ai-help">([^<]+)<\/p>/)?.[1];
    const manual = markup.match(
      /<p id="guided-start-manual-help">([^<]+)<\/p>/,
    )?.[1];
    expect(ai).toContain(
      locale === "zh-TW" ? "測試並確認選用" : "test and explicitly select",
    );
    expect(manual).toContain(
      locale === "zh-TW" ? "不需模型" : "No model is needed",
    );
    expect(manual).toContain(
      locale === "zh-TW" ? "即時聊天仍需模型" : "live chat still need models",
    );
    expect(manual).toContain(
      locale === "zh-TW" ? "不等於公開分享" : "does not publish it",
    );
    expect(markup).not.toMatch(
      /<details[^>]*>[\s\S]*id="guided-start-manual-help"/,
    );
    expect(input.onAction).not.toHaveBeenCalled();
    expect(input.onAnalyze).not.toHaveBeenCalled();
  },
);

it.each(["zh-TW", "en"] as const)(
  "renders draft recovery in the focused error summary without replacing content in %s",
  (locale) => {
    const current = state({ step: "review", profile, profileConfirmed: true });
    for (const errorCode of [
      "SERVICE_NOT_READY",
      "VALIDATION_ERROR",
      "REQUEST_FAILED",
      "untrusted-error-canary",
    ]) {
      const markup = renderToStaticMarkup(
        <GuidedOnboardingView
          {...props({ locale, state: current, errorCode })}
        />,
      );
      expect(markup).toContain('role="alert" tabindex="-1"');
      expect(markup).toContain(profile.displayName);
      expect(markup).toContain(
        locale === "zh-TW" ? "輸入仍保留" : "input is kept",
      );
      expect(markup).not.toContain("untrusted-error-canary");
      if (
        errorCode === "SERVICE_NOT_READY" ||
        errorCode === "untrusted-error-canary"
      ) {
        expect(markup).toContain(locale === "zh-TW" ? "維護" : "Maintenance");
        expect(markup).not.toContain(locale === "zh-TW" ? "回報" : "report");
      }
      expect(markup).not.toContain("https://github.com/username");
    }
    expect(current.step).toBe("review");
  },
);
