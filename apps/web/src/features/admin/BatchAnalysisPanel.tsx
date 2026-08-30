import type { Locale } from "../../i18n/messages";

export type BatchPreflightStatus =
  | "idle"
  | "loading"
  | "ready"
  | "blocked"
  | "failed";

export type BatchConnectionStatus =
  | "ready"
  | "checking"
  | "connection_required"
  | "unavailable";

export type BatchRateBudgetStatus = "available" | "limited" | "exhausted";

export type BatchPreflightBlocker =
  | "connection_required"
  | "provider_unavailable"
  | "rate_limited"
  | "selection_changed"
  | "no_repositories";

export interface BatchOperationError {
  scope: "preflight" | "batch" | "repository" | "batch_action";
  code: string;
  batchId?: string;
  slug?: string;
  retryAfterSeconds?: number;
  retryAt?: string;
  requestId?: string;
}

export interface BatchDurationEstimate {
  minimumSeconds: number;
  maximumSeconds: number;
  confidence: "low" | "medium" | "high";
}

export interface BatchPreflightPlan {
  selectionCount: number;
  cachedResultCount: number;
  connection: BatchConnectionStatus;
  rateBudget: BatchRateBudgetStatus;
  providerReady: boolean;
  effectiveConcurrency: number;
  serverConcurrency: number;
  maximumGenerationAttempts: number;
  estimatedDuration: BatchDurationEstimate | null;
}

export type BatchPreflightState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; plan: BatchPreflightPlan }
  | { status: "blocked"; blockers: readonly BatchPreflightBlocker[] }
  | { status: "failed"; error: BatchOperationError };

export type BatchJobStatus =
  | "queued"
  | "running"
  | "paused"
  | "cancelling"
  | "cancelled"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type BatchRepositoryStage =
  | "queued"
  | "resolving_commit"
  | "fetching_source"
  | "filtering"
  | "indexing"
  | "embedding"
  | "generating"
  | "validating"
  | "cleaning_up"
  | "complete";

export type BatchRepositoryState =
  | "queued"
  | "active"
  | "waiting_rate_limit"
  | "waiting_reconnection"
  | "needs_retry_confirmation"
  | "failed"
  | "cancelled"
  | "complete";

export interface BatchRepositoryItem {
  slug: string;
  stage: BatchRepositoryStage;
  state: BatchRepositoryState;
  retryable: boolean;
  error: BatchOperationError | null;
}

export interface BatchJobSnapshot {
  id: string;
  status: BatchJobStatus;
  items: readonly BatchRepositoryItem[];
}

export interface BatchProgressAnnouncement {
  completedItems: number;
  totalItems: number;
}

export interface BatchProgressState {
  totalItems: number;
  completedItems: number;
  activeItems: number;
  failedItems: number;
  cancelledItems: number;
  elapsedSeconds: number;
  estimatedRemaining: BatchDurationEstimate | null;
  effectiveConcurrency: number | null;
  serverConcurrency: number | null;
  /**
   * The caller updates this compact snapshot on a throttled cadence. It is the
   * only aggregate value announced in the polite progress region.
   */
  announcement: BatchProgressAnnouncement | null;
}

export type BatchSseConnectionState =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

export interface BatchSseState {
  connection: BatchSseConnectionState;
  reconnectAttempts: number;
  /** Retained by the client for Last-Event-ID, never rendered. */
  lastEventId: string | null;
}

export type BatchAction = "pause" | "resume" | "cancel" | "retry";

export interface BatchActionState {
  pending: BatchAction | null;
  error: BatchOperationError | null;
}

export interface BatchActionAvailability {
  pause: boolean;
  resume: boolean;
  cancel: boolean;
  retry: boolean;
}

export interface BatchAnalysisPanelProps {
  locale: Locale;
  preflight: BatchPreflightState;
  job: BatchJobSnapshot | null;
  progress: BatchProgressState | null;
  stream: BatchSseState;
  actions: BatchActionState;
  onPause: (batchId: string) => void;
  onResume: (batchId: string) => void;
  onCancel: (batchId: string) => void;
  onRetry: (batchId: string) => void;
}

