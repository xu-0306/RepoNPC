import { useId, useState } from "react";
import type { Locale } from "../../i18n/messages";
import { CheckboxField } from "./CheckboxField";

export interface BuiltinModelInfo {
  model_id: string;
  display_name: string;
  total_bytes: number;
  license: string;
  source_url: string;
  profile_id: string | null;
}

export interface BuiltinModelOperation {
  operation_id: string;
  profile_id: string;
  model_id: string;
  status: string;
  completed: number | null;
  total: number | null;
  error_code: string | null;
}

export interface BuiltinModelPanelProps {
  locale: Locale;
  info: BuiltinModelInfo | null;
  operation: BuiltinModelOperation | null;
  pending: boolean;
  error: string;
  onDownload: () => void;
  onCancel: () => void;
  onRefresh: () => void;
  onExternal: () => void;
  onLater: () => void;
}

const COPY = {
  "zh-TW": {
    heading: "準備本機內容查找模型",
    introduction: "選擇下載內建模型、使用外部模型服務，或稍後設定。",
    download: "下載內建模型",
    external: "使用外部模型服務",
    later: "稍後設定，繼續手動編輯",
    size: "下載大小",
    license: "授權",
    source: "查看模型來源與授權條款",
    unavailable: "尚未取得下載資訊。請更新狀態後再確認下載。",
    consent: "我同意從上述來源下載模型至這台主機，並已確認授權條款與下載大小。",
    reindex:
      "更換內容查找模型需要重新建立全部索引。下載完成後仍須測試模型並確認分析角色。",
    confirm: "確認並下載",
    resume: "同意並續傳",
    retry: "同意並重試",
    refresh: "更新狀態",
    cancel: "取消下載",
    progress: "模型下載進度",
    unknown: "等待下載進度資訊。",
    pending: "正在處理操作，請稍候。",
    deferred:
      "稍後設定時，模型尚未就緒會阻擋自動建置。你仍可繼續手動編輯內容。",
    deferredNotice: "已選擇稍後設定。你可以繼續手動編輯內容。",
    error: "操作未完成。請更新狀態，確認網路與磁碟空間後重試。",
    complete:
      "模型下載完成。接著請按「測試模型」，並確認它的分析角色；下載本身不會啟用公開回答服務。",
    states: {
      queued: "下載已排入佇列。",
      running: "正在下載並驗證模型檔案。",
      cancelled: "下載已取消。確認同意後可以續傳。",
      failed: "下載未完成。請確認網路與磁碟空間，再確認同意並重試。",
    },
  },
  en: {
    heading: "Prepare a local content finder model",
    introduction:
      "Download the built-in model, use an external model service, or set it up later.",
    download: "Download the built-in model",
    external: "Use an external model service",
    later: "Set up later and continue manual editing",
    size: "Download size",
    license: "License",
    source: "View the model source and license terms",
    unavailable:
      "Download information is unavailable. Refresh the status before confirming a download.",
    consent:
      "I agree to download the model from this source onto this host and have checked its license terms and download size.",
    reindex:
      "Changing the content finder model requires a full reindex. After downloading, test the model and confirm its analysis role.",
    confirm: "Confirm and download",
    resume: "Agree and resume",
    retry: "Agree and retry",
    refresh: "Refresh status",
    cancel: "Cancel download",
    progress: "Model download progress",
    unknown: "Waiting for download progress information.",
    pending: "An operation is in progress. Please wait.",
    deferred:
      "If you defer setup, RepoNPC blocks automatic builds until models are ready. You can continue editing content manually.",
    deferredNotice:
      "You chose to set up later. You can continue editing content manually.",
    error:
      "The operation could not be completed. Refresh the status, check the network and disk space, then retry.",
    complete:
      'The model download is complete. Next, press "Test model" and confirm its analysis role. Downloading alone does not activate public answers.',
    states: {
      queued: "The download is queued.",
      running: "Downloading and verifying the model files.",
      cancelled: "The download was cancelled. Confirm your consent to resume.",
      failed:
        "The download did not finish. Check the network and disk space, then confirm your consent to retry.",
    },
  },
};

function validBytes(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value >= 0;
}

function downloadSize(bytes: number, locale: Locale): string {
  const exact = new Intl.NumberFormat(locale).format(bytes);
  const gb = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 3,
  }).format(bytes / 1_000_000_000);
  return `${gb} GB (${exact} bytes)`;
}

