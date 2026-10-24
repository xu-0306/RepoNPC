import { useEffect, useState, type CSSProperties } from "react";

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

const COPY = {
  "zh-TW": {
    heading: "設定任務",
    ai: "AI 路線",
    manual: "手動路線",
    current: (step: number, total: number, completed: number) =>
      `目前第 ${step} 步，共 ${total} 步 · 已完成 ${completed}/${total}`,
  },
  en: {
    heading: "Setup quests",
    ai: "AI route",
    manual: "Manual route",
    current: (step: number, total: number, completed: number) =>
      `Step ${step} of ${total} · ${completed}/${total} complete`,
  },
} as const;

export function OnboardingStepper({ copy, locale, state }: Props) {
  const { steps, completed, total } = onboardingProgress(state);
  const current = steps.indexOf(state.step);
  const [wide, setWide] = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 761px)");
    const update = () => setWide(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  if (current < 0) return null;
  const labels = COPY[locale];
  const routeLabel = state.route === "manual" ? labels.manual : labels.ai;

  return (
    <nav
      aria-label={copy.progress}
      className="onboarding-stepper px-panel px-panel--inset"
    >
      <details
        className="onboarding-stepper__details"
        open={wide || expanded}
        onToggle={(event) => {
          if (!wide) setExpanded(event.currentTarget.open);
        }}
      >
        <summary>
          <span className="onboarding-stepper__summary-full">
            {labels.heading} · {routeLabel} ·{" "}
            {labels.current(current + 1, total, completed)}
          </span>
          <span
            className="onboarding-stepper__summary-compact"
            aria-hidden="true"
          >
            {routeLabel} · {current + 1}/{total}
          </span>
        </summary>
        <h2>{labels.heading}</h2>
        <div className="onboarding-stepper__xp">
          <span className="px-meta">{copy.progress}</span>
          <strong className="px-display">
            {completed} / {total}
          </strong>
        </div>
        <div
          aria-label={copy.progress}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={completed}
          className="px-progress"
          role="progressbar"
          style={
            {
              "--px-progress": `${(completed / total) * 100}%`,
            } as CSSProperties
          }
        />
        <p className="onboarding-stepper__route px-meta">
          {routeLabel} · {labels.current(current + 1, total, completed)}
        </p>
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
          <span aria-hidden="true" className="px-display">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span>{copy.steps[step]}</span>
        </li>
      ))}
    </ol>
  );
}
