import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import {
  initialGuidedOnboardingState,
  type GuidedOnboardingViewProps,
  type GuidedRepository,
  type GuidedStep,
} from "./guidedOnboarding";

function markup(step: GuidedStep, locale: "zh-TW" | "en", confirmed = false) {
  const text = { "zh-TW": "維護解析器", en: "Maintained the parser" };
  const proposal = {
    role: text,
    summary: text,
    claims: ["responsibility", "achievement"].map((kind, index) => ({
      id: `claim_${index}`,
      kind: kind as "responsibility" | "achievement",
      statement: text,
    })),
  };
  const repository: GuidedRepository = {
    metadata: {
      slug: "example/parser",
      name: "parser",
      description: "Public project",
      primary_language: "TypeScript",
      default_branch: "main",
      is_fork: false,
      is_archived: false,
      updated_at: null,
      html_url: "https://github.com/example/parser",
    },
    selected: true,
    ref: null,
    include: [],
    exclude: [],
    confirmedSelectionFingerprint: JSON.stringify([null, [], []]),
    analysisStatus: "complete",
    analysis: null,
    ownerStatement: text.en,
    proposal,
    proposalSource: "model",
    previousContribution: null,
    confirmedContribution: confirmed
      ? { ...proposal, evidence_class: "OWNER_ASSERTION" }
      : null,
  };
  const props: GuidedOnboardingViewProps = {
    locale,
    state: {
      ...initialGuidedOnboardingState(),
      step,
      repositories: [
        repository,
        {
          ...repository,
          metadata: {
            ...repository.metadata,
            slug: "example/second",
            name: "second",
          },
        },
      ],
    },
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
  };
  return renderToStaticMarkup(<GuidedOnboardingView {...props} />);
}

it.each(["zh-TW", "en"] as const)(
  "shares the pixel header on every step in %s",
  (locale) => {
    for (const step of [
      "models",
      "repositories",
      "analysis",
      "contributions",
      "profile",
      "review",
      "draft",
    ] as const) {
      const header = markup(step, locale).match(
        /<header class="guided-onboarding__header">[\s\S]*?<\/header>/,
      )?.[0];
      expect(header).toContain(
        'class="px-display" id="guided-onboarding-heading" tabindex="-1"',
      );
      expect(header).toMatch(
        /<button class="px-button px-button--secondary"[^>]*>/,
      );
      expect(header).toContain(
        'class="guided-onboarding__navigation-disclosure"',
      );
      expect(header).toContain('class="px-button px-button--danger"');
      expect(header).toContain(
        locale === "en" ? "Edit or start over" : "編輯或重新開始",
      );
      expect(header).not.toMatch(/style=/);
    }
  },
);

it.each(["zh-TW", "en"] as const)(
  "groups guidance, project status and bilingual statements in %s",
  (locale) => {
    const html = markup("contributions", locale);
    const help = locale === "en" ? "ⓘ Field guidance" : "ⓘ 填寫說明";
    expect(html.split(help)).toHaveLength(2);
    expect(html).toMatch(
      /<header class="p4-w2__tools p5-contributions__header">[\s\S]*?<summary>ⓘ/,
    );
    expect(html).toMatch(/class="p5-contributions__project px-panel" open=""/);
    expect(
      html.match(/class="p5-contributions__project px-panel" open=""/g),
    ).toHaveLength(1);
    expect(
      html.match(/class="p5-contributions__chevron" aria-hidden="true"/g),
    ).toHaveLength(2);
    expect(html).toContain(
      `<span class="px-badge">${locale === "en" ? "Not confirmed" : "尚未確認"}</span>`,
    );
    expect(markup("contributions", locale, true)).toContain(
      `<span class="px-badge">${locale === "en" ? "Confirmed" : "已確認"}</span>`,
    );
    expect(
      html.match(
        /class="p5-contribution__suggestion px-panel px-panel--inset"/g,
      ),
    ).toHaveLength(2);
    expect(
      html.match(/class="p5-contribution__claim px-panel px-panel--inset"/g),
    ).toHaveLength(4);
    expect(html.match(/class="px-button px-button--quiet"/g)).toHaveLength(4);
    expect(html).toContain(
      'aria-labelledby="guided-claims-heading-example-parser"',
    );
    expect(html).toContain('id="guided-claims-heading-example-parser"');
    expect(html).toContain(
      'aria-describedby="guided-owner-statement-help-example-parser"',
    );
    expect(html).toContain('id="guided-owner-statement-help-example-parser"');
    expect(html).toMatch(
      /<footer class="p4-w2__confirm">[\s\S]*?px-button--primary/,
    );
    expect(html).not.toMatch(/style="[^"]*(?:color|background)/i);
  },
);
