import type { Locale } from "../../i18n/messages";

export interface AnalysisModelPairBody {
  selection_generation?: number;
  chat?: {
    profile_id?: string;
    connection_id?: string;
    connection_revision?: number;
    provider?: string;
    model_id?: string;
  };
  embedding?: {
    profile_id?: string;
    connection_id?: string;
    connection_revision?: number;
    provider?: string;
    identity?: {
      adapter?: string;
      model_id?: string;
      dimension?: number;
      normalized?: boolean;
      query_prefix?: string;
      passage_prefix?: string;
    };
  };
}

export function analysisModelConfirmationMessage(
  locale: Locale,
  commitSha: string | null | undefined,
  frozen: AnalysisModelPairBody | null | undefined,
  current: {
    chat_profile_id?: string | null;
    embedding_profile_id?: string | null;
  },
): string {
  if (locale === "zh-TW") {
    return `原提交：${commitSha ?? "未知"}\n原模型：${frozen?.chat?.profile_id ?? "未知"} / ${frozen?.embedding?.profile_id ?? "未知"}\n目前模型：${current.chat_profile_id ?? "未設定"} / ${current.embedding_profile_id ?? "未設定"}\n確認以目前模型建立新一輪分析？`;
  }
  return `Original commit: ${commitSha ?? "unknown"}\nOriginal models: ${frozen?.chat?.profile_id ?? "unknown"} / ${frozen?.embedding?.profile_id ?? "unknown"}\nCurrent models: ${current.chat_profile_id ?? "not configured"} / ${current.embedding_profile_id ?? "not configured"}\nCreate a successor analysis with the current models?`;
}
