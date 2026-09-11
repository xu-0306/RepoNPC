import { useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";
import type { ModelConnectionView } from "./ModelConnectionPanel";

export interface ChatProfileView {
  profile_id: string;
  connection_id: string;
  connection_revision: number;
  model_id: string;
  status: string;
  active: boolean;
  observed_model_id: string | null;
  last_error_code: string | null;
  last_probed_at: string | null;
}

export interface ChatProfileDraft {
  connection_id: string;
  model_id: string;
}

interface Props {
  locale: Locale;
  connections: ModelConnectionView[];
  profiles: ChatProfileView[];
  pending: boolean;
  error: string;
  onRefresh: () => void;
  onCreate: (draft: ChatProfileDraft) => void;
  onUpdate: (profileId: string, draft: ChatProfileDraft) => void;
  onProbe: (profileId: string) => void;
  onActivate: (profileId: string) => void;
  onDelete: (profileId: string) => void;
}

const COPY = {
  "zh-TW": {
    heading: "Chat 模型",
    description: "選擇已設定的服務與模型，測試成功後才會切換目前使用的 Chat。",
    connection: "服務",
    model: "模型",
    select: "選擇服務",
    create: "新增待測模型",
    update: "更新模型",
    edit: "編輯",
    cancel: "取消",
    refresh: "重新整理",
    probe: "測試連線",
    activate: "啟用",
    remove: "刪除",
    active: "目前使用",
    empty: "尚未設定 Chat 模型。",
    noConnections: "請先設定一個模型服務。",
    pending: "正在處理 Chat 模型…",
    revision: "設定版本",
    status: "狀態",
    lastProbe: "最近測試",
  },
  en: {
    heading: "Chat models",
    description:
      "Choose a configured service and model. A successful test is required before Chat switches.",
    connection: "Service",
    model: "Model",
    select: "Select a service",
    create: "Add model to test",
    update: "Update model",
    edit: "Edit",
    cancel: "Cancel",
    refresh: "Refresh",
    probe: "Test connection",
    activate: "Use for Chat",
    remove: "Delete",
    active: "In use",
    empty: "No Chat models configured yet.",
    noConnections: "Configure a model service first.",
    pending: "Working on Chat models…",
    revision: "Connection revision",
    status: "Status",
    lastProbe: "Last test",
  },
} as const;

function connectionLabel(
  connections: ModelConnectionView[],
  connectionId: string,
): string {
  return (
    connections.find((connection) => connection.connection_id === connectionId)
      ?.display_name ?? connectionId
  );
}

export function ChatProfilePanel({
  locale,
  connections,
  profiles,
  pending,
  error,
  onRefresh,
  onCreate,
  onUpdate,
  onProbe,
  onActivate,
  onDelete,
}: Props) {
  const copy = COPY[locale];
  const [connectionId, setConnectionId] = useState("");
  const [modelId, setModelId] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!connectionId || !modelId.trim()) return;
    const draft = { connection_id: connectionId, model_id: modelId.trim() };
    if (editingId) onUpdate(editingId, draft);
    else onCreate(draft);
    setModelId("");
    setConnectionId("");
    setEditingId(null);
  }

  function edit(profile: ChatProfileView) {
    setEditingId(profile.profile_id);
    setConnectionId(profile.connection_id);
    setModelId(profile.model_id);
  }

  function cancelEdit() {
    setEditingId(null);
    setConnectionId("");
    setModelId("");
  }

  return (
    <section aria-labelledby="chat-profile-heading">
      <h2 id="chat-profile-heading">{copy.heading}</h2>
      <p>{copy.description}</p>
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
                <dt>{copy.connection}</dt>
                <dd>{connectionLabel(connections, profile.connection_id)}</dd>
                <dt>{copy.revision}</dt>
                <dd>{profile.connection_revision}</dd>
                <dt>{copy.status}</dt>
                <dd>{profile.status}</dd>
                {profile.last_probed_at && (
                  <>
                    <dt>{copy.lastProbe}</dt>
                    <dd>{profile.last_probed_at}</dd>
                  </>
                )}
              </dl>
              {profile.active && <strong>{copy.active}</strong>}
              {profile.last_error_code && (
                <p role="alert">{profile.last_error_code}</p>
              )}
              {!profile.active && (
                <button
                  disabled={pending}
                  onClick={() => edit(profile)}
                  type="button"
                >
                  {copy.edit}
                </button>
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
            </li>
          ))}
        </ul>
      )}
      {connections.length === 0 ? (
        <p>{copy.noConnections}</p>
      ) : (
        <form onSubmit={submit}>
          <label htmlFor="chat-profile-connection">
            {copy.connection}
            <select
              disabled={pending}
              id="chat-profile-connection"
              onChange={(event) => setConnectionId(event.target.value)}
              required
              value={connectionId}
            >
              <option value="">{copy.select}</option>
              {connections.map((connection) => (
                <option
                  key={connection.connection_id}
                  value={connection.connection_id}
                >
                  {connection.display_name}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor="chat-profile-model">
            {copy.model}
            <input
              disabled={pending}
              id="chat-profile-model"
              maxLength={256}
              onChange={(event) => setModelId(event.target.value)}
              required
              value={modelId}
            />
          </label>
          <button disabled={pending} type="submit">
            {editingId ? copy.update : copy.create}
          </button>
          {editingId && (
            <button disabled={pending} onClick={cancelEdit} type="button">
              {copy.cancel}
            </button>
          )}
        </form>
      )}
    </section>
  );
}
