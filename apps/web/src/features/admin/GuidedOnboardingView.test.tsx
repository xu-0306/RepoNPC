import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  initialGuidedOnboardingState,
  guidedOnboardingReducer,
  type ContributionProposal,
  type GuidedOnboardingState,
  type GuidedOnboardingViewProps,
  type GuidedProfile,
  type GuidedRepository,
  type RepositoryAnalysis,
  type RepositoryMetadata,
} from "./guidedOnboarding";
import {
  AnalysisHighlight,
  GuidedOnboardingView,
} from "./GuidedOnboardingView";
import { ConfirmButton } from "./ConfirmDialog";
import type { AnalysisSelectionView } from "./AnalysisSelectionPanel";
import { Dialog, DialogTrigger, Popover } from "react-aria-components";

// Keep server rendering real; direct handler checks opt into the shared hook pattern.
const directHooks = vi.hoisted(() => ({
  values: null as unknown[] | null,
  cursor: 0,
  effects: null as Array<() => unknown> | null,
  refs: null as Array<{ current: unknown }> | null,
  refCursor: 0,
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useId: () =>
      directHooks.values === null ? react.useId() : "highlight-body",
    useEffect: (...args: Parameters<typeof react.useEffect>) => {
      if (directHooks.values === null) react.useEffect(...args);
      else directHooks.effects?.push(args[0]);
    },
    useRef: (initial: unknown) => {
      if (directHooks.values === null) return react.useRef(initial);
      if (!directHooks.refs) return { current: initial };
      const index = directHooks.refCursor++;
      return (directHooks.refs[index] ??= { current: initial });
    },
    useState: (initial: unknown) => {
      if (directHooks.values === null) return react.useState(initial);
      const index = directHooks.cursor++;
      if (!(index in directHooks.values)) directHooks.values[index] = initial;
      return [
        directHooks.values[index],
        (next: unknown) => {
          directHooks.values![index] = next;
        },
      ];
    },
  };
});

function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

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
      url: `https://github.com/octocat/demo/blob/${"a".repeat(40)}/src/parser.ts#L4-L12`,
    },
  ],
  inferences: [
    {
      evidence_class: "MODEL_INFERENCE",
      title: { "zh-TW": "可重用的解析器", en: "Reusable parser" },
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
    analysisSelection: null,
    analysisSelectionPending: false,
    onAction: vi.fn(),
    onDiscover: vi.fn(),
    onResolve: vi.fn(),
    onAnalyze: vi.fn(),
    onRefreshAnalysisSelection: vi.fn(),
    onSuggestContribution: vi.fn(),
    onCreateDraft: vi.fn(),
    onCopyDraft: vi.fn(),
    onDownloadDraft: vi.fn(),
    ...overrides,
  };
}

const confirmedModels: AnalysisSelectionView = {
  selection: {
    chat_profile_id: "private-chat-profile",
    embedding_profile_id: "private-search-profile",
    generation: 1,
    updated_at: "1970-01-01T00:00:00Z",
  },
  eligible: true,
  reason: "READY",
  chat: {
    profile_id: "private-chat-profile",
    model_id: "confirmed-chat-model",
    status: "ready",
    connection_revision: 3,
    tested: true,
  },
  embedding: {
    profile_id: "private-search-profile",
    model_id: "confirmed-search-model",
    status: "ready",
    connection_revision: 5,
    tested: true,
  },
};

