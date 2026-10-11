import { useCallback, useEffect, useRef, useState } from "react";
import type { Locale } from "../../i18n/messages";
import {
  MaintenancePanel,
  type MaintenanceRestorePreview,
  type MaintenanceStatus,
} from "./MaintenancePanel";

export interface MaintenanceSetupProps {
  locale: Locale;
  sendRequest: (path: string, init?: RequestInit) => Promise<Response>;
}

const ROOT = "/api/admin/maintenance";
const COPY = {
  "zh-TW": {
    failure: "維護操作暫時無法完成。請確認本機服務與備份，再重試。",
    busy: "仍有工作正在執行。請等工作結束，再進行維護操作。",
    password: "備份密碼須為 12–1024 個字元。請重新輸入。",
    decrypt: "無法解開備份。請確認檔案與密碼，再檢查一次。",
    invalid: "此備份不符合還原要求。請選擇同一台主機的有效備份。",
    resources:
      "原資料目錄缺少還原需要的密鑰、網站資料或圖片。請先保留並確認原資料目錄。",
    owner: "這份備份屬於不同的擁有者。請選擇目前擁有者在原資料目錄建立的備份。",
    secrets:
      "無法解開備份中的模型服務設定。請確認原資料目錄內的加密密鑰仍然可用。",
    website: "備份需要的網站資料無法使用。請保留並確認原資料目錄內的網站資料。",
    appearance:
      "備份需要的角色或背景圖片無法使用。請保留並確認原資料目錄內的圖片。",
    portfolio: "備份需要的本機作品集資料無法使用。請保留並確認原資料目錄。",
    embedding: "備份中的搜尋模型設定與保留的網站資料不相容。請選擇相容的備份。",
    model:
      "備份需要的本機模型檔案無法使用。請先確認原資料目錄內的模型，再檢查備份。",
    resourceInvalid:
      "無法安全驗證備份需要的本機資料。請保留並確認原資料目錄，再檢查備份。",
    validationTimeout: "備份檢查超出時間，尚未進行還原。請確認檔案後重新檢查。",
    stopFailed: "無法安全停止本機服務。請確認本機狀態後，再進行維護操作。",
    restoreFailed:
      "還原未完成。請重新開啟管理頁並確認本機狀態，再決定是否重新還原。",
    expired: "檢查結果已過期。請重新選擇檔案並檢查備份。",
    auth: "管理登入已失效或無法驗證。請重新開啟管理頁並登入。",
    unavailable:
      "本機維護服務尚未就緒，或無法安全保存備份。請確認本機服務與資料目錄。",
    backup:
      "備份已建立。請按「下載剛建立的加密備份」保存檔案；這台主機也保留一份。請妥善保存檔案與密碼。",
    backupStatusUnavailable:
      "備份已建立，但無法更新上次備份時間。稍後可按「更新狀態」再確認。",
    inspected: "備份已檢查。請確認還原範圍與有效期限，再明確同意還原。",
    cancelled: "已取消還原並清除這次檢查結果。",
    restoring:
      "還原已接受，請等本機服務完成還原，再重新開啟管理頁並登入。gateway 會保持關閉。",
    uncertain:
      "無法確認還原是否已接受。請重新開啟管理頁並確認本機狀態；確認前請勿再次送出還原。",
    pinned: "已固定使用保留的網站資料。",
    stopped:
      "本機訪客 gateway 已停止。若要關閉 Funnel，請另外依 Tailscale 官方流程操作。",
  },
  en: {
    failure:
      "The maintenance operation could not finish. Check the local service and backup before trying again.",
    busy: "Other work is still running. Wait for it to finish before maintenance.",
    password:
      "The backup password must contain 12–1024 characters. Enter it again.",
    decrypt:
      "The backup could not be decrypted. Check the file and password, then inspect it again.",
    invalid:
      "This backup cannot be restored. Select a valid backup from this same host.",
    resources:
      "The original data directory is missing required keys, website data, or images. Keep and check the original data directory first.",
    owner:
      "This backup belongs to a different owner. Select a backup created for the current owner in the original data directory.",
    secrets:
      "The saved model-service settings could not be unlocked. Check that the encryption keys in the original data directory are still available.",
    website:
      "The website data needed by this backup is unavailable. Keep and check the website data in the original data directory.",
    appearance:
      "The character or background images needed by this backup are unavailable. Keep and check the images in the original data directory.",
    portfolio:
      "The local portfolio data needed by this backup is unavailable. Keep and check the original data directory.",
    embedding:
      "The backup's search-model settings are incompatible with the retained website data. Select a compatible backup.",
    model:
      "The local model files needed by this backup are unavailable. Check the models in the original data directory before inspecting the backup again.",
    resourceInvalid:
      "The local data needed by this backup could not be safely verified. Keep and check the original data directory, then inspect the backup again.",
    validationTimeout:
      "Backup inspection took too long. Restoration has not started. Check the file and inspect it again.",
    stopFailed:
      "The local service could not be safely stopped. Check the local status before further maintenance.",
    restoreFailed:
      "Restoration did not finish. Reopen the admin page and check the local status before deciding whether to restore again.",
    expired:
      "The inspection has expired. Select the file and inspect it again.",
    auth: "The admin session expired or could not be verified. Reopen the admin page and sign in.",
    unavailable:
      "Local maintenance is not ready or cannot safely save the backup. Check the local service and data directory.",
    backup:
      "The backup was created. Select ‘Download the encrypted backup’ to save the file; a copy is also retained on this host. Keep the file and password safe.",
    backupStatusUnavailable:
      "The backup was created, but its last-backup time could not be refreshed. Use Refresh status later to check it.",
    inspected:
      "The backup was inspected. Review the restore scope and expiry, then explicitly confirm restoration.",
    cancelled: "Restoration was cancelled and this inspection was cleared.",
    restoring:
      "Restoration was accepted. Wait for the local service to finish, then reopen the admin page and sign in. The gateway stays off.",
    uncertain:
      "Restoration acceptance could not be confirmed. Reopen the admin page and check the local status. Do not submit restoration again until it is confirmed.",
    pinned: "The retained website data is now pinned.",
    stopped:
      "The local visitor gateway stopped. To turn off Funnel, separately follow Tailscale's official steps.",
  },
};

