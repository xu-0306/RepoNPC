import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";

import {
  AdminWorkspace,
  type AdminPreview,
  type AdminStatus,
  type AdminValidation,
} from "./AdminWorkspace";
import {
  BatchAnalysisPanel,
  type BatchActionState,
  type BatchDurationEstimate,
  type BatchJobSnapshot,
  type BatchJobStatus,
  type BatchOperationError,
  type BatchPreflightBlocker,
  type BatchPreflightState,
  type BatchProgressAnnouncement,
  type BatchProgressState,
  type BatchRepositoryItem,
  type BatchRepositoryStage,
  type BatchRepositoryState,
  type BatchSseState,
} from "./BatchAnalysisPanel";
import { adminErrorStateReducer, initialAdminErrorState } from "./adminErrors";
import { GitHubButton } from "./GitHubButton";
import {
  GitHubOAuthSetupGuideDialog,
  type GitHubOAuthSetupGuideBody,
} from "./GitHubOAuthSetupGuideDialog";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import {
  guidedOnboardingReducer,
  initialGuidedOnboardingState,
  parseGuidedOnboarding,
  selectedRepositories,
  serializeGuidedOnboarding,
  type ContributionProposal,
  type GuidedOnboardingAction,
  type GuidedProviderStatus,
  type RepositoryAnalysis,
  type RepositoryMetadata,
} from "./guidedOnboarding";
import type { Locale } from "../../i18n/messages";

interface SessionBody {
  csrf_token: string;
}

interface SetupStatusBody {
  setup_required: boolean;
  setup_code_available: boolean;
}

interface AuthMethodsBody {
  password: { available: boolean };
  github: { available: boolean };
  setup_required: boolean;
}

interface GitHubConnection {
  id: number;
  purpose: "identity_public_read" | "public_read";
  github_login: string | null;
  expires_at: string | null;
  last_validated_at: string | null;
  status: "ready" | "connection_required" | "invalid";
}

interface GitHubConnectionsBody {
  connections: GitHubConnection[];
}

interface GitHubOAuthStartBody {
  authorization_url: string;
}

interface PublicStatusBody {
  model: {
    ready: boolean;
    provider: "ollama" | "openai_compatible" | null;
    last_checked_at: string | null;
  };
}

interface AdminAccessPanelProps {
  locale: Locale;
  busy: boolean;
  error: string;
  setupStatus: SetupStatusBody | null;
  setupStatusPending: boolean;
  username: string;
  password: string;
  setupCode: string;
  setupPassword: string;
  setupPasswordConfirmation: string;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSetupCodeChange: (value: string) => void;
  onSetupPasswordChange: (value: string) => void;
  onSetupPasswordConfirmationChange: (value: string) => void;
  onLogin: React.FormEventHandler<HTMLFormElement>;
  onSetupOwner: React.FormEventHandler<HTMLFormElement>;
  onRefreshSetupStatus: () => void;
  githubAvailable?: boolean;
  githubPending?: boolean;
  onGitHubRedirect?: () => void;
  onGitHubSetupGuide?: (trigger: HTMLButtonElement) => void;
}

interface ConfigBody {
  content: string;
  blob_sha: string;
}

interface SnippetBody {
  markdown: string;
  asset_url: string;
  target_url: string;
}

interface RepositoryDiscoveryBody {
  repositories: RepositoryMetadata[];
  page: number;
  has_more: boolean;
}

interface ContributionSuggestionBody {
  slug: string;
  original_statement: string;
  proposal: ContributionProposal;
  confirmed: false;
}

interface OnboardingDraftBody {
  content: string;
  validation: AdminValidation;
}

interface BatchSelectionBody {
  slug: string;
  ref: string | null;
  include: string[];
  exclude: string[];
  confirmed: true;
}

interface BatchCredentialBody {
  credential_id: number;
  purpose: "identity_public_read" | "public_read";
  github_login?: string | null;
}

interface BatchRepositoryPlanBody {
  slug: string;
  commit_sha: string;
  default_branch: string;
  is_archived: boolean;
}

interface BatchCachePredictionBody {
  derived_index_hit: boolean;
  validated_analysis_hit: boolean;
}

interface BatchRateBudgetBody {
  remaining?: number;
  reset_at?: string | null;
}

interface BatchCapacityBody {
  github_requests: number;
  archive_staging: number;
  index_work: number;
  generation: number;
  whole_job_items: number;
}

interface BatchDurationBody {
  minimum_seconds: number;
  maximum_seconds: number;
  confidence: "low" | "medium" | "high";
}

interface BatchBlockerBody {
  slug: string;
  code: string;
}

interface BatchPreflightBody {
  plan_id: string;
  expires_at: string;
  selection_hash: string;
  selected_credential: BatchCredentialBody | null;
  repositories: BatchRepositoryPlanBody[];
  cache_predictions: Record<string, BatchCachePredictionBody>;
  graphql_budget: BatchRateBudgetBody;
  core_budget: BatchRateBudgetBody;
  secondary_retry_at?: string | null;
  provider_ready: boolean;
  capacity: BatchCapacityBody;
  maximum_generation_attempts: number;
  duration: BatchDurationBody | null;
  blockers: BatchBlockerBody[];
  warnings: string[];
}

interface BatchProgressBody {
  total: number;
  complete: number;
  failed: number;
  cancelled: number;
  needs_retry_confirmation: number;
  terminal: number;
  active: number;
}

interface BatchItemBody {
  item_id: string;
  slug: string;
  requested_ref?: string | null;
  commit_sha?: string | null;
  state: string;
  retryable: boolean;
  error_code?: string | null;
  retry_at?: string | null;
  result?: Record<string, unknown> | null;
}

interface BatchSnapshotBody {
  batch_id: string;
  state: string;
  plan_id: string;
  selection_hash: string;
  maximum_generation_attempts: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  expires_at?: string | null;
  error_code?: string | null;
  items: BatchItemBody[];
  progress: BatchProgressBody;
}

interface BatchCreateBody {
  batch: BatchSnapshotBody;
  created: boolean;
}

interface BatchEventBody {
  event_id: number;
  batch_id: string;
  item_id?: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

class AdminRequestError extends Error {
  readonly retryAfterSeconds: number | undefined;

