import type { Locale } from "../../i18n/messages";

type Message = readonly [string, string];

const ERRORS: Record<string, Message> = {
  PROVIDER_AUTHENTICATION: ["服務驗證失敗。", "Service authentication failed."],
  PROVIDER_RATE_LIMIT: ["服務限制請求。", "The service limited the request."],
  PROVIDER_TIMEOUT: [
    "連線或模型回應逾時；請檢查服務是否可用，再重新測試。",
    "The connection or model response timed out. Check service availability, then test again.",
  ],
  PROVIDER_UNAVAILABLE: [
    "無法連線至模型服務；請檢查服務網址、網路與服務運行狀態。",
    "Could not connect to the model service. Check the service URL, network, and whether the service is running.",
  ],
  PROVIDER_INVALID_RESPONSE: [
    "RepoNPC 未取得可用的模型回答。",
    "RepoNPC could not obtain a usable model response.",
  ],
  PROVIDER_CONTEXT_OVERFLOW: [
    "測試輸入超過模型可處理的長度；請檢查模型的上下文限制。",
    "The test input exceeded the model's context limit. Check its context settings.",
  ],
  CHAT_CONNECTION_REQUIRED: [
    "模型服務設定無法使用；請檢查服務設定，再重新測試。",
    "The model service configuration is unavailable. Check the service settings, then test again.",
  ],
  EMBEDDING_CONNECTION_REQUIRED: [
    "模型服務設定無法使用；請檢查服務設定，再重新測試。",
    "The model service configuration is unavailable. Check the service settings, then test again.",
  ],
  CHAT_PROBE_INVALID_RESPONSE: [
    "模型未回傳測試要求的 JSON 結果；請確認模型支援結構化回答。",
    "The model did not return the expected test JSON. Check that it supports structured responses.",
  ],
  EMBEDDING_PROFILE_IDENTITY_MISMATCH: [
    "模型資訊與設定不符；請確認服務、模型名稱與維度設定。",
    "The model identity does not match the settings. Check the service, model name, and dimensions.",
  ],
  EMBEDDING_PROBE_DIMENSION_MISMATCH: [
    "模型回傳的向量維度與設定不符；請確認此模型的維度。",
    "The returned vector dimensions do not match the settings. Check this model's dimensions.",
  ],
  EMBEDDING_PROBE_INVALID_VECTOR: [
    "模型未回傳有效的資料查找向量；請確認此模型支援 Embedding API。",
    "The model did not return a valid embedding vector. Check that it supports the embedding API.",
  ],
  EMBEDDING_PROBE_NOT_NORMALIZED: [
    "模型回傳的向量未符合正規化要求；請檢查服務的向量設定。",
    "The returned vector does not meet normalization requirements. Check the service's vector settings.",
  ],
};

export function modelProbeError(
  locale: Locale,
  code: string,
  providerMessage?: string | null,
): string {
  const index = locale === "zh-TW" ? 0 : 1;
  const http = /^PROVIDER_HTTP_([1-5]\d{2})$/.exec(code);
  if (http) {
    const message = providerMessage?.trim()
      ? providerMessage
      : [
          "未提供可顯示的錯誤文字。",
          "No displayable error message was provided.",
        ][index];
    return `HTTP ${http[1]}: ${message}`;
  }
  if (code === "PROVIDER_INVALID_RESPONSE" && providerMessage?.trim()) {
    return `${ERRORS[code][index]} ${providerMessage}`;
  }
  return Object.hasOwn(ERRORS, code)
    ? ERRORS[code][index]
    : [
        "測試未通過，沒有可用的詳細原因；請重新測試以取得最新結果。",
        "The test failed without a detailed reason. Test again to get the latest result.",
      ][index];
}