function publicSource(source: string): string | undefined {
  try {
    const url = new URL(source);
    if (url.protocol === "https:" && !url.username && !url.password)
      return source;
  } catch {
    // An unavailable source cannot be used to give informed download consent.
  }
  return undefined;
}

export function BuiltinModelPanel({
  locale,
  info,
  operation,
  pending,
  error,
  onDownload,
  onCancel,
  onRefresh,
  onExternal,
  onLater,
}: BuiltinModelPanelProps) {
  const copy = COPY[locale];
  const id = useId();
  const [consentedModelId, setConsentedModelId] = useState<string | null>(null);
  const [deferred, setDeferred] = useState(false);
  const source = info ? publicSource(info.source_url) : undefined;
  const available = !!info && validBytes(info.total_bytes) && !!source;
  const consented = !!info && consentedModelId === info.model_id;
  const status = operation?.status;
  const active = status === "queued" || status === "running";
  const complete = status === "succeeded";
  const retryable = status === "cancelled" || status === "failed";
  const progress =
    operation &&
    validBytes(operation.completed) &&
    validBytes(operation.total) &&
    operation.total > 0
      ? { completed: operation.completed, total: operation.total }
      : null;
  const stateText = complete
    ? copy.complete
    : status && Object.hasOwn(copy.states, status)
      ? copy.states[status as keyof typeof copy.states]
      : copy.pending;

  return (
    <section className="admin-surface" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{copy.heading}</h2>
      <p>{copy.introduction}</p>
      {info && (
        <>
          <h3>{info.display_name}</h3>
          <dl>
            <dt>{copy.size}</dt>
            <dd>
              {validBytes(info.total_bytes)
                ? downloadSize(info.total_bytes, locale)
                : copy.unavailable}
            </dd>
            <dt>{copy.license}</dt>
            <dd>{info.license}</dd>
          </dl>
          {source && <a href={source}>{copy.source}</a>}
        </>
      )}
      <details open={retryable || undefined}>
        <summary>{copy.download}</summary>
        <p id={`${id}-reindex`}>{copy.reindex}</p>
        {!available && <p id={`${id}-unavailable`}>{copy.unavailable}</p>}
        <CheckboxField
          checked={consented}
          disabled={pending || active || complete || !available}
          aria-describedby={`${id}-reindex`}
          onChange={(event) =>
            setConsentedModelId(
              event.target.checked ? (info?.model_id ?? null) : null,
            )
          }
        >
          <span id={`${id}-consent`}>{copy.consent}</span>
        </CheckboxField>
        <button
          type="button"
          disabled={!available || !consented || pending || active || complete}
          aria-describedby={[
            `${id}-consent`,
            `${id}-reindex`,
            ...(!available ? [`${id}-unavailable`] : []),
            ...(operation ? [`${id}-status`] : []),
          ].join(" ")}
          onClick={() => {
            if (available && consented && !pending && !active && !complete) {
              setDeferred(false);
              onDownload();
            }
          }}
        >
          {status === "cancelled"
            ? copy.resume
            : status === "failed"
              ? copy.retry
              : copy.confirm}
        </button>
      </details>
      <div className="admin-workspace__actions">
        <button type="button" onClick={onExternal}>
          {copy.external}
        </button>
        <button
          type="button"
          aria-describedby={`${id}-deferred`}
          onClick={() => {
            setDeferred(true);
            onLater();
          }}
        >
          {copy.later}
        </button>
        <button type="button" disabled={pending} onClick={onRefresh}>
          {copy.refresh}
        </button>
      </div>
      <p id={`${id}-deferred`}>{copy.deferred}</p>
      {deferred && <p role="status">{copy.deferredNotice}</p>}
      {operation && (
        <p id={`${id}-status`} role="status" aria-live="polite">
          {stateText}
        </p>
      )}
      {active && (
        <>
          <label htmlFor={`${id}-progress`}>{copy.progress}</label>
          <progress
            id={`${id}-progress`}
            aria-describedby={`${id}-status`}
            max={progress?.total}
            value={
              progress
                ? Math.min(progress.completed, progress.total)
                : undefined
            }
          />
          <p>
            {progress
              ? `${downloadSize(progress.completed, locale)} / ${downloadSize(progress.total, locale)}`
              : copy.unknown}
          </p>
          <button
            type="button"
            disabled={pending}
            aria-describedby={`${id}-status`}
            onClick={onCancel}
          >
            {copy.cancel}
          </button>
        </>
      )}
      {pending && !operation && <p role="status">{copy.pending}</p>}
      {error && <p role="alert">{copy.error}</p>}
    </section>
  );
}
