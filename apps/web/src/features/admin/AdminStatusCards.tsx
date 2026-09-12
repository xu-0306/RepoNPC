import type { CSSProperties } from "react";

import type { Locale } from "../../i18n/messages";
import type { GuidedOnboardingState, GuidedStep } from "./guidedOnboarding";
import { ModelBrandIcon, type ModelProvider } from "./ModelBrandIcon";

export type AdminModelState =
  | "unconfigured"
  | "testing"
  | "tested"
  | "selected"
  | "unavailable";

export interface AdminModelSummary {
  model: string | null;
  connection: string | null;
  provider: ModelProvider | null;
  state: AdminModelState;
}

export interface AdminWorkspaceStatus {
  chat: AdminModelSummary;
  embedding: AdminModelSummary;
  publicBundleId: string | null;
}

interface Props {
  locale: Locale;
  state: GuidedOnboardingState;
  status: AdminWorkspaceStatus;
}

const COPY = {
  "zh-TW": {
    heading: "工作區狀態",
    progress: "設定進度",
    projects: "已選專案",
    chat: "分析與回答模型",
    embedding: "資料查找模型",
    publicSite: "公開網站",
    notStarted: "尚未開始",
    current: (current: number, total: number) =>
      `目前第 ${current} 步，共 ${total} 步`,
    completed: (completed: number, total: number) =>
      `已完成 ${completed}/${total}`,
    projectCount: (count: number) => `${count} 個專案`,
    confirmed: "清單已確認",
    unconfirmed: "尚未確認清單",
    publicReady: "網站資料已啟用",
    publicPending: "尚未就緒",
    connection: (value: string) => `連線：${value}`,
    modelStates: {
      unconfigured: "尚未設定",
      testing: "正在處理",
      tested: "已測試，尚未選用",
      selected: "已選用",
      unavailable: "目前無法使用",
    },
  },
  en: {
    heading: "Workspace status",
    progress: "Setup progress",
    projects: "Selected projects",
    chat: "Analysis and chat",
    embedding: "Content finder",
    publicSite: "Public website",
    notStarted: "Not started",
    current: (current: number, total: number) => `Step ${current} of ${total}`,
    completed: (completed: number, total: number) =>
      `${completed}/${total} complete`,
    projectCount: (count: number) => `${count} projects`,
    confirmed: "Selection confirmed",
    unconfirmed: "Selection not confirmed",
    publicReady: "Website data is active",
    publicPending: "Not ready yet",
    connection: (value: string) => `Connection: ${value}`,
    modelStates: {
      unconfigured: "Not configured",
      testing: "Working",
      tested: "Tested; not selected",
      selected: "Selected",
      unavailable: "Unavailable",
    },
  },
} as const;

const AI_STEPS: readonly GuidedStep[] = [
  "models",
  "repositories",
  "analysis",
  "contributions",
  "profile",
  "review",
];

const MANUAL_STEPS: readonly GuidedStep[] = [
  "repositories",
  "contributions",
  "profile",
  "review",
];

function onboardingProgress(state: GuidedOnboardingState): {
  completed: number;
  current: number;
  total: number;
} {
  const steps = state.route === "manual" ? MANUAL_STEPS : AI_STEPS;
  if (state.step === "intro") {
    return { completed: 0, current: 0, total: steps.length };
  }
  if (state.step === "draft") {
    return {
      completed: steps.length,
      current: steps.length,
      total: steps.length,
    };
  }
  const index = steps.indexOf(state.step);
  if (index < 0) return { completed: 0, current: 0, total: steps.length };
  return { completed: index, current: index + 1, total: steps.length };
}

