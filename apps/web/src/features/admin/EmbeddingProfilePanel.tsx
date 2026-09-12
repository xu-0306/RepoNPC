import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";
import { ModelBrandIcon } from "./ModelBrandIcon";
import { ModelEditor } from "./ModelEditor";
import { modelProbeError } from "./modelProbeError";
import { DeleteSettingButton } from "./DeleteSettingButton";
import type { ModelConnectionView } from "./ModelConnectionPanel";

export interface EmbeddingProfileView {
  profile_id: string;
  provider: "ollama" | "openai_compatible" | "vllm";
  model_id: string;
  dimension: number | null;
  query_prefix?: string;
  passage_prefix?: string;
  connection_revision?: number;
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
  last_error_message?: string | null;
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
  dimension: number | null;
  normalized: true;
  query_prefix: string;
  passage_prefix: string;
  connection_reference: string;
}

interface Props {
  locale: Locale;
  connections: ModelConnectionView[];
  catalog: EmbeddingModelCatalogEntry[];
  installedModels: string[];
  profiles: EmbeddingProfileView[];
  pending: boolean;
  error: string;
  notice?: string;
  onRefresh: () => void;
  onCreate: (draft: EmbeddingProfileDraft) => void;
  onUpdate?: (profileId: string, draft: EmbeddingProfileDraft) => void;
  onLoadInstalled?: (connectionId: string) => void;
  installedState?: {
    connectionId: string;
    status: "idle" | "loading" | "loaded" | "failed";
    models: string[];
  };
  pendingProfileId?: string | null;
  onProbe: (profileId: string) => void;
  onActivate: (profileId: string) => void;
  onDelete: (profileId: string) => void;
  onOllamaPull: (profileId: string) => void;
  onOllamaDelete: (profileId: string) => void;
  managementActions?: boolean;
}

const COPY = {
  "zh-TW": {
    heading: "資料查找模型",
    guidedHeading: "新增與測試模型",
    description:
      "把作品內容整理成可查找的資料，讓回答模型找到相關依據。技術名稱是 Embedding model。私有 URL 與憑證不會顯示在此頁。",
    guidedDescription:
      "選擇服務、填入模型名稱，再按「測試模型」。通過後到「確認分析模型」選用。",
    add: "新增模型",
    cancel: "取消",
    recommended: "建議起始值：Ollama qwen3-embedding:0.6b（1024 維）。",
    provider: "連線方式",
    model: "模型",
    dimension: "維度",
    status: "狀態",
    connection: "服務",
    selectService: "選擇服務",
    technical: "技術資訊",
    queryPrefix: "Query prefix",
    passagePrefix: "Passage prefix",
    savedService: "已儲存的服務",
    errorCode: "錯誤代碼",
    catalog: "經核准的 Ollama 目錄",
    installed: "已安裝於設定的 Ollama host",
    probeAuthoritative: "維度與相容性仍以實際 probe 結果為準。",
    create: "新增模型",
    refresh: "重新整理",
    probe: "測試資料查找",
    activate: "啟用",
    remove: "刪除",
    pullModel: "由 Ollama 安裝模型",
    deleteModel: "由 Ollama 刪除模型",
    modelConfirm: "此動作會變更 Ollama 的模型儲存。確定繼續嗎？",
    active: "目前啟用",
    empty: "尚未設定資料查找模型。",
    pending: "正在處理資料查找模型…",
  },
  en: {
    heading: "Content finder models",
    guidedHeading: "Add and test models",
    description:
      "Organize portfolio content so the answer model can find relevant evidence. The technical name is an embedding model. Private URLs and credentials are never shown here.",
    guidedDescription:
      "Choose a service, enter its model name, and test the model. Then use Confirm analysis models to select it.",
    add: "Add model",
    cancel: "Cancel",
    recommended: "Ollama recommendations appear after you choose Ollama.",
    provider: "Provider",
    model: "Model",
    dimension: "Dimensions",
    status: "Status",
    connection: "Service",
    selectService: "Select a service",
    technical: "Technical details",
    queryPrefix: "Query prefix",
    passagePrefix: "Passage prefix",
    savedService: "Saved service",
    errorCode: "Error code",
    catalog: "Approved Ollama catalog",
    installed: "Installed on the configured Ollama host",
    probeAuthoritative:
      "The live probe remains authoritative for dimensions and compatibility.",
    create: "Add model",
    refresh: "Refresh",
    probe: "Test content finding",
    activate: "Activate",
    remove: "Delete",
    pullModel: "Install through Ollama",
    deleteModel: "Delete through Ollama",
    modelConfirm: "This changes Ollama model storage. Continue?",
    active: "Active",
    empty: "No content finder model has been set up.",
    pending: "Working on content finder models…",
  },
} as const;

