import type { Locale } from "../../i18n/messages";
import { modelProbeError } from "./modelProbeError";

type Message = readonly [string, string];

// Probe-result codes reuse the stored-probe wording.
const PROBE_RESULT_CODES = new Set([
  "EMBEDDING_PROBE_DIMENSION_MISMATCH",
  "EMBEDDING_PROBE_INVALID_VECTOR",
  "EMBEDDING_PROBE_NOT_NORMALIZED",
  "EMBEDDING_PROFILE_IDENTITY_MISMATCH",
  "PROVIDER_AUTHENTICATION",
  "PROVIDER_RATE_LIMIT",
  "PROVIDER_TIMEOUT",
  "PROVIDER_UNAVAILABLE",
  "PROVIDER_INVALID_RESPONSE",
  "PROVIDER_CONTEXT_OVERFLOW",
]);

const PROFILE_IN_USE: Message = [
  "模型正在供公開網站使用或重建索引，無法刪除。請重新整理狀態，等待索引完成，並先切換公開模型。",
  "The model is active on the public site or rebuilding the index and cannot be deleted. Refresh its status, wait for indexing to finish, and switch the public model first.",
];

const MESSAGES: Record<string, Message> = {
  EMBEDDING_PROFILE_ACTIVE_REQUIRED: PROFILE_IN_USE,
  EMBEDDING_REINDEX_ACTIVE: PROFILE_IN_USE,
  EMBEDDING_REINDEX_REQUIRED: [
    "這個資料查找模型尚未通過測試，或與目前公開資料不相容；已保留上一個可用模型。",
    "This content finder has not passed testing or is incompatible with the current public data. The last known-good model was preserved.",
  ],
  EMBEDDING_CONNECTION_REQUIRED: [
    "這個服務連線尚未由伺服器設定；RepoNPC 不會自動改用其他服務。",
    "This service connection is not configured by the server. RepoNPC will not switch services automatically.",
  ],
  EMBEDDING_PROBE_REQUIRED: ["請先測試這個模型。", "Test this model first."],
  EMBEDDING_PROBE_FAILED: [
    "模型測試未通過，請重新測試。",
    "The model test failed; test it again.",
  ],
  EMBEDDING_MODEL_OPERATION_ACTIVE: [
    "模型下載正在進行，請等待完成或取消後再試。",
    "A model download is in progress; wait for it to finish or cancel it before retrying.",
  ],
  EMBEDDING_MODEL_OPERATION_FAILED: [
    "模型安裝或刪除失敗，請查看 Ollama 狀態後重試。",
    "Model installation or deletion failed; check Ollama's status and retry.",
  ],
  EMBEDDING_PROFILE_ACTIVE_IMMUTABLE: [
    "公開網站正在使用此模型，請先切換公開模型再修改。",
    "The public site uses this model; switch the public model before editing it.",
  ],
  EMBEDDING_REINDEX_STALE: [
    "模型設定已變更，請重新整理後再試。",
    "The model settings changed; refresh and retry.",
  ],
  NOT_FOUND: [
    "找不到指定的模型或操作，請重新整理後再試。",
    "The selected model or operation was not found; refresh and retry.",
  ],
  SERVICE_NOT_READY: [
    "模型管理服務尚未就緒，請稍後重試。",
    "The model management service is not ready; retry shortly.",
  ],
  VALIDATION_ERROR: [
    "模型設定無效，請檢查所選服務與模型名稱。",
    "The model settings are invalid; check the selected service and model name.",
  ],
  EMBEDDING_REINDEX_CANCELLED: [
    "索引重建已取消，可重新開始。",
    "Index rebuilding was cancelled; you can start it again.",
  ],
  EMBEDDING_REINDEX_TIMEOUT: [
    "索引重建逾時，請重試。",
    "Index rebuilding timed out; retry.",
  ],
  EMBEDDING_REINDEX_FAILED: [
    "索引重建失敗，請檢查來源與模型設定後重試。",
    "Index rebuilding failed; check the source and model settings, then retry.",
  ],
  EMBEDDING_REINDEX_INTERRUPTED: [
    "索引重建已中斷，請重新開始。",
    "Index rebuilding was interrupted; start it again.",
  ],
  EMBEDDING_ACTIVATION_FAILED: [
    "索引啟用失敗，請重新建立後再試。",
    "Index activation failed; rebuild it and retry.",
  ],
  EMBEDDING_BUNDLE_UNAVAILABLE: [
    "找不到可用的索引，請重新建立。",
    "No usable index was found; rebuild it.",
  ],
  GITHUB_RATE_LIMITED: [
    "GitHub 目前限制新的請求，請稍後重試。",
    "GitHub is currently limiting new requests; retry later.",
  ],
  GITHUB_ERROR: [
    "無法從 GitHub 取得此 repository，請稍後重試。",
    "RepoNPC could not retrieve this repository from GitHub; retry later.",
  ],
  GITHUB_TIMEOUT: [
    "GitHub 在設定的無活動期限內沒有傳回資料，請重試。",
    "GitHub returned no data within the configured inactivity timeout; retry.",
  ],
  ARCHIVED_NOT_ALLOWED: [
    "此 repository 已封存，請改選未封存的 repository。",
    "This repository is archived; select one that is not archived.",
  ],
  ARCHIVE_TOO_LARGE: [
    "Repository 封存檔超過安全上限，請改選較小的 repository。",
    "The repository archive exceeded the safety limit; choose a smaller repository.",
  ],
  ARCHIVE_INVALID: [
    "GitHub 回傳的 repository 封存檔無法解析，請重試。",
    "The repository archive returned by GitHub could not be parsed; retry.",
  ],
  ARCHIVE_UNSAFE: [
    "Repository 封存檔包含不安全的路徑或項目，請修正來源後重試。",
    "The repository archive contains unsafe paths or entries; correct the source and retry.",
  ],
};

const FALLBACK: Message = [
  "資料查找模型操作未完成。請確認已選服務與模型名稱，並檢查網路及登入狀態後重試。",
  "The content finder operation could not finish. Check the selected service, model name, network, and sign-in before retrying.",
];

export function embeddingProfileErrorMessage(
  locale: Locale,
  error: unknown,
): string {
  const code = error instanceof Error ? error.message : "REQUEST_FAILED";
  if (PROBE_RESULT_CODES.has(code) || /^PROVIDER_HTTP_[1-5]\d{2}$/.test(code)) {
    return modelProbeError(locale, code);
  }
  const message = Object.hasOwn(MESSAGES, code) ? MESSAGES[code] : FALLBACK;
  return message[locale === "zh-TW" ? 0 : 1];
}