type Copy = {
  eyebrow: string;
  title: string;
  description: string;
  preflightHeading: string;
  preflightIdle: string;
  preflightLoading: string;
  preflightReady: string;
  preflightBlocked: string;
  preflightFailed: string;
  repositories: string;
  cachePrediction: string;
  connection: string;
  rateBudget: string;
  provider: string;
  concurrency: string;
  maxGenerationAttempts: string;
  estimate: string;
  noEstimate: string;
  notReported: string;
  confidence: (confidence: BatchDurationEstimate["confidence"]) => string;
  blocker: (blocker: BatchPreflightBlocker) => string;
  connectionStatus: (status: BatchConnectionStatus) => string;
  rateStatus: (status: BatchRateBudgetStatus) => string;
  providerReady: string;
  providerUnavailable: string;
  batchHeading: string;
  noBatch: string;
  status: string;
  stream: string;
  streamState: (state: BatchSseState) => string;
  progress: string;
  progressSummary: (progress: BatchProgressState) => string;
  progressAnnouncement: (announcement: BatchProgressAnnouncement) => string;
  elapsed: string;
  remaining: string;
  effectiveConcurrency: string;
  serverConcurrency: string;
  completed: string;
  failed: string;
  cancelled: string;
  active: string;
  repositoryHeading: string;
  stage: string;
  actionHeading: string;
  pause: string;
  resume: string;
  cancel: string;
  retry: string;
  pauseUnavailable: string;
  resumeUnavailable: string;
  cancelUnavailable: string;
  retryUnavailable: string;
  actionPending: (action: BatchAction) => string;
  actionFailed: string;
  repositoryFailed: string;
  retryAfter: (seconds: number) => string;
  batchStatus: (status: BatchJobStatus) => string;
};

