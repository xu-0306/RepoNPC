import type { Locale } from "../../i18n/messages";
import type { GuidedOnboardingState, GuidedStep } from "./guidedOnboarding";

interface Props {
  copy: {
    progress: string;
    steps: Record<GuidedStep, string>;
  };
  locale: Locale;
  state: GuidedOnboardingState;
}

export function OnboardingStepper({ copy, locale, state }: Props) {
  const steps: readonly GuidedStep[] =
    state.route === "manual"
      ? ["repositories", "contributions", "profile", "review"]
      : [
          "models",
          "repositories",
          "analysis",
          "contributions",
          "profile",
          "review",
        ];
  const current = steps.indexOf(state.step);
  if (current < 0) return null;
  const currentLabel = copy.steps[state.step];
  const routeLabel =
    locale === "zh-TW"
      ? state.route === "manual"
        ? "手動路線"
        : "AI 路線"
      : state.route === "manual"
        ? "Manual route"
        : "AI route";

  return (
    <nav aria-label={copy.progress} className="onboarding-stepper">
      <div className="onboarding-stepper__summary">
        <span>{routeLabel}</span>
        <strong>{currentLabel}</strong>
        <span>
          {current + 1}/{steps.length}
        </span>
      </div>
      <progress max={steps.length} value={current}>
        {current}/{steps.length}
      </progress>
      <details className="onboarding-stepper__details">
        <summary>
          {copy.progress}: {current + 1}/{steps.length}
        </summary>
        <StepList copy={copy} current={current} steps={steps} />
      </details>
      <div className="onboarding-stepper__desktop">
        <StepList copy={copy} current={current} steps={steps} />
      </div>
    </nav>
  );
}

function StepList({
  copy,
  current,
  steps,
}: {
  copy: Props["copy"];
  current: number;
  steps: readonly GuidedStep[];
}) {
  return (
    <ol>
      {steps.map((step, index) => (
        <li
          aria-current={index === current ? "step" : undefined}
          data-state={
            index < current
              ? "complete"
              : index === current
                ? "current"
                : "upcoming"
          }
          key={step}
        >
          <span aria-hidden="true">{index + 1}</span>
          <span>{copy.steps[step]}</span>
        </li>
      ))}
    </ol>
  );
}
