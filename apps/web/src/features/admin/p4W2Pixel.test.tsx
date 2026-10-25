import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { ClaimEditor } from "./ClaimEditor";
import {
  initialGuidedOnboardingState,
  type GuidedOnboardingViewProps,
  type GuidedStep,
} from "./guidedOnboarding";

function markup(step: GuidedStep, locale: "zh-TW" | "en") {
  const props: GuidedOnboardingViewProps = {
    locale,
    state: {
      ...initialGuidedOnboardingState(),
      step,
      profile: {
        ...initialGuidedOnboardingState().profile,
        greeting: { "zh-TW": "", en: "" },
      },
    },
    busy: false,
    errorCode: "",
    draft: "",
    validation: null,
    onOpenPublication: vi.fn(),
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
  "keeps the four w2 steps semantic and pixel styled in %s",
  (locale) => {
    for (const step of [
      "contributions",
      "profile",
      "review",
      "draft",
    ] as const) {
      const html = markup(step, locale);
      expect(html).toContain(`aria-labelledby="guided-${step}-heading"`);
      expect(html).toContain(`id="guided-${step}-heading"`);
      expect(html).toContain(`p4-w2--${step} px-panel px-panel--raised`);
      expect(html).not.toMatch(/style="[^"]*(?:color|background)/i);
      expect(html).toMatch(/<button[^>]*class="[^"]*\bpx-button\b/);
    }
  },
);

it.each(["zh-TW", "en"] as const)(
  "links every missing profile field to adjacent validation in %s",
  (locale) => {
    const html = markup("profile", locale);
    const fieldIds = [
      "display-name",
      "github-login",
      "headline-zh-TW",
      "headline-en",
      "bio-zh-TW",
      "bio-en",
      "greeting-zh-TW",
      "greeting-en",
    ];
    for (const field of fieldIds) {
      const id = `guided-profile-${field}`;
      expect(html).toContain(`href="#${id}"`);
      expect(html).toMatch(
        new RegExp(
          `id="${id}"[^>]*aria-invalid="true"[^>]*aria-describedby="${id}-required"`,
        ),
      );
      expect(html).toContain(`id="${id}-required"`);
    }
    expect(html).toMatch(
      /<footer class="p4-w2__confirm"><button aria-describedby="guided-profile-confirm-reason" disabled="" class="ux-primary px-button px-button--primary"/,
    );
    expect(html).toContain('id="guided-profile-confirm-reason"');
    expect(html).toContain('id="guided-profile-github-help"');
  },
);

it.each(["zh-TW", "en"] as const)(
  "retains independent statement editor labels, limits and disabled state in %s",
  (locale) => {
    const html = renderToStaticMarkup(
      <ClaimEditor
        locale={locale}
        id="claim-test"
        kind="responsibility"
        statement={{ "zh-TW": "原文", en: "Original" }}
        disabled
        onChange={vi.fn()}
      />,
    );
    expect(html).toContain('class="p4-w2-claim p4-w2__fields" disabled=""');
    for (const field of ["kind", "zh-TW", "en"]) {
      expect(html).toContain(`for="claim-test-${field}"`);
      expect(html).toContain(`id="claim-test-${field}"`);
    }
    expect(html.match(/maxLength="4000"/g)).toHaveLength(2);
    expect(html.match(/class="px-field"/g)).toHaveLength(3);
  },
);