function errorCode(error: unknown): string {
  return typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string"
    ? error.code
    : "";
}

function failureMessage(locale: Locale, error: unknown): string {
  const copy = COPY[locale];
  switch (errorCode(error)) {
    case "MAINTENANCE_BUSY":
    case "RESTORE_WORK_PENDING":
      return copy.busy;
    case "BACKUP_PASSWORD_INVALID":
      return copy.password;
    case "BACKUP_DECRYPT_FAILED":
      return copy.decrypt;
    case "RESTORE_PREVIEW_EXPIRED":
      return copy.expired;
    case "AUTHENTICATION_REQUIRED":
    case "CSRF_FAILED":
      return copy.auth;
    case "BACKUP_FORMAT_INVALID":
    case "BACKUP_METADATA_INVALID":
    case "BACKUP_SQLITE_INVALID":
    case "BACKUP_TOO_LARGE":
    case "BACKUP_VERSION_UNSUPPORTED":
    case "BACKUP_AUTH_STATE_INVALID":
    case "BACKUP_FOREIGN_KEYS_INVALID":
    case "BACKUP_HEADER_INVALID":
    case "BACKUP_INTEGRITY_INVALID":
    case "BACKUP_MIGRATIONS_INVALID":
    case "BACKUP_SCHEMA_INVALID":
    case "BACKUP_SIZE_INVALID":
    case "BACKUP_SQLITE_CONFIGURATION_INVALID":
      return copy.invalid;
    case "RESTORE_RESOURCE_MISSING":
    case "BACKUP_PRIVATE_FILE_INVALID":
      return copy.resources;
    case "RESTORE_OWNER_MISMATCH":
      return copy.owner;
    case "RESTORE_SECRET_UNAVAILABLE":
      return copy.secrets;
    case "RESTORE_BUNDLE_UNAVAILABLE":
      return copy.website;
    case "RESTORE_APPEARANCE_UNAVAILABLE":
      return copy.appearance;
    case "RESTORE_PORTFOLIO_UNAVAILABLE":
      return copy.portfolio;
    case "RESTORE_EMBEDDING_INCOMPATIBLE":
      return copy.embedding;
    case "RESTORE_MODEL_UNAVAILABLE":
      return copy.model;
    case "RESTORE_RESOURCE_INVALID":
      return copy.resourceInvalid;
    case "BACKUP_VALIDATION_TIMEOUT":
      return copy.validationTimeout;
    case "MAINTENANCE_STOP_FAILED":
      return copy.stopFailed;
    case "RESTORE_FAILED":
      return copy.restoreFailed;
    case "SERVICE_NOT_READY":
    case "BACKUP_STORAGE_UNAVAILABLE":
    case "BACKUP_ENCRYPT_FAILED":
    case "BACKUP_WORKING_DIRECTORY_INVALID":
    case "BACKUP_WORKING_DIRECTORY_NOT_PRIVATE":
    case "BACKUP_WORKING_DIRECTORY_NOT_FRESH":
    case "MAINTENANCE_NOT_STARTED":
      return copy.unavailable;
    default:
      return copy.failure;
  }
}

