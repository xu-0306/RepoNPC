import { useEffect, useMemo, useState } from "react";

import type { Locale } from "../../i18n/messages";
import type { ChatProfileView } from "./ChatProfilePanel";
import type { EmbeddingProfileView } from "./EmbeddingProfilePanel";
import type { ModelConnectionView } from "./ModelConnectionPanel";

export type AnalysisSelectionView = {
  selection: {
    chat_profile_id: string | null;
    embedding_profile_id: string | null;
    generation: number;
    updated_at: string;
  };
  eligible: boolean;
  reason: string;
};

export function AnalysisSelectionPanel({
  locale,
  chatProfiles,
  embeddingProfiles,
  value,
  pending,
  error,
  onSelect,
  connections,
}: {
  locale: Locale;
  chatProfiles: ChatProfileView[];
  embeddingProfiles: EmbeddingProfileView[];
  value: AnalysisSelectionView | null;
  pending: boolean;
  error: string;
  connections?: ModelConnectionView[];
  onSelect: (
    chatProfileId: string,
    embeddingProfileId: string,
    generation: number,
  ) => void;
}) {
  const readyChat = useMemo(
    () =>
      chatProfiles.filter(
        (profile) =>
          profile.status === "ready" &&
          profile.last_probed_at !== null &&
          !profile.last_error_code &&
          (!connections ||
            connections.some(
              (c) =>
                c.connection_id === profile.connection_id &&
                c.revision === profile.connection_revision,
            )),
      ),
    [chatProfiles, connections],
  );
  const readyEmbedding = useMemo(
    () =>
      embeddingProfiles.filter(
        (profile) =>
          ["ready", "reindex_required", "last_known_good"].includes(
            profile.status,
          ) &&
          profile.last_probed_at !== null &&
          profile.last_error_code === null &&
          (!connections ||
            connections.some(
              (c) =>
                c.connection_id === profile.connection_reference &&
                c.revision === profile.connection_revision,
            )),
      ),
    [embeddingProfiles, connections],
  );
  const [chatProfileId, setChatProfileId] = useState("");
  const [embeddingProfileId, setEmbeddingProfileId] = useState("");

  useEffect(() => {
    setChatProfileId((current) =>
      readyChat.some((profile) => profile.profile_id === current)
        ? current
        : readyChat.some(
              (p) => p.profile_id === value?.selection.chat_profile_id,
            )
          ? (value?.selection.chat_profile_id ?? "")
          : "",
    );
    setEmbeddingProfileId((current) =>
      readyEmbedding.some((profile) => profile.profile_id === current)
        ? current
        : readyEmbedding.some(
              (p) => p.profile_id === value?.selection.embedding_profile_id,
            )
          ? (value?.selection.embedding_profile_id ?? "")
          : "",
    );
  }, [
    readyChat,
    readyEmbedding,
    value?.selection.chat_profile_id,
    value?.selection.embedding_profile_id,
  ]);

  const chinese = locale === "zh-TW";
  const changed =
    chatProfileId !== (value?.selection.chat_profile_id ?? "") ||
    embeddingProfileId !== (value?.selection.embedding_profile_id ?? "");
  const canSelect =
    readyChat.some((p) => p.profile_id === chatProfileId) &&
    readyEmbedding.some((p) => p.profile_id === embeddingProfileId) &&
    !pending &&
    (changed || !value?.eligible);
  function optionLabel(profile: ChatProfileView | EmbeddingProfileView) {
    const connectionId =
      "connection_id" in profile
        ? profile.connection_id
        : profile.connection_reference;
    const service = connections?.find(
      (c) => c.connection_id === connectionId,
    )?.display_name;
    const peers = [...chatProfiles, ...embeddingProfiles].filter(
      (p) =>
        p.model_id === profile.model_id &&
        ("connection_id" in p ? p.connection_id : p.connection_reference) ===
          connectionId,
    );
    return `${profile.model_id}${service ? ` · ${service}` : ""}${peers.length > 1 ? ` · ${profile.profile_id.slice(-6)}` : ""}`;
  }
  const unavailableReason = value?.reason.includes("REVISION_STALE")
    ? chinese
      ? "服務設定已變更。請編輯對應模型並儲存，再測試及重新確認選用。"
      : "A service changed. Edit and save its model settings, test again, then confirm your selection."
    : value?.reason.includes("NOT_READY")
      ? chinese
        ? "有模型尚未通過測試，請先在模型卡片上測試。"
        : "A model has not passed testing. Test it on its model card first."
      : value?.reason === "MODEL_CONNECTION_UNAVAILABLE"
        ? chinese
          ? "模型使用的服務目前無法讀取。請檢查服務設定，或重新新增服務及模型。"
          : "A model's service is unavailable. Check its settings, or add the service and model again."
        : readyChat.length > 0 && readyEmbedding.length > 0
          ? chinese
            ? "兩種模型都已可用，請分別選擇並按「確認用於分析」。"
            : "Both model types are available. Select one of each, then use them for analysis."
          : chinese
            ? "請先新增並測試兩種模型，再分別選擇並確認。"
            : "Add and test both types of model, then select and confirm them.";
  return (
    <section
      aria-labelledby="analysis-model-selection-heading"
      className="model-selection model-panel"
    >
      <h3 className="visually-hidden" id="analysis-model-selection-heading">
        {chinese ? "選擇用於分析的模型" : "Choose models for analysis"}
      </h3>
      <p>
        {chinese
          ? "分析會使用兩個已測試的模型；不會變更網站目前使用的公開模型或索引。"
          : "Analysis uses two tested models. This does not change the public website model or index."}
      </p>
      <label htmlFor="analysis-chat-profile">
        {chinese ? "分析與回答模型" : "Analysis and chat model"}
        <select
          disabled={pending}
          id="analysis-chat-profile"
          onChange={(event) => setChatProfileId(event.target.value)}
          value={chatProfileId}
        >
          <option value="">
            {chinese
              ? readyChat.length
                ? "選擇回答模型"
                : "請先新增並測試回答模型"
              : readyChat.length
                ? "Select an answer model"
                : "Add and test an answer model first"}
          </option>
          {readyChat.map((profile) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {optionLabel(profile)}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor="analysis-embedding-profile">
        {chinese ? "資料查找模型" : "Content finder"}
        <select
          disabled={pending}
          id="analysis-embedding-profile"
          onChange={(event) => setEmbeddingProfileId(event.target.value)}
          value={embeddingProfileId}
        >
          <option value="">
            {chinese
              ? readyEmbedding.length
                ? "選擇資料查找模型"
                : "請先新增並測試資料查找模型"
              : readyEmbedding.length
                ? "Select a content finder"
                : "Add and test a content finder first"}
          </option>
          {readyEmbedding.map((profile) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {optionLabel(profile)}
            </option>
          ))}
        </select>
      </label>
      <button
        disabled={!canSelect}
        onClick={() =>
          onSelect(
            chatProfileId,
            embeddingProfileId,
            value?.selection.generation ?? 0,
          )
        }
        type="button"
      >
        {chinese ? "確認用於分析" : "Use for analysis"}
      </button>
      <p role="status">
        {changed && (chatProfileId || embeddingProfileId)
          ? chinese
            ? "選擇尚未確認。按「確認用於分析」後才會套用。"
            : "Your selection is not confirmed. Use for analysis applies these changes."
          : value?.eligible && !changed && chatProfileId && embeddingProfileId
            ? chinese
              ? "兩個模型已選用，可開始分析。"
              : "Both models are selected and ready for analysis."
            : unavailableReason}
      </p>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
