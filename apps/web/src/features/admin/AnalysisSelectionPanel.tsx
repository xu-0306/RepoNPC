import { useEffect, useState } from "react";

import type { Locale } from "../../i18n/messages";
import type { ChatProfileView } from "./ChatProfilePanel";
import type { EmbeddingProfileView } from "./EmbeddingProfilePanel";

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
}: {
  locale: Locale;
  chatProfiles: ChatProfileView[];
  embeddingProfiles: EmbeddingProfileView[];
  value: AnalysisSelectionView | null;
  pending: boolean;
  error: string;
  onSelect: (
    chatProfileId: string,
    embeddingProfileId: string,
    generation: number,
  ) => void;
}) {
  const readyChat = chatProfiles.filter(
    (profile) => profile.status === "ready" && profile.last_probed_at !== null,
  );
  const readyEmbedding = embeddingProfiles.filter(
    (profile) =>
      ["ready", "reindex_required", "last_known_good"].includes(
        profile.status,
      ) &&
      profile.last_probed_at !== null &&
      profile.last_error_code === null,
  );
  const [chatProfileId, setChatProfileId] = useState("");
  const [embeddingProfileId, setEmbeddingProfileId] = useState("");

  useEffect(() => {
    setChatProfileId((current) =>
      readyChat.some((profile) => profile.profile_id === current)
        ? current
        : (value?.selection.chat_profile_id ?? ""),
    );
    setEmbeddingProfileId((current) =>
      readyEmbedding.some((profile) => profile.profile_id === current)
        ? current
        : (value?.selection.embedding_profile_id ?? ""),
    );
  }, [
    readyChat,
    readyEmbedding,
    value?.selection.chat_profile_id,
    value?.selection.embedding_profile_id,
  ]);

  const chinese = locale === "zh-TW";
  const canSelect = Boolean(chatProfileId && embeddingProfileId) && !pending;
  return (
    <section
      aria-labelledby="analysis-model-selection-heading"
      className="model-selection"
    >
      <h3 id="analysis-model-selection-heading">
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
              ? "先建立並測試 Chat profile"
              : "Create and test a chat profile first"}
          </option>
          {readyChat.map((profile) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {profile.model_id}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor="analysis-embedding-profile">
        {chinese ? "搜尋模型" : "Search model"}
        <select
          disabled={pending}
          id="analysis-embedding-profile"
          onChange={(event) => setEmbeddingProfileId(event.target.value)}
          value={embeddingProfileId}
        >
          <option value="">
            {chinese
              ? "先建立並測試搜尋 profile"
              : "Create and test a search profile first"}
          </option>
          {readyEmbedding.map((profile) => (
            <option key={profile.profile_id} value={profile.profile_id}>
              {profile.model_id}
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
        {value?.eligible
          ? chinese
            ? "兩個模型已選用，可開始分析。"
            : "Both models are selected and ready for analysis."
          : chinese
            ? "請分別測試並選擇兩個模型。"
            : "Test and explicitly select both models."}
      </p>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
