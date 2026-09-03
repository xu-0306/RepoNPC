import { useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";

export interface EmbeddingProfileView {
  profile_id: string;
  provider: "ollama" | "openai_compatible" | "vllm";
  model_id: string;
  dimension: number;
  normalized: boolean;
  connection_reference: string;
  status:
    | "probe"
    | "reindex_required"
    | "reindexing"
    | "ready"
    | "last_known_good"
    | "probe_failed";
  active: boolean;
  last_error_code: string | null;
  last_probed_at: string | null;
}

export interface EmbeddingModelCatalogEntry {
  provider: "ollama";
  model_id: string;
  recommended: boolean;
  license: string;
  language_context_notes: string;
  resource_hint: string;
  operations: string[];
}

export interface EmbeddingProfileDraft {
  provider: EmbeddingProfileView["provider"];
  model_id: string;
  dimension: number;
  normalized: true;
  query_prefix: string;
  passage_prefix: string;
  connection_reference: string;
}

interface Props {
  locale: Locale;
  catalog: EmbeddingModelCatalogEntry[];
  installedModels: string[];
  profiles: EmbeddingProfileView[];
  pending: boolean;
  error: string;
  onRefresh: () => void;
  onCreate: (draft: EmbeddingProfileDraft) => void;
  onProbe: (profileId: string) => void;
  onActivate: (profileId: string) => void;
  onDelete: (profileId: string) => void;
  onOllamaPull: (profileId: string) => void;
  onOllamaDelete: (profileId: string) => void;
}

const COPY = {
  "zh-TW": {
    heading: "Embedding 模型中心",
    description:
      "管理外部 embedding profile。私有 URL 與憑證只留在伺服器環境或秘密儲存，不會顯示在此頁。",
    recommended: "建議起始值：Ollama qwen3-embedding:0.6b（1024 維）。",
    provider: "Provider",
    model: "模型",
    dimension: "維度",
    status: "狀態",
    connection: "連線參照",
    catalog: "經核准的 Ollama 目錄",
    installed: "已安裝於設定的 Ollama host",
    probeAuthoritative: "維度與相容性仍以實際 probe 結果為準。",
    create: "新增非啟用 profile",
    refresh: "重新整理",
    probe: "Probe",
    activate: "啟用",
    remove: "刪除",
    pullModel: "由 Ollama 安裝模型",
    deleteModel: "由 Ollama 刪除模型",
    modelConfirm: "此動作會變更 Ollama 的模型儲存。確定繼續嗎？",
    active: "目前啟用",
    empty: "尚無 embedding profile。",
    pending: "正在處理 embedding profile…",
  },
  en: {
    heading: "Embedding model center",
    description:
      "Manage external embedding profiles. Private URLs and credentials stay in server environment or secret storage and are never shown here.",
    recommended:
      "Recommended starter: Ollama qwen3-embedding:0.6b (1024 dimensions).",
    provider: "Provider",
    model: "Model",
    dimension: "Dimensions",
    status: "Status",
    connection: "Connection reference",
    catalog: "Approved Ollama catalog",
    installed: "Installed on the configured Ollama host",
    probeAuthoritative:
      "The live probe remains authoritative for dimensions and compatibility.",
    create: "Create inactive profile",
    refresh: "Refresh",
    probe: "Probe",
    activate: "Activate",
    remove: "Delete",
    pullModel: "Install through Ollama",
    deleteModel: "Delete through Ollama",
    modelConfirm: "This changes Ollama model storage. Continue?",
    active: "Active",
    empty: "No embedding profiles yet.",
    pending: "Working on embedding profiles…",
  },
} as const;

export function EmbeddingProfilePanel({
  locale,
  catalog,
  installedModels,
  profiles,
  pending,
  error,
  onRefresh,
  onCreate,
  onProbe,
  onActivate,
  onDelete,
  onOllamaPull,
  onOllamaDelete,
}: Props) {
  const copy = COPY[locale];
  const [provider, setProvider] =
    useState<EmbeddingProfileDraft["provider"]>("ollama");
  const [model, setModel] = useState("qwen3-embedding:0.6b");
  const [dimension, setDimension] = useState(1024);
  const [connection, setConnection] = useState("environment");
  const ollamaModels = catalog.filter((entry) => entry.provider === "ollama");

  function submit(event: FormEvent) {
    event.preventDefault();
    onCreate({
      provider,
      model_id: model,
      dimension,
      normalized: true,
      query_prefix: "query: ",
      passage_prefix: "passage: ",
      connection_reference: connection,
    });
  }

  return (
    <section aria-labelledby="embedding-profile-heading">
      <h2 id="embedding-profile-heading">{copy.heading}</h2>
      <p>{copy.description}</p>
      <p>{copy.recommended}</p>
      <h3>{copy.catalog}</h3>
      <ul>
        {ollamaModels.map((entry) => (
          <li key={entry.model_id}>
            <strong>{entry.model_id}</strong> — {entry.license};{" "}
            {entry.language_context_notes}; {entry.resource_hint}
          </li>
        ))}
      </ul>
      <p>{copy.probeAuthoritative}</p>
      <h3>{copy.installed}</h3>
      {installedModels.length > 0 ? (
        <ul>
          {installedModels.map((installedModel) => (
            <li key={installedModel}>{installedModel}</li>
          ))}
        </ul>
      ) : (
        <p>{copy.empty}</p>
      )}
      <button disabled={pending} onClick={onRefresh} type="button">
        {copy.refresh}
      </button>
      {pending && <p role="status">{copy.pending}</p>}
      {error && <p role="alert">{error}</p>}
      {profiles.length === 0 ? (
        <p>{copy.empty}</p>
      ) : (
        <ul>
          {profiles.map((profile) => (
            <li key={profile.profile_id}>
              <h3>{profile.model_id}</h3>
              <dl>
                <dt>{copy.provider}</dt>
                <dd>{profile.provider}</dd>
                <dt>{copy.dimension}</dt>
                <dd>{profile.dimension}</dd>
                <dt>{copy.status}</dt>
                <dd>{profile.status}</dd>
                <dt>{copy.connection}</dt>
                <dd>{profile.connection_reference}</dd>
              </dl>
              {profile.active && <strong>{copy.active}</strong>}
              {profile.last_error_code && (
                <p role="alert">{profile.last_error_code}</p>
              )}
              <button
                disabled={pending}
                onClick={() => onProbe(profile.profile_id)}
                type="button"
              >
                {copy.probe}
              </button>
              {!profile.active && (
                <>
                  <button
                    disabled={pending || profile.status !== "ready"}
                    onClick={() => onActivate(profile.profile_id)}
                    type="button"
                  >
                    {copy.activate}
                  </button>
                  <button
                    disabled={pending}
                    onClick={() => onDelete(profile.profile_id)}
                    type="button"
                  >
                    {copy.remove}
                  </button>
                </>
              )}
              {profile.provider === "ollama" && !profile.active && (
                <>
                  <button
                    disabled={pending}
                    onClick={() => {
                      if (window.confirm(copy.modelConfirm)) {
                        onOllamaPull(profile.profile_id);
                      }
                    }}
                    type="button"
                  >
                    {copy.pullModel}
                  </button>
                  <button
                    disabled={pending}
                    onClick={() => {
                      if (window.confirm(copy.modelConfirm)) {
                        onOllamaDelete(profile.profile_id);
                      }
                    }}
                    type="button"
                  >
                    {copy.deleteModel}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit}>
        <label htmlFor="embedding-profile-provider">
          {copy.provider}
          <select
            disabled={pending}
            id="embedding-profile-provider"
            onChange={(event) => {
              const nextProvider = event.target
                .value as EmbeddingProfileDraft["provider"];
              setProvider(nextProvider);
              if (nextProvider === "ollama" && ollamaModels.length > 0) {
                setModel(ollamaModels[0].model_id);
              }
            }}
            value={provider}
          >
            <option value="ollama">Ollama</option>
            <option value="vllm">vLLM</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
        </label>
        <label htmlFor="embedding-profile-model">
          {copy.model}
          {provider === "ollama" ? (
            <select
              disabled={pending || ollamaModels.length === 0}
              id="embedding-profile-model"
              onChange={(event) => setModel(event.target.value)}
              required
              value={model}
            >
              {ollamaModels.map((entry) => (
                <option key={entry.model_id} value={entry.model_id}>
                  {entry.model_id}
                </option>
              ))}
            </select>
          ) : (
            <input
              disabled={pending}
              id="embedding-profile-model"
              maxLength={256}
              onChange={(event) => setModel(event.target.value)}
              required
              value={model}
            />
          )}
        </label>
        <label htmlFor="embedding-profile-dimension">
          {copy.dimension}
          <input
            disabled={pending}
            id="embedding-profile-dimension"
            max={65536}
            min={1}
            onChange={(event) => setDimension(event.target.valueAsNumber)}
            required
            type="number"
            value={dimension}
          />
        </label>
        <label htmlFor="embedding-profile-connection">
          {copy.connection}
          <input
            disabled={pending}
            id="embedding-profile-connection"
            maxLength={64}
            onChange={(event) => setConnection(event.target.value)}
            pattern="[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
            required
            value={connection}
          />
        </label>
        <button disabled={pending} type="submit">
          {copy.create}
        </button>
      </form>
    </section>
  );
}