const COPY: Record<Locale, Copy> = {
  "zh-TW": {
    eyebrow: "受控批次作業",
    title: "批次分析",
    description:
      "伺服器會依照容量與 GitHub 限制處理已確認的公開 repositories；進度不會揭露憑證、請求內容或來源資料。",
    preflightHeading: "分析前檢查",
    preflightIdle: "確認 repository 選擇後，即可建立分析前檢查。",
    preflightLoading: "正在檢查 GitHub 連線、快取、容量與 provider 狀態。",
    preflightReady: "分析前檢查已完成，可以建立批次。",
    preflightBlocked: "分析前檢查已封鎖；請先處理下列項目。",
    preflightFailed: "分析前檢查未完成。請重新檢查後再建立批次。",
    repositories: "已選 repositories",
    cachePrediction: "預測快取命中",
    connection: "GitHub 連線",
    rateBudget: "GitHub 配額",
    provider: "模型 provider",
    concurrency: "預計並行數",
    maxGenerationAttempts: "每個 repository 的最多生成次數",
    estimate: "預估時間",
    noEstimate: "目前無法提供預估時間",
    notReported: "伺服器尚未回報",
    confidence: (confidence) =>
      ({ low: "信心低", medium: "信心中等", high: "信心高" })[confidence],
    blocker: (blocker) =>
      ({
        connection_required: "需要重新連接 GitHub，才能開始分析。",
        provider_unavailable: "模型 provider 尚未就緒，無法開始分析。",
        rate_limited: "GitHub 目前限制新的工作；請依重試時間再試。",
        selection_changed: "選擇的 repositories 已變更，請重新執行分析前檢查。",
        no_repositories: "請至少選擇一個公開 repository。",
      })[blocker],
    connectionStatus: (status) =>
      ({
        ready: "已就緒",
        checking: "檢查中",
        connection_required: "需要重新連接",
        unavailable: "無法使用",
      })[status],
    rateStatus: (status) =>
      ({ available: "可使用", limited: "暫時受限", exhausted: "已用盡" })[
        status
      ],
    providerReady: "已就緒",
    providerUnavailable: "尚未就緒",
    batchHeading: "批次進度",
    noBatch: "尚未建立分析批次。建立後，這裡會顯示可回復的伺服器端進度。",
    status: "批次狀態",
    stream: "即時進度連線",
    streamState: (state) => {
      if (state.connection === "reconnecting") {
        return `正在重新連線即時進度（第 ${state.reconnectAttempts} 次）。`;
      }
      return {
        idle: "批次開始後會連接即時進度。",
        connecting: "正在連接即時進度。",
        connected: "即時進度已連接。",
        disconnected: "即時進度已中斷；畫面會以最新快照繼續顯示。",
        error: "即時進度暫時無法使用；畫面會以最新快照繼續顯示。",
        reconnecting: "",
      }[state.connection];
    },
    progress: "彙總進度",
    progressSummary: (progress) =>
      `已完成 ${progress.completedItems}/${progress.totalItems}；進行中 ${progress.activeItems}；失敗 ${progress.failedItems}；已取消 ${progress.cancelledItems}。`,
    progressAnnouncement: (announcement) =>
      `批次進度：已完成 ${announcement.completedItems}/${announcement.totalItems}。`,
    elapsed: "已耗時間",
    remaining: "預估剩餘時間",
    effectiveConcurrency: "有效並行數",
    serverConcurrency: "伺服器上限",
    completed: "已完成",
    failed: "失敗",
    cancelled: "已取消",
    active: "進行中",
    repositoryHeading: "各 repository 的進度",
    stage: "階段",
    actionHeading: "批次操作",
    pause: "暫停批次",
    resume: "繼續批次",
    cancel: "取消批次",
    retry: "重試需要確認的項目",
    pauseUnavailable: "只有執行中的批次可以暫停。",
    resumeUnavailable: "只有已暫停的批次可以繼續。",
    cancelUnavailable: "只有佇列中、執行中或已暫停的批次可以取消。",
    retryUnavailable: "沒有需要明確確認重試的 repository。",
    actionPending: (action) =>
      `正在${{ pause: "暫停", resume: "繼續", cancel: "取消", retry: "重試" }[action]}批次。`,
    actionFailed: "批次操作未完成。請確認目前狀態後再試。",
    repositoryFailed:
      "此 repository 需要處理；詳細內容不會顯示在這個狀態面板。",
    retryAfter: (seconds) =>
      `請在約 ${formatDuration(seconds, "zh-TW")} 後再試。`,
    batchStatus: (status) => batchStatusLabel(status, "zh-TW"),
  },
  en: {
    eyebrow: "Bounded batch work",
    title: "Batch analysis",
    description:
      "The server processes confirmed public repositories within capacity and GitHub limits. Progress never exposes credentials, request bodies, or source data.",
    preflightHeading: "Analysis preflight",
    preflightIdle:
      "Create a preflight after confirming the repository selection.",
    preflightLoading:
      "Checking GitHub connection, cache, capacity, and provider readiness.",
    preflightReady: "Preflight is complete. The batch can be created.",
    preflightBlocked: "Preflight is blocked. Resolve the items below first.",
    preflightFailed:
      "Preflight did not complete. Check again before creating a batch.",
    repositories: "Selected repositories",
    cachePrediction: "Predicted cache hits",
    connection: "GitHub connection",
    rateBudget: "GitHub budget",
    provider: "Model provider",
    concurrency: "Planned concurrency",
    maxGenerationAttempts: "Maximum generations per repository",
    estimate: "Estimated duration",
    noEstimate: "An estimate is not available yet",
    notReported: "Not reported by the server",
    confidence: (confidence) =>
      ({
        low: "Low confidence",
        medium: "Medium confidence",
        high: "High confidence",
      })[confidence],
    blocker: (blocker) =>
      ({
        connection_required: "Reconnect GitHub before analysis can begin.",
        provider_unavailable:
          "The model provider is not ready, so analysis cannot begin.",
        rate_limited:
          "GitHub is limiting new work. Try again after its retry window.",
        selection_changed:
          "The repository selection changed. Run preflight again.",
        no_repositories: "Select at least one public repository.",
      })[blocker],
    connectionStatus: (status) =>
      ({
        ready: "Ready",
        checking: "Checking",
        connection_required: "Reconnect required",
        unavailable: "Unavailable",
      })[status],
    rateStatus: (status) =>
      ({
        available: "Available",
        limited: "Temporarily limited",
        exhausted: "Exhausted",
      })[status],
    providerReady: "Ready",
    providerUnavailable: "Not ready",
    batchHeading: "Batch progress",
    noBatch:
      "No analysis batch has been created. Recoverable server-side progress will appear here after it starts.",
    status: "Batch status",
    stream: "Live progress connection",
    streamState: (state) => {
      if (state.connection === "reconnecting") {
        return `Reconnecting live progress (attempt ${state.reconnectAttempts}).`;
      }
      return {
        idle: "Live progress will connect after the batch starts.",
        connecting: "Connecting live progress.",
        connected: "Live progress is connected.",
        disconnected:
          "Live progress disconnected; the latest snapshot remains visible.",
        error:
          "Live progress is temporarily unavailable; the latest snapshot remains visible.",
        reconnecting: "",
      }[state.connection];
    },
    progress: "Aggregate progress",
    progressSummary: (progress) =>
      `${progress.completedItems}/${progress.totalItems} complete; ${progress.activeItems} active; ${progress.failedItems} failed; ${progress.cancelledItems} cancelled.`,
    progressAnnouncement: (announcement) =>
      `Batch progress: ${announcement.completedItems} of ${announcement.totalItems} complete.`,
    elapsed: "Elapsed",
    remaining: "Estimated remaining",
    effectiveConcurrency: "Effective concurrency",
    serverConcurrency: "Server limit",
    completed: "Complete",
    failed: "Failed",
    cancelled: "Cancelled",
    active: "Active",
    repositoryHeading: "Repository progress",
    stage: "Stage",
    actionHeading: "Batch controls",
    pause: "Pause batch",
    resume: "Resume batch",
    cancel: "Cancel batch",
    retry: "Retry items that need confirmation",
    pauseUnavailable: "Only a running batch can be paused.",
    resumeUnavailable: "Only a paused batch can be resumed.",
    cancelUnavailable:
      "Only a queued, running, or paused batch can be cancelled.",
    retryUnavailable:
      "No repository currently needs an explicit retry confirmation.",
    actionPending: (action) =>
      `Batch ${{ pause: "pause", resume: "resume", cancel: "cancellation", retry: "retry" }[action]} is in progress.`,
    actionFailed:
      "The batch action did not complete. Check the current status and try again.",
    repositoryFailed:
      "This repository needs attention. Details are not shown in this status panel.",
    retryAfter: (seconds) =>
      `Try again in about ${formatDuration(seconds, "en")}.`,
    batchStatus: (status) => batchStatusLabel(status, "en"),
  },
};

