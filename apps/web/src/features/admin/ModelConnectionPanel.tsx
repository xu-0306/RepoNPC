import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";
import { ProviderBrandIcon } from "./ModelBrandIcon";
import { ModelEditor } from "./ModelEditor";
import { DeleteSettingButton } from "./DeleteSettingButton";
import { CheckboxField } from "./CheckboxField";

export interface ModelConnectionView {
  connection_id: string;
  display_name: string;
  provider: "ollama" | "openai_compatible" | "vllm";
  source: "host-managed" | "managed";
  revision: number;
  endpoint_configured: boolean;
  key_configured: boolean;
  status: string;
}

export interface ModelConnectionDraft {
  display_name: string;
  provider: ModelConnectionView["provider"];
  base_url?: string;
  endpoint_action?: "retain" | "replace";
  api_key?: string;
  credential_action: "retain" | "replace" | "remove";
}

interface Props {
  locale: Locale;
  connections: ModelConnectionView[];
  pending: boolean;
  error: string;
  notice?: string;
  onRefresh: () => void;
  onCreate: (draft: ModelConnectionDraft) => void;
  onUpdate: (connectionId: string, draft: ModelConnectionDraft) => void;
  onDelete: (connectionId: string) => void;
  onReadEndpoint?: (
    connectionId: string,
  ) => Promise<{ connection_id: string; revision: number; base_url: string }>;
  managementActions?: boolean;
  purpose?: "chat" | "embedding";
}

const COPY = {
  "zh-TW": {
    heading: "可用的 AI 服務",
    chatHeading: "管理回答模型的服務",
    embeddingHeading: "管理資料查找的服務",
    description:
      "這裡是模型可以連接的服務，不代表模型已完成設定。選好服務後，還要輸入模型名稱並測試。",
    guidedDescription:
      "先新增提供模型的服務，再到「新增模型」選擇它。已有合適的服務就不必重複新增。",
    hostChat: "環境預設連線（回答）",
    hostEmbedding: "環境預設連線（資料查找）",
    hostManaged:
      "這只是啟動環境中的連線設定，不是 RepoNPC 內建的 AI 服務，也不代表 Ollama 等服務已安裝、啟動或可用。請先新增模型並測試。此連線由環境設定管理；修改或移除需調整啟動環境設定。",
    connectionDetails: "連線資訊",
    addService: "新增 AI 服務",
    editService: "編輯 AI 服務",
    name: "服務名稱（方便自己辨認）",
    provider: "連線方式",
    address: "服務網址（API 位址）",
    key: "服務金鑰（API key，可選）",
    create: "儲存服務",
    update: "更新服務",
    cancel: "取消",
    edit: "編輯",
    removeKey: "移除已儲存的 API key",
    refresh: "重新整理",
    empty: "還沒有服務。請先新增服務，再新增模型。",
    configured: "已設定",
    notConfigured: "未設定",
    remove: "刪除",
    select: "選擇服務商支援的連線方式",
    pending: "正在處理模型連線…",
    revision: "設定版本",
  },
  en: {
    heading: "Available AI services",
    chatHeading: "Manage answer model services",
    embeddingHeading: "Manage content finder services",
    description:
      "Save a service, then choose it when adding a model. Test the model before using it.",
    guidedDescription:
      "Add the service that provides your model, then choose it in Add model. Reuse a saved service when it fits.",
    hostChat: "Environment connection (answers)",
    hostEmbedding: "Environment connection (content finding)",
    hostManaged:
      "This is a connection setting from the startup environment, not a built-in AI service. It does not mean Ollama or another service is installed, running, or available. Add and test a model first. To change or remove this connection, update the startup environment settings.",
    connectionDetails: "Connection details",
    addService: "Add an AI service",
    editService: "Edit AI service",
    name: "Service name (for your reference)",
    provider: "Connection type",
    address: "Service URL (API address)",
    key: "Service key (API key, optional)",
    create: "Save service",
    update: "Update service",
    cancel: "Cancel",
    edit: "Edit",
    removeKey: "Remove saved key",
    refresh: "Refresh",
    empty: "No model connections yet.",
    configured: "Configured",
    notConfigured: "Not configured",
    remove: "Delete",
    select: "Select the connection type your provider supports",
    pending: "Working on model connections…",
    revision: "Revision",
  },
} as const;

