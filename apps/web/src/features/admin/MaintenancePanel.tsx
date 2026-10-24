import { useEffect, useId, useRef, useState } from "react";
import type { Locale } from "../../i18n/messages";
import { CheckboxField } from "./CheckboxField";
import "../../p4-w4.css";

export interface MaintenanceStatus {
  active_bundle_id: string | null;
  previous_bundle_id: string | null;
  pinned_bundle_id: string | null;
  last_backup_at: string | null;
  local_ready: boolean;
  gateway_configured: boolean;
  externally_verified: boolean;
}

export interface MaintenanceRestorePreview {
  preview_id: string;
  created_at: string;
  application_version: string;
  schema_version: number;
  expires_at: string;
}

export interface MaintenancePanelProps {
  locale: Locale;
  status: MaintenanceStatus | null;
  pending: boolean;
  error?: string;
  notice?: string;
  backupDownloadUrl?: string | null;
  restorePreview: MaintenanceRestorePreview | null;
  onRefresh: () => void;
  onBackup: (password: string) => void;
  onInspect: (file: File, password: string) => void;
  onRestore: (previewId: string) => void;
  onCancelRestore: () => void;
  onPinPrevious: (bundleId: string) => void;
  onStopGateway: () => void;
}

const MAX_BACKUP_BYTES = 128 * 1024 * 1024 + 8192;
const COPY = {
  "zh-TW": {
    heading: "維護",
    statusGroup: "服務狀態",
    dataGroup: "網站資料",
    scope:
      "此加密備份只還原同一台主機的 SQLite 設定。請保留原資料目錄內的密鑰、網站資料與圖片；備份不含模型權重，也不是完整搬移工具。",
    refresh: "更新狀態",
    local: "本機服務",
    gateway: "訪客 gateway 設定",
    verified: "外網檢查",
    ready: "就緒",
    notReady: "尚未就緒",
    configured: "已設定",
    unconfigured: "尚未設定",
    checked: "已確認",
    unchecked: "尚未確認",
    unknown: "尚未取得狀態",
    active: "目前網站資料",
    previous: "保留的前一份網站資料",
    pinned: "固定使用的網站資料",
    none: "無",
    lastBackup: "上次備份時間",
    never: "尚無備份紀錄",
    backup: "建立備份",
    restore: "從備份還原",
    password: "備份密碼",
    confirmation: "再次輸入備份密碼",
    passwordHelp:
      "請使用 12–1024 個字元的密碼並妥善保存。密碼不會儲存在瀏覽器；遺失密碼就無法解開這份備份。",
    matchHelp: "兩次密碼須一致，才能建立備份。",
    create: "建立加密備份",
    download: "下載剛建立的加密備份",
    file: "選擇備份檔案",
    fileHelp:
      "選擇 .reponpc-backup 檔案，大小最多 128 MiB 加 8192 bytes 標頭。",
    fileInvalid:
      "檔案格式或大小不符合要求。請重新選擇 .reponpc-backup 備份檔案。",
    inspectHelp:
      "選擇符合格式的備份並輸入密碼，再按「檢查備份」。檢查不會更改目前設定。",
    inspect: "檢查備份",
    preview: "檢查結果與還原範圍",
    created: "備份建立時間",
    version: "應用程式版本",
    schema: "設定格式版本",
    expires: "檢查結果有效期限",
    expired: "檢查結果已過期或有效期限無法確認。請重新選擇檔案並檢查備份。",
    changed: "檔案或密碼已更改，請重新檢查備份。",
    autoBackup:
      "還原前會先以剛上傳備份的密碼加密備份目前設定，並保留在這台主機。還原後 gateway 會保持關閉。",
    restoreConsent: "我了解還原會取代目前的 SQLite 設定。",
    restoreHelp: "請先確認上方還原範圍，再勾選確認。",
    confirmRestore: "確認還原設定",
    cancel: "取消還原",
    relogin:
      "還原完成後，請重新開啟管理頁並登入；本機安裝版可重新開啟 RepoNPC。",
    pin: "回復保留網站資料",
    pinHelp: "此操作會固定使用保留的前一份網站資料；不會還原 SQLite 設定。",
    pinConsent: "我了解目前網站會改用上方保留的網站資料。",
    noPrevious: "目前沒有可回復的保留網站資料。",
    stop: "停止訪客 gateway",
    stopHelp:
      "停止 gateway 會停止本機訪客服務，不代表已關閉 Tailscale Funnel。",
    noGateway: "尚未設定訪客 gateway，無需停止。",
    updateHeading: "更新 RepoNPC",
    update:
      "執行較新版安裝程式以更新 RepoNPC，並保留原資料目錄。更新前請先建立備份。",
    funnelHeading: "關閉 Tailscale Funnel",
    funnel:
      "停止 gateway 後，請另外依 Tailscale 的官方流程關閉 Funnel。RepoNPC 不會操作 Tailscale，也不會要求其憑證。",
    funnelLink: "查看 Tailscale Funnel 官方說明（外部網站）",
    pending: "正在處理維護操作，請稍候。",
  },
  en: {
    heading: "Maintenance",
    statusGroup: "Service status",
    dataGroup: "Website data",
    scope:
      "This encrypted backup restores only SQLite settings on the same host. Keep the keys, website data, and images in the original data directory. It excludes model weights and is not a full migration tool.",
    refresh: "Refresh status",
    local: "Local service",
    gateway: "Visitor gateway configuration",
    verified: "External check",
    ready: "Ready",
    notReady: "Not ready yet",
    configured: "Configured",
    unconfigured: "Not configured",
    checked: "Confirmed",
    unchecked: "Not confirmed",
    unknown: "Status not available yet",
    active: "Current website data",
    previous: "Retained previous website data",
    pinned: "Pinned website data",
    none: "None",
    lastBackup: "Last backup time",
    never: "No backup recorded yet",
    backup: "Create a backup",
    restore: "Restore from a backup",
    password: "Backup password",
    confirmation: "Confirm the backup password",
    passwordHelp:
      "Use 12–1024 characters and keep this password safe. It is not stored in the browser. Without the password, you cannot decrypt this backup.",
    matchHelp: "Both passwords must match before you can create a backup.",
    create: "Create encrypted backup",
    download: "Download the encrypted backup",
    file: "Choose a backup file",
    fileHelp:
      "Choose a .reponpc-backup file, at most 128 MiB plus an 8192-byte header.",
    fileInvalid:
      "The file format or size is invalid. Select a .reponpc-backup file again.",
    inspectHelp:
      'Choose a valid backup and enter its password, then press "Inspect backup". Inspection does not change your settings.',
    inspect: "Inspect backup",
    preview: "Inspection result and restore scope",
    created: "Backup creation time",
    version: "Application version",
    schema: "Settings schema version",
    expires: "Inspection valid until",
    expired:
      "This inspection has expired or its expiry cannot be verified. Select the file and inspect it again.",
    changed: "The file or password changed. Inspect the backup again.",
    autoBackup:
      "Before restoring, your current settings are automatically backed up, encrypted with the uploaded backup's password, and retained on this host. The gateway stays off after restoration.",
    restoreConsent:
      "I understand that restoring replaces the current SQLite settings.",
    restoreHelp:
      "Review the restore scope above, then check the confirmation box.",
    confirmRestore: "Confirm settings restore",
    cancel: "Cancel restore",
    relogin:
      "After restoring, reopen the admin page and sign in. For the local installation, reopen RepoNPC.",
    pin: "Restore retained website data",
    pinHelp:
      "This pins the retained previous website data. It does not restore SQLite settings.",
    pinConsent:
      "I understand that the website will use the retained data shown above.",
    noPrevious: "There is no retained previous website data to restore.",
    stop: "Stop visitor gateway",
    stopHelp:
      "Stopping the gateway stops the local visitor service. It does not turn off Tailscale Funnel.",
    noGateway:
      "The visitor gateway is not configured, so it does not need stopping.",
    updateHeading: "Update RepoNPC",
    update:
      "Run the newer installer to update RepoNPC and keep the original data directory. Create a backup before updating.",
    funnelHeading: "Turn off Tailscale Funnel",
    funnel:
      "After stopping the gateway, separately follow Tailscale's official steps to turn off Funnel. RepoNPC does not operate Tailscale or request its credentials.",
    funnelLink:
      "Read the official Tailscale Funnel documentation (external site)",
    pending: "A maintenance operation is in progress. Please wait.",
  },
};

