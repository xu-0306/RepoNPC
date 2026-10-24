import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";

import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { initialGuidedOnboardingState } from "./guidedOnboarding";
import type { GuidedOnboardingViewProps } from "./guidedOnboarding";
import type { GuidedRepository } from "./guidedOnboarding";
import {
  BatchAnalysisPanel,
  type BatchAnalysisPanelProps,
} from "./BatchAnalysisPanel";

const noop = () => {};
const props: GuidedOnboardingViewProps = {
  locale: "en",
  state: initialGuidedOnboardingState(),
  busy: false,
  errorCode: "",
  analysisSelection: null,
  analysisSelectionPending: false,
  onAction: noop,
  onDiscover: noop,
  onResolve: noop,
  onAnalyze: noop,
  onRefreshAnalysisSelection: noop,
  onSuggestContribution: noop,
  onCreateDraft: noop,
  onCopyDraft: noop,
  onDownloadDraft: noop,
};

it.each(["en", "zh-TW"] as const)(
  "keeps w1 pixel panels, disclosures and accessible names in %s",
  (locale) => {
    const intro = renderToStaticMarkup(
      <GuidedOnboardingView {...props} locale={locale} />,
    );
    expect(intro).toContain("p4-w1-intro px-panel");
    expect(intro).toContain(
      'class="px-button px-button--primary" aria-describedby="guided-start-ai-help"',
    );
    expect(intro).toContain('id="guided-start-ai-help"');
    expect(intro).toContain('id="guided-start-manual-help"');
    const repositories = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props}
        locale={locale}
        state={{ ...props.state, step: "repositories" }}
      />,
    );
    expect(repositories).toContain(
      'aria-labelledby="guided-repositories-heading"',
    );
    expect(repositories).toContain('<details class="p4-w1-discovery" open="">');
    expect(repositories).toContain('<footer class="p4-w1-confirm">');
    const analysis = renderToStaticMarkup(
      <GuidedOnboardingView
        {...props}
        locale={locale}
        state={{ ...props.state, step: "analysis" }}
        batchAnalysisTerminal
        batchAnalysisView={<p>Batch details</p>}
      />,
    );
    expect(analysis).toMatch(
      /<details class="p4-w1-diagnostics"><summary>[^<]+<\/summary><p>Batch details<\/p><\/details>/,
    );
    expect(analysis).toContain('<footer class="guided-analysis__actions">');
    for (const markup of [intro, repositories, analysis])
      expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
  },
);

it("keeps aggregate progress values and announcements in the pixel progressbar", () => {
  const input: BatchAnalysisPanelProps = {
    locale: "en",
    preflight: { status: "idle" },
    job: null,
    recovery: false,
    progress: null,
    stream: { connection: "idle", reconnectAttempts: 0, lastEventId: null },
    actions: { pending: null, error: null },
    onPause: noop,
    onResume: noop,
    onCancel: noop,
    onRetry: noop,
    onReanalyze: noop,
    onDismissRecovery: noop,
    onReconcile: noop,
    onRetryPreflight: noop,
  };
  input.job = { id: "batch", status: "running", items: [] };
  input.progress = {
    totalItems: 7,
    processedItems: 3,
    successfulItems: 2,
    activeItems: 1,
    failedItems: 1,
    attentionItems: 0,
    cancelledItems: 0,
    elapsedSeconds: 12,
    estimatedRemaining: null,
    announcement: { processedItems: 3, totalItems: 7 },
    effectiveConcurrency: 2,
    serverConcurrency: 4,
  };
  const markup = renderToStaticMarkup(<BatchAnalysisPanel {...input} />);
  expect(markup).toContain(
    'class="px-progress" role="progressbar" aria-label="Aggregate progress" aria-valuemin="0" aria-valuemax="7" aria-valuenow="3"',
  );
  expect(markup).toContain("Batch progress: 3 of 7 processed.");
  expect(markup).not.toContain("<progress");
});

it("keeps 17 repository choices compact while retaining their options, safety and source links", () => {
  const repositories: GuidedRepository[] = Array.from(
    { length: 17 },
    (_, index) => ({
      metadata: {
        slug: `owner/project-${index}`,
        name: `project-${index}`,
        description: `Details ${index}`,
        primary_language: "TypeScript",
        default_branch: "main",
        is_fork: index === 15,
        is_archived: index === 16,
        updated_at: null,
        html_url: `https://github.com/owner/project-${index}`,
      },
      selected: index === 0,
      ref: null,
      include: [],
      exclude: [],
      confirmedSelectionFingerprint: null,
      analysisStatus: "idle",
      analysis: null,
      ownerStatement: "",
      proposal: null,
      confirmedContribution: null,
      previousContribution: null,
    }),
  );
  const markup = renderToStaticMarkup(
    <GuidedOnboardingView
      {...props}
      state={{ ...props.state, step: "repositories", repositories }}
    />,
  );
  expect(markup).toContain('<details class="p4-w1-sources">');
  const rows = markup.split('class="guided-onboarding__repository"').slice(1);
  expect(rows).toHaveLength(17);
  rows.forEach((row, index) => {
    const [header, details] = row.split(
      '<details class="p4-w1-repository__details">',
    );
    expect(header).toContain(`<strong>project-${index}</strong>`);
    expect(header).toContain(
      `<span class="visually-hidden">owner/project-${index}</span>`,
    );
    expect(header).toContain('<span class="px-badge">TypeScript</span>');
    expect(header).not.toContain(`Details ${index}`);
    expect(details).toContain(`Details ${index}`);
    expect(details).toContain(
      `href="https://github.com/owner/project-${index}"`,
    );
    expect(details).toContain(`id="guided-include-owner-project-${index}"`);
  });
  expect(rows[16]).toContain(
    '<input disabled="" id="guided-repository-owner-project-16" type="checkbox"/>',
  );
  expect(rows[16]).toContain(" · archived");
  expect(rows[15]).toContain("fork");
});
