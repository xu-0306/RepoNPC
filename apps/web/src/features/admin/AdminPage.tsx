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
import { AdminAccessLayout } from "./AdminAccessLayout";
import {
  BatchAnalysisPanel,
  type BatchActionState,
  type BatchJobSnapshot,
  type BatchJobStatus,
  type BatchOperationError,
  type BatchPreflightState,
  type BatchProgressAnnouncement,
  type BatchProgressState,
  type BatchRepositoryItem,
  type BatchRepositoryStage,
  type BatchRepositoryState,
  type BatchSseState,
} from "./BatchAnalysisPanel";
import {
  ChatProfilePanel,
  type ChatProfileDraft,
  type ChatProfileView,
} from "./ChatProfilePanel";
import {
  AnalysisSelectionPanel,
  type AnalysisSelectionView,
} from "./AnalysisSelectionPanel";
import type { AdminModelState, AdminWorkspaceStatus } from "./AdminStatusCards";
import {
  batchDuration,
  preflightState,
  type BatchPreflightBody,
} from "./batchPreflight";
import { adminErrorStateReducer, initialAdminErrorState } from "./adminErrors";
import {
  EmbeddingProfilePanel,
  type EmbeddingModelCatalogEntry,
  type EmbeddingProfileDraft,
  type EmbeddingProfileView,
} from "./EmbeddingProfilePanel";
import {
  ModelConnectionPanel,
  type ModelConnectionDraft,
  type ModelConnectionView,
} from "./ModelConnectionPanel";
import { ModelSetupRequests, replaceSetting } from "./modelSetupRequests";
import { TransientNotice } from "./TransientNotice";
import { ModelSetupWorkspace } from "./ModelSetupWorkspace";
import { GuidedOnboardingView } from "./GuidedOnboardingView";
import { LocalLaunchAccessPanel } from "./LocalLaunchAccessPanel";
import {
  guidedOnboardingReducer,
  guidedOnboardingFromConfig,
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
  mode: "local_launch" | "password";
  password: { available: boolean };
  setup_required: boolean;
}

