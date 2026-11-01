import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { EmbeddingProfilePanel } from "./EmbeddingProfilePanel";
import { embeddingProfileErrorMessage } from "./embeddingProfileError";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { initialGuidedOnboardingState } from "./guidedOnboarding";

describe.each([
  [
    "zh-TW",
    "這個 GitHub repository 是空專案，沒有內容可以分析。請改選其他專案。",
  ],
  [
    "en",
    "This GitHub repository is an empty project, so there is nothing to analyze. Choose another project.",
  ],
] as const)("empty repository messages in %s", (locale, message) => {
  it("renders the guided onboarding failure as plain actionable text", () => {
    const markup = renderToStaticMarkup(
      <GuidedOnboardingView
        locale={locale}
        state={initialGuidedOnboardingState()}
        busy={false}
        errorCode="EMPTY_REPOSITORY"
        draft=""
        validation={null}
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
    expect(markup).toContain(message);
    expect(markup).not.toContain("EMPTY_REPOSITORY");
    expect(markup).not.toMatch(/稍後|try again later|temporarily unavailable/i);
  });

  it.each(["request", "stored"] as const)(
    "renders the %s embedding reindex failure without retry advice",
    (surface) => {
      const markup = renderToStaticMarkup(
        <EmbeddingProfilePanel
          locale={locale}
          connections={[]}
          catalog={[]}
          installedModels={[]}
          pending={false}
          error={
            surface === "request"
              ? embeddingProfileErrorMessage(
                  locale,
                  new Error("EMPTY_REPOSITORY"),
                )
              : ""
          }
          profiles={
            surface === "stored"
              ? [
                  {
                    profile_id: "embedding-fixture",
                    provider: "ollama",
                    model_id: "fixture",
                    dimension: 1024,
                    normalized: true,
                    connection_reference: null,
                    status: "reindex_required",
                    active: false,
                    last_error_code: "EMPTY_REPOSITORY",
                    last_probed_at: null,
                  },
                ]
              : []
          }
          onRefresh={vi.fn()}
          onCreate={vi.fn()}
          onProbe={vi.fn()}
          onActivate={vi.fn()}
          onDelete={vi.fn()}
          onOllamaPull={vi.fn()}
          onOllamaDelete={vi.fn()}
        />,
      );
      expect(markup).toContain(message);
      expect(markup).not.toContain("EMPTY_REPOSITORY");
      expect(markup).not.toMatch(
        /稍後|try again later|temporarily unavailable/i,
      );
    },
  );
});