describe("GuidedOnboardingView", () => {
  it.each(["zh-TW", "en"] as const)(
    "focuses mount and async draft restoration without scrolling, but scrolls user step changes in %s",
    (locale) => {
      directHooks.values = [];
      directHooks.refs = [];
      directHooks.effects = [];
      const heading = { focus: vi.fn(), scrollIntoView: vi.fn() };
      const input = props({
        locale,
        state: state({ step: "intro" }),
      });
      const view = () => {
        directHooks.cursor = 0;
        directHooks.refCursor = 0;
        directHooks.effects = [];
        const tree = GuidedOnboardingView(input);
        const title = elements(tree).find(
          (node) => node.props.id === "guided-onboarding-heading",
        )!;
        (title.props.ref as { current: unknown }).current = heading;
        return { effects: directHooks.effects, section: tree };
      };
      try {
        const mountEffects = view().effects;
        mountEffects.forEach((effect) => effect());
        expect(heading.focus).toHaveBeenCalledWith({ preventScroll: true });
        expect(heading.scrollIntoView).not.toHaveBeenCalled();
        // React StrictMode replays mount effects without changing the step.
        mountEffects.forEach((effect) => effect());
        expect(heading.scrollIntoView).not.toHaveBeenCalled();
        input.state = { ...input.state, step: "profile", route: "manual" };
        const restored = view();
        restored.effects.forEach((effect) => effect());
        expect(heading.scrollIntoView).not.toHaveBeenCalled();
        const interaction =
          locale === "en" ? "onKeyDownCapture" : "onClickCapture";
        (restored.section.props[interaction] as () => void)();
        input.state = { ...input.state, step: "review" };
        view().effects.forEach((effect) => effect());
        expect(heading.scrollIntoView).toHaveBeenCalledExactlyOnceWith({
          block: "start",
          behavior: "instant",
        });
        view().effects.forEach((effect) => effect());
        expect(heading.scrollIntoView).toHaveBeenCalledTimes(1);
      } finally {
        directHooks.values = null;
        directHooks.refs = null;
        directHooks.effects = null;
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "renders specific analysis and GitHub timeout errors in %s",
    (locale) => {
      const messages = [
        [
          "ANALYSIS_TIMEOUT",
          locale === "zh-TW"
            ? "此 repository 已達整體分析安全上限，請重試或繼續手動填寫。"
            : "This repository reached the overall analysis safety ceiling; retry or continue manually.",
        ],
        [
          "GITHUB_TIMEOUT",
          locale === "zh-TW"
            ? "GitHub 在設定的無活動期限內沒有傳回資料，請重試或繼續手動填寫。"
            : "GitHub returned no data within the configured inactivity timeout; retry or continue manually.",
        ],
        [
          "CANCELLED",
          locale === "zh-TW"
            ? "操作已取消，可重新開始或繼續手動填寫。"
            : "The operation was cancelled; start again or continue manually.",
        ],
      ];
      for (const [errorCode, message] of messages) {
        const markup = renderToStaticMarkup(
          <GuidedOnboardingView
            {...props({
              locale,
              state: { ...initialGuidedOnboardingState(), step: "analysis" },
              errorCode,
            })}
          />,
        );
        expect(markup).toContain('role="alert"');
        expect(markup).toContain(message);
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "disables archived selection with its accessible name and visible label in %s",
    (locale) => {
      const archived = repository({
        selected: false,
        metadata: { ...metadata, is_archived: true },
      });
      const input = props({
        locale,
        state: state({
          step: "repositories",
          selectionConfirmed: false,
          repositories: [archived],
        }),
      });
      const markup = renderToStaticMarkup(<GuidedOnboardingView {...input} />);
      expect(markup).toMatch(
        /<input[^>]*disabled=""[^>]*type="checkbox"|<input[^>]*type="checkbox"[^>]*disabled=""/,
      );
      expect(markup).toContain(`<strong>${metadata.name}</strong>`);
      expect(markup).toContain(`<code>${metadata.slug}</code>`);
      expect(markup).toMatch(/<label[^>]*for="guided-repository-[^"]+"/);
      expect(markup).toContain(locale === "zh-TW" ? "已封存" : "archived");
      expect(
        guidedOnboardingReducer(input.state, {
          type: "TOGGLE_REPOSITORY",
          slug: metadata.slug,
        }),
      ).toEqual(input.state);
      directHooks.values = [];
      try {
        const tree = GuidedOnboardingView(input);
        const step = elements(tree).find(
          (node) =>
            typeof node.type === "function" &&
            node.props.onDiscover === input.onDiscover,
        )!;
        const stepTree = (step.type as (value: typeof step.props) => ReactNode)(
          step.props,
        );
        const row = elements(stepTree).find(
          (node) => node.props.repository === archived,
        )!;
        const rowTree = (row.type as (value: typeof row.props) => ReactNode)(
          row.props,
        );
        const checkbox = elements(rowTree).find(
          (node) => node.props.id && node.props.onChange,
        )!;
        expect(checkbox.props.disabled).toBe(true);
        (checkbox.props.onChange as () => void)();
        expect(input.onAction).not.toHaveBeenCalled();
      } finally {
        directHooks.values = null;
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "shows confirmed tested model ids from the current selection in %s",
    (locale) => {
      const input = props({
        locale,
        state: state({ step: "analysis" }),
        analysisSelection: confirmedModels,
      });
      const markup = renderToStaticMarkup(<GuidedOnboardingView {...input} />);
      expect(markup).toContain(
        locale === "zh-TW" ? "分析與回答模型" : "Analysis and chat",
      );
      expect(markup).toContain(
        locale === "zh-TW" ? "資料查找模型" : "Content finder",
      );
      expect(markup).toContain(
        `confirmed-chat-model · ${locale === "zh-TW" ? "已測試" : "Tested"}`,
      );
      expect(markup).toContain(
        `confirmed-search-model · ${locale === "zh-TW" ? "已測試" : "Tested"}`,
      );
      expect(markup).not.toContain("1970");
      expect(markup).not.toContain("private-chat-profile");
      expect(markup).not.toContain("private-search-profile");
      const refreshed = renderToStaticMarkup(
        <GuidedOnboardingView
          {...input}
          analysisSelection={{
            ...confirmedModels,
            chat: { ...confirmedModels.chat, model_id: "new-confirmed-chat" },
          }}
        />,
      );
      expect(refreshed).toContain("new-confirmed-chat");
      expect(refreshed).not.toContain("confirmed-chat-model");
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "shows not selected for generation zero or an empty selection in %s",
    (locale) => {
      for (const selection of [
        { ...confirmedModels.selection, generation: 0 },
        {
          ...confirmedModels.selection,
          chat_profile_id: null,
          embedding_profile_id: null,
        },
      ]) {
        const markup = renderToStaticMarkup(
          <GuidedOnboardingView
            {...props({
              locale,
              state: state({ step: "analysis" }),
              analysisSelection: {
                ...confirmedModels,
                selection,
                eligible: false,
                reason: "CHAT_MODEL_NOT_SELECTED",
              },
            })}
          />,
        );
        expect(markup).toContain(
          locale === "zh-TW" ? "尚未選擇" : "Not selected",
        );
        expect(markup).not.toContain("1970");
        expect(markup).not.toContain("confirmed-chat-model");
      }
    },
  );

  it("rechecks the shared analysis selection", () => {
    directHooks.values = [];
    try {
      const input = props({ state: state({ step: "analysis" }) });
      const tree = GuidedOnboardingView(input);
      const step = elements(tree).find(
        (node) =>
          typeof node.type === "function" &&
          node.props.onRefreshAnalysisSelection ===
            input.onRefreshAnalysisSelection,
      )!;
      const stepTree = (step.type as (value: typeof step.props) => ReactNode)(
        step.props,
      );
      const panel = elements(stepTree).find(
        (node) =>
          typeof node.type === "function" &&
          node.props.onRefresh === input.onRefreshAnalysisSelection,
      )!;
      const panelTree = (
        panel.type as (value: typeof panel.props) => ReactNode
      )(panel.props);
      const button = elements(panelTree).find(
        (node) => node.type === "button",
      )!;
      (button.props.onClick as () => void)();
      expect(input.onRefreshAnalysisSelection).toHaveBeenCalledOnce();
    } finally {
      directHooks.values = null;
    }
  });
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

  it("keeps cited repository sources distinct from model highlights", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props({ state: state({ step: "analysis" }) })}
      />,
    );

    expect(markup).toContain('data-evidence-class="REPOSITORY_FACT"');
    expect(markup).toContain('data-evidence-class="MODEL_INFERENCE"');
    expect(markup).toContain("Reusable parser");
    expect(markup).toContain("Highlights");
    expect(markup).not.toContain("E_fact_1");
    expect(markup).toContain("The repository may provide a reusable parser.");
  });

  it.each(["en", "zh-TW"] as const)(
    "renders localized flat highlights, linked sources and final actions in %s",
    (locale) => {
      const extraFact = {
        ...analysis.facts[0],
        evidence_id: "extra-source",
        path: "docs/guide.md",
        start_line: null,
        end_line: null,
        url: `https://github.com/octocat/demo/blob/${"a".repeat(40)}/docs/guide.md`,
      };
      const uncitedFact = {
        ...extraFact,
        evidence_id: "unreferenced",
        path: "docs/notes.md",
        url: "https://github.com/octocat/demo/blob/main/docs/notes.md",
      };
      const firstInference = {
        ...analysis.inferences[0],
        supporting_evidence_ids: [extraFact.evidence_id, "E_fact_1"],
      };
      const secondInference = {
        ...analysis.inferences[0],
        title: { en: "Second highlight", "zh-TW": "另一個重點" },
        statement: {
          en:
            "Second interpretation. ".repeat(30) +
            "<script>untrusted()</script>",
          "zh-TW":
            "另一段完整的解讀內容。".repeat(40) +
            "<script>untrusted()</script>",
        },
        supporting_evidence_ids: ["missing"],
      };
      const input = props({
        locale,
        state: state({
          step: "analysis",
          repositories: [
            repository({
              analysis: {
                ...analysis,
                facts: [...analysis.facts, extraFact, uncitedFact],
                inferences: [firstInference, secondInference],
              },
            }),
          ],
        }),
      });
      const markup = renderToStaticMarkup(<GuidedOnboardingView {...input} />);
      const rows = markup.split('class="guided-analysis__highlight"').slice(1);
      expect(rows).toHaveLength(2);
      for (const link of rows.join("").matchAll(/href="([^"]+)"/g)) {
        expect(link[1]).toMatch(/^https:\/\/github\.com\//);
      }
      expect(rows[0]).toContain("src/parser.ts:4-12");
      expect(rows[0]).toContain(`>${firstInference.title[locale]}</button>`);
      expect(rows[0]).toContain('aria-expanded="false"');
      expect(rows[0]).toMatch(
        /aria-controls="([^"]+)"[\s\S]*id="\1" hidden=""/,
      );
      expect(rows[0]).toContain(
        '<span class="guided-analysis__more">+1</span>',
      );
      const chip = rows[0].match(
        /class="guided-analysis__source-chip"[\s\S]*?<a href="([^"]+)"/,
      );
      expect(chip?.[1]).toBe(extraFact.url);
      expect(rows[0]).toContain(`href="${analysis.facts[0].url}"`);
      expect(rows[0]).toContain('target="_blank" rel="noopener noreferrer"');
      expect(rows[0]).not.toContain("docs/notes.md");
      expect(rows[1]).toContain(`>${secondInference.title[locale]}</button>`);
      expect(rows[1]).not.toContain("src/parser.ts");
      expect(rows[1]).not.toContain('class="guided-analysis__source-chip"');
      const missingNote =
        locale === "en"
          ? "Some sources are not in this result; do not treat them as verified."
          : "部分出處不在這次結果中，請勿視為已核對。";
      expect(rows[1]).toContain(missingNote);
      expect(rows[0]).not.toContain(missingNote);
      expect(markup).toContain(locale === "en" ? "Highlights" : "專案重點");
      const note =
        locale === "en"
          ? "AI summary, for your reference"
          : "AI 整理，僅供你參考";
      expect(markup).toContain(`<p>${note}</p>`);
      expect(markup).toContain(
        `aria-label="${locale === "en" ? "Privacy details" : "隱私說明"}"`,
      );
      expect(markup).not.toContain(`aria-label="${note}"`);
      expect(markup).toMatch(
        /<button class="guided-analysis__info"[^>]*aria-expanded="false"/,
      );
      for (const removed of [
        "AI 整理・尚未確認",
        "AI interpretation · unconfirmed",
        "閱讀完整解讀",
        "Read the full interpretation",
        "其他可核對的專案內容",
        "Other verifiable project content",
        "技術識別資訊",
        "Technical identifiers",
        "guided-onboarding__interpretation",
        "guided-onboarding__sources",
        "<pre",
        "E_fact_1",
        "docs/notes.md",
      ]) {
        expect(markup).not.toContain(removed);
      }
      expect(markup).toContain("&lt;script&gt;untrusted()&lt;/script&gt;");
      expect(markup).not.toContain("<script>");
      expect(markup).not.toMatch(/<details[^>]*open/);
      expect(markup).toContain(
        '<code class="guided-analysis__chip">aaaaaaa</code>',
      );
      expect(markup).toContain(
        '<span class="guided-analysis__chip">TypeScript</span>',
      );
      expect(markup).not.toContain('data-evidence-class="OWNER_ASSERTION"');
      const actions = markup.slice(
        markup.indexOf('class="guided-analysis__actions"'),
      );
      expect(
        markup.indexOf('class="guided-analysis__actions"'),
      ).toBeGreaterThan(
        markup.lastIndexOf('class="guided-analysis__highlight"'),
      );
      const next =
        locale === "en"
          ? "Next: describe my contribution"
          : "下一步：描述我的貢獻";
      const retry = locale === "en" ? "Analyze again" : "重新分析";
      expect(actions).toContain(`>${next}</button>`);
      expect(actions).toContain(`>${retry}</button>`);
      expect(actions.indexOf(next)).toBeLessThan(actions.indexOf(retry));
      expect(markup.split(`>${retry}</button>`)).toHaveLength(2);
      expect(input.onAction).not.toHaveBeenCalled();
      expect(input.onAnalyze).not.toHaveBeenCalled();
    },
  );

  it.each(["en", "zh-TW"] as const)(
    "expands only the statement and all source links in %s",
    (locale) => {
      directHooks.values = [];
      try {
        const render = () => {
          directHooks.cursor = 0;
          return AnalysisHighlight({
            inference: analysis.inferences[0],
            locale,
            facts: analysis.facts,
          });
        };
        const collapsed = render();
        const toggle = elements(collapsed).find(
          (node) => node.type === "button",
        )!;
        expect(toggle.props["aria-expanded"]).toBe(false);
        expect(renderToStaticMarkup(collapsed)).toContain(
          'id="highlight-body" hidden=""',
        );
        (toggle.props.onClick as () => void)();
        const expanded = render();
        const markup = renderToStaticMarkup(expanded);
        expect(markup).toContain(
          'aria-expanded="true" aria-controls="highlight-body"',
        );
        expect(markup).not.toContain('hidden=""');
        const body = elements(expanded).find(
          (node) => node.props.id === "highlight-body",
        )!;
        expect(
          Children.toArray(body.props.children as ReactNode)
            .filter(isValidElement)
            .map((node) => node.type),
        ).toEqual(["p", "ul"]);
        expect(markup).toContain(analysis.inferences[0].statement[locale]);
        expect(markup).toContain(`href="${analysis.facts[0].url}"`);
        (
          elements(expanded).find((node) => node.type === "button")!.props
            .onClick as () => void
        )();
        expect(renderToStaticMarkup(render())).toContain(
          'aria-expanded="false"',
        );
      } finally {
        directHooks.values = null;
      }
    },
  );

  it.each(["en", "zh-TW"] as const)(
    "keeps an empty completed result usable without uncited content in %s",
    (locale) => {
      for (const facts of [analysis.facts, []]) {
        const markup = renderToStaticMarkup(
          <GuidedOnboardingView
            {...props({
              locale,
              state: state({
                step: "analysis",
                repositories: [
                  repository({
                    analysis: { ...analysis, facts, inferences: [] },
                    metadata: { ...metadata, primary_language: null },
                  }),
                ],
              }),
            })}
          />,
        );
        expect(markup).toContain(
          locale === "en" ? "No AI inferences." : "沒有 AI 推論。",
        );
        expect(markup).toMatch(
          locale === "en"
            ? /<button[^>]*>Next: describe my contribution<\/button>/
            : /<button[^>]*>下一步：描述我的貢獻<\/button>/,
        );
        expect(markup).not.toContain("Other verifiable project content");
        expect(markup).not.toContain("其他可核對的專案內容");
        expect(markup).not.toContain("src/parser.ts");
        expect(markup).not.toContain("TypeScript");
        expect(markup).not.toContain('class="guided-analysis__source-chip"');
      }
    },
  );

  it.each(["en", "zh-TW"] as const)(
    "requires destructive start-over confirmation and preserves disabled guards in %s",
    (locale) => {
      directHooks.values = [];
      try {
        for (const blocked of [
          { busy: false, batchAnalysisActive: false },
          { busy: true, batchAnalysisActive: false },
          { busy: false, batchAnalysisActive: true },
        ]) {
          const input = props({
            locale,
            state: state({ step: "analysis" }),
            ...blocked,
          });
          const tree = GuidedOnboardingView(input);
          const confirm = elements(tree).find(
            (node) => node.type === ConfirmButton,
          )!;
          expect(confirm.props.locale).toBe(locale);
          expect(confirm.props.title).toBe(
            locale === "en" ? "Start over?" : "重新開始？",
          );
          expect(confirm.props.description).toBe(
            locale === "en"
              ? "This clears the unsaved guided setup."
              : "這會清除目前尚未儲存的引導內容。",
          );
          expect(confirm.props.destructive).toBe(true);
          expect(confirm.props.confirmLabel).toBe(
            locale === "en" ? "Start over" : "重新開始",
          );
          expect(confirm.props.disabled).toBe(
            blocked.busy || blocked.batchAnalysisActive,
          );
          expect(confirm.props["aria-describedby"]).toBe(
            blocked.batchAnalysisActive
              ? "guided-navigation-batch-reason"
              : undefined,
          );
          expect(input.onAction).not.toHaveBeenCalled();
          (confirm.props.onConfirm as () => void)();
          expect(input.onAction).toHaveBeenCalledTimes(
            blocked.busy || blocked.batchAnalysisActive ? 0 : 1,
          );
          if (!blocked.busy && !blocked.batchAnalysisActive)
            expect(input.onAction).toHaveBeenCalledWith({ type: "RESET" });
        }
      } finally {
        directHooks.values = null;
      }
    },
  );

  it.each(["en", "zh-TW"] as const)(
    "uses a React Aria privacy popover and keeps moved action callbacks in %s",
    (locale) => {
      directHooks.values = [];
      try {
        const input = props({ locale, state: state({ step: "analysis" }) });
        const step = elements(GuidedOnboardingView(input)).find(
          (node) =>
            typeof node.type === "function" &&
            node.type.name === "AnalysisStep",
        )!;
        const stepTree = (step.type as (props: unknown) => ReactNode)(
          step.props,
        );
        const group = elements(stepTree).find(
          (node) =>
            typeof node.type === "function" &&
            node.type.name === "EvidenceGroups",
        )!;
        const groupTree = (group.type as (props: unknown) => ReactNode)(
          group.props,
        );
        const nodes = elements(groupTree);
        expect(
          nodes.filter((node) => node.type === DialogTrigger),
        ).toHaveLength(1);
        expect(nodes.filter((node) => node.type === Popover)).toHaveLength(1);
        const dialog = nodes.find((node) => node.type === Dialog)!;
        expect(dialog.props.lang).toBe(locale);
        expect(dialog.props["aria-label"]).toBe(
          locale === "en" ? "Privacy details" : "隱私說明",
        );
        expect(renderToStaticMarkup(dialog.props.children as ReactNode)).toBe(
          locale === "en"
            ? "<p>Never public, never added to your portfolio automatically.</p>"
            : "<p>不會公開，也不會自動寫進作品集。</p>",
        );
        const footer = elements(stepTree).find(
          (node) => node.props.className === "guided-analysis__actions",
        )!;
        const buttons = elements(footer).filter(
          (node) => node.type === "button",
        );
        expect(buttons).toHaveLength(2);
        expect(input.onAnalyze).not.toHaveBeenCalled();
        expect(input.onAction).not.toHaveBeenCalled();
        (buttons[0].props.onClick as () => void)();
        expect(input.onAction).toHaveBeenCalledExactlyOnceWith({
          type: "CONTINUE_TO_CONTRIBUTIONS",
        });
        (buttons[1].props.onClick as () => void)();
        expect(input.onAnalyze).toHaveBeenCalledExactlyOnceWith(metadata.slug);
      } finally {
        directHooks.values = null;
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "shows the analysis selection reason without exposing connection details in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <GuidedOnboardingView
          {...props({
            locale,
            state: state({ step: "analysis" }),
            analysisSelection: {
              ...confirmedModels,
              eligible: false,
              reason: "CHAT_MODEL_NOT_READY",
              chat: { ...confirmedModels.chat, tested: false },
            },
          })}
        />,
      );

      expect(markup).toContain(
        locale === "zh-TW" ? "分析模型" : "Analysis models",
      );
      expect(markup).toContain(
        locale === "zh-TW"
          ? "回答模型尚未通過測試"
          : "Chat model has not passed testing",
      );
      expect(markup).toContain(locale === "zh-TW" ? "重新檢查" : "Recheck");
      expect(markup).not.toContain("1970");
      expect(markup).not.toContain("<time");
      expect(markup).not.toContain("connection_id");
      expect(markup).not.toContain("private-chat-profile");
      expect(markup).not.toContain("api_key");
      expect(markup).not.toContain("base_url");
    },
  );

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
    expect(terminalMarkup).toContain(`href="${analysis.facts[0].url}"`);
    expect(terminalMarkup).toContain("Reusable parser");
    expect(terminalMarkup).not.toContain("<pre");
    expect(
      terminalMarkup.indexOf('class="guided-analysis__actions"'),
    ).toBeGreaterThan(
      terminalMarkup.indexOf('data-analysis-result="octocat/demo"'),
    );
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

it.each([
  "models",
  "repositories",
  "analysis",
  "contributions",
  "profile",
  "review",
] as const)("leaves the %s stepper to the workspace shell", (step) => {
  const markup = renderToStaticMarkup(
    <GuidedOnboardingView {...props({ state: state({ step }) })} />,
  );
  expect(markup).not.toContain('class="onboarding-stepper');
  expect(markup).toContain('id="guided-onboarding-heading"');
  expect(markup).toContain("admin-status-overview");
});