function validPassword(password: string): boolean {
  const length = Array.from(password).length;
  return length >= 12 && length <= 1024;
}

function validFile(file: File | null): file is File {
  return (
    !!file &&
    file.name.toLowerCase().endsWith(".reponpc-backup") &&
    file.size > 0 &&
    file.size <= MAX_BACKUP_BYTES
  );
}

/** Remount ephemeral form state when the locale changes; never persist secrets. */
export function MaintenancePanel(props: MaintenancePanelProps) {
  return <MaintenanceContent key={props.locale} {...props} />;
}

function MaintenanceContent({
  locale,
  status,
  pending,
  error,
  notice,
  backupDownloadUrl,
  restorePreview,
  onRefresh,
  onBackup,
  onInspect,
  onRestore,
  onCancelRestore,
  onPinPrevious,
  onStopGateway,
}: MaintenancePanelProps) {
  const copy = COPY[locale];
  const id = useId();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [restorePassword, setRestorePassword] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [confirmedPreviewId, setConfirmedPreviewId] = useState<string | null>(
    null,
  );
  const [confirmedPreviousId, setConfirmedPreviousId] = useState<string | null>(
    null,
  );
  const [expiredPreviewId, setExpiredPreviewId] = useState<string | null>(null);
  const [modifiedPreviewId, setModifiedPreviewId] = useState<string | null>(
    null,
  );
  const previewId = restorePreview?.preview_id;
  const expiresAt = restorePreview?.expires_at;
  const expiry = Date.parse(expiresAt ?? "");
  const expired =
    !Number.isFinite(expiry) ||
    expiry <= Date.now() ||
    expiredPreviewId === previewId;
  const backupAllowed =
    validPassword(password) && password === confirmation && !pending;
  const inspectAllowed =
    validFile(file) && validPassword(restorePassword) && !pending;
  const restoreAllowed =
    !!restorePreview &&
    confirmedPreviewId === previewId &&
    modifiedPreviewId !== previewId &&
    !expired &&
    !pending;
  const previous = status?.previous_bundle_id;
  const pinAllowed = !!previous && confirmedPreviousId === previous && !pending;

  useEffect(() => {
    if (!previewId || !expiresAt) return;
    const expires = Date.parse(expiresAt);
    if (!Number.isFinite(expires)) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const checkExpiry = () => {
      const remaining = expires - Date.now();
      if (remaining <= 0) setExpiredPreviewId(previewId);
      else
        timer = setTimeout(checkExpiry, Math.min(remaining + 1, 2_147_483_647));
    };
    checkExpiry();
    return () => clearTimeout(timer);
  }, [previewId, expiresAt]);

  const clearRestore = () => {
    setRestorePassword("");
    setFile(null);
    setConfirmedPreviewId(null);
    if (fileInput.current) fileInput.current.value = "";
  };
  const date = (value: string | null | undefined) => {
    const parsed = Date.parse(value ?? "");
    return Number.isFinite(parsed) ? (
      <time dateTime={value ?? undefined}>
        {new Intl.DateTimeFormat(locale, {
          dateStyle: "medium",
          timeStyle: "short",
        }).format(parsed)}
      </time>
    ) : (
      copy.unknown
    );
  };

  return (
    <section
      className="admin-maintenance px-panel px-panel--raised"
      lang={locale}
      aria-labelledby="admin-maintenance-heading"
      aria-busy={pending}
    >
      <h2 id="admin-maintenance-heading">{copy.heading}</h2>
      <details className="admin-maintenance__scope px-info">
        <summary>ⓘ {copy.preview}</summary>
        <p id={`${id}-scope`}>{copy.scope}</p>
      </details>
      <button
        className="px-button px-button--secondary"
        type="button"
        disabled={pending}
        onClick={onRefresh}
      >
        {copy.refresh}
      </button>
      <section
        aria-labelledby={`${id}-status-heading`}
        className="admin-maintenance__group"
      >
        <h3
          className="admin-maintenance__group-title"
          id={`${id}-status-heading`}
        >
          {copy.statusGroup}
        </h3>
        <dl className="admin-maintenance__status">
          <dt>{copy.local}</dt>
          <dd className="px-badge">
            {status
              ? status.local_ready
                ? copy.ready
                : copy.notReady
              : copy.unknown}
          </dd>
          <dt>{copy.gateway}</dt>
          <dd className="px-badge">
            {status
              ? status.gateway_configured
                ? copy.configured
                : copy.unconfigured
              : copy.unknown}
          </dd>
          <dt>{copy.verified}</dt>
          <dd className="px-badge">
            {status
              ? status.externally_verified
                ? copy.checked
                : copy.unchecked
              : copy.unknown}
          </dd>
        </dl>
      </section>
      <section
        aria-labelledby={`${id}-data-heading`}
        className="admin-maintenance__group"
      >
        <h3
          className="admin-maintenance__group-title"
          id={`${id}-data-heading`}
        >
          {copy.dataGroup}
        </h3>
        <dl className="admin-maintenance__data">
          <dt>{copy.active}</dt>
          <dd>
            {status ? (status.active_bundle_id ?? copy.none) : copy.unknown}
          </dd>
          <dt>{copy.previous}</dt>
          <dd>{status ? (previous ?? copy.none) : copy.unknown}</dd>
          <dt>{copy.pinned}</dt>
          <dd>
            {status ? (status.pinned_bundle_id ?? copy.none) : copy.unknown}
          </dd>
          <dt>{copy.lastBackup}</dt>
          <dd>
            {status
              ? status.last_backup_at
                ? date(status.last_backup_at)
                : copy.never
              : copy.unknown}
          </dd>
        </dl>
      </section>
      {pending && <p role="status">{copy.pending}</p>}
      {notice && (
        <p role="status" aria-live="polite">
          {notice}
        </p>
      )}
      {backupDownloadUrl && (
        <p>
          <a href={backupDownloadUrl} download="reponpc-backup.reponpc-backup">
            {copy.download}
          </a>
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      <details className="admin-maintenance__section">
        <summary>{copy.backup}</summary>
        <form
          aria-label={copy.backup}
          aria-describedby={`${id}-scope`}
          onSubmit={(event) => {
            event.preventDefault();
            if (!backupAllowed) return;
            try {
              onBackup(password);
            } finally {
              setPassword("");
              setConfirmation("");
            }
          }}
        >
          <p id={`${id}-password-help`}>{copy.passwordHelp}</p>
          <label htmlFor={`${id}-backup-password`}>{copy.password}</label>
          <input
            className="px-field"
            id={`${id}-backup-password`}
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={1024}
            required
            disabled={pending}
            value={password}
            aria-describedby={`${id}-password-help`}
            onChange={(event) => setPassword(event.target.value)}
          />
          <label htmlFor={`${id}-backup-confirmation`}>
            {copy.confirmation}
          </label>
          <input
            className="px-field"
            id={`${id}-backup-confirmation`}
            type="password"
            autoComplete="new-password"
            minLength={12}
            maxLength={1024}
            required
            disabled={pending}
            value={confirmation}
            aria-describedby={`${id}-password-help ${id}-match-help`}
            onChange={(event) => setConfirmation(event.target.value)}
          />
          <p id={`${id}-match-help`}>{copy.matchHelp}</p>
          <button
            className="px-button px-button--primary"
            type="submit"
            disabled={!backupAllowed}
            aria-describedby={`${id}-password-help ${id}-match-help`}
          >
            {copy.create}
          </button>
        </form>
      </details>
      <details
        className="admin-maintenance__section"
        open={!!restorePreview || undefined}
      >
        <summary>{copy.restore}</summary>
        <form
          aria-label={copy.inspect}
          aria-describedby={`${id}-scope ${id}-inspect-help`}
          onSubmit={(event) => {
            event.preventDefault();
            if (!inspectAllowed || !file) return;
            try {
              onInspect(file, restorePassword);
            } finally {
              clearRestore();
            }
          }}
        >
          <label htmlFor={`${id}-restore-file`}>{copy.file}</label>
          <input
            className="px-field"
            id={`${id}-restore-file`}
            ref={fileInput}
            type="file"
            accept=".reponpc-backup"
            required
            disabled={pending}
            aria-describedby={`${id}-file-help ${id}-inspect-help`}
            aria-invalid={!!file && !validFile(file)}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setConfirmedPreviewId(null);
              if (previewId) setModifiedPreviewId(previewId);
            }}
          />
          <p id={`${id}-file-help`}>{copy.fileHelp}</p>
          {!!file && !validFile(file) && <p role="alert">{copy.fileInvalid}</p>}
          <label htmlFor={`${id}-restore-password`}>{copy.password}</label>
          <input
            className="px-field"
            id={`${id}-restore-password`}
            type="password"
            autoComplete="off"
            minLength={12}
            maxLength={1024}
            required
            disabled={pending}
            value={restorePassword}
            aria-describedby={`${id}-password-help ${id}-inspect-help`}
            onChange={(event) => {
              setRestorePassword(event.target.value);
              setConfirmedPreviewId(null);
              if (previewId) setModifiedPreviewId(previewId);
            }}
          />
          <p id={`${id}-inspect-help`}>{copy.inspectHelp}</p>
          <button
            className="px-button px-button--secondary"
            type="submit"
            disabled={!inspectAllowed}
            aria-describedby={`${id}-inspect-help`}
          >
            {copy.inspect}
          </button>
        </form>
        {restorePreview && (
          <div aria-labelledby={`${id}-preview-heading`}>
            <h3 id={`${id}-preview-heading`}>{copy.preview}</h3>
            <dl>
              <dt>{copy.created}</dt>
              <dd>{date(restorePreview.created_at)}</dd>
              <dt>{copy.version}</dt>
              <dd>{restorePreview.application_version}</dd>
              <dt>{copy.schema}</dt>
              <dd>{restorePreview.schema_version}</dd>
              <dt>{copy.expires}</dt>
              <dd>{date(restorePreview.expires_at)}</dd>
            </dl>
            <p>{copy.scope}</p>
            <p id={`${id}-auto-backup`}>{copy.autoBackup}</p>
            <p id={`${id}-restore-help`}>
              {expired
                ? copy.expired
                : modifiedPreviewId === previewId
                  ? copy.changed
                  : copy.restoreHelp}
            </p>
            <CheckboxField
              checked={confirmedPreviewId === previewId}
              disabled={pending || expired || modifiedPreviewId === previewId}
              aria-describedby={`${id}-scope ${id}-auto-backup ${id}-restore-help`}
              onChange={(event) =>
                setConfirmedPreviewId(
                  event.target.checked ? restorePreview.preview_id : null,
                )
              }
            >
              {copy.restoreConsent}
            </CheckboxField>
            <button
              className="px-button px-button--danger"
              type="button"
              disabled={!restoreAllowed}
              aria-describedby={`${id}-restore-help ${id}-auto-backup`}
              onClick={() => {
                if (
                  !restoreAllowed ||
                  Date.parse(restorePreview.expires_at) <= Date.now()
                )
                  return;
                try {
                  onRestore(restorePreview.preview_id);
                } finally {
                  clearRestore();
                }
              }}
            >
              {copy.confirmRestore}
            </button>
            <p>{copy.relogin}</p>
          </div>
        )}
        <button
          className="px-button px-button--secondary"
          type="button"
          disabled={pending}
          onClick={() => {
            clearRestore();
            setPassword("");
            setConfirmation("");
            onCancelRestore();
          }}
        >
          {copy.cancel}
        </button>
      </details>
      <h3>{copy.pin}</h3>
      <p id={`${id}-pin-help`}>
        {previous ? copy.pinHelp : status ? copy.noPrevious : copy.unknown}
      </p>
      <CheckboxField
        checked={!!previous && confirmedPreviousId === previous}
        disabled={pending || !previous}
        aria-describedby={`${id}-pin-help`}
        onChange={(event) =>
          setConfirmedPreviousId(
            event.target.checked ? (previous ?? null) : null,
          )
        }
      >
        {copy.pinConsent}
      </CheckboxField>
      <button
        className="px-button px-button--danger"
        type="button"
        disabled={!pinAllowed}
        aria-describedby={`${id}-pin-help`}
        onClick={() => {
          if (!pinAllowed || !previous) return;
          try {
            onPinPrevious(previous);
          } finally {
            setConfirmedPreviousId(null);
          }
        }}
      >
        {copy.pin}
      </button>
      <h3>{copy.stop}</h3>
      <p id={`${id}-stop-help`}>{copy.stopHelp}</p>
      {!status?.gateway_configured && (
        <p id={`${id}-gateway-unavailable`}>
          {status ? copy.noGateway : copy.unknown}
        </p>
      )}
      <button
        className="px-button px-button--secondary"
        type="button"
        disabled={pending || !status?.gateway_configured}
        aria-describedby={`${id}-stop-help${!status?.gateway_configured ? ` ${id}-gateway-unavailable` : ""}`}
        onClick={onStopGateway}
      >
        {copy.stop}
      </button>
      <h3>{copy.updateHeading}</h3>
      <p>{copy.update}</p>
      <h3>{copy.funnelHeading}</h3>
      <p>{copy.funnel}</p>
      <a
        href="https://tailscale.com/docs/features/tailscale-funnel"
        target="_blank"
        rel="noopener noreferrer"
      >
        {copy.funnelLink}
      </a>
    </section>
  );
}