const VISUALLY_HIDDEN_STYLE = {
  border: 0,
  clip: "rect(0 0 0 0)",
  height: "1px",
  margin: "-1px",
  overflow: "hidden",
  padding: 0,
  position: "absolute",
  whiteSpace: "nowrap",
  width: "1px",
} as const;

function batchActionAvailability(
  job: BatchJobSnapshot | null,
  actions: BatchActionState,
): BatchActionAvailability {
  if (!job) {
    return { pause: false, resume: false, cancel: false, retry: false };
  }

  return {
    pause: job.status === "running" && actions.pending !== "pause",
    resume: job.status === "paused" && actions.pending !== "resume",
    cancel:
      ["queued", "running", "paused"].includes(job.status) &&
      actions.pending !== "cancel",
    retry:
      job.items.some((item) => item.retryable) && actions.pending !== "retry",
  };
}

export function BatchAnalysisPanel({
  locale,
  preflight,
  job,
  progress,
  stream,
  actions,
  onPause,
  onResume,
  onCancel,
  onRetry,
}: BatchAnalysisPanelProps) {
  const copy = COPY[locale];
  const availability = batchActionAvailability(job, actions);

  return (
    <section
      aria-labelledby="batch-analysis-heading"
      className="guided-onboarding__step batch-analysis-panel"
      data-batch-status={job?.status ?? "not_created"}
      lang={locale}
    >
      <header className="guided-onboarding__header">
        <p className="guided-onboarding__eyebrow">{copy.eyebrow}</p>
        <h2 id="batch-analysis-heading">{copy.title}</h2>
        <p>{copy.description}</p>
      </header>

      <PreflightSummary copy={copy} locale={locale} preflight={preflight} />

      {actions.error && (
        <p className="guided-onboarding__error" role="alert">
          {operationErrorMessage(actions.error, copy)}
        </p>
      )}

      <section aria-labelledby="batch-progress-heading">
        <h3 id="batch-progress-heading">{copy.batchHeading}</h3>
        {!job && <p role="status">{copy.noBatch}</p>}
        {job && (
          <>
            <div className="guided-onboarding__provider-status">
              <div>
                <h4>{copy.status}</h4>
                <p data-batch-status={job.status}>
                  {copy.batchStatus(job.status)}
                </p>
              </div>
              <p aria-atomic="true" aria-live="polite" role="status">
                {copy.streamState(stream)}
              </p>
            </div>

            {progress ? (
              <ProgressSummary
                copy={copy}
                locale={locale}
                progress={progress}
              />
            ) : (
              <p aria-live="polite" role="status">
                {copy.progress}: {copy.noEstimate}
              </p>
            )}

            <BatchControls
              actions={actions}
              availability={availability}
              copy={copy}
              job={job}
              onCancel={onCancel}
              onPause={onPause}
              onResume={onResume}
              onRetry={onRetry}
            />

            <RepositoryList copy={copy} items={job.items} locale={locale} />
          </>
        )}
      </section>
    </section>
  );
}

