import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import type { Locale } from "../../i18n/messages";
import { ModelBrandIcon } from "./ModelBrandIcon";
import { ModelEditor } from "./ModelEditor";
import { modelProbeError } from "./modelProbeError";
import { DeleteSettingButton } from "./DeleteSettingButton";
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
  last_error_message?: string | null;
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
  notice?: string;
  pendingProfileId?: string | null;
  onRefresh: () => void;
  onCreate: (draft: ChatProfileDraft) => void;
  onUpdate: (profileId: string, draft: ChatProfileDraft) => void;
  onProbe: (profileId: string) => void;
  onActivate: (profileId: string) => void;
  onDelete: (profileId: string) => void;
  managementActions?: boolean;
}

const COPY = {
  "zh-TW": {
    heading: "分析與回答模型",
    guidedHeading: "新增與測試模型",
    description: "負責整理專案內容並產生回答；測試成功後才能選用。",
    guidedDescription:
      "選擇服務、填入模型名稱，再按「測試模型」。通過後到「確認分析模型」選用。",
    add: "新增模型",
    connection: "服務",
    model: "模型",
    select: "選擇服務",
    create: "新增模型",
    update: "更新模型",
    edit: "編輯",
    cancel: "取消",
    refresh: "重新整理",
    probe: "測試模型",
    activate: "啟用",
    remove: "刪除",
    active: "目前使用",
    empty: "還沒有回答模型。請先新增模型，再測試是否可用。",
    noConnections: "請先設定一個模型服務。",
    pending: "正在處理回答模型…",
    revision: "設定版本",
    status: "狀態",
    lastProbe: "最近測試",
    technical: "技術資訊",
    errorCode: "錯誤代碼",
  },
  en: {
    heading: "Analysis and answer models",
    guidedHeading: "Add and test models",
    description:
      "Organizes project content and generates answers. A successful test is required before selection.",
    guidedDescription:
      "Choose a service, enter its model name, and test the model. Then use Confirm analysis models to select it.",
    add: "Add model",
    connection: "Service",
    model: "Model",
    select: "Select a service",
    create: "Add model",
    update: "Update model",
    edit: "Edit",
    cancel: "Cancel",
    refresh: "Refresh",
    probe: "Test model",
    activate: "Use for Chat",
    remove: "Delete",
    active: "In use",
    empty: "No Chat models configured yet.",
    noConnections: "Configure a model service first.",
    pending: "Working on Chat models…",
    revision: "Connection revision",
    status: "Status",
    lastProbe: "Last test",
    technical: "Technical details",
    errorCode: "Error code",
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
  if (!connection) return connectionId;
  if (connection.source === "host-managed") {
    return locale === "zh-TW"
      ? "環境預設連線（回答）"
      : "Environment connection (answers)";
  }
  return connection.display_name;
}

export function ChatProfilePanel({
  locale,
  connections,
  profiles,
  pending,
  error,
  notice,
  pendingProfileId,
  onRefresh,
  onCreate,
  onUpdate,
  onProbe,
  onActivate,
  onDelete,
  managementActions = true,
}: Props) {
  const copy = COPY[locale];
  const editorRef = useRef<HTMLDetailsElement>(null);
  const [connectionId, setConnectionId] = useState("");
  const [modelId, setModelId] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  useEffect(() => {
    if (editingId && !profiles.some((item) => item.profile_id === editingId)) {
      cancelEdit();
      if (editorRef.current) {
        editorRef.current.open = false;
        editorRef.current.querySelector("summary")?.focus();
      }
    }
  }, [profiles, editingId]);
  const Heading = managementActions ? "h2" : "h4";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!connectionId || !modelId.trim()) return;
    const draft = { connection_id: connectionId, model_id: modelId.trim() };
    if (editingId) onUpdate(editingId, draft);
    else onCreate(draft);
  }

  function edit(profile: ChatProfileView) {
    if (editorRef.current) {
      editorRef.current.open = true;
      editorRef.current.querySelector("select")?.focus();
    }
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
    <section
      aria-labelledby="chat-profile-heading"
      className="model-panel model-panel--chat"
    >
      <Heading id="chat-profile-heading">
        {managementActions ? copy.heading : copy.guidedHeading}
      </Heading>
      <p>{managementActions ? copy.description : copy.guidedDescription}</p>
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
                  provider={
                    connections.find(
                      (connection) =>
                        connection.connection_id === profile.connection_id,
                    )?.provider
                  }
                />
                <strong>{profile.model_id}</strong>
                <span className="model-card__provider">
                  {profile.last_error_code
                    ? locale === "zh-TW"
                      ? "測試失敗"
                      : "Test failed"
                    : profile.status === "ready"
                      ? locale === "zh-TW"
                        ? "測試通過"
                        : "Test passed"
                      : locale === "zh-TW"
                        ? "待測試"
                        : "Needs test"}
                </span>
              </div>
              <dl>
                <dt>{copy.connection}</dt>
                <dd>
                  {connectionLabel(connections, profile.connection_id, locale)}
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
              {!profile.active && (
                <button
                  disabled={pending}
                  aria-label={`${copy.edit} ${profile.model_id} · ${connectionLabel(connections, profile.connection_id, locale)}`}
                  onClick={() => edit(profile)}
                  type="button"
                >
                  {copy.edit}
                </button>
              )}
              <button
                disabled={pending}
                aria-label={`${copy.probe} ${profile.model_id} · ${connectionLabel(connections, profile.connection_id, locale)}`}
                onClick={() => onProbe(profile.profile_id)}
                type="button"
              >
                {pending && pendingProfileId === profile.profile_id
                  ? locale === "zh-TW"
                    ? "正在測試…"
                    : "Testing…"
                  : copy.probe}
              </button>
              {managementActions && !profile.active && (
                <>
                  <button
                    disabled={pending || profile.status !== "ready"}
                    onClick={() => onActivate(profile.profile_id)}
                    type="button"
                  >
                    {copy.activate}
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
                    : undefined
                }
                onDelete={() => onDelete(profile.profile_id)}
              />
              <details className="model-card__technical">
                <summary>{copy.technical}</summary>
                <dl>
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
        <p>{copy.noConnections}</p>
      ) : (
        <ModelEditor
          label={editingId ? copy.update : copy.add}
          onClose={cancelEdit}
          cancel={copy.cancel}
          editorRef={editorRef}
          pending={pending}
          error={error}
        >
          <form onSubmit={submit}>
            <h3>{editingId ? copy.update : copy.add}</h3>
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
                    {connectionLabel(
                      connections,
                      connection.connection_id,
                      locale,
                    )}
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
            <p>
              {locale === "zh-TW"
                ? "模型名稱請從服務商複製。新增只會儲存設定；按「測試模型」才會連線，服務商可能計費。"
                : "Copy the model name from your provider. Adding only saves the settings; testing connects to the service and may incur provider charges."}
            </p>
          </form>
        </ModelEditor>
      )}
    </section>
  );
}