function rejectedRestore(error: unknown): boolean {
  return [
    "MAINTENANCE_BUSY",
    "RESTORE_WORK_PENDING",
    "RESTORE_PREVIEW_EXPIRED",
    "SERVICE_NOT_READY",
    "AUTHENTICATION_REQUIRED",
    "CSRF_FAILED",
    "RESTORE_OWNER_MISMATCH",
    "RESTORE_SECRET_UNAVAILABLE",
    "RESTORE_BUNDLE_UNAVAILABLE",
    "RESTORE_APPEARANCE_UNAVAILABLE",
    "RESTORE_PORTFOLIO_UNAVAILABLE",
    "RESTORE_EMBEDDING_INCOMPATIBLE",
    "RESTORE_MODEL_UNAVAILABLE",
    "RESTORE_RESOURCE_INVALID",
  ].includes(errorCode(error));
}

/** Only the existing authenticated request boundary may communicate with the host. */
export function MaintenanceSetup({
  locale,
  sendRequest,
}: MaintenanceSetupProps) {
  const copy = COPY[locale];
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);
  const [restorePreview, setRestorePreview] =
    useState<MaintenanceRestorePreview | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [backupDownloadUrl, setBackupDownloadUrl] = useState<string | null>(
    null,
  );
  const lifetime = useRef(0);
  const mounted = useRef(false);
  const operation = useRef<AbortController | null>(null);
  const restorationAccepted = useRef(false);

  const current = useCallback(
    (controller: AbortController, generation: number) =>
      mounted.current &&
      lifetime.current === generation &&
      operation.current === controller &&
      !controller.signal.aborted,
    [],
  );

  const run = useCallback(
    async (
      action: (
        controller: AbortController,
        generation: number,
      ) => Promise<void>,
      restore = false,
    ) => {
      if (!mounted.current || operation.current || restorationAccepted.current)
        return;
      const controller = new AbortController();
      const generation = lifetime.current;
      operation.current = controller;
      setPending(true);
      setError("");
      setNotice("");
      try {
        await action(controller, generation);
      } catch (caught) {
        if (!current(controller, generation)) return;
        if (restore && !rejectedRestore(caught)) {
          // An uncertain write must never be submitted again by this mounted view.
          restorationAccepted.current = true;
          setRestorePreview(null);
          setStatus(null);
          setError(COPY[locale].uncertain);
        } else {
          if (errorCode(caught) === "RESTORE_PREVIEW_EXPIRED")
            setRestorePreview(null);
          setError(failureMessage(locale, caught));
        }
      } finally {
        if (current(controller, generation)) {
          operation.current = null;
          setPending(false);
        }
      }
    },
    [current, locale],
  );

  const refresh = useCallback(
    () =>
      run(async (controller, generation) => {
        const response = await sendRequest(`${ROOT}/status`, {
          signal: controller.signal,
        });
        const value = (await response.json()) as MaintenanceStatus;
        if (current(controller, generation)) setStatus(value);
      }),
    [run, sendRequest, current],
  );

  useEffect(() => {
    const generation = ++lifetime.current;
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
      lifetime.current = generation + 1;
      operation.current?.abort();
      operation.current = null;
    };
  }, [refresh]);

  async function backup(password: string) {
    await run(async (controller, generation) => {
      setBackupDownloadUrl(null);
      const response = await sendRequest(`${ROOT}/backup`, {
        method: "POST",
        body: JSON.stringify({ password }),
        signal: controller.signal,
      });
      if (
        response.headers.get("Content-Type")?.split(";")[0].trim() !==
        "application/octet-stream"
      )
        throw new Error();
      if (!current(controller, generation)) return;
      const location = response.headers.get("Content-Location");
      if (
        !location ||
        !/^\/api\/admin\/maintenance\/backup\/[0-9]{8}T[0-9]{6}-[0-9a-f]{16}$/.test(
          location,
        )
      )
        throw new Error();
      setBackupDownloadUrl(location);
      setNotice(copy.backup);
      try {
        const statusResponse = await sendRequest(`${ROOT}/status`, {
          signal: controller.signal,
        });
        const updated = (await statusResponse.json()) as MaintenanceStatus;
        if (current(controller, generation)) setStatus(updated);
      } catch {
        if (current(controller, generation))
          setNotice(`${copy.backup} ${copy.backupStatusUnavailable}`);
      }
    });
  }

  async function inspect(file: File, password: string) {
    setRestorePreview(null);
    await run(async (controller, generation) => {
      const body = new FormData();
      body.append("backup", file);
      body.append("password", password);
      const response = await sendRequest(`${ROOT}/restore/inspect`, {
        method: "POST",
        body,
        signal: controller.signal,
      });
      const value = (await response.json()) as MaintenanceRestorePreview;
      if (!current(controller, generation)) return;
      setRestorePreview(value);
      setNotice(copy.inspected);
    });
  }

  async function restore(previewId: string) {
    if (restorePreview?.preview_id !== previewId) return;
    await run(async (controller, generation) => {
      const response = await sendRequest(`${ROOT}/restore`, {
        method: "POST",
        body: JSON.stringify({ preview_id: previewId, confirmed: true }),
        signal: controller.signal,
      });
      const value = (await response.json()) as { status?: string };
      if (!current(controller, generation)) return;
      if (response.status !== 202 || value.status !== "restoring")
        throw new Error();
      restorationAccepted.current = true;
      setRestorePreview(null);
      setStatus(null);
      setNotice(copy.restoring);
    }, true);
  }

  async function cancel() {
    const previewId = restorePreview?.preview_id;
    if (!previewId) {
      setNotice(copy.cancelled);
      return;
    }
    await run(async (controller, generation) => {
      await sendRequest(`${ROOT}/restore/${encodeURIComponent(previewId)}`, {
        method: "DELETE",
        signal: controller.signal,
      });
      if (!current(controller, generation)) return;
      setRestorePreview(null);
      setNotice(copy.cancelled);
    });
  }

  async function updateStatus(
    path: "/pin" | "/gateway/stop",
    body: object,
    message: string,
  ) {
    await run(async (controller, generation) => {
      const response = await sendRequest(`${ROOT}${path}`, {
        method: "POST",
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      const value = (await response.json()) as MaintenanceStatus;
      if (!current(controller, generation)) return;
      setStatus(value);
      setNotice(message);
    });
  }

  return (
    <MaintenancePanel
      locale={locale}
      status={status}
      pending={pending || restorationAccepted.current}
      error={error}
      notice={notice}
      backupDownloadUrl={backupDownloadUrl}
      restorePreview={restorePreview}
      onRefresh={() => void refresh()}
      onBackup={(password) => void backup(password)}
      onInspect={(file, password) => void inspect(file, password)}
      onRestore={(previewId) => void restore(previewId)}
      onCancelRestore={() => void cancel()}
      onPinPrevious={(bundleId) => {
        if (bundleId !== status?.previous_bundle_id) return;
        void updateStatus(
          "/pin",
          { bundle_id: bundleId, confirmed: true },
          copy.pinned,
        );
      }}
      onStopGateway={() => void updateStatus("/gateway/stop", {}, copy.stopped)}
    />
  );
}