function PreflightSummary({
  copy,
  locale,
  preflight,
}: {
  copy: Copy;
  locale: Locale;
  preflight: BatchPreflightState;
}) {
  return (
    <section
      aria-labelledby="batch-preflight-heading"
      className="guided-onboarding__provider-status batch-analysis-panel__preflight"
      data-preflight-status={preflight.status}
    >
      <h3 id="batch-preflight-heading">{copy.preflightHeading}</h3>
      {preflight.status === "idle" && <p role="status">{copy.preflightIdle}</p>}
      {preflight.status === "loading" && (
        <p aria-live="polite" role="status">
          {copy.preflightLoading}
        </p>
      )}
      {preflight.status === "failed" && (
        <p className="guided-onboarding__error" role="alert">
          {operationErrorMessage(preflight.error, copy)}
        </p>
      )}
      {preflight.status === "blocked" && (
        <>
          <p role="status">{copy.preflightBlocked}</p>
          <ul>
            {preflight.blockers.map((blocker) => (
              <li key={blocker}>{copy.blocker(blocker)}</li>
            ))}
          </ul>
        </>
      )}
      {preflight.status === "ready" && (
        <>
          <p className="guided-onboarding__confirmed" role="status">
            {copy.preflightReady}
          </p>
          <dl className="guided-onboarding__repository-meta">
            <dt>{copy.repositories}</dt>
            <dd>{preflight.plan.selectionCount}</dd>
            <dt>{copy.cachePrediction}</dt>
            <dd>{preflight.plan.cachedResultCount}</dd>
            <dt>{copy.connection}</dt>
            <dd>{copy.connectionStatus(preflight.plan.connection)}</dd>
            <dt>{copy.rateBudget}</dt>
            <dd>{copy.rateStatus(preflight.plan.rateBudget)}</dd>
            <dt>{copy.provider}</dt>
            <dd>
              {preflight.plan.providerReady
                ? copy.providerReady
                : copy.providerUnavailable}
            </dd>
            <dt>{copy.concurrency}</dt>
            <dd>
              {preflight.plan.effectiveConcurrency}/
              {preflight.plan.serverConcurrency}
            </dd>
            <dt>{copy.maxGenerationAttempts}</dt>
            <dd>{preflight.plan.maximumGenerationAttempts}</dd>
            <dt>{copy.estimate}</dt>
            <dd>
              {preflight.plan.estimatedDuration
                ? `${formatDurationRange(preflight.plan.estimatedDuration, locale)} (${copy.confidence(preflight.plan.estimatedDuration.confidence)})`
                : copy.noEstimate}
            </dd>
          </dl>
        </>
      )}
    </section>
  );
}

function ProgressSummary({
  copy,
  locale,
  progress,
}: {
  copy: Copy;
  locale: Locale;
  progress: BatchProgressState;
}) {
  return (
    <section
      aria-labelledby="batch-aggregate-progress-heading"
      className="guided-onboarding__progress batch-analysis-panel__progress"
    >
      <h4 id="batch-aggregate-progress-heading">{copy.progress}</h4>
      <p>{copy.progressSummary(progress)}</p>
      <progress
        max={Math.max(progress.totalItems, 1)}
        value={progress.completedItems}
      >
        {progress.completedItems}/{progress.totalItems}
      </progress>
      <p
        aria-atomic="true"
        aria-live="polite"
        className="visually-hidden"
        role="status"
        style={VISUALLY_HIDDEN_STYLE}
      >
        {progress.announcement
          ? copy.progressAnnouncement(progress.announcement)
          : ""}
      </p>
      <dl className="guided-onboarding__repository-meta">
        <dt>{copy.elapsed}</dt>
        <dd>{formatDuration(progress.elapsedSeconds, locale)}</dd>
        <dt>{copy.remaining}</dt>
        <dd>
          {progress.estimatedRemaining
            ? formatDurationRange(progress.estimatedRemaining, locale)
            : copy.noEstimate}
        </dd>
        <dt>{copy.effectiveConcurrency}</dt>
        <dd>{progress.effectiveConcurrency ?? copy.notReported}</dd>
        <dt>{copy.serverConcurrency}</dt>
        <dd>{progress.serverConcurrency ?? copy.notReported}</dd>
        <dt>{copy.completed}</dt>
        <dd>{progress.completedItems}</dd>
        <dt>{copy.active}</dt>
        <dd>{progress.activeItems}</dd>
        <dt>{copy.failed}</dt>
        <dd>{progress.failedItems}</dd>
        <dt>{copy.cancelled}</dt>
        <dd>{progress.cancelledItems}</dd>
      </dl>
    </section>
  );
}

