import type { Locale } from "../../i18n/messages";
import {
  onboardingProgress,
  type GuidedOnboardingState,
  type GuidedStep,
} from "./guidedOnboarding";

interface Props {
  copy: {
    progress: string;
    steps: Record<GuidedStep, string>;
  };
  locale: Locale;
  state: GuidedOnboardingState;
}

export function OnboardingStepper({ copy, locale, state }: Props) {
  const { steps, completed, total } = onboardingProgress(state);
  const current = steps.indexOf(state.step);
  if (current < 0) return null;
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
      <progress aria-label={copy.progress} max={total} value={completed}>
        {completed}/{total}
      </progress>
      <details className="onboarding-stepper__details">
        <summary>
          {routeLabel} ·{" "}
          {locale === "zh-TW"
            ? `目前第 ${current + 1} 步，共 ${total} 步 · 已完成 ${completed}/${total}`
            : `Step ${current + 1} of ${total} · ${completed}/${total} complete`}
        </summary>
        <StepList copy={copy} current={current} steps={steps} />
      </details>
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
