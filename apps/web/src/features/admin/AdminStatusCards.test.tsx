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
    expect(markup).toContain("1/4");
    expect(markup).toContain('<progress max="4" value="0">0/4</progress>');
    expect(markup).not.toContain(">Models<");
    expect(markup).not.toContain(">Analysis<");
    expect(markup).toContain('aria-current="step"');
  });
});
