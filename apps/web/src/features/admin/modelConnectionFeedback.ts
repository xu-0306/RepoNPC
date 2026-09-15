import type { Locale } from "../../i18n/messages";

export interface ModelConnectionFailureDetails {
  code: string;
  requestId?: string;
}

const MESSAGES: Record<string, [string, string]> = {
  CREDENTIAL_REPLACE_REQUIRED: [
    "無法更新服務：連線方式、協定、主機或連接埠已改變，因此不能把舊金鑰送到新的 origin。原設定仍保留；請重新填入新服務的 API key，或選擇移除金鑰後再儲存。",
    "The service was not updated because its connection type, protocol, host, or port changed, so the saved key cannot be sent to the new origin. The existing setting is preserved. Enter the new service key or choose to remove the key, then save again.",
  ],
  HOST_CONNECTION_REPLACEMENT_REQUIRED: [
    "無法更新環境預設連線：原始網址不會顯示，也不能留空沿用。原設定仍保留；請輸入完整的新服務網址後再儲存。",
    "The environment connection was not updated because its original URL is hidden and cannot be retained from a blank field. The existing setting is preserved. Enter the complete replacement URL and save again.",
  ],
  MODEL_CONNECTION_IN_USE: [
    "無法刪除服務：仍有模型使用它，原設定未變更。請先讓那些模型改用其他服務，或刪除不需要的模型設定。",
    "The service was not deleted because models still use it; no settings changed. Move those models to another service or delete the model settings you no longer need.",
  ],
  MODEL_SECRET_STORAGE_UNAVAILABLE: [
    "無法更新服務：伺服器讀不到受保護的服務設定，原設定不會被覆寫。請檢查模型秘密金鑰檔、資料目錄與存取權限，再重試。",
    "The service was not updated because the server could not read its protected settings. Existing settings were not overwritten. Check the model-secret key file, data directory, and permissions, then retry.",
  ],
  INVALID_PROVIDER_URL: [
    "無法儲存服務：網址格式不正確，原設定未變更。請貼上包含 http:// 或 https:// 的完整 API 位址，且不要包含帳密、查詢參數或 # 片段。",
    "The service was not saved because the URL is invalid; existing settings are unchanged. Enter a complete http:// or https:// API address without credentials, query parameters, or a # fragment.",
  ],
  INSECURE_PROVIDER_URL: [
    "無法儲存服務：非本機網路服務必須使用 https，原設定未變更。請改用服務商提供的 https API 位址。",
    "The service was not saved because non-local network services require HTTPS; existing settings are unchanged. Use the provider's HTTPS API address.",
  ],
  PROVIDER_NETWORK_BLOCKED: [
    "無法儲存服務：網址解析到不允許的網路位址，原設定未變更。請確認主機名稱與部署網路設定，不要使用 link-local、multicast 或 metadata 位址。",
    "The service was not saved because its URL resolves to a blocked network address; existing settings are unchanged. Check the host and deployment network configuration, and do not use link-local, multicast, or metadata addresses.",
  ],
  MODEL_CONNECTION_SAVE_FAILED: [
    "服務未能寫入伺服器，但原設定仍保留。請檢查 runtime 資料庫與磁碟權限後重試；若持續失敗，可用下方診斷代碼查詢伺服器紀錄。",
    "The server could not write the service, but the existing setting is preserved. Check the runtime database and disk permissions, then retry. If it continues, use the diagnostic ID below to find the server log entry.",
  ],
  MODEL_CONNECTION_DELETE_FAILED: [
    "伺服器無法刪除服務，但原設定仍保留。請檢查 runtime 資料庫與磁碟權限後重試；若持續失敗，可用診斷代碼查詢伺服器紀錄。",
    "The server could not delete the service, but the existing setting is preserved. Check the runtime database and disk permissions, then retry. If it continues, use the diagnostic ID to find the server log entry.",
  ],
  PROVIDER_NETWORK_UNAVAILABLE: [
    "無法儲存服務：伺服器無法解析或連到網址主機，原設定未變更。請檢查主機名稱、DNS 與部署網路後再試。",
    "The service was not saved because the server could not resolve or reach the URL host; existing settings are unchanged. Check the hostname, DNS, and deployment network, then retry.",
  ],
  NOT_FOUND: [
    "無法變更服務：這筆設定已不存在，其他設定未變更。請重新整理服務清單後，選擇目前存在的服務再操作。",
    "The service could not be changed because it no longer exists; other settings are unchanged. Refresh the service list and retry with a current service.",
  ],
  SERVICE_NOT_READY: [
    "無法變更服務：伺服器的模型設定功能尚未就緒，原設定未變更。請檢查後端啟動設定與 runtime 資料目錄，重新啟動服務後再試。",
    "The service could not be changed because server-side model settings are not ready; existing settings are unchanged. Check backend startup configuration and the runtime data directory, restart the service, and retry.",
  ],
  AUTHENTICATION_REQUIRED: [
    "服務沒有更新：管理登入已失效，原設定未變更。請重新載入頁面並恢復或重新登入，再重做這次操作。",
    "The service was not updated because the admin session expired; existing settings are unchanged. Reload the page, resume or sign in again, and repeat the operation.",
  ],
  CSRF_FAILED: [
    "服務沒有更新：安全驗證已失效，原設定未變更。請重新載入頁面取得新的工作階段資料後再試。",
    "The service was not updated because the security check expired; existing settings are unchanged. Reload the page to obtain fresh session data, then retry.",
  ],
  REQUEST_FAILED: [
    "瀏覽器沒有收到可確認的儲存結果，因此目前無法判定更新是否完成。請先按「重新整理」核對服務清單，再決定是否重試；剛輸入的金鑰不會保留在表單中。",
    "The browser did not receive a confirmable save result, so it is not yet known whether the update completed. Refresh the service list before deciding whether to retry. Any key you entered is not retained in the form.",
  ],
  VALIDATION_ERROR: [
    "服務未儲存，原設定未變更。請檢查服務名稱、連線方式與完整網址後再試。",
    "The service was not saved and existing settings are unchanged. Check the service name, connection type, and complete URL, then retry.",
  ],
};

export function modelConnectionFailureMessage(
  locale: Locale,
  failure: ModelConnectionFailureDetails,
): string {
  const message = Object.hasOwn(MESSAGES, failure.code)
    ? MESSAGES[failure.code]
    : null;
  const base = message
    ? locale === "zh-TW"
      ? message[0]
      : message[1]
    : locale === "zh-TW"
      ? "服務設定沒有更新，原設定仍保留。請確認網路與登入狀態後重試；若剛輸入過金鑰，請重新填入。"
      : "The service setting was not updated and the existing setting is preserved. Check your network and sign-in, then retry. Re-enter any key you just submitted.";
  const requestId =
    failure.requestId &&
    /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(failure.requestId)
      ? failure.requestId
      : undefined;
  if (!requestId) return base;
  const label = locale === "zh-TW" ? "診斷代碼" : "Diagnostic ID";
  return `${base} ${label}: ${requestId}`;
}