function BatchControls({
  actions,
  availability,
  copy,
  job,
  onCancel,
  onPause,
  onResume,
  onRetry,
}: {
  actions: BatchActionState;
  availability: BatchActionAvailability;
  copy: Copy;
  job: BatchJobSnapshot;
  onCancel: (batchId: string) => void;
  onPause: (batchId: string) => void;
  onResume: (batchId: string) => void;
  onRetry: (batchId: string) => void;
}) {
  const controls: Array<{
    action: BatchAction;
    label: string;
    available: boolean;
    unavailable: string;
    onClick: () => void;
  }> = [
    {
      action: "pause",
      label: copy.pause,
      available: availability.pause,
      unavailable: copy.pauseUnavailable,
      onClick: () => onPause(job.id),
    },
    {
      action: "resume",
      label: copy.resume,
      available: availability.resume,
      unavailable: copy.resumeUnavailable,
      onClick: () => onResume(job.id),
    },
    {
      action: "cancel",
      label: copy.cancel,
      available: availability.cancel,
      unavailable: copy.cancelUnavailable,
      onClick: () => onCancel(job.id),
    },
    {
      action: "retry",
      label: copy.retry,
      available: availability.retry,
      unavailable: copy.retryUnavailable,
      onClick: () => onRetry(job.id),
    },
  ];

  return (
    <section
      aria-labelledby="batch-controls-heading"
      className="guided-onboarding__analysis-action batch-analysis-panel__controls"
    >
      <h4 id="batch-controls-heading">{copy.actionHeading}</h4>
      {controls.map((control) => {
        const pending = actions.pending === control.action;
        const reasonId = `batch-${control.action}-reason`;
        const disabled = !control.available;
        return (
          <div key={control.action}>
            <button
              aria-busy={pending || undefined}
              aria-describedby={disabled ? reasonId : undefined}
              disabled={disabled}
              onClick={control.onClick}
              type="button"
            >
              {control.label}
            </button>
            {pending && (
              <p className="guided-onboarding__busy" role="status">
                {copy.actionPending(control.action)}
              </p>
            )}
            {disabled && (
              <p className="guided-onboarding__disabled-reason" id={reasonId}>
                {control.unavailable}
              </p>
            )}
          </div>
        );
      })}
    </section>
  );
}