  constructor(code: string, retryAfterSeconds?: number) {
    super(code);
    this.name = "AdminRequestError";
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

interface GitHubConnectionPanelProps {
  locale: Locale;
  oauthAvailable: boolean;
  connections: GitHubConnection[];
  pending: boolean;
  linkPending: boolean;
  patToken: string;
  error: string;
  onLink: () => void;
  onUnlink: () => void;
  onCheck: (credentialId: number) => void;
  onDelete: (credentialId: number) => void;
  onPatChange: (value: string) => void;
  onSavePat: React.FormEventHandler<HTMLFormElement>;
  onGitHubSetupGuide?: (trigger: HTMLButtonElement) => void;
}

const MIN_ADMIN_PASSWORD_LENGTH = 4;
const GUIDED_ONBOARDING_STORAGE_KEY = "reponpc.guided-onboarding.v1";

function copyFor(locale: Locale, chinese: string, english: string): string {
  return locale === "zh-TW" ? chinese : english;
}

function batchOperationError(
  error: unknown,
  scope: BatchOperationError["scope"],
): BatchOperationError {
  return {
    scope,
    code: error instanceof Error ? error.message : "REQUEST_FAILED",
    retryAfterSeconds:
      error instanceof AdminRequestError ? error.retryAfterSeconds : undefined,
  };
}

function batchDuration(
  duration: BatchDurationBody | null,
): BatchDurationEstimate | null {
  if (!duration) return null;
  return {
    minimumSeconds: Math.max(0, duration.minimum_seconds),
    maximumSeconds: Math.max(0, duration.maximum_seconds),
    confidence: duration.confidence,
  };
}

function preflightBlocker(code: string): BatchPreflightBlocker {
  if (code === "GITHUB_CONNECTION_REQUIRED") return "connection_required";
  if (code === "MODEL_UNAVAILABLE") return "provider_unavailable";
  if (code === "GITHUB_RATE_LIMITED" || code === "RATE_LIMITED") {
    return "rate_limited";
  }
  if (code === "NO_REPOSITORIES") return "no_repositories";
  return "selection_changed";
}

function budgetStatus(
  plan: BatchPreflightBody,
): "available" | "limited" | "exhausted" {
  const remaining = [plan.graphql_budget.remaining, plan.core_budget.remaining]
    .filter((value): value is number => typeof value === "number")
    .some((value) => value <= 0);
  if (remaining) return "exhausted";
  return plan.secondary_retry_at ? "limited" : "available";
}

function preflightState(plan: BatchPreflightBody): BatchPreflightState {
  const blockers = plan.blockers.map((blocker) =>
    preflightBlocker(blocker.code),
  );
  if (blockers.length > 0) return { status: "blocked", blockers };

  const cachedResultCount = Object.values(plan.cache_predictions).filter(
    (prediction) => prediction.validated_analysis_hit,
  ).length;
  return {
    status: "ready",
    plan: {
      selectionCount: plan.repositories.length,
      cachedResultCount,
      connection: plan.selected_credential ? "ready" : "connection_required",
      rateBudget: budgetStatus(plan),
      providerReady: plan.provider_ready,
      effectiveConcurrency: Math.min(
        plan.capacity.generation,
        plan.capacity.whole_job_items,
      ),
      serverConcurrency: plan.capacity.whole_job_items,
      maximumGenerationAttempts: plan.maximum_generation_attempts,
      estimatedDuration: batchDuration(plan.duration),
    },
  };
}

function batchJobStatus(state: string): BatchJobStatus {
  const statuses: readonly BatchJobStatus[] = [
    "queued",
    "running",
    "paused",
    "cancelling",
    "cancelled",
    "completed",
    "completed_with_errors",
    "failed",
  ];
  return statuses.includes(state as BatchJobStatus)
    ? (state as BatchJobStatus)
    : "failed";
}

function batchRepositoryState(state: string): BatchRepositoryState {
  const states: readonly BatchRepositoryState[] = [
    "queued",
    "active",
    "waiting_rate_limit",
    "waiting_reconnection",
    "needs_retry_confirmation",
    "failed",
    "cancelled",
    "complete",
  ];
  if (states.includes(state as BatchRepositoryState)) {
    return state as BatchRepositoryState;
  }
  const activeStages: readonly BatchRepositoryStage[] = [
    "resolving_commit",
    "fetching_source",
    "filtering",
    "indexing",
    "embedding",
    "generating",
    "validating",
    "cleaning_up",
  ];
  return activeStages.includes(state as BatchRepositoryStage)
    ? "active"
    : "failed";
}

function batchRepositoryStage(state: string): BatchRepositoryStage {
  const activeStages: readonly BatchRepositoryStage[] = [
    "resolving_commit",
    "fetching_source",
    "filtering",
    "indexing",
    "embedding",
    "generating",
    "validating",
    "cleaning_up",
  ];
  if (activeStages.includes(state as BatchRepositoryStage)) {
    return state as BatchRepositoryStage;
  }
  return state === "complete" ? "complete" : "queued";
}

function retryAfterSeconds(
  retryAt: string | null | undefined,
): number | undefined {
  if (!retryAt) return undefined;
  const value = Date.parse(retryAt);
  if (Number.isNaN(value)) return undefined;
  return Math.max(0, Math.ceil((value - Date.now()) / 1000));
}

function batchItem(item: BatchItemBody): BatchRepositoryItem {
  return {
    slug: item.slug,
    stage: batchRepositoryStage(item.state),
    state: batchRepositoryState(item.state),
    retryable: item.retryable,
    error: item.error_code
      ? {
          scope: "repository",
          code: item.error_code,
          retryAfterSeconds: retryAfterSeconds(item.retry_at),
        }
      : null,
  };
}

function batchJob(snapshot: BatchSnapshotBody): BatchJobSnapshot {
  return {
    id: snapshot.batch_id,
    status: batchJobStatus(snapshot.state),
    items: snapshot.items.map(batchItem),
  };
}

function elapsedSeconds(snapshot: BatchSnapshotBody): number {
  const start = Date.parse(snapshot.started_at ?? snapshot.created_at);
  if (Number.isNaN(start)) return 0;
  return Math.max(0, Math.round((Date.now() - start) / 1000));
}

function terminalCount(snapshot: BatchSnapshotBody): number {
  if (typeof snapshot.progress.terminal === "number") {
    return snapshot.progress.terminal;
  }
  return snapshot.items.filter((item) =>
    ["complete", "failed", "cancelled", "needs_retry_confirmation"].includes(
      item.state,
    ),
  ).length;
}

function batchProgress(
  snapshot: BatchSnapshotBody,
  plan: BatchPreflightBody | null,
  announcement: BatchProgressAnnouncement | null,
): BatchProgressState {
  const elapsed = elapsedSeconds(snapshot);
  const duration = batchDuration(plan?.duration ?? null);
  const estimatedRemaining = duration
    ? {
        ...duration,
        minimumSeconds: Math.max(0, duration.minimumSeconds - elapsed),
        maximumSeconds: Math.max(0, duration.maximumSeconds - elapsed),
      }
    : null;
  const failedItems =
    snapshot.progress.failed + snapshot.progress.needs_retry_confirmation;

  return {
    totalItems: snapshot.progress.total,
    completedItems: terminalCount(snapshot),
    activeItems: snapshot.progress.active,
    failedItems,
    cancelledItems: snapshot.progress.cancelled,
    elapsedSeconds: elapsed,
    estimatedRemaining,
    effectiveConcurrency: plan
      ? Math.min(plan.capacity.generation, plan.capacity.whole_job_items)
      : null,
    serverConcurrency: plan?.capacity.whole_job_items ?? null,
    announcement,
  };
}

function isTerminalBatch(state: BatchJobStatus): boolean {
  return ["cancelled", "completed", "completed_with_errors", "failed"].includes(
    state,
  );
}

function batchAnalysisResult(
  result: Record<string, unknown> | null | undefined,
): RepositoryAnalysis | null {
  if (!result || typeof result !== "object") return null;
  const repository = result.repository;
  if (!repository || typeof repository !== "object") return null;
  const values = repository as Record<string, unknown>;
  if (
    typeof values.slug !== "string" ||
    typeof values.commit_sha !== "string" ||
    typeof values.default_branch !== "string" ||
    typeof values.html_url !== "string" ||
    !Array.isArray(result.facts) ||
    !Array.isArray(result.inferences)
  ) {
    return null;
  }
  return result as unknown as RepositoryAnalysis;
}

function parseBatchEvent(data: string): BatchEventBody | null {
  try {
    const value = JSON.parse(data) as Partial<BatchEventBody>;
    if (
      typeof value.event_id !== "number" ||
      typeof value.batch_id !== "string" ||
      typeof value.event_type !== "string"
    ) {
      return null;
    }
    return value as BatchEventBody;
  } catch {
    return null;
  }
}

export function loginErrorMessage(locale: Locale, error: unknown): string {
  if (error instanceof Error && error.message === "SERVICE_NOT_READY") {
    return copyFor(
      locale,
      "管理員服務尚未就緒。請在部署主機設定 REPONPC_IP_HASH_KEY_FILE，重新啟動服務後再試。",
      "Admin sign-in is not ready. Configure REPONPC_IP_HASH_KEY_FILE on the deployment host, restart the service, and try again.",
    );
  }

  return copyFor(locale, "登入失敗。", "Sign-in failed.");
}

export function setupErrorMessage(locale: Locale, error: unknown): string {
  if (error instanceof Error && error.message === "SETUP_DENIED") {
    return copyFor(
      locale,
      "設定碼無效或已過期。請在部署主機重新產生設定碼後再試。",
      "The setup code is invalid or expired. Generate a new code on the deployment host and try again.",
    );
  }

  return copyFor(
    locale,
    "建立管理員失敗。請再試一次。",
    "Administrator setup failed. Try again.",
  );
}

export function adminDataErrorMessage(locale: Locale, error: unknown): string {
  if (error instanceof Error && error.message === "SERVICE_NOT_READY") {
    return copyFor(
      locale,
      "已登入，但 GitHub 管理操作尚未設定。",
      "You are signed in, but GitHub management operations are not configured.",
    );
  }

  return copyFor(
    locale,
    "無法載入管理資料。",
    "Admin data could not be loaded.",
  );
}

export function AdminAccessPanel({
  locale,
  busy,
  error,
  setupStatus,
  setupStatusPending,
  username,
  password,
  setupCode,
  setupPassword,
  setupPasswordConfirmation,
  onUsernameChange,
  onPasswordChange,
  onSetupCodeChange,
  onSetupPasswordChange,
  onSetupPasswordConfirmationChange,
  onLogin,
  onSetupOwner,
  onRefreshSetupStatus,
  githubAvailable = false,
  githubPending = false,
  onGitHubRedirect,
  onGitHubSetupGuide = () => undefined,
}: AdminAccessPanelProps) {
  const setupRequired = setupStatus?.setup_required === true;
  const setupUnavailable = !setupStatusPending && setupStatus === null;
  const mode = setupStatusPending
    ? "loading"
    : setupRequired
      ? "setup"
      : setupUnavailable
        ? "unavailable"
        : "login";
  const title =
    mode === "setup"
      ? copyFor(locale, "首次設定", "first-time setup")
      : mode === "login"
        ? copyFor(locale, "管理員登入", "admin sign in")
        : copyFor(locale, "管理介面", "admin console");

  function handleGitHubFormSubmit(event: React.FormEvent<HTMLFormElement>) {
    const button = event.currentTarget.querySelector<HTMLButtonElement>(
      "button.github-button",
    );
    if (!githubAvailable) {
      // A form can be submitted by pressing Enter in another field without a
      // button click. Keep that keyboard path aligned with the button path:
      // show the safe setup guide and never send an OAuth start request.
      event.preventDefault();
      if (button !== null) onGitHubSetupGuide(button);
      return;
    }
    if (button?.disabled) {
      // Prerequisite-disabled configured controls (for example, a missing
      // setup code) must not submit a partially valid OAuth request.
      event.preventDefault();
      return;
    }
    onGitHubRedirect?.();
  }

  return (
    <main className="admin-auth-shell" lang={locale}>
      <section
        aria-labelledby="admin-access-heading"
        className="admin-auth-card"
        data-mode={mode}
      >
        <header className="admin-auth__header">
          <p className="admin-auth__eyebrow">
            {copyFor(locale, "本機管理主控台", "Local admin console")}
          </p>
          <h1
            className="admin-auth__title"
            id="admin-access-heading"
            tabIndex={-1}
          >
            <span className="admin-auth__product">RepoNPC</span>
            <span className="admin-auth__title-action">{title}</span>
          </h1>
        </header>

        {error && (
          <p className="admin-auth__alert" role="alert">
            {error}
          </p>
        )}

        {mode === "loading" && (
          <p className="admin-auth__status" role="status">
            {copyFor(
              locale,
              "正在確認這台裝置的首次設定狀態…",
              "Checking first-time setup status for this device…",
            )}
          </p>
        )}

        {mode === "unavailable" && (
          <div className="admin-auth__content">
            <p className="admin-auth__intro">
              {copyFor(
                locale,
                "目前無法確認管理員是否已建立。請確認服務正在執行後再試一次。",
                "RepoNPC could not confirm whether an administrator exists. Check that the service is running, then try again.",
              )}
            </p>
            <button
              className="admin-auth__secondary-action"
              disabled={busy}
              onClick={onRefreshSetupStatus}
              type="button"
            >
              {copyFor(locale, "重新檢查", "Check again")}
            </button>
          </div>
        )}

        {mode === "setup" && (
          <div className="admin-auth__content">
            <p className="admin-auth__intro">
              {copyFor(
                locale,
                "這裡沒有預設帳密。請使用啟動視窗顯示的一次性設定碼，建立只屬於這個本機資料目錄的管理員。",
                "There are no default credentials. Use the one-time code shown by the launcher to create the administrator for this local data directory.",
              )}
            </p>
            <p className="admin-auth__status" role="status">
              {setupStatus?.setup_code_available
                ? copyFor(
                    locale,
                    "設定碼已就緒，現在可以建立管理員。",
                    "The setup code is ready. You can create the administrator now.",
                  )
                : copyFor(
                    locale,
                    "尚未產生設定碼。請重新執行一鍵啟動腳本取得一次性設定碼。",
                    "No setup code is available. Run the one-click launcher again to obtain one.",
                  )}
            </p>
            <form className="admin-auth__form" onSubmit={onSetupOwner}>
              <div className="admin-auth__field">
                <label htmlFor="admin-setup-code">
                  {copyFor(locale, "一次性設定碼", "One-time setup code")}
                </label>
                <input
                  autoComplete="one-time-code"
                  id="admin-setup-code"
                  onChange={(event) => onSetupCodeChange(event.target.value)}
                  required
                  spellCheck={false}
                  value={setupCode}
                />
              </div>
              <div className="admin-auth__field">
                <label htmlFor="admin-setup-username">
                  {copyFor(locale, "管理員帳號", "Administrator username")}
                </label>
                <input
                  autoComplete="username"
                  id="admin-setup-username"
                  maxLength={64}
                  onChange={(event) => onUsernameChange(event.target.value)}
                  required
                  spellCheck={false}
                  value={username}
                />
              </div>
              <div className="admin-auth__field">
                <label htmlFor="admin-setup-password">
                  {copyFor(locale, "密碼", "Password")}
                </label>
                <input
                  aria-describedby="admin-password-requirements"
                  autoComplete="new-password"
                  id="admin-setup-password"
                  maxLength={1024}
                  minLength={MIN_ADMIN_PASSWORD_LENGTH}
                  onChange={(event) =>
                    onSetupPasswordChange(event.target.value)
                  }
                  required
                  type="password"
                  value={setupPassword}
                />
                <small
                  className="admin-auth__field-help"
                  id="admin-password-requirements"
                >
                  {copyFor(
                    locale,
                    "至少 4 個字元，不限制大小寫、數字或符號；密碼只會以 Argon2id 雜湊保存在本機。",
                    "Use at least 4 characters; uppercase, numbers, and symbols are optional. Only an Argon2id hash is stored locally.",
                  )}
                </small>
              </div>
              <div className="admin-auth__field">
                <label htmlFor="admin-setup-password-confirmation">
                  {copyFor(locale, "確認密碼", "Confirm password")}
                </label>
                <input
                  autoComplete="new-password"
                  id="admin-setup-password-confirmation"
                  maxLength={1024}
                  minLength={MIN_ADMIN_PASSWORD_LENGTH}
                  onChange={(event) =>
                    onSetupPasswordConfirmationChange(event.target.value)
                  }
                  required
                  type="password"
                  value={setupPasswordConfirmation}
                />
              </div>
              <button disabled={busy} type="submit">
                {busy
                  ? copyFor(locale, "建立中…", "Creating…")
                  : copyFor(
                      locale,
                      "建立我的管理員",
                      "Create my administrator",
                    )}
              </button>
            </form>
            <form
              action="/api/admin/setup/github/start"
              className="admin-auth__oauth-form"
              method="post"
              onSubmit={handleGitHubFormSubmit}
            >
              <input name="setup_code" type="hidden" value={setupCode} />
              <GitHubButton
                available={githubAvailable}
                className="admin-auth__github-button"
                disabled={!setupCode || githubPending}
                label={copyFor(
                  locale,
                  "使用 GitHub 建立管理員",
                  "Create admin with GitHub",
                )}
                onOpenSetupGuide={onGitHubSetupGuide}
                pending={githubPending}
                pendingLabel={copyFor(
                  locale,
                  "正在前往 GitHub…",
                  "Redirecting to GitHub…",
                )}
                type="submit"
              />
            </form>
            <p className="admin-auth__privacy-note">
              {copyFor(
                locale,
                "帳號、密碼雜湊與登入工作階段都留在 runtime-data 本機資料中，不會寫入 GitHub。",
                "The username, password hash, and sessions stay in local runtime-data and are never written to GitHub.",
              )}
            </p>
          </div>
        )}

        {mode === "login" && (
          <div className="admin-auth__content">
            <p className="admin-auth__intro">
              {copyFor(
                locale,
                "這個本機資料目錄已完成首次設定。請使用你建立的管理員帳密登入。",
                "First-time setup is complete for this local data directory. Sign in with the administrator credentials you created.",
              )}
            </p>
            <form
              action="/api/admin/session/github/start"
              className="admin-auth__oauth-form"
              method="post"
              onSubmit={handleGitHubFormSubmit}
            >
              <GitHubButton
                available={githubAvailable}
                className="admin-auth__github-button"
                disabled={githubPending}
                label={copyFor(
                  locale,
                  "使用 GitHub 登入",
                  "Sign in with GitHub",
                )}
                onOpenSetupGuide={onGitHubSetupGuide}
                pending={githubPending}
                pendingLabel={copyFor(
                  locale,
                  "正在前往 GitHub…",
                  "Redirecting to GitHub…",
                )}
                type="submit"
              />
            </form>
            <p
              aria-label={copyFor(locale, "或", "or")}
              className="admin-auth__separator"
            >
              <span>{copyFor(locale, "或", "or")}</span>
            </p>
            <form className="admin-auth__form" onSubmit={onLogin}>
              <div className="admin-auth__field">
                <label htmlFor="admin-username">
                  {copyFor(locale, "管理員帳號", "Username")}
                </label>
                <input
                  autoComplete="username"
                  id="admin-username"
                  maxLength={64}
                  onChange={(event) => onUsernameChange(event.target.value)}
                  required
                  spellCheck={false}
                  value={username}
                />
              </div>
              <div className="admin-auth__field">
                <label htmlFor="admin-password">
                  {copyFor(locale, "密碼", "Password")}
                </label>
                <input
                  autoComplete="current-password"
                  id="admin-password"
                  maxLength={1024}
                  onChange={(event) => onPasswordChange(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </div>
              <button disabled={busy} type="submit">
                {busy
                  ? copyFor(locale, "登入中…", "Signing in…")
                  : copyFor(locale, "登入管理介面", "Sign in to admin")}
              </button>
            </form>
            <p className="admin-auth__privacy-note">
              {copyFor(
                locale,
                "RepoNPC 沒有預設帳密。這組帳密由首次設定者建立，只保存在本機，不會推送到 GitHub。",
                "RepoNPC has no default credentials. They were created during first-time setup, stay local, and are never pushed to GitHub.",
              )}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

export function GitHubConnectionPanel({
  locale,
  oauthAvailable,
  connections,
  pending,
  linkPending,
  patToken,
  error,
  onLink,
  onUnlink,
  onCheck,
  onDelete,
  onPatChange,
  onSavePat,
  onGitHubSetupGuide = () => undefined,
}: GitHubConnectionPanelProps) {
  const identityConnection = connections.find(
    (connection) => connection.purpose === "identity_public_read",
  );
  const publicReadConnections = connections.filter(
    (connection) => connection.purpose === "public_read",
  );
  const title = copyFor(locale, "GitHub 連線", "GitHub connection");
  const unavailable = copyFor(
    locale,
    "部署管理員尚未設定 GitHub OAuth。請選擇「連結 GitHub」查看主機端設定步驟；帳密登入與本機管理功能仍可使用。",
    "GitHub OAuth is not configured yet. Select Link GitHub to see the host-side setup steps; password sign-in and local administration remain available.",
  );

  return (
    <section
      aria-busy={pending || linkPending || undefined}
      aria-labelledby="github-connection-heading"
      className="admin-github-connection"
    >
      <h2 id="github-connection-heading">{title}</h2>
      <p className="admin-github-connection__intro">
        {copyFor(
          locale,
          "GitHub 登入與公開儲存庫讀取只會使用明確選取的唯讀憑證；寫回憑證始終獨立。",
          "GitHub sign-in and public repository reads use only an explicitly selected read-only credential. The writeback credential always remains separate.",
        )}
      </p>

      {!oauthAvailable && (
        <p className="admin-github-connection__status" role="status">
          {unavailable}
        </p>
      )}

      <div className="admin-github-connection__actions">
        <GitHubButton
          available={oauthAvailable}
          disabled={pending || linkPending}
          label={
            identityConnection
              ? copyFor(locale, "重新驗證 GitHub", "Reauthenticate GitHub")
              : copyFor(locale, "連結 GitHub", "Link GitHub")
          }
          onClick={onLink}
          onOpenSetupGuide={onGitHubSetupGuide}
          pending={linkPending}
          pendingLabel={copyFor(
            locale,
            "正在前往 GitHub…",
            "Redirecting to GitHub…",
          )}
          type="button"
        />
        {identityConnection && (
          <button
            disabled={pending || linkPending}
            onClick={onUnlink}
            type="button"
          >
            {copyFor(locale, "解除 GitHub 連結", "Unlink GitHub")}
          </button>
        )}
      </div>

      {connections.length > 0 && (
        <ul className="admin-github-connection__list" aria-label={title}>
          {connections.map((connection) => (
            <li key={connection.id}>
              <div>
                <strong>
                  {connection.purpose === "identity_public_read"
                    ? copyFor(
                        locale,
                        "GitHub 身分與公開讀取",
                        "GitHub identity and public read",
                      )
                    : copyFor(locale, "公開讀取 PAT", "Public-read PAT")}
                </strong>
                <p>
                  {connection.github_login ??
                    copyFor(locale, "未提供帳號", "No account name")}
                  {" · "}
                  {connection.status}
                </p>
                {connection.last_validated_at && (
                  <p className="admin-github-connection__metadata">
                    {copyFor(locale, "上次驗證：", "Last checked: ")}
                    {connection.last_validated_at}
                  </p>
                )}
              </div>
              <div className="admin-github-connection__actions">
                <button
                  disabled={pending || linkPending}
                  onClick={() => onCheck(connection.id)}
                  type="button"
                >
                  {copyFor(locale, "重新檢查", "Check again")}
                </button>
                {connection.purpose === "public_read" && (
                  <button
                    disabled={pending || linkPending}
                    onClick={() => onDelete(connection.id)}
                    type="button"
                  >
                    {copyFor(locale, "移除 PAT", "Remove PAT")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <form className="admin-github-connection__pat" onSubmit={onSavePat}>
        <label htmlFor="github-public-read-pat">
          {copyFor(
            locale,
            "公開讀取 Fine-grained PAT（選用）",
            "Public-read fine-grained PAT (optional)",
          )}
        </label>
        <p id="github-public-read-pat-help">
          {copyFor(
            locale,
            "此 PAT 只可用於公開讀取，不能登入或寫入。送出後會立刻從此頁面清除。",
            "This PAT is for public reads only. It cannot sign in or write, and is cleared from this page immediately after submission.",
          )}
        </p>
        <div className="admin-github-connection__actions">
          <input
            aria-describedby="github-public-read-pat-help"
            autoComplete="off"
            id="github-public-read-pat"
            maxLength={1024}
            disabled={pending || linkPending}
            onChange={(event) => onPatChange(event.target.value)}
            spellCheck={false}
            type="password"
            value={patToken}
          />
          <button disabled={pending || linkPending || !patToken} type="submit">
            {copyFor(locale, "儲存公開讀取 PAT", "Save public-read PAT")}
          </button>
        </div>
      </form>

      {error && (
        <p className="admin-github-connection__error" role="alert">
          {error}
        </p>
      )}

      {publicReadConnections.some(
        (connection) => connection.status === "connection_required",
      ) && (
        <p className="admin-github-connection__status" role="status">
          {copyFor(
            locale,
            "公開讀取憑證需要重新連線；RepoNPC 不會自動改用其他憑證。",
            "A public-read credential needs reconnection. RepoNPC will not automatically switch to another credential.",
          )}
        </p>
      )}
    </section>
  );
}

export function AdminPage({ locale }: { locale: Locale }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [setupCode, setSetupCode] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupPasswordConfirmation, setSetupPasswordConfirmation] =
    useState("");
  const [setupStatus, setSetupStatus] = useState<SetupStatusBody | null>(null);
  const [setupStatusPending, setSetupStatusPending] = useState(true);
  const [authMethods, setAuthMethods] = useState<AuthMethodsBody | null>(null);
  const [githubSetupGuide, setGithubSetupGuide] =
    useState<GitHubOAuthSetupGuideBody | null>(null);
  const [githubSetupGuideOpen, setGithubSetupGuideOpen] = useState(false);
  const [githubSetupGuidePending, setGithubSetupGuidePending] = useState(false);
  const [githubSetupGuideError, setGithubSetupGuideError] = useState("");
  const [githubRedirectPending, setGithubRedirectPending] = useState(false);
  const [githubConnections, setGithubConnections] = useState<
    GitHubConnection[]
  >([]);
  const [githubConnectionsPending, setGithubConnectionsPending] =
    useState(false);
  const [githubLinkPending, setGithubLinkPending] = useState(false);
  const [githubConnectionError, setGithubConnectionError] = useState("");
  const [publicReadPat, setPublicReadPat] = useState("");
  const [csrfToken, setCsrfToken] = useState("");
  const [draft, setDraft] = useState("");
  const [blobSha, setBlobSha] = useState("");
  const [validation, setValidation] = useState<AdminValidation | null>(null);
  const [preview, setPreview] = useState<AdminPreview | null>(null);
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [providerStatus, setProviderStatus] =
    useState<GuidedProviderStatus | null>(null);
  const [providerStatusPending, setProviderStatusPending] = useState(true);
  const [snippet, setSnippet] = useState<SnippetBody | null>(null);
  const [conflict, setConflict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [adminErrors, dispatchAdminError] = useReducer(
    adminErrorStateReducer,
    initialAdminErrorState,
  );
  const [githubOperationsReady, setGitHubOperationsReady] = useState(false);
  const [baseConfig, setBaseConfig] = useState<Record<string, unknown> | null>(
    null,
  );
  const [guidedState, setGuidedState] = useState(() =>
    initialGuidedOnboardingState(),
  );
  const [guidedResumeReady, setGuidedResumeReady] = useState(false);
  const guidedResumeFound = useRef(false);
  const [batchPreflight, setBatchPreflight] = useState<BatchPreflightState>({
    status: "idle",
  });
  const [batchPlan, setBatchPlan] = useState<BatchPreflightBody | null>(null);
  const batchPlanRef = useRef<BatchPreflightBody | null>(null);
  const [batchSnapshot, setBatchSnapshot] = useState<BatchJobSnapshot | null>(
    null,
  );
  const [batchProgressState, setBatchProgressState] =
    useState<BatchProgressState | null>(null);
  const [batchStream, setBatchStream] = useState<BatchSseState>({
    connection: "idle",
    reconnectAttempts: 0,
    lastEventId: null,
  });
  const [batchActions, setBatchActions] = useState<BatchActionState>({
    pending: null,
    error: null,
  });
  const [batchCreatePending, setBatchCreatePending] = useState(false);
  const [activeBatchLoaded, setActiveBatchLoaded] = useState(false);
  const batchEventSource = useRef<EventSource | null>(null);
  const batchLastEventId = useRef<string | null>(null);
  const batchAnnouncement = useRef<{
    batchId: string;
    terminalItems: number;
    announcedAt: number;
  } | null>(null);
  const batchIdempotency = useRef<{ planId: string; key: string } | null>(null);
  const githubSetupGuideTrigger = useRef<HTMLElement | null>(null);
  const authenticated = Boolean(csrfToken);

  const request = useCallback(
    async function request<T>(path: string, init?: RequestInit): Promise<T> {
      const response = await fetch(path, {
        credentials: "same-origin",
        ...init,
        headers: {
          ...(init?.body instanceof FormData
            ? {}
            : { "Content-Type": "application/json" }),
          ...(init?.method && init.method !== "GET" && csrfToken
            ? { "X-CSRF-Token": csrfToken }
            : {}),
          ...init?.headers,
        },
      });
      const body = (await response.json().catch(() => null)) as
        | T
        | {
            error?: {
              code?: string;
              details?: { reason?: string };
              retry_after_seconds?: number;
            };
          }
        | null;
      if (!response.ok) {
        if (response.status === 409 && path.startsWith("/api/admin/config")) {
          setConflict(true);
        }
        const code =
          body !== null && typeof body === "object" && "error" in body
            ? (body.error?.details?.reason ?? body.error?.code)
            : "REQUEST_FAILED";
        const retryAfterSeconds =
          body !== null && typeof body === "object" && "error" in body
            ? body.error?.retry_after_seconds
            : undefined;
        throw new AdminRequestError(
          code ?? "REQUEST_FAILED",
          retryAfterSeconds,
        );
      }
      return body as T;
    },
    [csrfToken],
  );

  const batchSelections = useMemo(
    () =>
      selectedRepositories(guidedState).map(
        (repository): BatchSelectionBody => ({
          slug: repository.metadata.slug,
          ref: repository.ref,
          include: repository.include,
          exclude: repository.exclude,
          confirmed: true,
        }),
      ),
    [guidedState],
  );
  const batchStreamBatchId = batchSnapshot?.id ?? null;
  const batchStreamTerminal =
    batchSnapshot !== null && isTerminalBatch(batchSnapshot.status);
  const applyBatchSnapshot = useCallback((snapshot: BatchSnapshotBody) => {
    const job = batchJob(snapshot);
    const terminalItems = terminalCount(snapshot);
    const now = Date.now();
    const previousAnnouncement = batchAnnouncement.current;
    const shouldAnnounce =
      previousAnnouncement?.batchId !== snapshot.batch_id ||
      (terminalItems > (previousAnnouncement?.terminalItems ?? 0) &&
        now - (previousAnnouncement?.announcedAt ?? 0) >= 5_000) ||
      isTerminalBatch(job.status);
    const announcement = shouldAnnounce
      ? { completedItems: terminalItems, totalItems: snapshot.progress.total }
      : null;
    if (shouldAnnounce) {
      batchAnnouncement.current = {
        batchId: snapshot.batch_id,
        terminalItems,
        announcedAt: now,
      };
    }

    setBatchSnapshot(job);
    setBatchProgressState(
      batchProgress(snapshot, batchPlanRef.current, announcement),
    );
    if (isTerminalBatch(job.status)) {
      batchEventSource.current?.close();
      batchEventSource.current = null;
      setBatchStream((current) => ({
        ...current,
        connection: "disconnected",
      }));
    }
    setGuidedState((current) => {
      if (current.step !== "analysis") return current;
      return snapshot.items.reduce((next, item) => {
        const selected = next.repositories.some(
          (repository) =>
            repository.selected && repository.metadata.slug === item.slug,
        );
        if (!selected) return next;
        if (item.state === "complete") {
          const analysis = batchAnalysisResult(item.result);
          return guidedOnboardingReducer(
            next,
            analysis
              ? { type: "ANALYSIS_COMPLETED", slug: item.slug, analysis }
              : { type: "ANALYSIS_UNAVAILABLE", slug: item.slug },
          );
        }
        if (
          ["failed", "cancelled", "needs_retry_confirmation"].includes(
            item.state,
          )
        ) {
          return guidedOnboardingReducer(next, {
            type: "ANALYSIS_UNAVAILABLE",
            slug: item.slug,
          });
        }
        return next;
      }, current);
    });
  }, []);

  const refreshBatchSnapshot = useCallback(
    async (batchId: string) => {
      const snapshot = await request<BatchSnapshotBody>(
        `/api/admin/onboarding/analysis-batches/${encodeURIComponent(batchId)}`,
      );
      applyBatchSnapshot(snapshot);
    },
    [applyBatchSnapshot, request],
  );

  const refreshSetupStatus = useCallback(async () => {
    setSetupStatusPending(true);
    try {
      const currentStatus = await request<SetupStatusBody>("/api/admin/setup");
      setSetupStatus(currentStatus);
    } catch (setupStatusError) {
      setSetupStatus(null);
      throw setupStatusError;
    } finally {
      setSetupStatusPending(false);
    }
  }, [request]);

  const refreshAuthMethods = useCallback(async () => {
    try {
      setAuthMethods(await request<AuthMethodsBody>("/api/admin/auth/methods"));
    } catch {
      setAuthMethods(null);
    }
  }, [request]);

  const loadGitHubSetupGuide = useCallback(async () => {
    setGithubSetupGuidePending(true);
    setGithubSetupGuideError("");
    try {
      setGithubSetupGuide(
        await request<GitHubOAuthSetupGuideBody>(
          "/api/admin/github/oauth/setup-guide",
        ),
      );
    } catch {
      setGithubSetupGuide(null);
      setGithubSetupGuideError(
        copyFor(
          locale,
          "無法讀取 GitHub 登入設定說明。請確認服務正在執行後再試一次。",
          "GitHub sign-in setup guidance could not be loaded. Confirm the service is running and try again.",
        ),
      );
    } finally {
      setGithubSetupGuidePending(false);
    }
  }, [locale, request]);

  const openGitHubSetupGuide = useCallback(
    (trigger: HTMLButtonElement) => {
      githubSetupGuideTrigger.current = trigger;
      setGithubSetupGuideOpen(true);
      void loadGitHubSetupGuide();
    },
    [loadGitHubSetupGuide],
  );

  const closeGitHubSetupGuide = useCallback(() => {
    setGithubSetupGuideOpen(false);
  }, []);

  const refreshGitHubSetupGuide = useCallback(() => {
    void Promise.all([loadGitHubSetupGuide(), refreshAuthMethods()]);
  }, [loadGitHubSetupGuide, refreshAuthMethods]);

  const refreshGitHubConnections = useCallback(async () => {
    setGithubConnectionsPending(true);
    try {
      const result = await request<GitHubConnectionsBody>(
        "/api/admin/github/connections",
      );
      setGithubConnections(result.connections);
      setGithubConnectionError("");
    } catch (connectionError) {
      setGithubConnections([]);
      setGithubConnectionError(
        connectionError instanceof Error &&
          connectionError.message === "GITHUB_LOGIN_UNAVAILABLE"
          ? copyFor(
              locale,
              "GitHub OAuth 尚未由部署管理員設定。",
              "GitHub OAuth has not been configured by the deployment operator.",
            )
          : copyFor(
              locale,
              "無法讀取 GitHub 連線狀態，請再試一次。",
              "GitHub connection status could not be loaded. Try again.",
            ),
      );
    } finally {
      setGithubConnectionsPending(false);
    }
  }, [locale, request]);

  const refreshProviderStatus = useCallback(async () => {
    setProviderStatusPending(true);
    try {
      const currentStatus =
        await request<PublicStatusBody>("/api/public/status");
      setProviderStatus({
        ready: currentStatus.model.ready,
        provider: currentStatus.model.provider,
        lastCheckedAt: currentStatus.model.last_checked_at,
      });
    } catch {
      setProviderStatus(null);
    } finally {
      setProviderStatusPending(false);
    }
  }, [request]);

  useEffect(() => {
    if (authenticated) return;
    void refreshSetupStatus().catch(() => {
      setSetupStatus(null);
    });
    void refreshAuthMethods();
  }, [authenticated, refreshAuthMethods, refreshSetupStatus]);

  useEffect(() => {
    const oauthResult = new URLSearchParams(window.location.search).get(
      "github_oauth",
    );
    if (!oauthResult) return;
    if (oauthResult !== "success") {
      setGithubRedirectPending(false);
      dispatchAdminError({
        type: "SET_GLOBAL_ERROR",
        message: copyFor(
          locale,
          "GitHub 登入未完成。請再試一次。",
          "GitHub sign-in did not complete. Try again.",
        ),
      });
      window.setTimeout(() => {
        document.getElementById("admin-access-heading")?.focus();
      }, 0);
    }
    window.history.replaceState({}, "", "/admin");
  }, [locale]);

  useEffect(() => {
    if (authenticated) return;
    void (async () => {
      try {
        const result = await request<SessionBody>(
          "/api/admin/session/github/result",
        );
        setCsrfToken(result.csrf_token);
        setGithubRedirectPending(false);
      } catch {
        // This endpoint normally has no handoff; its error is intentionally not global.
      }
    })();
  }, [authenticated, request]);

  useEffect(() => {
    if (!authenticated) return;
    const resumed = parseGuidedOnboarding(
      window.sessionStorage.getItem(GUIDED_ONBOARDING_STORAGE_KEY) ?? "",
    );
    guidedResumeFound.current = resumed !== null;
    if (resumed) setGuidedState(resumed);
    setGuidedResumeReady(true);
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) return;
    void refreshProviderStatus();
  }, [authenticated, refreshProviderStatus]);

  useEffect(() => {
    if (!authenticated) return;
    void refreshGitHubConnections();
  }, [authenticated, refreshGitHubConnections]);

  useEffect(() => {
    if (!authenticated) {
      batchEventSource.current?.close();
      batchEventSource.current = null;
      batchLastEventId.current = null;
      batchAnnouncement.current = null;
      batchIdempotency.current = null;
      setBatchSnapshot(null);
      setBatchProgressState(null);
      setBatchPlan(null);
      batchPlanRef.current = null;
      setBatchPreflight({ status: "idle" });
      setBatchStream({
        connection: "idle",
        reconnectAttempts: 0,
        lastEventId: null,
      });
      setActiveBatchLoaded(false);
      return;
    }

    let cancelled = false;
    setActiveBatchLoaded(false);
    void request<BatchSnapshotBody>(
      "/api/admin/onboarding/analysis-batches/active",
    )
      .then((snapshot) => {
        if (!cancelled) applyBatchSnapshot(snapshot);
      })
      .catch(() => {
        if (!cancelled) {
          setBatchSnapshot(null);
          setBatchProgressState(null);
        }
      })
      .finally(() => {
        if (!cancelled) setActiveBatchLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [applyBatchSnapshot, authenticated, request]);

  useEffect(() => {
    if (
      !authenticated ||
      !activeBatchLoaded ||
      guidedState.step !== "analysis" ||
      !guidedState.selectionConfirmed ||
      batchSnapshot !== null
    ) {
      return;
    }

    let cancelled = false;
    setBatchPreflight({ status: "loading" });
    setBatchPlan(null);
    batchPlanRef.current = null;
    setBatchActions({ pending: null, error: null });
    batchIdempotency.current = null;
    void request<BatchPreflightBody>(
      "/api/admin/onboarding/analysis-batches/preflight",
      {
        method: "POST",
        body: JSON.stringify({ selections: batchSelections }),
      },
    )
      .then((plan) => {
        if (cancelled) return;
        setBatchPlan(plan);
        batchPlanRef.current = plan;
        setBatchPreflight(preflightState(plan));
      })
      .catch((error) => {
        if (!cancelled) {
          setBatchPreflight({
            status: "failed",
            error: batchOperationError(error, "preflight"),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    activeBatchLoaded,
    authenticated,
    batchSelections,
    batchSnapshot,
    guidedState.selectionConfirmed,
    guidedState.step,
    request,
  ]);

  useEffect(() => {
    if (!authenticated || !batchStreamBatchId || batchStreamTerminal) {
      batchEventSource.current?.close();
      batchEventSource.current = null;
      if (batchStreamBatchId && batchStreamTerminal) {
        setBatchStream((current) => ({
          ...current,
          connection: "disconnected",
        }));
      }
      return;
    }

    const batchId = batchStreamBatchId;

    const source = new EventSource(
      `/api/admin/onboarding/analysis-batches/${encodeURIComponent(batchId)}/events`,
      { withCredentials: true },
    );
    batchEventSource.current = source;
    setBatchStream((current) => ({
      ...current,
      connection: current.reconnectAttempts > 0 ? "reconnecting" : "connecting",
    }));
    let snapshotRefreshPending = false;

    const refreshFromEvent = (event: Event) => {
      const message = event as MessageEvent<string>;
      const parsed = parseBatchEvent(message.data);
      const eventId =
        parsed?.event_id ?? Number.parseInt(message.lastEventId, 10);
      if (Number.isSafeInteger(eventId) && eventId > 0) {
        batchLastEventId.current = String(eventId);
        setBatchStream((current) => ({
          ...current,
          lastEventId: String(eventId),
        }));
      }
      if (snapshotRefreshPending) return;
      snapshotRefreshPending = true;
      void refreshBatchSnapshot(batchId)
        .catch(() => {
          setBatchStream((current) => ({ ...current, connection: "error" }));
        })
        .finally(() => {
          snapshotRefreshPending = false;
        });
    };

    const eventTypes = [
      "batch_created",
      "batch_pause",
      "batch_resume",
      "batch_cancel",
      "batch_retry",
      "item_recovered",
      "item_stage",
      "item_terminal",
      "batch_terminal",
    ];
    eventTypes.forEach((eventType) =>
      source.addEventListener(eventType, refreshFromEvent),
    );
    source.onopen = () => {
      setBatchStream((current) => ({ ...current, connection: "connected" }));
    };
    source.onerror = () => {
      setBatchStream((current) => ({
        ...current,
        connection: "reconnecting",
        reconnectAttempts: current.reconnectAttempts + 1,
      }));
    };

    return () => {
      eventTypes.forEach((eventType) =>
        source.removeEventListener(eventType, refreshFromEvent),
      );
      source.close();
      if (batchEventSource.current === source) {
        batchEventSource.current = null;
      }
    };
  }, [
    authenticated,
    batchStreamBatchId,
    batchStreamTerminal,
    refreshBatchSnapshot,
  ]);

  useEffect(() => {
    if (!authenticated || !guidedResumeReady) return;
    try {
      window.sessionStorage.setItem(
        GUIDED_ONBOARDING_STORAGE_KEY,
        serializeGuidedOnboarding(guidedState),
      );
    } catch {
      // Resume is a convenience. The in-memory guided flow remains authoritative.
    }
  }, [authenticated, guidedResumeReady, guidedState]);

  useEffect(() => {
    if (!authenticated) return;
    void (async () => {
      setBusy(true);
      dispatchAdminError({ type: "CLEAR_GLOBAL_ERROR" });
      const [configResult, statusResult, snippetResult] =
        await Promise.allSettled([
          request<ConfigBody>("/api/admin/config"),
          request<AdminStatus>("/api/admin/index/status"),
          request<SnippetBody>(
            `/api/admin/readme-snippet?locale=${encodeURIComponent(locale)}&theme=light&extension=svg&revision=1`,
          ),
        ]);
      if (configResult.status === "fulfilled") {
        setDraft(configResult.value.content);
        setBlobSha(configResult.value.blob_sha);
        setGitHubOperationsReady(true);
        try {
          const parsed = await request<AdminValidation>(
            "/api/admin/config/validate",
            {
              method: "POST",
              body: JSON.stringify({ content: configResult.value.content }),
            },
          );
          setBaseConfig(parsed.parsed ?? null);
        } catch {
          setBaseConfig(null);
        }
        if (!guidedResumeFound.current) {
          setGuidedState(initialGuidedOnboardingState(true));
        }
      } else {
        setGitHubOperationsReady(
          !(
            configResult.reason instanceof Error &&
            configResult.reason.message === "SERVICE_NOT_READY"
          ),
        );
        dispatchAdminError({
          type: "SET_GLOBAL_ERROR",
          message: adminDataErrorMessage(locale, configResult.reason),
        });
      }
      if (statusResult.status === "fulfilled") setStatus(statusResult.value);
      if (snippetResult.status === "fulfilled") setSnippet(snippetResult.value);
      if (
        configResult.status === "fulfilled" &&
        (statusResult.status === "rejected" ||
          snippetResult.status === "rejected")
      ) {
        dispatchAdminError({
          type: "SET_GLOBAL_ERROR",
          message: adminDataErrorMessage(
            locale,
            statusResult.status === "rejected"
              ? statusResult.reason
              : snippetResult.status === "rejected"
                ? snippetResult.reason
                : new Error("REQUEST_FAILED"),
          ),
        });
      }
      setBusy(false);
    })();
  }, [authenticated, locale, request]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    dispatchAdminError({ type: "CLEAR_GLOBAL_ERROR" });
    try {
      const session = await request<SessionBody>("/api/admin/session", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setPassword("");
      setCsrfToken(session.csrf_token);
    } catch (loginError) {
      setPassword("");
      dispatchAdminError({
        type: "SET_GLOBAL_ERROR",
        message: loginErrorMessage(locale, loginError),
      });
    } finally {
      setBusy(false);
    }
  }

  async function setupOwner(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    dispatchAdminError({ type: "CLEAR_GLOBAL_ERROR" });
    try {
      const session = await request<SessionBody>("/api/admin/setup", {
        method: "POST",
        body: JSON.stringify({
          setup_code: setupCode,
          username,
          password: setupPassword,
          password_confirmation: setupPasswordConfirmation,
        }),
      });
      setSetupCode("");
      setSetupPassword("");
      setSetupPasswordConfirmation("");
      setCsrfToken(session.csrf_token);
    } catch (setupError) {
      setSetupCode("");
      setSetupPassword("");
      setSetupPasswordConfirmation("");
      if (
        setupError instanceof Error &&
        setupError.message === "SETUP_ALREADY_COMPLETE"
      ) {
        await refreshSetupStatus().catch(() => undefined);
        return;
      }
      dispatchAdminError({
        type: "SET_GLOBAL_ERROR",
        message: setupErrorMessage(locale, setupError),
      });
    } finally {
      setBusy(false);
    }
  }

  function beginGitHubRedirect() {
    setGithubRedirectPending(true);
    dispatchAdminError({ type: "CLEAR_GLOBAL_ERROR" });
  }

  async function beginGitHubLink() {
    setGithubLinkPending(true);
    setGithubConnectionError("");
    try {
      const started = await request<GitHubOAuthStartBody>(
        "/api/admin/identity/github/link/start",
        { method: "POST", headers: { Accept: "application/json" } },
      );
      window.location.assign(started.authorization_url);
    } catch (linkError) {
      setGithubConnectionError(
        linkError instanceof Error &&
          linkError.message === "RECENT_AUTHENTICATION_REQUIRED"
          ? copyFor(
              locale,
              "請先以目前的登入方式重新驗證，再連結或變更 GitHub 身分。",
              "Reauthenticate with your current sign-in method before changing the GitHub identity.",
            )
          : copyFor(
              locale,
              "無法開始 GitHub 連結，請再試一次。",
              "GitHub linking could not start. Try again.",
            ),
      );
    } finally {
      setGithubLinkPending(false);
    }
  }

  async function unlinkGitHub() {
    setGithubConnectionsPending(true);
    setGithubConnectionError("");
    try {
      await request<unknown>("/api/admin/identity/github", {
        method: "DELETE",
      });
      await refreshGitHubConnections();
    } catch (unlinkError) {
      setGithubConnectionError(
        unlinkError instanceof Error &&
          unlinkError.message === "LAST_AUTH_METHOD_REQUIRED"
          ? copyFor(
              locale,
              "無法移除唯一可用的登入方式。請先新增或復原帳密登入。",
              "The final usable sign-in method cannot be removed. Add or recover password sign-in first.",
            )
          : copyFor(
              locale,
              "無法解除 GitHub 連結，請再試一次。",
              "GitHub could not be unlinked. Try again.",
            ),
      );
    } finally {
      setGithubConnectionsPending(false);
    }
  }

  async function checkGitHubConnection(credentialId: number) {
    setGithubConnectionsPending(true);
    setGithubConnectionError("");
    try {
      await request<GitHubConnection>(
        `/api/admin/github/connections/${credentialId}/check`,
        { method: "POST" },
      );
      await refreshGitHubConnections();
    } catch (checkError) {
      setGithubConnectionError(
        checkError instanceof Error &&
          checkError.message === "GITHUB_CONNECTION_REQUIRED"
          ? copyFor(
              locale,
              "此 GitHub 憑證需要重新連線；RepoNPC 不會自動改用其他憑證。",
              "This GitHub credential needs reconnection. RepoNPC will not switch to another credential automatically.",
            )
          : copyFor(
              locale,
              "無法驗證 GitHub 連線，請再試一次。",
              "GitHub connection validation failed. Try again.",
            ),
      );
      await refreshGitHubConnections();
    } finally {
      setGithubConnectionsPending(false);
    }
  }

  async function deleteGitHubConnection(credentialId: number) {
    setGithubConnectionsPending(true);
    setGithubConnectionError("");
    try {
      await request<unknown>(`/api/admin/github/connections/${credentialId}`, {
        method: "DELETE",
      });
      await refreshGitHubConnections();
    } catch {
      setGithubConnectionError(
        copyFor(
          locale,
          "無法移除 GitHub 公開讀取憑證，請再試一次。",
          "The GitHub public-read credential could not be removed. Try again.",
        ),
      );
    } finally {
      setGithubConnectionsPending(false);
    }
  }

  async function savePublicReadPat(event: React.FormEvent) {
    event.preventDefault();
    const token = publicReadPat;
    setPublicReadPat("");
    if (!token) return;
    setGithubConnectionsPending(true);
    setGithubConnectionError("");
    try {
      await request<GitHubConnection>("/api/admin/github/connections/pat", {
        method: "PUT",
        body: JSON.stringify({ token }),
      });
      await refreshGitHubConnections();
    } catch {
      setGithubConnectionError(
        copyFor(
          locale,
          "無法儲存 GitHub 公開讀取 PAT。請確認它沒有額外權限後再試一次。",
          "The GitHub public-read PAT could not be saved. Confirm that it has no additional permissions, then try again.",
        ),
      );
    } finally {
      // Keep the secret out of controlled component state even on a failed request.
      setPublicReadPat("");
      setGithubConnectionsPending(false);
    }
  }

  function applyGuidedAction(action: GuidedOnboardingAction) {
    try {
      setGuidedState(guidedOnboardingReducer(guidedState, action));
      dispatchAdminError({ type: "CLEAR_GUIDED_ERROR" });
    } catch (transitionError) {
      const code =
        transitionError instanceof Error
          ? transitionError.message
          : "VALIDATION_ERROR";
      dispatchAdminError({ type: "SET_GUIDED_ERROR", code });
    }
  }

  async function discoverRepositories(account: string, page: number) {
    await performGuided(async () => {
      const result = await request<RepositoryDiscoveryBody>(
        "/api/admin/onboarding/repositories/discover",
        {
          method: "POST",
          body: JSON.stringify({ account, page }),
        },
      );
      setGuidedState((current) => {
        const withAccount = guidedOnboardingReducer(current, {
          type: "SET_ACCOUNT",
          account,
        });
        return guidedOnboardingReducer(withAccount, {
          type: "MERGE_REPOSITORIES",
          repositories: result.repositories,
          page: result.page,
          hasMore: result.has_more,
        });
      });
    });
  }

  async function resolveRepository(repository: string, ref: string | null) {
    await performGuided(async () => {
      const result = await request<RepositoryMetadata & { ref: string | null }>(
        "/api/admin/onboarding/repositories/resolve",
        {
          method: "POST",
          body: JSON.stringify({ repository, ref }),
        },
      );
      setGuidedState((current) =>
        guidedOnboardingReducer(current, {
          type: "ADD_REPOSITORY",
          repository: result,
        }),
      );
    });
  }

  function markBatchAnalysisStarted() {
    setGuidedState((current) => {
      if (current.step !== "analysis") return current;
      return selectedRepositories(current).reduce(
        (next, repository) =>
          guidedOnboardingReducer(next, {
            type: "ANALYSIS_STARTED",
            slug: repository.metadata.slug,
          }),
        current,
      );
    });
  }

  async function createAnalysisBatch() {
    if (!batchPlan || batchPreflight.status !== "ready") return;
    setBatchCreatePending(true);
    setBatchActions({ pending: null, error: null });
    try {
      const existingKey = batchIdempotency.current;
      const idempotencyKey =
        existingKey?.planId === batchPlan.plan_id
          ? existingKey.key
          : (window.crypto?.randomUUID?.() ??
            `batch-${Date.now()}-${Math.random().toString(16).slice(2)}`);
      batchIdempotency.current = {
        planId: batchPlan.plan_id,
        key: idempotencyKey,
      };
      const result = await request<BatchCreateBody>(
        "/api/admin/onboarding/analysis-batches",
        {
          method: "POST",
          body: JSON.stringify({
            plan_id: batchPlan.plan_id,
            selections: batchSelections,
            idempotency_key: idempotencyKey,
          }),
        },
      );
      markBatchAnalysisStarted();
      applyBatchSnapshot(result.batch);
    } catch (error) {
      setBatchActions({
        pending: null,
        error: batchOperationError(error, "batch"),
      });
    } finally {
      setBatchCreatePending(false);
    }
  }

  async function actOnBatch(
    batchId: string,
    action: "pause" | "resume" | "cancel" | "retry",
  ) {
    setBatchActions({ pending: action, error: null });
    try {
      const snapshot = await request<BatchSnapshotBody>(
        `/api/admin/onboarding/analysis-batches/${encodeURIComponent(batchId)}/${action}`,
        { method: "POST" },
      );
      applyBatchSnapshot(snapshot);
    } catch (error) {
      setBatchActions({
        pending: null,
        error: batchOperationError(error, "batch_action"),
      });
    } finally {
      setBatchActions((current) =>
        current.pending === action ? { ...current, pending: null } : current,
      );
    }
  }

  async function analyzeRepository(slug: string) {
    const repository = selectedRepositories(guidedState).find(
      (candidate) => candidate.metadata.slug === slug,
    );
    if (!repository) return;
    applyGuidedAction({ type: "ANALYSIS_STARTED", slug });
    try {
      setBusy(true);
      dispatchAdminError({ type: "CLEAR_GUIDED_ERROR" });
      const analysis = await request<RepositoryAnalysis>(
        "/api/admin/onboarding/repositories/analyze",
        {
          method: "POST",
          body: JSON.stringify({
            slug,
            ref: repository.ref,
            include: repository.include,
            exclude: repository.exclude,
          }),
        },
      );
      setGuidedState((current) =>
        guidedOnboardingReducer(current, {
          type: "ANALYSIS_COMPLETED",
          slug,
          analysis,
        }),
      );
    } catch (analysisError) {
      setGuidedState((current) =>
        guidedOnboardingReducer(current, {
          type: "ANALYSIS_UNAVAILABLE",
          slug,
        }),
      );
      const code =
        analysisError instanceof Error
          ? analysisError.message
          : "PROVIDER_ERROR";
      dispatchAdminError({ type: "SET_GUIDED_ERROR", code });
    } finally {
      setBusy(false);
    }
  }

  async function suggestContribution(slug: string) {
    const repository = selectedRepositories(guidedState).find(
      (candidate) => candidate.metadata.slug === slug,
    );
    if (!repository?.ownerStatement.trim()) return;
    await performGuided(async () => {
      const result = await request<ContributionSuggestionBody>(
        "/api/admin/onboarding/contributions/suggest",
        {
          method: "POST",
          body: JSON.stringify({
            slug,
            owner_statement: repository.ownerStatement,
          }),
        },
      );
      setGuidedState((current) =>
        guidedOnboardingReducer(current, {
          type: "SET_CONTRIBUTION_PROPOSAL",
          slug,
          originalStatement: result.original_statement,
          proposal: result.proposal,
        }),
      );
    });
  }

  async function createGuidedDraft() {
    const repositories = selectedRepositories(guidedState);
    await performGuided(async () => {
      const result = await request<OnboardingDraftBody>(
        "/api/admin/onboarding/draft",
        {
          method: "POST",
          body: JSON.stringify({
            profile: {
              display_name: guidedState.profile.displayName,
              headline: guidedState.profile.headline,
              bio: guidedState.profile.bio,
              greeting: guidedState.profile.greeting,
            },
            repositories: repositories.map((repository) => ({
              slug: repository.metadata.slug,
              ref: repository.ref,
              include: repository.include,
              exclude: repository.exclude,
              role: repository.confirmedContribution?.role,
              summary: repository.confirmedContribution?.summary,
              claims: repository.confirmedContribution?.claims ?? [],
            })),
            base_config: baseConfig,
            confirmed_assertions: true,
          }),
        },
      );
      setDraft(result.content);
      setValidation(result.validation);
      setConflict(false);
      setGuidedState((current) =>
        guidedOnboardingReducer(current, { type: "DRAFT_READY" }),
      );
    });
  }

  async function copyGuidedDraft() {
    if (!draft) return;
    await navigator.clipboard.writeText(draft);
  }

  function downloadGuidedDraft() {
    if (!draft) return;
    const url = URL.createObjectURL(
      new Blob([draft], { type: "text/yaml;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "reponpc.yml";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function performGuided(operation: () => Promise<void>) {
    setBusy(true);
    dispatchAdminError({ type: "CLEAR_GUIDED_ERROR" });
    try {
      await operation();
    } catch (guidedError) {
      const code =
        guidedError instanceof Error ? guidedError.message : "REQUEST_FAILED";
      dispatchAdminError({ type: "SET_GUIDED_ERROR", code });
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    await perform(async () => {
      const result = await request<AdminValidation>(
        "/api/admin/config/validate",
        {
          method: "POST",
          body: JSON.stringify({ content: draft }),
        },
      );
      setValidation(result);
      setConflict(false);
    });
  }

  async function showPreview() {
    await perform(async () => {
      setPreview(
        await request<AdminPreview>("/api/admin/config/preview", {
          method: "POST",
          body: JSON.stringify({ content: draft }),
        }),
      );
    });
  }

  async function save() {
    await perform(async () => {
      const result = await request<{ blob_sha: string }>("/api/admin/config", {
        method: "PUT",
        body: JSON.stringify({
          content: draft,
          expected_blob_sha: blobSha,
          commit_message: "Update RepoNPC configuration",
        }),
      });
      setBlobSha(result.blob_sha);
      setConflict(false);
      window.sessionStorage.removeItem(GUIDED_ONBOARDING_STORAGE_KEY);
      guidedResumeFound.current = false;
      setGuidedResumeReady(false);
    });
  }

  async function dispatch() {
    await perform(async () => {
      await request<{ accepted: boolean }>("/api/admin/index/dispatch", {
        method: "POST",
      });
      setStatus(await request<AdminStatus>("/api/admin/index/status"));
    });
  }

  async function logout() {
    await perform(async () => {
      await request<unknown>("/api/admin/session", { method: "DELETE" });
      clearSensitiveState();
      await refreshSetupStatus();
      await refreshAuthMethods();
    });
  }

  async function perform(operation: () => Promise<void>) {
    setBusy(true);
    dispatchAdminError({ type: "CLEAR_GLOBAL_ERROR" });
    try {
      await operation();
    } catch {
      dispatchAdminError({
        type: "SET_GLOBAL_ERROR",
        message: copyFor(
          locale,
          "操作失敗，請再試一次。",
          "The operation failed. Try again.",
        ),
      });
    } finally {
      setBusy(false);
    }
  }

  function clearSensitiveState() {
    setCsrfToken("");
    setPassword("");
    setSetupCode("");
    setSetupPassword("");
    setSetupPasswordConfirmation("");
    setDraft("");
    setBlobSha("");
    setValidation(null);
    setPreview(null);
    setStatus(null);
    setProviderStatus(null);
    setProviderStatusPending(true);
    setSnippet(null);
    setConflict(false);
    setGitHubOperationsReady(false);
    setGithubSetupGuide(null);
    setGithubSetupGuideOpen(false);
    setGithubSetupGuidePending(false);
    setGithubSetupGuideError("");
    githubSetupGuideTrigger.current = null;
    setGithubRedirectPending(false);
    setGithubConnections([]);
    setGithubConnectionsPending(false);
    setGithubLinkPending(false);
    setGithubConnectionError("");
    setPublicReadPat("");
    dispatchAdminError({ type: "CLEAR_ALL_ERRORS" });
    setBaseConfig(null);
    setGuidedState(initialGuidedOnboardingState());
    guidedResumeFound.current = false;
    setGuidedResumeReady(false);
    batchEventSource.current?.close();
    batchEventSource.current = null;
    batchLastEventId.current = null;
    batchAnnouncement.current = null;
    batchIdempotency.current = null;
    batchPlanRef.current = null;
    setBatchPreflight({ status: "idle" });
    setBatchPlan(null);
    setBatchSnapshot(null);
    setBatchProgressState(null);
    setBatchStream({
      connection: "idle",
      reconnectAttempts: 0,
      lastEventId: null,
    });
    setBatchActions({ pending: null, error: null });
    setBatchCreatePending(false);
    setActiveBatchLoaded(false);
    window.sessionStorage.removeItem(GUIDED_ONBOARDING_STORAGE_KEY);
  }

  if (!authenticated) {
    return (
      <>
        <AdminAccessPanel
          busy={busy}
          error={adminErrors.globalMessage}
          locale={locale}
          onGitHubRedirect={beginGitHubRedirect}
          onGitHubSetupGuide={openGitHubSetupGuide}
          onLogin={(event) => void login(event)}
          onPasswordChange={setPassword}
          onRefreshSetupStatus={() => {
            void refreshSetupStatus().catch(() => undefined);
          }}
          onSetupCodeChange={setSetupCode}
          onSetupOwner={(event) => void setupOwner(event)}
          onSetupPasswordChange={setSetupPassword}
          onSetupPasswordConfirmationChange={setSetupPasswordConfirmation}
          onUsernameChange={setUsername}
          githubAvailable={authMethods?.github.available === true}
          githubPending={githubRedirectPending}
          password={password}
          setupCode={setupCode}
          setupPassword={setupPassword}
          setupPasswordConfirmation={setupPasswordConfirmation}
          setupStatus={setupStatus}
          setupStatusPending={setupStatusPending}
          username={username}
        />
        <GitHubOAuthSetupGuideDialog
          error={githubSetupGuideError}
          guide={githubSetupGuide}
          locale={locale}
          onClose={closeGitHubSetupGuide}
          onRefresh={refreshGitHubSetupGuide}
          open={githubSetupGuideOpen}
          pending={githubSetupGuidePending}
          returnFocusRef={githubSetupGuideTrigger}
        />
      </>
    );
  }

  return (
    <>
      <AdminWorkspace
        advancedMode={guidedState.mode === "advanced"}
        authenticated
        busy={busy}
        conflict={conflict}
        draft={draft}
        githubConnectionView={
          <GitHubConnectionPanel
            connections={githubConnections}
            error={githubConnectionError}
            linkPending={githubLinkPending}
            locale={locale}
            oauthAvailable={authMethods?.github.available === true}
            onCheck={(credentialId) => void checkGitHubConnection(credentialId)}
            onDelete={(credentialId) =>
              void deleteGitHubConnection(credentialId)
            }
            onLink={() => void beginGitHubLink()}
            onGitHubSetupGuide={openGitHubSetupGuide}
            onPatChange={setPublicReadPat}
            onSavePat={(event) => void savePublicReadPat(event)}
            onUnlink={() => void unlinkGitHub()}
            patToken={publicReadPat}
            pending={githubConnectionsPending}
          />
        }
        githubOperationsReady={githubOperationsReady}
        guidedView={
          <GuidedOnboardingView
            batchAnalysisTerminal={
              batchSnapshot !== null && isTerminalBatch(batchSnapshot.status)
            }
            batchAnalysisView={
              <BatchAnalysisPanel
                actions={batchActions}
                job={batchSnapshot}
                locale={locale}
                onCancel={(batchId) => void actOnBatch(batchId, "cancel")}
                onPause={(batchId) => void actOnBatch(batchId, "pause")}
                onResume={(batchId) => void actOnBatch(batchId, "resume")}
                onRetry={(batchId) => void actOnBatch(batchId, "retry")}
                preflight={batchPreflight}
                progress={batchProgressState}
                stream={batchStream}
              />
            }
            batchCanCreate={
              batchPlan !== null &&
              batchPreflight.status === "ready" &&
              batchSnapshot === null &&
              !batchCreatePending
            }
            batchCreatePending={batchCreatePending}
            busy={busy}
            errorCode={adminErrors.guidedCode}
            locale={locale}
            providerStatus={providerStatus}
            providerStatusPending={providerStatusPending}
            onAction={applyGuidedAction}
            onAnalyze={(slug) => void analyzeRepository(slug)}
            onCreateBatch={() => void createAnalysisBatch()}
            onCopyDraft={() => void copyGuidedDraft()}
            onCreateDraft={() => void createGuidedDraft()}
            onDiscover={(account, page) =>
              void discoverRepositories(account, page)
            }
            onDownloadDraft={downloadGuidedDraft}
            onResolve={(repository, ref) =>
              void resolveRepository(repository, ref)
            }
            onRefreshProviderStatus={() => void refreshProviderStatus()}
            onSuggestContribution={(slug) => void suggestContribution(slug)}
            state={guidedState}
          />
        }
        locale={locale}
        notice={adminErrors.globalMessage}
        onCopy={() =>
          void navigator.clipboard.writeText(snippet?.markdown ?? "")
        }
        onDispatch={() => void dispatch()}
        onDraftChange={(value) => {
          setDraft(value);
          setValidation(null);
          setConflict(false);
          setGuidedState((current) =>
            guidedOnboardingReducer(current, {
              type: "MARK_RAW_YAML_UNMAPPED",
              value: true,
            }),
          );
        }}
        onLogout={() => void logout()}
        onAdvancedModeChange={(advanced) =>
          applyGuidedAction({
            type: "SET_MODE",
            mode: advanced ? "advanced" : "guided",
          })
        }
        onPreview={() => void showPreview()}
        onSave={() => void save()}
        onValidate={() => void validate()}
        preview={preview}
        snippet={snippet}
        status={status}
        validation={validation}
      />
      <GitHubOAuthSetupGuideDialog
        error={githubSetupGuideError}
        guide={githubSetupGuide}
        locale={locale}
        onClose={closeGitHubSetupGuide}
        onRefresh={refreshGitHubSetupGuide}
        open={githubSetupGuideOpen}
        pending={githubSetupGuidePending}
        returnFocusRef={githubSetupGuideTrigger}
      />
    </>
  );
}