export function ModelConnectionPanel({
  locale,
  connections,
  pending,
  error,
  notice,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
  onReadEndpoint,
  purpose,
}: Props) {
  const copy = COPY[locale];
  const editorRef = useRef<HTMLDetailsElement>(null);
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState<
    "" | ModelConnectionView["provider"]
  >("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [replaceAddress, setReplaceAddress] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [removeKey, setRemoveKey] = useState(false);
  const [endpointLoading, setEndpointLoading] = useState(false);
  const [endpointError, setEndpointError] = useState(false);
  const endpointRequest = useRef(0);
  useEffect(
    () => () => {
      endpointRequest.current += 1;
    },
    [],
  );

  const clearEndpointRead = useCallback(() => {
    endpointRequest.current += 1;
    setEndpointLoading(false);
    setEndpointError(false);
    setBaseUrl("");
  }, []);

  const cancelEdit = useCallback(() => {
    setEditorOpen(false);
    clearEndpointRead();
    setEditingId(null);
    setDisplayName("");
    setProvider("");
    setBaseUrl("");
    setApiKey("");
    setReplaceAddress(true);
    setRemoveKey(false);
  }, [clearEndpointRead]);

  async function readEndpoint() {
    if (!editingId || !onReadEndpoint) return;
    const generation = ++endpointRequest.current;
    setEndpointLoading(true);
    setEndpointError(false);
    try {
      const result = await onReadEndpoint(editingId);
      if (generation !== endpointRequest.current) return;
      if (
        result.connection_id !== editingId ||
        result.revision !== editingConnection?.revision
      )
        throw new Error("stale endpoint");
      setBaseUrl(result.base_url);
    } catch {
      if (generation === endpointRequest.current) setEndpointError(true);
    } finally {
      if (generation === endpointRequest.current) setEndpointLoading(false);
    }
  }
  useEffect(() => {
    if (
      editingId &&
      !connections.some((item) => item.connection_id === editingId)
    ) {
      cancelEdit();
      if (editorRef.current) {
        editorRef.current.open = false;
        editorRef.current.querySelector("summary")?.focus();
      }
    }
  }, [connections, editingId, cancelEdit]);
  const visibleConnections = purpose
    ? connections.filter(
        (connection) =>
          connection.source === "managed" ||
          connection.connection_id === `environment-${purpose}`,
      )
    : connections;
  const idSuffix = purpose ? `-${purpose}` : "";
  const headingId = `model-connection-heading${idSuffix}`;
  const editingConnection = connections.find(
    (item) => item.connection_id === editingId,
  );
  useEffect(() => {
    endpointRequest.current += 1;
    setEndpointLoading(false);
    setEndpointError(false);
    setBaseUrl("");
  }, [editingId, editingConnection?.revision]);
  const providerChanged = Boolean(
    editingConnection && editingConnection.provider !== provider,
  );
  const Heading = purpose ? "h4" : "h2";
  const heading = purpose
    ? purpose === "chat"
      ? copy.chatHeading
      : copy.embeddingHeading
    : copy.heading;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || endpointLoading) return;
    if (!provider || !displayName.trim() || (replaceAddress && !baseUrl.trim()))
      return;
    const draft = {
      display_name: displayName.trim(),
      provider,
      base_url: replaceAddress ? baseUrl.trim() : undefined,
      endpoint_action: replaceAddress ? "replace" : "retain",
      api_key: removeKey || !apiKey ? undefined : apiKey,
      credential_action: removeKey ? "remove" : apiKey ? "replace" : "retain",
    } satisfies ModelConnectionDraft;
    setApiKey("");
    if (editingId) onUpdate(editingId, draft);
    else onCreate(draft);
  }

  function edit(connection: ModelConnectionView) {
    clearEndpointRead();
    if (editorRef.current) {
      editorRef.current.open = true;
      editorRef.current.querySelector("input")?.focus();
    }
    setEditingId(connection.connection_id);
    setDisplayName(connection.display_name);
    setProvider(connection.provider);
    setBaseUrl("");
    setApiKey("");
    setReplaceAddress(false);
    setRemoveKey(false);
  }

  return (
    <section
      aria-labelledby={headingId}
      className="model-panel model-panel--connection"
    >
      <Heading id={headingId}>{heading}</Heading>
      <p>{purpose ? copy.guidedDescription : copy.description}</p>
      <button disabled={pending} onClick={onRefresh} type="button">
        {copy.refresh}
      </button>
      {pending && <p role="status">{copy.pending}</p>}
      {error && !editorOpen && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {visibleConnections.length === 0 ? (
        <p>{copy.empty}</p>
      ) : (
        <ul className="model-card-list">
          {visibleConnections.map((connection) => (
            <li className="model-card" key={connection.connection_id}>
              <div className="model-card__heading">
                <ProviderBrandIcon provider={connection.provider} />
                <strong>
                  {connection.source === "host-managed"
                    ? connection.connection_id === "environment-chat"
                      ? copy.hostChat
                      : copy.hostEmbedding
                    : connection.display_name}
                </strong>
                <span className="model-card__provider">
                  {connection.provider === "openai_compatible"
                    ? "OpenAI-compatible"
                    : connection.provider === "vllm"
                      ? "vLLM"
                      : "Ollama"}
                </span>
              </div>
              {connection.source === "host-managed" ? (
                <>
                  <p className="model-card__note">{copy.hostManaged}</p>
                  <details className="model-card__technical">
                    <summary>{copy.connectionDetails}</summary>
                    <ConnectionMetadata connection={connection} copy={copy} />
                  </details>
                </>
              ) : (
                <details className="model-card__technical">
                  <summary>{copy.connectionDetails}</summary>
                  <ConnectionMetadata connection={connection} copy={copy} />
                </details>
              )}
              {connection.source === "managed" && (
                <>
                  <button
                    aria-label={`${copy.edit} ${connection.display_name}`}
                    disabled={pending}
                    onClick={() => edit(connection)}
                    type="button"
                  >
                    {copy.edit}
                  </button>
                  <DeleteSettingButton
                    locale={locale}
                    name={connection.display_name}
                    kind="connection"
                    pending={pending}
                    onDelete={() => onDelete(connection.connection_id)}
                  />
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <ModelEditor
        label={editingId ? copy.editService : copy.addService}
        cancel={copy.cancel}
        editorRef={editorRef}
        pending={pending}
        error={error}
        onClose={cancelEdit}
        onOpen={() => setEditorOpen(true)}
      >
        <form className="model-connection-form" onSubmit={submit}>
          <h3>{editingId ? copy.editService : copy.addService}</h3>
          <p>
            {locale === "zh-TW"
              ? "從服務商的設定頁複製服務網址與 API key。金鑰只用於連線，送出或離開表單後會清除輸入；重試時請重新填入。"
              : "Copy the service URL and API key from your provider's settings. The typed key clears after submission or leaving this form; enter it again when retrying."}
          </p>
          <label htmlFor={`model-connection-name${idSuffix}`}>
            {copy.name}
            <input
              disabled={pending}
              id={`model-connection-name${idSuffix}`}
              maxLength={120}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              value={displayName}
            />
          </label>
          <label htmlFor={`model-connection-provider${idSuffix}`}>
            {copy.provider}
            <select
              disabled={pending}
              id={`model-connection-provider${idSuffix}`}
              onChange={(event) => {
                clearEndpointRead();
                setReplaceAddress(true);
                setApiKey("");
                setRemoveKey(false);
                setProvider(
                  event.target.value as ModelConnectionView["provider"],
                );
              }}
              required
              value={provider}
            >
              <option value="">{copy.select}</option>
              <option value="ollama">Ollama</option>
              <option value="vllm">vLLM</option>
              <option value="openai_compatible">OpenAI-compatible</option>
            </select>
          </label>
          {editingId && (
            <CheckboxField
              id={`model-connection-replace-address${idSuffix}`}
              checked={replaceAddress}
              disabled={pending || providerChanged}
              onChange={(event) => {
                clearEndpointRead();
                setReplaceAddress(event.target.checked);
                setBaseUrl("");
                setApiKey("");
                setRemoveKey(false);
                if (event.target.checked) void readEndpoint();
              }}
            >
              {locale === "zh-TW" ? "更換服務網址" : "Replace the service URL"}
            </CheckboxField>
          )}
          {editingId && !replaceAddress && (
            <p>
              {locale === "zh-TW"
                ? "保留目前網址。勾選「更換服務網址」可載入原網址並修改；只改名稱不需要重新測試模型。"
                : "Keep the current URL. Select Replace the service URL to load and edit it. Renaming does not require a new model test."}
            </p>
          )}
          {replaceAddress && (
            <label htmlFor={`model-connection-address${idSuffix}`}>
              {copy.address}
              <input
                disabled={pending || endpointLoading}
                id={`model-connection-address${idSuffix}`}
                autoComplete="off"
                spellCheck={false}
                maxLength={2048}
                onChange={(event) => setBaseUrl(event.target.value)}
                required
                type="url"
                value={baseUrl}
              />
            </label>
          )}
          {endpointLoading && (
            <p role="status">
              {locale === "zh-TW"
                ? "正在讀取目前網址…"
                : "Loading the current URL…"}
            </p>
          )}
          {endpointError && (
            <div role="alert">
              <p>
                {locale === "zh-TW"
                  ? "無法讀取目前網址。你可以重試，或直接輸入新網址。"
                  : "Could not load the current URL. Retry or enter a new URL."}
              </p>
              <button
                type="button"
                onClick={() => void readEndpoint()}
                disabled={pending}
              >
                {locale === "zh-TW" ? "重新讀取網址" : "Reload URL"}
              </button>
            </div>
          )}
          {editingId && replaceAddress && (
            <p>
              {locale === "zh-TW"
                ? "更換網址或連線方式時，請填入此服務的新金鑰，或明確選擇移除金鑰。之後需要更新模型設定並重新測試。"
                : "When changing the URL or connection type, enter a new key for that service or explicitly remove the key. Then update and retest its model settings."}
            </p>
          )}
          <label htmlFor={`model-connection-key${idSuffix}`}>
            {copy.key}
            <input
              autoComplete="new-password"
              disabled={pending}
              id={`model-connection-key${idSuffix}`}
              maxLength={4096}
              onChange={(event) => {
                setApiKey(event.target.value);
                setRemoveKey(false);
              }}
              type="password"
              value={apiKey}
            />
          </label>
          {editingId &&
            (replaceAddress ||
              connections.find(
                (connection) => connection.connection_id === editingId,
              )?.key_configured) && (
              <CheckboxField
                labelClassName="model-connection-form__credential-option"
                checked={removeKey}
                disabled={pending}
                id={`model-connection-remove-key${idSuffix}`}
                onChange={(event) => {
                  setRemoveKey(event.target.checked);
                  setApiKey("");
                }}
              >
                {replaceAddress
                  ? locale === "zh-TW"
                    ? "新網址不使用金鑰（移除已儲存的金鑰）"
                    : "Use no key at the new URL (remove saved key)"
                  : copy.removeKey}
              </CheckboxField>
            )}
          <div className="model-connection-form__actions">
            <button disabled={pending || endpointLoading} type="submit">
              {editingId ? copy.update : copy.create}
            </button>
            {editingId && (
              <DeleteSettingButton
                locale={locale}
                name={
                  connections.find((item) => item.connection_id === editingId)
                    ?.display_name ?? displayName
                }
                kind="connection"
                pending={pending}
                onDelete={() => onDelete(editingId)}
              />
            )}
          </div>
          {error && editorOpen && <p role="alert">{error}</p>}
        </form>
      </ModelEditor>
    </section>
  );
}

function ConnectionMetadata({
  connection,
  copy,
}: {
  connection: ModelConnectionView;
  copy: (typeof COPY)[Locale];
}) {
  return (
    <dl>
      <dt>{copy.provider}</dt>
      <dd>{connection.provider}</dd>
      <dt>{copy.revision}</dt>
      <dd>{connection.revision}</dd>
      <dt>{copy.address}</dt>
      <dd>
        {connection.endpoint_configured ? copy.configured : copy.notConfigured}
      </dd>
      <dt>{copy.key}</dt>
      <dd>
        {connection.key_configured ? copy.configured : copy.notConfigured}
      </dd>
    </dl>
  );
}
