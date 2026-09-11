import { useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";

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
  base_url: string;
  api_key?: string;
  credential_action: "retain" | "replace" | "remove";
}

interface Props {
  locale: Locale;
  connections: ModelConnectionView[];
  pending: boolean;
  error: string;
  onRefresh: () => void;
  onCreate: (draft: ModelConnectionDraft) => void;
  onUpdate: (connectionId: string, draft: ModelConnectionDraft) => void;
  onDelete: (connectionId: string) => void;
}

const COPY = {
  "zh-TW": {
    heading: "模型連線",
    description:
      "先選擇服務，再輸入 API 位址與可選的 API key。已儲存的秘密只顯示是否已設定。",
    name: "名稱",
    provider: "服務",
    address: "API 位址",
    key: "API key（可選）",
    create: "儲存連線",
    refresh: "重新整理",
    empty: "尚無模型連線。",
    configured: "已設定",
    notConfigured: "未設定",
    remove: "刪除",
    select: "選擇服務",
    pending: "正在處理模型連線…",
  },
  en: {
    heading: "Model connections",
    description:
      "Choose a service, then enter its API address and optional API key. Saved secrets show only whether they are configured.",
    name: "Name",
    provider: "Service",
    address: "API address",
    key: "API key (optional)",
    create: "Save connection",
    update: "Update connection",
    cancel: "Cancel",
    edit: "Edit",
    removeKey: "Remove saved key",
    refresh: "Refresh",
    empty: "No model connections yet.",
    configured: "Configured",
    notConfigured: "Not configured",
    remove: "Delete",
    select: "Select a service",
    pending: "Working on model connections…",
  },
} as const;

export function ModelConnectionPanel({
  locale,
  connections,
  pending,
  error,
  onRefresh,
  onCreate,
  onUpdate,
  onDelete,
}: Props) {
  const copy = COPY[locale];
  const editLabel = "edit" in copy ? copy.edit : "編輯";
  const updateLabel = "update" in copy ? copy.update : "更新連線";
  const cancelLabel = "cancel" in copy ? copy.cancel : "取消";
  const removeKeyLabel =
    "removeKey" in copy ? copy.removeKey : "移除已儲存的 key";
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState<
    "" | ModelConnectionView["provider"]
  >("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [removeKey, setRemoveKey] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!provider || !displayName.trim() || !baseUrl.trim()) return;
    const draft = {
      display_name: displayName.trim(),
      provider,
      base_url: baseUrl.trim(),
      api_key: removeKey || !apiKey ? undefined : apiKey,
      credential_action: removeKey ? "remove" : apiKey ? "replace" : "retain",
    } satisfies ModelConnectionDraft;
    if (editingId) onUpdate(editingId, draft);
    else onCreate(draft);
    setApiKey("");
    setRemoveKey(false);
    setEditingId(null);
  }

  function edit(connection: ModelConnectionView) {
    setEditingId(connection.connection_id);
    setDisplayName(connection.display_name);
    setProvider(connection.provider);
    setBaseUrl("");
    setApiKey("");
    setRemoveKey(false);
  }

  function cancelEdit() {
    setEditingId(null);
    setDisplayName("");
    setProvider("");
    setBaseUrl("");
    setApiKey("");
    setRemoveKey(false);
  }

  return (
    <section aria-labelledby="model-connection-heading">
      <h2 id="model-connection-heading">{copy.heading}</h2>
      <p>{copy.description}</p>
      <button disabled={pending} onClick={onRefresh} type="button">
        {copy.refresh}
      </button>
      {pending && <p role="status">{copy.pending}</p>}
      {error && <p role="alert">{error}</p>}
      {connections.length === 0 ? (
        <p>{copy.empty}</p>
      ) : (
        <ul>
          {connections.map((connection) => (
            <li key={connection.connection_id}>
              <strong>{connection.display_name}</strong>
              <dl>
                <dt>{copy.provider}</dt>
                <dd>{connection.provider}</dd>
                <dt>Revision</dt>
                <dd>{connection.revision}</dd>
                <dt>{copy.address}</dt>
                <dd>
                  {connection.endpoint_configured
                    ? copy.configured
                    : copy.notConfigured}
                </dd>
                <dt>{copy.key}</dt>
                <dd>
                  {connection.key_configured
                    ? copy.configured
                    : copy.notConfigured}
                </dd>
              </dl>
              {connection.source === "managed" && (
                <>
                  <button
                    disabled={pending}
                    onClick={() => edit(connection)}
                    type="button"
                  >
                    {editLabel}
                  </button>
                  <button
                    disabled={pending}
                    onClick={() => onDelete(connection.connection_id)}
                    type="button"
                  >
                    {copy.remove}
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit}>
        <label htmlFor="model-connection-name">
          {copy.name}
          <input
            disabled={pending}
            id="model-connection-name"
            maxLength={120}
            onChange={(event) => setDisplayName(event.target.value)}
            required
            value={displayName}
          />
        </label>
        <label htmlFor="model-connection-provider">
          {copy.provider}
          <select
            disabled={pending}
            id="model-connection-provider"
            onChange={(event) =>
              setProvider(event.target.value as ModelConnectionView["provider"])
            }
            required
            value={provider}
          >
            <option value="">{copy.select}</option>
            <option value="ollama">Ollama</option>
            <option value="vllm">vLLM</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
        </label>
        <label htmlFor="model-connection-address">
          {copy.address}
          <input
            disabled={pending}
            id="model-connection-address"
            maxLength={2048}
            onChange={(event) => setBaseUrl(event.target.value)}
            required
            type="url"
            value={baseUrl}
          />
        </label>
        <label htmlFor="model-connection-key">
          {copy.key}
          <input
            autoComplete="new-password"
            disabled={pending}
            id="model-connection-key"
            maxLength={4096}
            onChange={(event) => setApiKey(event.target.value)}
            type="password"
            value={apiKey}
          />
        </label>
        {editingId &&
          connections.find(
            (connection) => connection.connection_id === editingId,
          )?.key_configured && (
            <label htmlFor="model-connection-remove-key">
              <input
                checked={removeKey}
                disabled={pending}
                id="model-connection-remove-key"
                onChange={(event) => setRemoveKey(event.target.checked)}
                type="checkbox"
              />
              {removeKeyLabel}
            </label>
          )}
        <button disabled={pending} type="submit">
          {editingId ? updateLabel : copy.create}
        </button>
        {editingId && (
          <button disabled={pending} onClick={cancelEdit} type="button">
            {cancelLabel}
          </button>
        )}
      </form>
    </section>
  );
}