interface AdminAccessPanelProps {
  locale: Locale;
  busy: boolean;
  error: string;
  passwordAvailable: boolean | null;
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

type AdminAccessState =
  | "checking"
  | "local_launch"
  | "password"
  | "unavailable";

const GUIDED_ONBOARDING_STORAGE_KEY = "reponpc.guided-onboarding.v1";
export const GUIDED_DRAFT_STORAGE_KEY = "reponpc.guided-draft.v1";

export function safeDraftForSessionStorage(content: string): string | null {
  if (!content || content.length > 128 * 1024) return null;
  if (
    /(^|\n)\s*(?:api[_ -]?key|password|secret|token|credential|private[_ -]?url)\s*:/i.test(
      content,
    )
  ) {
    return null;
  }
  return content;
}

function copyFor(locale: Locale, chinese: string, english: string): string {
  return locale === "zh-TW" ? chinese : english;
}

export function takeLocalLaunchGrant(
  hash: string,
  clearFragment: () => void,
): string | null {
  if (!hash) return null;

  const values = new URLSearchParams(
    hash.startsWith("#") ? hash.slice(1) : hash,
  ).getAll("local-launch");
  clearFragment();
  return values.length === 1 && values[0].length > 0 ? values[0] : null;
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

function embeddingProfileErrorMessage(locale: Locale, error: unknown): string {
  const code = error instanceof Error ? error.message : "REQUEST_FAILED";
  if (
    code === "EMBEDDING_PROFILE_ACTIVE_REQUIRED" ||
    code === "EMBEDDING_REINDEX_ACTIVE"
  ) {
    return copyFor(
      locale,
      "模型正在供公開網站使用或重建索引，無法刪除。請重新整理狀態，等待索引完成，並先切換公開模型。",
      "The model is active on the public site or rebuilding the index and cannot be deleted. Refresh its status, wait for indexing to finish, and switch the public model first.",
    );
  }
  if (code === "EMBEDDING_REINDEX_REQUIRED") {
    return copyFor(
      locale,
      "這個資料查找模型尚未通過測試，或與目前公開資料不相容；已保留上一個可用模型。",
      "This content finder has not passed testing or is incompatible with the current public data. The last known-good model was preserved.",
    );
  }
  if (code === "EMBEDDING_CONNECTION_REQUIRED") {
    return copyFor(
      locale,
      "這個服務連線尚未由伺服器設定；RepoNPC 不會自動改用其他服務。",
      "This service connection is not configured by the server. RepoNPC will not switch services automatically.",
    );
  }
  return copyFor(
    locale,
    "資料查找模型操作未完成。請確認已選服務與模型名稱，並檢查網路及登入狀態後重試。",
    "The content finder operation could not finish. Check the selected service, model name, network, and sign-in before retrying.",
  );
}

function modelConnectionErrorMessage(locale: Locale, error: unknown): string {
  const code = error instanceof Error ? error.message : "REQUEST_FAILED";
  const messages: Record<string, [string, string]> = {
    CREDENTIAL_REPLACE_REQUIRED: [
      "更換網址或連線方式時，請重新填入此服務的 API key，或選擇移除金鑰後再儲存。",
      "When changing a service URL or connection type, enter a new API key for that service or choose to remove the key before saving.",
    ],
    MODEL_CONNECTION_IN_USE: [
      "有模型仍使用此服務。請先編輯那些模型改用其他服務，或刪除不需要的模型設定。",
      "Models still use this service. Edit those models to use another service, or delete model settings you no longer need.",
    ],
    MODEL_SECRET_STORAGE_UNAVAILABLE: [
      "無法讀取受保護的服務設定。請檢查本機金鑰檔與存取權限，原設定不會被覆寫。",
      "Protected service settings could not be read. Check the local key file and access permissions; existing settings will not be overwritten.",
    ],
    INVALID_PROVIDER_URL: [
      "服務網址格式不正確，請從服務商複製完整 API 位址。",
      "The service URL is invalid. Copy the complete API address from your provider.",
    ],
    INSECURE_PROVIDER_URL: [
      "網路服務需要 https 網址，請確認服務商提供的 API 位址。",
      "Internet services require an https URL. Check the API address supplied by your provider.",
    ],
    VALIDATION_ERROR: [
      "請檢查服務名稱、連線方式與網址；如果剛送出過，請重新填入金鑰再試。",
      "Check the service name, connection type, and URL. If you already submitted the form, re-enter the key before retrying.",
    ],
  };
  const message = Object.hasOwn(messages, code) ? messages[code] : null;
  return message
    ? copyFor(locale, message[0], message[1])
    : copyFor(
        locale,
        "服務設定操作未完成。請確認網路與登入狀態，再重新操作；需要金鑰時請重新填入。",
        "The service setting could not be changed. Check your network and sign-in, then retry; re-enter the key if needed.",
      );
}

function chatProfileErrorMessage(locale: Locale, error: unknown): string {
  const code = error instanceof Error ? error.message : "REQUEST_FAILED";
  const messages: Record<string, [string, string]> = {
    CHAT_PROFILE_ACTIVE_IMMUTABLE: [
      "公開網站正在使用此模型，無法修改或刪除。請先到進階設定切換公開模型。",
      "The public site uses this model, so it cannot be edited or deleted. Switch the public model in advanced settings first.",
    ],
    CHAT_CONNECTION_REQUIRED: [
      "Chat 服務尚未設定，請先選擇可用的模型服務。",
      "This Chat service is not configured. Choose a configured model service first.",
    ],
    CHAT_PROBE_REQUIRED: [
      "請先測試 Chat 模型，再啟用它。",
      "Test this Chat model before using it.",
    ],
    CHAT_PROFILE_STALE: [
      "模型服務設定已變更，請重新測試後再啟用。",
      "The service changed. Test the model again before using it.",
    ],
    CHAT_PROBE_INVALID_RESPONSE: [
      "模型回應格式不符合測試要求，請修改模型或服務後重試。",
      "The model response did not pass the capability test. Edit the model or service and retry.",
    ],
  };
  const message = messages[code];
  return message
    ? copyFor(locale, message[0], message[1])
    : copyFor(
        locale,
        "模型操作未完成。請確認網路連線，查看模型卡片上的說明後重試。",
        "The model operation did not finish. Check your connection and the message on the model card, then retry.",
      );
}

export function AdminAccessPanel({
  locale,
  busy,
  error,
  passwordAvailable,
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
}: AdminAccessPanelProps) {
  const setupRequired = setupStatus?.setup_required === true;
  const setupUnavailable = !setupStatusPending && setupStatus === null;
  const passwordRecoveryRequired =
    !setupStatusPending &&
    setupStatus?.setup_required === false &&
    passwordAvailable === false;
  const mode = setupStatusPending
    ? "loading"
    : setupRequired
      ? "setup"
      : passwordRecoveryRequired
        ? "recovery"
        : setupUnavailable
          ? "unavailable"
          : "login";
  const title =
    mode === "setup"
      ? copyFor(locale, "首次設定", "first-time setup")
      : mode === "login"
        ? copyFor(locale, "管理員登入", "admin sign in")
        : mode === "recovery"
          ? copyFor(locale, "恢復管理員存取", "restore admin access")
          : copyFor(locale, "管理介面", "admin console");

  return (
    <AdminAccessLayout
      locale={locale}
      mode={mode}
      headingId="admin-access-heading"
      title={
        <>
          <span className="admin-auth__product">RepoNPC</span>
          <span className="admin-auth__title-action">{title}</span>
        </>
      }
    >
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

      {mode === "recovery" && (
        <div className="admin-auth__content">
          <p className="admin-auth__intro">
            {copyFor(
              locale,
              "這個資料目錄已有管理員，但目前沒有可用的 production 密碼。請在部署主機執行下方命令設定新密碼，再重新檢查。",
              "This data directory has an administrator, but no production password is available. Run the command below on the deployment host to set a new password, then check again.",
            )}
          </p>
          <code>reponpc admin set-password --data-dir &lt;dir&gt;</code>
          <button
            className="admin-auth__secondary-action"
            disabled={busy}
            onClick={onRefreshSetupStatus}
            type="button"
          >
            {copyFor(
              locale,
              "設定密碼後重新檢查",
              "Check after setting password",
            )}
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
                maxLength={128}
                onChange={(event) => onSetupPasswordChange(event.target.value)}
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
                  "僅限 loopback evaluation 時至少 4 個字元；production 至少 15 個字元，兩者上限皆為 128。不限制大小寫、數字或符號，常見密碼會被拒絕。",
                  "Loopback evaluation accepts 4–128 characters; production requires 15–128. Character composition is optional and common passwords are blocked.",
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
                maxLength={128}
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
                : copyFor(locale, "建立我的管理員", "Create my administrator")}
            </button>
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
    </AdminAccessLayout>
  );
}

export function AdminPage({
  locale,
  onLocaleChange,
}: {
  locale: Locale;
  onLocaleChange?: (locale: Locale) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [setupCode, setSetupCode] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupPasswordConfirmation, setSetupPasswordConfirmation] =
    useState("");
  const [setupStatus, setSetupStatus] = useState<SetupStatusBody | null>(null);
  const [setupStatusPending, setSetupStatusPending] = useState(true);
  const [passwordAvailable, setPasswordAvailable] = useState<boolean | null>(
    null,
  );
  const [accessState, setAccessState] = useState<AdminAccessState>("checking");
  const [csrfToken, setCsrfToken] = useState("");
  const [draft, setDraft] = useState("");
  const [blobSha, setBlobSha] = useState("");
  const [validation, setValidation] = useState<AdminValidation | null>(null);
  const [preview, setPreview] = useState<AdminPreview | null>(null);
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [providerStatus, setProviderStatus] =
    useState<GuidedProviderStatus | null>(null);
  const [providerStatusPending, setProviderStatusPending] = useState(true);
  const [embeddingProfiles, setEmbeddingProfiles] = useState<
    EmbeddingProfileView[]
  >([]);
  const [embeddingModelCatalog, setEmbeddingModelCatalog] = useState<
    EmbeddingModelCatalogEntry[]
  >([]);
  const [modelConnections, setModelConnections] = useState<
    ModelConnectionView[]
  >([]);
  const [installedState, setInstalledState] = useState<{
    connectionId: string;
    connectionRevision: number | null;
    status: "idle" | "loading" | "loaded" | "failed";
    models: string[];
  }>({
    connectionId: "",
    connectionRevision: null,
    status: "idle",
    models: [],
  });
  const installedGeneration = useRef(0);
  useEffect(() => {
    if (!installedState.connectionId) return;
    const current = modelConnections.find(
      (item) => item.connection_id === installedState.connectionId,
    );
    if (
      !current ||
      current.provider !== "ollama" ||
      current.revision !== installedState.connectionRevision
    ) {
      installedGeneration.current += 1;
      setInstalledState({
        connectionId: "",
        connectionRevision: null,
        status: "idle",
        models: [],
      });
    }
  }, [
    modelConnections,
    installedState.connectionId,
    installedState.connectionRevision,
  ]);
  const modelRequests = useRef({
    chat: new ModelSetupRequests(),
    embedding: new ModelSetupRequests(),
    connection: new ModelSetupRequests(),
    selection: new ModelSetupRequests(),
  });
  const [chatProfilesLoading, setChatProfilesLoading] = useState(false);
  const [embeddingProfilesLoading, setEmbeddingProfilesLoading] =
    useState(false);
  const [modelConnectionsLoading, setModelConnectionsLoading] = useState(false);
  const [chatProfilesNotice, setChatProfilesNotice] = useState("");
  const [embeddingProfilesNotice, setEmbeddingProfilesNotice] = useState("");
  const [modelConnectionsNotice, setModelConnectionsNotice] = useState("");
  const [serviceSaveNotice, setServiceSaveNotice] = useState<{
    id: number;
    message: string;
  } | null>(null);
  const serviceSaveSequence = useRef(0);
  const [chatProbeId, setChatProbeId] = useState<string | null>(null);
  const [embeddingProbeId, setEmbeddingProbeId] = useState<string | null>(null);
  const [embeddingProfilesPending, setEmbeddingProfilesPending] =
    useState(false);
  const [embeddingProfilesError, setEmbeddingProfilesError] = useState("");
  const [modelConnectionsPending, setModelConnectionsPending] = useState(false);
  const [modelConnectionsError, setModelConnectionsError] = useState("");
  const [chatProfiles, setChatProfiles] = useState<ChatProfileView[]>([]);
  const [chatProfilesPending, setChatProfilesPending] = useState(false);
  const [chatProfilesError, setChatProfilesError] = useState("");
  const [analysisSelection, setAnalysisSelection] =
    useState<AnalysisSelectionView | null>(null);
  const [analysisSelectionPending, setAnalysisSelectionPending] =
    useState(false);
  const [analysisSelectionError, setAnalysisSelectionError] = useState("");
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
  const draftHydrated = useRef(false);
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
  const accessBootstrapStarted = useRef(false);
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

  const refreshEmbeddingProfiles = useCallback(async () => {
    setEmbeddingProfilesLoading(true);
    setEmbeddingProfilesNotice("");
    try {
      await modelRequests.current.embedding.read(
        async () => {
          const profiles = await request<{ profiles: EmbeddingProfileView[] }>(
            "/api/admin/embedding-profiles",
          );
          const catalog = await request<{
            models: EmbeddingModelCatalogEntry[];
          }>("/api/admin/embedding-models/catalog").catch(() => ({
            models: [],
          }));
          return { profiles, catalog };
        },
        ({ profiles, catalog }) => {
          setEmbeddingProfiles(profiles.profiles);
          setEmbeddingModelCatalog(catalog.models);
        },
      );
    } catch {
      setEmbeddingProfilesNotice(
        copyFor(
          locale,
          "清單更新失敗，已完成的操作仍然保留。請按「重新整理」再讀取。",
          "The list could not refresh. Completed changes are kept. Use Refresh to load it again.",
        ),
      );
    } finally {
      setEmbeddingProfilesLoading(false);
    }
  }, [locale, request]);

  const refreshModelConnections = useCallback(async () => {
    setModelConnectionsLoading(true);
    setModelConnectionsNotice("");
    try {
      await modelRequests.current.connection.read(
        () =>
          request<{ connections: ModelConnectionView[] }>(
            "/api/admin/model-connections",
          ),
        (value) => setModelConnections(value.connections),
      );
    } catch {
      setModelConnectionsNotice(
        copyFor(
          locale,
          "服務清單更新失敗，已完成的操作仍然保留。請按「重新整理」再讀取。",
          "The service list could not refresh. Completed changes are kept. Use Refresh to load it again.",
        ),
      );
    } finally {
      setModelConnectionsLoading(false);
    }
  }, [locale, request]);

  const refreshChatProfiles = useCallback(async () => {
    setChatProfilesLoading(true);
    setChatProfilesNotice("");
    try {
      await modelRequests.current.chat.read(
        () =>
          request<{ profiles: ChatProfileView[] }>("/api/admin/chat-profiles"),
        (value) => setChatProfiles(value.profiles),
      );
    } catch {
      setChatProfilesNotice(
        copyFor(
          locale,
          "清單更新失敗，已完成的操作仍然保留。請按「重新整理」再讀取。",
          "The list could not refresh. Completed changes are kept. Use Refresh to load it again.",
        ),
      );
    } finally {
      setChatProfilesLoading(false);
    }
  }, [locale, request]);

  async function loadInstalledModels(connectionId: string) {
    const connection = modelConnections.find(
      (item) => item.connection_id === connectionId,
    );
    if (!connection || connection.provider !== "ollama") return;
    const connectionRevision = connection.revision;
    const generation = ++installedGeneration.current;
    setInstalledState({
      connectionId,
      connectionRevision,
      status: "loading",
      models: [],
    });
    try {
      const result = await request<{ models: string[] }>(
        `/api/admin/embedding-models/installed?connection_id=${encodeURIComponent(connectionId)}`,
      );
      if (generation === installedGeneration.current)
        setInstalledState({
          connectionId,
          connectionRevision,
          status: "loaded",
          models: result.models,
        });
    } catch {
      if (generation === installedGeneration.current)
        setInstalledState({
          connectionId,
          connectionRevision,
          status: "failed",
          models: [],
        });
    }
  }

  const refreshAnalysisSelection = useCallback(async () => {
    try {
      await modelRequests.current.selection.read(
        () => request<AnalysisSelectionView>("/api/admin/analysis-selection"),
        (value) => {
          setAnalysisSelection(value);
          setAnalysisSelectionError("");
          setGuidedState((current) =>
            guidedOnboardingReducer(current, {
              type: "SET_MODELS_CONFIGURED",
              value: value.eligible,
            }),
          );
        },
      );
    } catch {
      setAnalysisSelection(null);
      setAnalysisSelectionError(
        copyFor(
          locale,
          "無法讀取分析模型狀態，請重新檢查。",
          "Analysis model status could not be loaded. Recheck to continue.",
        ),
      );
      setGuidedState((current) =>
        guidedOnboardingReducer(current, {
          type: "SET_MODELS_CONFIGURED",
          value: false,
        }),
      );
    }
  }, [locale, request]);

  async function selectAnalysisModels(
    chatProfileId: string,
    embeddingProfileId: string,
    generation: number,
  ) {
    setAnalysisSelectionPending(true);
    setAnalysisSelectionError("");
    try {
      await modelRequests.current.selection.mutate(
        () =>
          request<AnalysisSelectionView>("/api/admin/analysis-selection", {
            method: "POST",
            body: JSON.stringify({
              chat_profile_id: chatProfileId,
              embedding_profile_id: embeddingProfileId,
              expected_generation: generation,
            }),
          }),
        (value) => {
          setAnalysisSelection(value);
          setGuidedState((current) =>
            guidedOnboardingReducer(current, {
              type: "SET_MODELS_CONFIGURED",
              value: value.eligible,
            }),
          );
        },
      );
    } catch (error) {
      await refreshAnalysisSelection();
      setAnalysisSelectionError(
        error instanceof Error && error.message.includes("STALE")
          ? copyFor(
              locale,
              "模型或服務設定已變更，請依目前狀態重新選擇並確認。",
              "Model or service settings changed. Review the current status, then select and confirm again.",
            )
          : copyFor(
              locale,
              "未能確認操作回應，已嘗試重新讀取目前狀態。請查看模型卡片；若仍無法選用，請確認連線後重試。",
              "The operation response could not be confirmed. We tried to reload the current status. Check the model cards and your connection before retrying.",
            ),
      );
    } finally {
      setAnalysisSelectionPending(false);
    }
  }

  const refreshProviderStatus = useCallback(async () => {
    setProviderStatusPending(true);
    try {
      const currentStatus = await request<AnalysisSelectionView>(
        "/api/admin/analysis-selection",
      );
      setProviderStatus({
        ready: currentStatus.eligible,
        provider: null,
        lastCheckedAt: currentStatus.selection.updated_at,
      });
    } catch {
      setProviderStatus(null);
    } finally {
      setProviderStatusPending(false);
    }
  }, [request]);

  useEffect(() => {
    if (authenticated || accessBootstrapStarted.current) return;
    accessBootstrapStarted.current = true;

    let grant = takeLocalLaunchGrant(window.location.hash, () => {
      window.history.replaceState(
        {},
        "",
        `${window.location.pathname}${window.location.search}`,
      );
    });

    void (async () => {
      if (grant !== null) {
        const body = JSON.stringify({ grant });
        grant = null;
        try {
          const session = await request<SessionBody>(
            "/api/admin/session/local-launch",
            { method: "POST", body },
          );
          setAccessState("local_launch");
          setCsrfToken(session.csrf_token);
        } catch {
          setAccessState("local_launch");
        }
        return;
      }

      try {
        const methods = await request<AuthMethodsBody>(
          "/api/admin/auth/methods",
        );
        if (methods.mode === "local_launch") {
          setAccessState("local_launch");
          return;
        }
        setPasswordAvailable(methods.password.available);
        setAccessState("password");
        await refreshSetupStatus();
      } catch {
        setSetupStatus(null);
        setSetupStatusPending(false);
        setAccessState("unavailable");
      }
    })();
  }, [accessState, authenticated, refreshSetupStatus, request]);

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
    void refreshEmbeddingProfiles();
  }, [authenticated, refreshEmbeddingProfiles]);

  useEffect(() => {
    if (!authenticated) return;
    void refreshModelConnections();
  }, [authenticated, refreshModelConnections]);

  useEffect(() => {
    if (!authenticated) return;
    void refreshChatProfiles();
  }, [authenticated, refreshChatProfiles]);

  useEffect(() => {
    if (!authenticated) return;
    void refreshAnalysisSelection();
  }, [authenticated, refreshAnalysisSelection]);

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
    if (!authenticated || !draftHydrated.current) return;
    const safeDraft = safeDraftForSessionStorage(draft);
    try {
      if (safeDraft === null) {
        window.sessionStorage.removeItem(GUIDED_DRAFT_STORAGE_KEY);
      } else {
        window.sessionStorage.setItem(GUIDED_DRAFT_STORAGE_KEY, safeDraft);
      }
    } catch {
      // Draft continuity is best effort.
    }
  }, [authenticated, draft]);

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
        const resumedDraft = safeDraftForSessionStorage(
          window.sessionStorage.getItem(GUIDED_DRAFT_STORAGE_KEY) ?? "",
        );
        draftHydrated.current = true;
        setDraft(resumedDraft ?? configResult.value.content);
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
          if (!guidedResumeFound.current) {
            setGuidedState(
              guidedOnboardingFromConfig(parsed.parsed) ??
                initialGuidedOnboardingState(true),
            );
          }
        } catch {
          setBaseConfig(null);
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
      setPasswordAvailable(true);
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

  function applyChatProfile(saved: ChatProfileView) {
    setChatProfiles((current) =>
      replaceSetting(
        saved.active ? current.map((p) => ({ ...p, active: false })) : current,
        saved,
        "profile_id",
      ),
    );
  }
  function applyEmbeddingProfile(saved: EmbeddingProfileView) {
    setEmbeddingProfiles((current) =>
      replaceSetting(
        saved.active ? current.map((p) => ({ ...p, active: false })) : current,
        saved,
        "profile_id",
      ),
    );
  }
  function applyModelConnection(saved: ModelConnectionView) {
    setModelConnections((current) =>
      replaceSetting(current, saved, "connection_id"),
    );
  }
  async function saveEmbeddingProfile(
    draft: EmbeddingProfileDraft,
    profileId?: string,
  ) {
    setEmbeddingProfilesPending(true);
    setEmbeddingProfilesError("");
    try {
      await modelRequests.current.embedding.mutate(
        () =>
          request<EmbeddingProfileView>(
            "/api/admin/embedding-profiles" +
              (profileId ? "/" + encodeURIComponent(profileId) : ""),
            { method: profileId ? "PUT" : "POST", body: JSON.stringify(draft) },
          ),
        applyEmbeddingProfile,
      );
      await refreshEmbeddingProfiles();
      await refreshAnalysisSelection();
    } catch (error) {
      setEmbeddingProfilesError(embeddingProfileErrorMessage(locale, error));
    } finally {
      setEmbeddingProfilesPending(false);
    }
  }
  async function createEmbeddingProfile(draft: EmbeddingProfileDraft) {
    await saveEmbeddingProfile(draft);
  }

  async function saveModelConnection(
    draft: ModelConnectionDraft,
    connectionId?: string,
  ) {
    setModelConnectionsPending(true);
    setModelConnectionsError("");
    setServiceSaveNotice(null);
    try {
      await modelRequests.current.connection.mutate(
        () =>
          request<ModelConnectionView>(
            "/api/admin/model-connections" +
              (connectionId ? "/" + encodeURIComponent(connectionId) : ""),
            {
              method: connectionId ? "PUT" : "POST",
              body: JSON.stringify(draft),
            },
          ),
        applyModelConnection,
      );
      setServiceSaveNotice({
        id: ++serviceSaveSequence.current,
        message: connectionId
          ? copyFor(locale, "服務已更新", "Service updated")
          : copyFor(locale, "服務已儲存", "Service saved"),
      });
      await refreshModelConnections();
      await refreshAnalysisSelection();
    } catch (error) {
      setModelConnectionsError(modelConnectionErrorMessage(locale, error));
    } finally {
      setModelConnectionsPending(false);
    }
  }
  async function createModelConnection(draft: ModelConnectionDraft) {
    await saveModelConnection(draft);
  }
  async function updateModelConnection(
    id: string,
    draft: ModelConnectionDraft,
  ) {
    await saveModelConnection(draft, id);
  }

  async function deleteModelConnection(connectionId: string) {
    setServiceSaveNotice(null);
    setModelConnectionsPending(true);
    setModelConnectionsError("");
    try {
      await modelRequests.current.connection.mutate(
        () =>
          request<void>(
            "/api/admin/model-connections/" + encodeURIComponent(connectionId),
            { method: "DELETE" },
          ),
        () =>
          setModelConnections((current) =>
            current.filter((c) => c.connection_id !== connectionId),
          ),
      );
      await refreshModelConnections();
      await refreshAnalysisSelection();
    } catch (error) {
      setModelConnectionsError(modelConnectionErrorMessage(locale, error));
    } finally {
      setModelConnectionsPending(false);
    }
  }

  async function saveChatProfile(draft: ChatProfileDraft, profileId?: string) {
    setChatProfilesPending(true);
    setChatProfilesError("");
    try {
      await modelRequests.current.chat.mutate(
        () =>
          request<ChatProfileView>(
            "/api/admin/chat-profiles" +
              (profileId ? "/" + encodeURIComponent(profileId) : ""),
            { method: profileId ? "PUT" : "POST", body: JSON.stringify(draft) },
          ),
        applyChatProfile,
      );
      await refreshChatProfiles();
      await refreshAnalysisSelection();
    } catch (error) {
      setChatProfilesError(chatProfileErrorMessage(locale, error));
    } finally {
      setChatProfilesPending(false);
    }
  }
  async function createChatProfile(draft: ChatProfileDraft) {
    await saveChatProfile(draft);
  }
  async function updateChatProfile(id: string, draft: ChatProfileDraft) {
    await saveChatProfile(draft, id);
  }

  async function actOnChatProfile(
    profileId: string,
    action: "probe" | "activate" | "delete",
  ) {
    setChatProfilesPending(true);
    setChatProfilesError("");
    setChatProbeId(action === "probe" ? profileId : null);
    try {
      await modelRequests.current.chat.mutate(
        () =>
          request<ChatProfileView>(
            `/api/admin/chat-profiles/${encodeURIComponent(profileId)}${action === "delete" ? "" : `/${action}`}`,
            { method: action === "delete" ? "DELETE" : "POST" },
          ),
        (saved) => {
          if (action === "delete")
            setChatProfiles((current) =>
              current.filter((p) => p.profile_id !== profileId),
            );
          else applyChatProfile(saved);
        },
      );
      await refreshChatProfiles();
      await refreshAnalysisSelection();
    } catch (error) {
      setChatProfilesError(chatProfileErrorMessage(locale, error));
    } finally {
      setChatProfilesPending(false);
      setChatProbeId(null);
    }
  }

  async function actOnEmbeddingProfile(
    profileId: string,
    action: "probe" | "activate" | "delete",
  ) {
    setEmbeddingProfilesPending(true);
    setEmbeddingProfilesError("");
    setEmbeddingProbeId(action === "probe" ? profileId : null);
    try {
      await modelRequests.current.embedding.mutate(
        () =>
          request<EmbeddingProfileView>(
            `/api/admin/embedding-profiles/${encodeURIComponent(profileId)}${action === "delete" ? "" : `/${action}`}`,
            { method: action === "delete" ? "DELETE" : "POST" },
          ),
        (saved) => {
          if (action === "delete")
            setEmbeddingProfiles((current) =>
              current.filter((p) => p.profile_id !== profileId),
            );
          else applyEmbeddingProfile(saved);
        },
      );
      await refreshEmbeddingProfiles();
      await refreshAnalysisSelection();
    } catch (error) {
      setEmbeddingProfilesError(embeddingProfileErrorMessage(locale, error));
    } finally {
      setEmbeddingProfilesPending(false);
      setEmbeddingProbeId(null);
    }
  }

  async function actOnOllamaEmbeddingModel(
    profileId: string,
    action: "pull" | "delete",
  ) {
    setEmbeddingProfilesPending(true);
    setEmbeddingProfilesError("");
    try {
      const profile = embeddingProfiles.find(
        (candidate) => candidate.profile_id === profileId,
      );
      if (!profile) throw new Error("NOT_FOUND");
      const path =
        action === "pull"
          ? "/api/admin/embedding-models/ollama/pull"
          : `/api/admin/embedding-models/ollama/${encodeURIComponent(profile.model_id)}`;
      await request<EmbeddingProfileView>(path, {
        method: action === "pull" ? "POST" : "DELETE",
        body: JSON.stringify({ profile_id: profileId, confirmed: true }),
      });
      await refreshEmbeddingProfiles();
    } catch (error) {
      setEmbeddingProfilesError(embeddingProfileErrorMessage(locale, error));
    } finally {
      setEmbeddingProfilesPending(false);
    }
  }

  function applyGuidedAction(action: GuidedOnboardingAction) {
    try {
      const invalidatesBatch =
        action.type === "CONFIRM_SELECTION" ||
        action.type === "EDIT_SELECTION" ||
        action.type === "RESET" ||
        (action.type === "GO_BACK" && guidedState.step === "analysis");
      if (
        invalidatesBatch &&
        batchSnapshot !== null &&
        !isTerminalBatch(batchSnapshot.status)
      ) {
        dispatchAdminError({
          type: "SET_GUIDED_ERROR",
          code: "CONCURRENCY_LIMIT",
        });
        return;
      }
      const nextState = guidedOnboardingReducer(guidedState, action);
      if (invalidatesBatch) {
        batchEventSource.current?.close();
        batchEventSource.current = null;
        batchLastEventId.current = null;
        batchAnnouncement.current = null;
        batchIdempotency.current = null;
        batchPlanRef.current = null;
        setBatchSnapshot(null);
        setBatchProgressState(null);
        setBatchStream({
          connection: "idle",
          reconnectAttempts: 0,
          lastEventId: null,
        });
        setBatchPlan(null);
        setBatchPreflight({ status: "idle" });
        setBatchActions({ pending: null, error: null });
      }
      setGuidedState(nextState);
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
    let plan = batchPlan;
    if (plan === null) {
      if (!authenticated || !activeBatchLoaded || batchSnapshot !== null)
        return;
      setBatchPreflight({ status: "loading" });
      try {
        plan = await request<BatchPreflightBody>(
          "/api/admin/onboarding/analysis-batches/preflight",
          {
            method: "POST",
            body: JSON.stringify({ selections: batchSelections }),
          },
        );
        setBatchPlan(plan);
        batchPlanRef.current = plan;
        setBatchPreflight(preflightState(plan));
      } catch (error) {
        setBatchPreflight({
          status: "failed",
          error: batchOperationError(error, "preflight"),
        });
        return;
      }
    }
    if (!plan) return;
    if (preflightState(plan).status !== "ready") return;
    setBatchCreatePending(true);
    setBatchActions({ pending: null, error: null });
    try {
      const existingKey = batchIdempotency.current;
      const idempotencyKey =
        existingKey?.planId === plan.plan_id
          ? existingKey.key
          : (window.crypto?.randomUUID?.() ??
            `batch-${Date.now()}-${Math.random().toString(16).slice(2)}`);
      batchIdempotency.current = {
        planId: plan.plan_id,
        key: idempotencyKey,
      };
      const result = await request<BatchCreateBody>(
        "/api/admin/onboarding/analysis-batches",
        {
          method: "POST",
          body: JSON.stringify({
            plan_id: plan.plan_id,
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

  async function retryAnalysisPreflight() {
    if (!authenticated || !activeBatchLoaded || batchCreatePending) return;
    setBatchPlan(null);
    batchPlanRef.current = null;
    setBatchActions({ pending: null, error: null });
    setBatchPreflight({ status: "loading" });
    try {
      try {
        const active = await request<BatchSnapshotBody>(
          "/api/admin/onboarding/analysis-batches/active",
        );
        applyBatchSnapshot(active);
        setBatchPreflight({ status: "idle" });
        return;
      } catch (error) {
        if (
          !(error instanceof AdminRequestError) ||
          error.message !== "NOT_FOUND"
        ) {
          throw error;
        }
      }
      batchEventSource.current?.close();
      batchEventSource.current = null;
      batchLastEventId.current = null;
      batchAnnouncement.current = null;
      batchIdempotency.current = null;
      setBatchSnapshot(null);
      setBatchProgressState(null);
      setBatchStream({
        connection: "idle",
        reconnectAttempts: 0,
        lastEventId: null,
      });
      const plan = await request<BatchPreflightBody>(
        "/api/admin/onboarding/analysis-batches/preflight",
        {
          method: "POST",
          body: JSON.stringify({ selections: batchSelections }),
        },
      );
      setBatchPlan(plan);
      batchPlanRef.current = plan;
      setBatchPreflight(preflightState(plan));
    } catch (error) {
      setBatchPreflight({
        status: "failed",
        error: batchOperationError(error, "preflight"),
      });
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
    if (!draft) throw new Error("DRAFT_NOT_READY");
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
      window.sessionStorage.removeItem(GUIDED_DRAFT_STORAGE_KEY);
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
      if (accessState === "password") await refreshSetupStatus();
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
    dispatchAdminError({ type: "CLEAR_ALL_ERRORS" });
    setBaseConfig(null);
    setGuidedState(initialGuidedOnboardingState());
    guidedResumeFound.current = false;
    setGuidedResumeReady(false);
    draftHydrated.current = false;
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
    window.sessionStorage.removeItem(GUIDED_DRAFT_STORAGE_KEY);
  }

  if (!authenticated) {
    if (accessState === "checking") {
      return <LocalLaunchAccessPanel locale={locale} state="checking" />;
    }
    if (accessState === "local_launch") {
      return <LocalLaunchAccessPanel locale={locale} state="relaunch" />;
    }

    return (
      <AdminAccessPanel
        busy={busy}
        error={adminErrors.globalMessage}
        locale={locale}
        onLogin={(event) => void login(event)}
        onPasswordChange={setPassword}
        onRefreshSetupStatus={() => {
          if (accessState === "unavailable" || passwordAvailable === false) {
            accessBootstrapStarted.current = false;
            setPasswordAvailable(null);
            setSetupStatusPending(true);
            setAccessState("checking");
          } else {
            void refreshSetupStatus().catch(() => undefined);
          }
        }}
        onSetupCodeChange={setSetupCode}
        onSetupOwner={(event) => void setupOwner(event)}
        onSetupPasswordChange={setSetupPassword}
        onSetupPasswordConfirmationChange={setSetupPasswordConfirmation}
        onUsernameChange={setUsername}
        password={password}
        passwordAvailable={passwordAvailable}
        setupCode={setupCode}
        setupPassword={setupPassword}
        setupPasswordConfirmation={setupPasswordConfirmation}
        setupStatus={setupStatus}
        setupStatusPending={
          accessState === "password" ? setupStatusPending : false
        }
        username={username}
      />
    );
  }

  const connectionsForPurpose = (purpose: "chat" | "embedding") =>
    modelConnections.filter(
      (connection) =>
        connection.source === "managed" ||
        connection.connection_id === `environment-${purpose}`,
    );
  const connectionPanel = (
    managementActions: boolean,
    purpose?: "chat" | "embedding",
  ) => (
    <ModelConnectionPanel
      onReadEndpoint={(connectionId) =>
        request<{ connection_id: string; revision: number; base_url: string }>(
          `/api/admin/model-connections/${encodeURIComponent(connectionId)}/edit-endpoint`,
          { method: "POST" },
        )
      }
      connections={modelConnections}
      error={modelConnectionsError}
      locale={locale}
      managementActions={managementActions}
      onCreate={(value) => void createModelConnection(value)}
      onDelete={(value) => void deleteModelConnection(value)}
      onRefresh={() => void refreshModelConnections()}
      onUpdate={(connectionId, value) =>
        void updateModelConnection(connectionId, value)
      }
      pending={modelConnectionsPending || modelConnectionsLoading}
      notice={modelConnectionsNotice}
      purpose={purpose}
    />
  );
  const chatPanel = (managementActions: boolean) => (
    <ChatProfilePanel
      connections={connectionsForPurpose("chat")}
      error={chatProfilesError}
      locale={locale}
      managementActions={managementActions}
      onActivate={(profileId) => void actOnChatProfile(profileId, "activate")}
      onCreate={(profile) => void createChatProfile(profile)}
      onDelete={(profileId) => void actOnChatProfile(profileId, "delete")}
      onUpdate={(profileId, profile) =>
        void updateChatProfile(profileId, profile)
      }
      onProbe={(profileId) => void actOnChatProfile(profileId, "probe")}
      onRefresh={() => void refreshChatProfiles()}
      pending={chatProfilesPending || chatProfilesLoading}
      pendingProfileId={chatProbeId}
      notice={chatProfilesNotice}
      profiles={chatProfiles}
    />
  );
  const embeddingPanel = (managementActions: boolean) => (
    <EmbeddingProfilePanel
      catalog={embeddingModelCatalog}
      connections={connectionsForPurpose("embedding")}
      error={embeddingProfilesError}
      installedModels={[]}
      installedState={installedState}
      onLoadInstalled={(connectionId) => void loadInstalledModels(connectionId)}
      onUpdate={(profileId, draft) =>
        void saveEmbeddingProfile(draft, profileId)
      }
      locale={locale}
      managementActions={managementActions}
      onActivate={(profileId) =>
        void actOnEmbeddingProfile(profileId, "activate")
      }
      onCreate={(profile) => void createEmbeddingProfile(profile)}
      onDelete={(profileId) => void actOnEmbeddingProfile(profileId, "delete")}
      onOllamaDelete={(profileId) =>
        void actOnOllamaEmbeddingModel(profileId, "delete")
      }
      onOllamaPull={(profileId) =>
        void actOnOllamaEmbeddingModel(profileId, "pull")
      }
      onProbe={(profileId) => void actOnEmbeddingProfile(profileId, "probe")}
      onRefresh={() => void refreshEmbeddingProfiles()}
      pending={embeddingProfilesPending || embeddingProfilesLoading}
      pendingProfileId={embeddingProbeId}
      notice={embeddingProfilesNotice}
      profiles={embeddingProfiles}
    />
  );
  const modelPanels = (
    <div className="admin-model-management">
      {connectionPanel(true)}
      {chatPanel(true)}
      {embeddingPanel(true)}
    </div>
  );
  const selectedChatId = analysisSelection?.selection.chat_profile_id ?? null;
  const selectedEmbeddingId =
    analysisSelection?.selection.embedding_profile_id ?? null;
  const selectedChat = selectedChatId
    ? chatProfiles.find((profile) => profile.profile_id === selectedChatId)
    : null;
  const selectedEmbedding = selectedEmbeddingId
    ? embeddingProfiles.find(
        (profile) => profile.profile_id === selectedEmbeddingId,
      )
    : null;
  const displayedChat =
    selectedChat ??
    chatProfiles.find(
      (profile) => profile.status === "ready" && profile.last_probed_at,
    ) ??
    chatProfiles[0] ??
    null;
  const displayedEmbedding =
    selectedEmbedding ??
    embeddingProfiles.find(
      (profile) => profile.last_probed_at && !profile.last_error_code,
    ) ??
    embeddingProfiles[0] ??
    null;
  const modelState = (
    selected: boolean,
    profile: ChatProfileView | EmbeddingProfileView | null | undefined,
    pending: boolean,
  ): AdminModelState => {
    if (pending) return "testing";
    if (!profile) return "unconfigured";
    if (profile.last_error_code || profile.status === "probe_failed") {
      return "unavailable";
    }
    if (selected && analysisSelection?.eligible) return "selected";
    if (profile.last_probed_at) return "tested";
    return "unconfigured";
  };
  const connectionName = (connectionId: string | null | undefined) =>
    modelConnections.find(
      (connection) => connection.connection_id === connectionId,
    )?.display_name ?? null;
  const connectionProvider = (connectionId: string | null | undefined) =>
    modelConnections.find(
      (connection) => connection.connection_id === connectionId,
    )?.provider ?? null;
  const workspaceStatus: AdminWorkspaceStatus = {
    chat: {
      model: displayedChat?.model_id ?? null,
      connection: connectionName(displayedChat?.connection_id),
      provider: connectionProvider(displayedChat?.connection_id),
      state: modelState(
        displayedChat?.profile_id === selectedChatId,
        displayedChat,
        chatProbeId === displayedChat?.profile_id,
      ),
    },
    embedding: {
      model: displayedEmbedding?.model_id ?? null,
      connection: connectionName(displayedEmbedding?.connection_reference),
      provider: displayedEmbedding?.provider ?? null,
      state: modelState(
        displayedEmbedding?.profile_id === selectedEmbeddingId,
        displayedEmbedding,
        embeddingProbeId === displayedEmbedding?.profile_id,
      ),
    },
    publicBundleId: status?.active_bundle_id ?? null,
  };
  const guidedModelSetup = (
    <ModelSetupWorkspace
      chatConnectionView={connectionPanel(false, "chat")}
      chatView={chatPanel(false)}
      embeddingConnectionView={connectionPanel(false, "embedding")}
      embeddingView={embeddingPanel(false)}
      locale={locale}
      selectionView={
        <AnalysisSelectionPanel
          connections={modelConnections}
          chatProfiles={chatProfiles}
          embeddingProfiles={embeddingProfiles}
          error={analysisSelectionError}
          locale={locale}
          onSelect={(chatId, embeddingId, generation) =>
            void selectAnalysisModels(chatId, embeddingId, generation)
          }
          pending={analysisSelectionPending}
          value={analysisSelection}
        />
      }
    />
  );

  return (
    <>
      <AdminWorkspace
        advancedMode={guidedState.mode === "advanced"}
        authenticated
        busy={busy}
        conflict={conflict}
        draft={draft}
        embeddingProfileView={modelPanels}
        githubOperationsReady={githubOperationsReady}
        guidedView={
          <GuidedOnboardingView
            workspaceStatus={workspaceStatus}
            batchAnalysisActive={
              batchSnapshot !== null && !isTerminalBatch(batchSnapshot.status)
            }
            batchAnalysisTerminal={
              batchSnapshot !== null && isTerminalBatch(batchSnapshot.status)
            }
            batchAnalysisView={
              batchPreflight.status !== "idle" || batchSnapshot !== null ? (
                <BatchAnalysisPanel
                  actions={batchActions}
                  job={batchSnapshot}
                  locale={locale}
                  onCancel={(batchId) => void actOnBatch(batchId, "cancel")}
                  onPause={(batchId) => void actOnBatch(batchId, "pause")}
                  onResume={(batchId) => void actOnBatch(batchId, "resume")}
                  onRetry={(batchId) => void actOnBatch(batchId, "retry")}
                  onRetryPreflight={() => void retryAnalysisPreflight()}
                  preflight={batchPreflight}
                  progress={batchProgressState}
                  stream={batchStream}
                />
              ) : undefined
            }
            batchCanCreate={
              batchPlan !== null &&
              batchPreflight.status === "ready" &&
              batchSnapshot === null &&
              !batchCreatePending
            }
            batchCreatePending={batchCreatePending}
            modelSetupView={guidedModelSetup}
            busy={busy}
            errorCode={adminErrors.guidedCode}
            locale={locale}
            providerStatus={providerStatus}
            providerStatusPending={providerStatusPending}
            onAction={applyGuidedAction}
            onAnalyze={(slug) => void analyzeRepository(slug)}
            onCreateBatch={() => void createAnalysisBatch()}
            onCopyDraft={copyGuidedDraft}
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
        onLocaleChange={onLocaleChange}
        onCopy={() =>
          void navigator.clipboard.writeText(snippet?.markdown ?? "")
        }
        onDispatch={() => void dispatch()}
        onDraftChange={(value) => {
          setDraft(value);
          setValidation(null);
          setPreview(null);
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
      {serviceSaveNotice && (
        <TransientNotice
          key={serviceSaveNotice.id}
          message={serviceSaveNotice.message}
        />
      )}
    </>
  );
}