function connectionLabel(
  connections: ModelConnectionView[],
  connectionId: string,
  locale: Locale,
): string {
  const connection = connections.find(
    (candidate) => candidate.connection_id === connectionId,
  );
  if (!connection) return "";
  if (connection.source === "host-managed") {
    return locale === "zh-TW"
      ? "環境預設連線（資料查找）"
      : "Environment connection (content finding)";
  }
  return connection.display_name;
}

export function EmbeddingProfilePanel({
  locale,
  connections,
  catalog,
  installedModels,
  profiles,
  pending,
  error,
  notice,
  onRefresh,
  onCreate,
  onUpdate,
  onLoadInstalled,
  installedState,
  pendingProfileId,
  onProbe,
  onActivate,
  onDelete,
  onOllamaPull,
  onOllamaDelete,
  managementActions = true,
}: Props) {
  const copy = COPY[locale];
  const editorRef = useRef<HTMLDetailsElement>(null);
  const [model, setModel] = useState("");
  const [dimension, setDimension] = useState("");
  const [connection, setConnection] = useState("");
  const [queryPrefix, setQueryPrefix] = useState("");
  const [passagePrefix, setPassagePrefix] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const ollamaModels = catalog.filter((entry) => entry.provider === "ollama");
  const selectedConnection = connections.find(
    (candidate) => candidate.connection_id === connection,
  );
  const provider = selectedConnection?.provider ?? "";
  const Heading = managementActions ? "h2" : "h4";

  function resetForm() {
    setEditingId(null);
    setConnection("");
    setModel("");
    setDimension("");
    setQueryPrefix("");
    setPassagePrefix("");
  }
  useEffect(() => {
    if (editingId && !profiles.some((item) => item.profile_id === editingId)) {
      resetForm();
      if (editorRef.current) editorRef.current.open = false;
    }
  }, [profiles, editingId]);

  function edit(profile: EmbeddingProfileView) {
    setEditingId(profile.profile_id);
    setConnection(profile.connection_reference);
    setModel(profile.model_id);
    setDimension(profile.dimension === null ? "" : String(profile.dimension));
    setQueryPrefix(profile.query_prefix ?? "");
    setPassagePrefix(profile.passage_prefix ?? "");
    if (editorRef.current) {
      editorRef.current.open = true;
      editorRef.current.querySelector("select")?.focus();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const parsedDimension = dimension.trim() ? Number(dimension) : null;
    if (
      !provider ||
      !model.trim() ||
      !connection.trim() ||
      (parsedDimension !== null &&
        (!Number.isInteger(parsedDimension) ||
          parsedDimension < 1 ||
          parsedDimension > 65536))
    )
      return;
    const draft: EmbeddingProfileDraft = {
      provider,
      model_id: model.trim(),
      dimension: parsedDimension,
      normalized: true,
      query_prefix: queryPrefix,
      passage_prefix: passagePrefix,
      connection_reference: connection,
    };
    if (editingId && onUpdate) onUpdate(editingId, draft);
    else onCreate(draft);
  }

  return (
    <section
      aria-labelledby="embedding-profile-heading"
      className="model-panel model-panel--embedding"
    >
      <Heading id="embedding-profile-heading">
        {managementActions ? copy.heading : copy.guidedHeading}
      </Heading>
      <p>{managementActions ? copy.description : copy.guidedDescription}</p>
      {provider === "ollama" && (
        <details className="model-card__technical">
          <summary>
            {locale === "zh-TW"
              ? "查看此服務的已安裝模型"
              : "View this service's installed models"}
          </summary>
          {provider === "ollama" && <p>{copy.recommended}</p>}
          {provider === "ollama" && <h3>{copy.catalog}</h3>}
          <ul>
            {provider === "ollama" &&
              ollamaModels.map((entry) => (
                <li key={entry.model_id}>
                  <strong>{entry.model_id}</strong> — {entry.license};{" "}
                  {entry.language_context_notes}; {entry.resource_hint}
                </li>
              ))}
          </ul>
          <p>{copy.probeAuthoritative}</p>
          {onLoadInstalled && (
            <button
              type="button"
              disabled={pending || installedState?.status === "loading"}
              onClick={() => onLoadInstalled(connection)}
            >
              {locale === "zh-TW" ? "讀取模型清單" : "Load model list"}
            </button>
          )}
          {installedState?.connectionId === connection &&
            installedState.status === "loading" && (
              <p role="status">
                {locale === "zh-TW" ? "正在讀取模型清單…" : "Loading models…"}
              </p>
            )}
          {installedState?.connectionId === connection &&
            installedState.status === "failed" && (
              <p role="alert">
                {locale === "zh-TW"
                  ? "讀取失敗，請確認這個 Ollama 服務正在執行，再按「讀取模型清單」重試。"
                  : "Could not load models. Check that this Ollama service is running, then load the list again."}
              </p>
            )}
          {(installedState?.connectionId === connection &&
          installedState.status === "loaded"
            ? installedState.models
            : installedModels
          ).length > 0 ? (
            <ul>
              {(installedState?.connectionId === connection &&
              installedState.status === "loaded"
                ? installedState.models
                : installedModels
              ).map((installedModel) => (
                <li key={installedModel}>{installedModel}</li>
              ))}
            </ul>
          ) : installedState?.connectionId !== connection ||
            installedState?.status === "idle" ||
            installedState?.status === "loaded" ? (
            <p>
              {installedState?.connectionId === connection &&
              installedState.status === "loaded"
                ? locale === "zh-TW"
                  ? "此服務尚未安裝模型。"
                  : "No models are installed on this service."
                : locale === "zh-TW"
                  ? "尚未讀取；你也可以直接輸入模型名稱並測試。"
                  : "Not loaded yet. You can also enter a model name and test it directly."}
            </p>
          ) : null}
        </details>
      )}
      <button disabled={pending} onClick={onRefresh} type="button">
        {copy.refresh}
      </button>
      {pending && <p role="status">{copy.pending}</p>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {profiles.length === 0 ? (
        <p>{copy.empty}</p>
      ) : (
        <ul className="model-card-list">
          {profiles.map((profile) => (
            <li className="model-card" key={profile.profile_id}>
              <div className="model-card__heading">
                <ModelBrandIcon
                  modelId={profile.model_id}
                  provider={profile.provider}
                />
                <strong>{profile.model_id}</strong>
                <span className="model-card__provider">
                  {profile.last_error_code
                    ? locale === "zh-TW"
                      ? "測試失敗"
                      : "Test failed"
                    : profile.last_probed_at &&
                        [
                          "ready",
                          "reindex_required",
                          "last_known_good",
                        ].includes(profile.status)
                      ? locale === "zh-TW"
                        ? "測試通過"
                        : "Test passed"
                      : profile.status === "probe"
                        ? locale === "zh-TW"
                          ? "待測試"
                          : "Needs test"
                        : profile.status === "reindexing"
                          ? locale === "zh-TW"
                            ? "正在更新網站資料"
                            : "Updating website data"
                          : locale === "zh-TW"
                            ? "待測試"
                            : "Needs test"}
                </span>
              </div>
              <dl>
                <dt>{copy.provider}</dt>
                <dd>
                  {profile.provider === "openai_compatible"
                    ? "OpenAI-compatible"
                    : profile.provider === "vllm"
                      ? "vLLM"
                      : "Ollama"}
                </dd>
                <dt>{copy.connection}</dt>
                <dd>
                  {connectionLabel(
                    connections,
                    profile.connection_reference,
                    locale,
                  ) || copy.savedService}
                </dd>
              </dl>
              {managementActions && profile.active && (
                <strong className="model-card__state">{copy.active}</strong>
              )}
              {profile.last_error_code && (
                <p
                  role="alert"
                  style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                >
                  {modelProbeError(
                    locale,
                    profile.last_error_code,
                    profile.last_error_message,
                  )}
                </p>
              )}
              {onUpdate &&
                !profile.active &&
                profile.status !== "reindexing" && (
                  <button
                    type="button"
                    disabled={pending}
                    aria-label={`${locale === "zh-TW" ? "編輯" : "Edit"} ${profile.model_id} · ${connectionLabel(connections, profile.connection_reference, locale)}`}
                    onClick={() => edit(profile)}
                  >
                    {locale === "zh-TW" ? "編輯" : "Edit"}
                  </button>
                )}
              <button
                disabled={pending || profile.status === "reindexing"}
                aria-label={`${locale === "zh-TW" ? "測試模型" : "Test model"} ${profile.model_id} · ${connectionLabel(connections, profile.connection_reference, locale)}`}
                onClick={() => onProbe(profile.profile_id)}
                type="button"
              >
                {pending && pendingProfileId === profile.profile_id
                  ? locale === "zh-TW"
                    ? "正在測試…"
                    : "Testing…"
                  : locale === "zh-TW"
                    ? "測試模型"
                    : "Test model"}
              </button>
              {managementActions && !profile.active && (
                <>
                  <button
                    disabled={
                      pending ||
                      !profile.last_probed_at ||
                      Boolean(profile.last_error_code) ||
                      !["ready", "reindex_required"].includes(profile.status)
                    }
                    onClick={() => onActivate(profile.profile_id)}
                    type="button"
                  >
                    {profile.status === "reindex_required"
                      ? locale === "zh-TW"
                        ? "更新網站資料並啟用"
                        : "Update website data and activate"
                      : copy.activate}
                  </button>
                </>
              )}
              <DeleteSettingButton
                locale={locale}
                name={profile.model_id}
                kind="model"
                pending={pending}
                blockedReason={
                  profile.active
                    ? locale === "zh-TW"
                      ? "公開網站正在使用此模型，請先到進階設定切換模型後再刪除。"
                      : "The public site uses this model. Switch to another model in advanced settings before deleting it."
                    : profile.status === "reindexing"
                      ? locale === "zh-TW"
                        ? "此模型正在重建索引，完成後才能刪除。"
                        : "This model is rebuilding the index. Wait for completion before deleting it."
                      : undefined
                }
                onDelete={() => onDelete(profile.profile_id)}
              />
              {managementActions &&
                profile.provider === "ollama" &&
                !profile.active && (
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
              <details className="model-card__technical">
                <summary>{copy.technical}</summary>
                <dl>
                  <dt>{copy.dimension}</dt>
                  <dd>
                    {profile.dimension ??
                      (locale === "zh-TW"
                        ? "測試後取得"
                        : "Detected during testing")}
                  </dd>
                  <dt>{copy.status}</dt>
                  <dd>{profile.status}</dd>
                  {profile.last_error_code && (
                    <>
                      <dt>{copy.errorCode}</dt>
                      <dd>{profile.last_error_code}</dd>
                    </>
                  )}
                </dl>
              </details>
            </li>
          ))}
        </ul>
      )}
      {connections.length === 0 ? (
        <p>
          {locale === "zh-TW"
            ? "請先新增一個服務，再新增模型。"
            : "Add a service before adding a model."}
        </p>
      ) : (
        <ModelEditor
          label={
            editingId
              ? locale === "zh-TW"
                ? "編輯模型"
                : "Edit model"
              : copy.add
          }
          cancel={copy.cancel}
          editorRef={editorRef}
          pending={pending}
          error={error}
          onClose={resetForm}
        >
          <form onSubmit={submit}>
            <label htmlFor="embedding-profile-connection">
              {copy.connection}
              <select
                disabled={pending}
                id="embedding-profile-connection"
                onChange={(event) => {
                  setConnection(event.target.value);
                  setModel("");
                  setDimension("");
                  setQueryPrefix("");
                  setPassagePrefix("");
                }}
                required
                value={connection}
              >
                <option value="">{copy.selectService}</option>
                {connections.map((modelConnection) => (
                  <option
                    key={modelConnection.connection_id}
                    value={modelConnection.connection_id}
                  >
                    {modelConnection.source === "host-managed"
                      ? locale === "zh-TW"
                        ? "環境預設連線（資料查找）"
                        : "Environment connection (content finding)"
                      : modelConnection.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor="embedding-profile-model">
              {copy.model}
              {provider === "ollama" ? (
                <>
                  <input
                    autoComplete="off"
                    disabled={pending}
                    id="embedding-profile-model"
                    list="embedding-profile-model-options"
                    maxLength={256}
                    onChange={(event) => {
                      setModel(event.target.value);
                      setDimension("");
                    }}
                    required
                    value={model}
                  />
                  <datalist id="embedding-profile-model-options">
                    {ollamaModels.map((entry) => (
                      <option key={entry.model_id} value={entry.model_id} />
                    ))}
                  </datalist>
                </>
              ) : (
                <input
                  disabled={pending}
                  id="embedding-profile-model"
                  maxLength={256}
                  onChange={(event) => {
                    setModel(event.target.value);
                    setDimension("");
                  }}
                  required
                  value={model}
                />
              )}
            </label>
            <p>
              {locale === "zh-TW"
                ? "模型名稱請從服務商複製。新增只會儲存設定；按「測試模型」才會連線，服務商可能計費。"
                : "Copy the model name from your provider. Adding only saves the settings; testing connects to the service and may incur provider charges."}
            </p>
            <details className="model-form__technical">
              <summary>
                {locale === "zh-TW"
                  ? "進階設定（一般不需修改）"
                  : "Advanced settings (usually unchanged)"}
              </summary>
              <label htmlFor="embedding-profile-dimension">
                {copy.dimension}
                <input
                  disabled={pending}
                  id="embedding-profile-dimension"
                  max={65536}
                  min={1}
                  onChange={(event) => setDimension(event.target.value)}
                  type="number"
                  value={dimension}
                />
              </label>
              <p>
                {locale === "zh-TW"
                  ? "維度留空即可，測試時會自動取得。前綴只有服務商特別要求時才需填寫。"
                  : "Leave dimensions blank to detect them during testing. Enter prefixes only if your provider requires them."}
              </p>
              <label htmlFor="embedding-profile-query-prefix">
                {copy.queryPrefix}
                <input
                  disabled={pending}
                  id="embedding-profile-query-prefix"
                  maxLength={128}
                  onChange={(event) => setQueryPrefix(event.target.value)}
                  value={queryPrefix}
                />
              </label>
              <label htmlFor="embedding-profile-passage-prefix">
                {copy.passagePrefix}
                <input
                  disabled={pending}
                  id="embedding-profile-passage-prefix"
                  maxLength={128}
                  onChange={(event) => setPassagePrefix(event.target.value)}
                  value={passagePrefix}
                />
              </label>
            </details>
            <button disabled={pending} type="submit">
              {editingId
                ? locale === "zh-TW"
                  ? "儲存修改"
                  : "Save changes"
                : copy.create}
            </button>
          </form>
        </ModelEditor>
      )}
    </section>
  );
}