function RepositoryList({
  copy,
  items,
  locale,
}: {
  copy: Copy;
  items: readonly BatchRepositoryItem[];
  locale: Locale;
}) {
  return (
    <section aria-labelledby="batch-repository-progress-heading">
      <h4 id="batch-repository-progress-heading">{copy.repositoryHeading}</h4>
      <ul>
        {items.map((item) => {
          const itemId = item.slug.replaceAll(/[^a-zA-Z0-9_-]+/g, "-");
          return (
            <li
              aria-labelledby={`batch-repository-${itemId}`}
              className="guided-onboarding__repository"
              data-repository-state={item.state}
              key={item.slug}
            >
              <div className="guided-onboarding__repository-header">
                <h5 id={`batch-repository-${itemId}`}>{item.slug}</h5>
                <p>{repositoryStateLabel(item, locale)}</p>
              </div>
              <dl className="guided-onboarding__repository-meta">
                <dt>{copy.stage}</dt>
                <dd>{repositoryStageLabel(item.stage, locale)}</dd>
              </dl>
              {item.error && (
                <p className="guided-onboarding__disabled-reason">
                  {copy.repositoryFailed}
                  {item.error.retryAfterSeconds
                    ? ` ${copy.retryAfter(item.error.retryAfterSeconds)}`
                    : ""}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function operationErrorMessage(error: BatchOperationError, copy: Copy): string {
  const retry = error.retryAfterSeconds
    ? ` ${copy.retryAfter(error.retryAfterSeconds)}`
    : "";
  if (error.code === "RATE_LIMITED" || error.code === "GITHUB_RATE_LIMITED") {
    return `${copy.blocker("rate_limited")}${retry}`;
  }
  if (error.scope === "preflight") {
    return `${copy.preflightFailed}${retry}`;
  }
  if (
    error.code === "GITHUB_CONNECTION_REQUIRED" ||
    error.code === "GITHUB_CREDENTIAL_INVALID"
  ) {
    return `${copy.blocker("connection_required")}${retry}`;
  }
  if (error.code === "MODEL_UNAVAILABLE" || error.code === "PROVIDER_TIMEOUT") {
    return `${copy.blocker("provider_unavailable")}${retry}`;
  }
  return `${copy.actionFailed}${retry}`;
}

function batchStatusLabel(status: BatchJobStatus, locale: Locale): string {
  const labels: Record<Locale, Record<BatchJobStatus, string>> = {
    "zh-TW": {
      queued: "等待處理",
      running: "執行中",
      paused: "已暫停",
      cancelling: "取消中",
      cancelled: "已取消",
      completed: "已完成",
      completed_with_errors: "部分完成",
      failed: "未完成",
    },
    en: {
      queued: "Queued",
      running: "Running",
      paused: "Paused",
      cancelling: "Cancelling",
      cancelled: "Cancelled",
      completed: "Completed",
      completed_with_errors: "Completed with errors",
      failed: "Failed",
    },
  };
  return labels[locale][status];
}

function repositoryStageLabel(
  stage: BatchRepositoryStage,
  locale: Locale,
): string {
  const labels: Record<Locale, Record<BatchRepositoryStage, string>> = {
    "zh-TW": {
      queued: "等待處理",
      resolving_commit: "解析固定 commit",
      fetching_source: "取得來源",
      filtering: "篩選內容",
      indexing: "建立索引",
      embedding: "建立 embeddings",
      generating: "產生分析",
      validating: "驗證結果",
      cleaning_up: "清除暫存資料",
      complete: "已完成",
    },
    en: {
      queued: "Queued",
      resolving_commit: "Resolving immutable commit",
      fetching_source: "Fetching source",
      filtering: "Filtering content",
      indexing: "Indexing",
      embedding: "Embedding",
      generating: "Generating analysis",
      validating: "Validating result",
      cleaning_up: "Cleaning up staging",
      complete: "Complete",
    },
  };
  return labels[locale][stage];
}

function repositoryStateLabel(
  item: BatchRepositoryItem,
  locale: Locale,
): string {
  if (item.state === "active") {
    return repositoryStageLabel(item.stage, locale);
  }
  const labels: Record<
    Locale,
    Record<Exclude<BatchRepositoryState, "active">, string>
  > = {
    "zh-TW": {
      queued: "等待處理",
      waiting_rate_limit: "等待 GitHub 配額",
      waiting_reconnection: "等待重新連接",
      needs_retry_confirmation: "需要明確確認重試",
      failed: "需要處理",
      cancelled: "已取消",
      complete: "已完成",
    },
    en: {
      queued: "Queued",
      waiting_rate_limit: "Waiting for GitHub capacity",
      waiting_reconnection: "Waiting for reconnection",
      needs_retry_confirmation: "Needs explicit retry confirmation",
      failed: "Needs attention",
      cancelled: "Cancelled",
      complete: "Complete",
    },
  };
  return labels[locale][item.state];
}

function formatDurationRange(
  estimate: BatchDurationEstimate,
  locale: Locale,
): string {
  return `${formatDuration(estimate.minimumSeconds, locale)}–${formatDuration(estimate.maximumSeconds, locale)}`;
}

function formatDuration(seconds: number, locale: Locale): string {
  const boundedSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(boundedSeconds / 60);
  const remainder = boundedSeconds % 60;
  if (locale === "zh-TW") {
    return minutes > 0 ? `${minutes} 分 ${remainder} 秒` : `${remainder} 秒`;
  }
  return minutes > 0 ? `${minutes}m ${remainder}s` : `${remainder}s`;
}