export function AdminStatusCards({ locale, state, status }: Props) {
  const copy = COPY[locale];
  const progress = onboardingProgress(state);
  const selected = state.repositories.filter(
    (repository) => repository.selected,
  ).length;
  const progressStyle = {
    "--admin-progress": `${Math.round(
      (progress.completed / progress.total) * 360,
    )}deg`,
  } as CSSProperties;

  return (
    <section
      aria-labelledby="admin-status-cards-heading"
      className="admin-status-cards"
    >
      <h2 className="visually-hidden" id="admin-status-cards-heading">
        {copy.heading}
      </h2>
      <div className="admin-status-card admin-status-card--progress">
        <StatusIcon kind="progress" />
        <span
          aria-hidden="true"
          className="admin-status-card__progress-ring"
          style={progressStyle}
        >
          {progress.completed}/{progress.total}
        </span>
        <StatusCopy
          detail={
            progress.current > 0
              ? copy.current(progress.current, progress.total)
              : copy.notStarted
          }
          label={copy.progress}
          value={copy.completed(progress.completed, progress.total)}
        />
      </div>
      <div className="admin-status-card">
        <StatusIcon kind="projects" />
        <StatusCopy
          detail={state.selectionConfirmed ? copy.confirmed : copy.unconfirmed}
          label={copy.projects}
          value={copy.projectCount(selected)}
        />
      </div>
      <ModelStatusCard
        copy={copy}
        icon="chat"
        label={copy.chat}
        summary={status.chat}
      />
      <ModelStatusCard
        copy={copy}
        icon="search"
        label={copy.embedding}
        summary={status.embedding}
      />
      <div className="admin-status-card">
        <StatusIcon kind="public" />
        <StatusCopy
          detail={
            status.publicBundleId ? status.publicBundleId : copy.publicPending
          }
          label={copy.publicSite}
          value={status.publicBundleId ? copy.publicReady : copy.publicPending}
        />
        <span
          className={`admin-status-card__badge admin-status-card__badge--${
            status.publicBundleId ? "selected" : "unconfigured"
          }`}
        >
          {status.publicBundleId
            ? copy.modelStates.selected
            : copy.publicPending}
        </span>
      </div>
    </section>
  );
}

function ModelStatusCard({
  copy,
  icon,
  label,
  summary,
}: {
  copy: (typeof COPY)[Locale];
  icon: "chat" | "search";
  label: string;
  summary: AdminModelSummary;
}) {
  return (
    <div className="admin-status-card">
      {summary.provider ? (
        <ModelBrandIcon modelId={summary.model} provider={summary.provider} />
      ) : (
        <StatusIcon kind={icon} />
      )}
      <StatusCopy
        detail={
          summary.connection
            ? copy.connection(summary.connection)
            : copy.modelStates[summary.state]
        }
        label={label}
        value={summary.model ?? copy.modelStates[summary.state]}
      />
      <span
        className={`admin-status-card__badge admin-status-card__badge--${summary.state}`}
      >
        {copy.modelStates[summary.state]}
      </span>
    </div>
  );
}

function StatusCopy({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <span className="admin-status-card__copy">
      <span className="admin-status-card__label">{label}</span>
      <strong>{value}</strong>
      <span className="admin-status-card__detail">{detail}</span>
    </span>
  );
}

function StatusIcon({
  kind,
}: {
  kind: "progress" | "projects" | "chat" | "search" | "public";
}) {
  const paths = {
    progress: <path d="M12 5v7l4 2M4.9 5.1a10 10 0 1 0 2-1.5" />,
    projects: <path d="M3 6.5h6l2 2h10v10.5H3z" />,
    chat: <path d="M4 5h16v11H9l-5 4zm4 5h.01M12 10h.01M16 10h.01" />,
    search: (
      <path d="m20 20-4.5-4.5M10.5 17a6.5 6.5 0 1 1 0-13 6.5 6.5 0 0 1 0 13Z" />
    ),
    public: <path d="M4 5h16v14H4zm0 4h16M8 5v4m4-4v4" />,
  } as const;
  return (
    <svg
      aria-hidden="true"
      className="admin-status-card__icon"
      fill="none"
      viewBox="0 0 24 24"
    >
      <g
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      >
        {paths[kind]}
      </g>
    </svg>
  );
}
