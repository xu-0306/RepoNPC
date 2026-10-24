import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AdminStatusCards } from "./AdminStatusCards";
import { initialGuidedOnboardingState } from "./guidedOnboarding";
import { OnboardingStepper } from "./OnboardingStepper";

const steps = {
  intro: "Welcome",
  models: "Models",
  repositories: "Projects",
  analysis: "Analysis",
  contributions: "Contributions",
  profile: "Profile",
  review: "Preview",
  draft: "Draft",
} as const;

describe("admin workspace navigation and status", () => {
  it("does not count the welcome or current first AI step as completed", () => {
    const intro = initialGuidedOnboardingState();
    const status = {
      chat: {
        model: null,
        connection: null,
        provider: null,
        state: "unconfigured" as const,
      },
      embedding: {
        model: null,
        connection: null,
        provider: null,
        state: "unconfigured" as const,
      },
      publicBundleId: null,
    };
    const welcome = renderToStaticMarkup(
      <AdminStatusCards locale="en" state={intro} status={status} />,
    );
    const firstStep = renderToStaticMarkup(
      <AdminStatusCards
        locale="en"
        state={{ ...intro, step: "models", route: "ai" }}
        status={status}
      />,
    );

    expect(welcome).toContain("0/6 complete");
    expect(welcome).toContain("Not started");
    expect(welcome).toContain('<details class="admin-status-overview">');
    expect(welcome).not.toContain("<details open");
    expect(welcome.match(/Not configured/g)).toHaveLength(2);
    expect(firstStep).toContain("0/6 complete");
    expect(firstStep).toContain("Step 1 of 6");
  });

  it("renders five truthful status cards without exposing connection ids", () => {
    const state = {
      ...initialGuidedOnboardingState(),
      step: "models" as const,
    };
    const markup = renderToStaticMarkup(
      <AdminStatusCards
        locale="en"
        state={state}
        status={{
          chat: {
            model: "chat-model-with-a-long-name",
            connection: "Private gateway",
            provider: "openai_compatible",
            state: "tested",
          },
          embedding: {
            model: "embedding-model",
            connection: null,
            provider: "ollama",
            state: "selected",
          },
          publicBundleId: null,
        }}
      />,
    );

    expect(markup.match(/class="admin-status-card(?: |")/g)).toHaveLength(5);
    expect(markup).toContain("0/6 complete");
    expect(markup).toContain("Tested; not selected");
    expect(markup).toContain("Private gateway");
    expect(markup).toContain('class="model-brand-icon"');
    expect(markup).toContain("Not ready yet");
    expect(markup).not.toContain("connection_id");
  });

  it("uses only the four applicable steps for the manual route", () => {
    const state = {
      ...initialGuidedOnboardingState(),
      step: "repositories" as const,
      route: "manual" as const,
    };
    const markup = renderToStaticMarkup(
      <OnboardingStepper
        copy={{ progress: "Setup progress", steps }}
        locale="en"
        state={state}
      />,
    );

    expect(markup).toContain("Manual route");
    expect(markup).toContain("Step 1 of 4 · 0/4 complete");
    expect(markup).toContain(
      'aria-label="Setup progress" aria-valuemin="0" aria-valuemax="4" aria-valuenow="0"',
    );
    expect(markup).not.toContain(">Models<");
    expect(markup).not.toContain(">Analysis<");
    expect(markup).toContain('aria-current="step"');
  });
});

describe("shared onboarding progress", () => {
  it.each([
    ["ai", "models", 0, 6],
    ["ai", "analysis", 2, 6],
    ["manual", "contributions", 1, 4],
    ["manual", "review", 3, 4],
  ] as const)(
    "keeps %s %s completion consistent in both displays",
    (route, step, completed, total) => {
      const state = { ...initialGuidedOnboardingState(), route, step };
      const markup = renderToStaticMarkup(
        <OnboardingStepper
          copy={{ progress: "Setup progress", steps }}
          locale="en"
          state={state}
        />,
      );
      expect(markup).toContain(`${completed}/${total} complete`);
      expect(markup).toContain(
        `aria-valuemax="${total}" aria-valuenow="${completed}"`,
      );
      expect(markup).toContain(`Step ${completed + 1} of ${total}`);
    },
  );
});

it.each(["ai", "manual"] as const)(
  "renders display-only %s quests with a collapsed phone disclosure",
  (route) => {
    const markup = renderToStaticMarkup(
      <OnboardingStepper
        copy={{ progress: "Setup progress", steps }}
        locale="en"
        state={{ ...initialGuidedOnboardingState(), route, step: "profile" }}
      />,
    );
    expect(markup).toContain('<details class="onboarding-stepper__details">');
    expect(markup).toContain('role="progressbar"');
    expect(markup).toContain('aria-current="step" data-state="current"');
    expect(markup).toContain('data-state="complete"');
    expect(markup).toContain('data-state="upcoming"');
    expect(markup.match(/<li /g)).toHaveLength(route === "ai" ? 6 : 4);
    expect(markup).not.toContain("<button");
    expect(markup).not.toContain("<a ");
  },
);

it.each([
  ["zh-TW", "ai", "AI 路線", 5, 6],
  ["zh-TW", "manual", "手動路線", 3, 4],
  ["en", "ai", "AI route", 5, 6],
  ["en", "manual", "Manual route", 3, 4],
] as const)(
  "keeps the full progress name behind a compact %s %s phone summary",
  (locale, route, routeLabel, current, total) => {
    const markup = renderToStaticMarkup(
      <OnboardingStepper
        copy={{ progress: "Setup progress", steps }}
        locale={locale}
        state={{ ...initialGuidedOnboardingState(), route, step: "profile" }}
      />,
    );
    const summary = markup.match(/<summary>(.*?)<\/summary>/)?.[1];
    expect(summary).toContain(
      '<span class="onboarding-stepper__summary-full">',
    );
    expect(summary).toContain(
      locale === "en"
        ? `Setup quests · ${routeLabel} · Step ${current} of ${total} · ${current - 1}/${total} complete`
        : `設定任務 · ${routeLabel} · 目前第 ${current} 步，共 ${total} 步 · 已完成 ${current - 1}/${total}`,
    );
    expect(summary).toContain(
      `<span class="onboarding-stepper__summary-compact" aria-hidden="true">${routeLabel} · ${current}/${total}</span>`,
    );
    expect(markup).toContain(
      `aria-valuemax="${total}" aria-valuenow="${current - 1}"`,
    );
    expect(markup).toContain('<details class="onboarding-stepper__details">');
    expect(markup.match(/<li /g)).toHaveLength(total);
  },
);
