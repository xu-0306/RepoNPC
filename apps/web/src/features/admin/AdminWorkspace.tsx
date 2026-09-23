import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";

import { Base64PngCanvas } from "./Base64PngCanvas";
import {
  ADMIN_UI_SCALES,
  applyAdminUiScale,
  persistAdminUiScale,
  readAdminUiScale,
  type AdminUiScale,
} from "./adminUiScale";

export type AdminLocale = "zh-TW" | "en";
export type AdminWorkspaceMode =
  | "guided"
  | "character"
  | "publish"
  | "advanced";

export interface ValidationIssue {
  path: string;
  code?: string;
  message: string;
  severity?: "error" | "warning";
}

export interface AdminValidation {
  valid?: boolean;
  errors?: ValidationIssue[];
  warnings?: ValidationIssue[];
  parsed?: Record<string, unknown>;
}

export interface PreviewProfile {
  display_name: string;
  headline: string;
  bio: string;
  greeting?: string;
}

export interface PreviewCharacter {
  mode: string;
  revision: number;
  png_base64?: string;
  sha256?: string;
}

export interface PreviewCard {
  png_base64?: string;
  svg_base64?: string;
  gif_base64?: string;
}

export interface AdminPreview {
  repositories?: Array<{
    slug: string;
    role: Record<string, string>;
    summary: Record<string, string>;
    claims: Array<{ id: string; statement: Record<string, string> }>;
  }>;
  profile?: Record<string, PreviewProfile> | PreviewProfile;
  character?: PreviewCharacter;
  cards?: Record<string, PreviewCard>;
}

export interface AdminStatus {
  active_bundle_id?: string | null;
  previous_bundle_id?: string | null;
  pinned_bundle_id?: string | null;
  last_checked_at?: string | null;
  update_error?: string | null;
}

export interface AdminSnippet {
  markdown: string;
  asset_url?: string;
  target_url?: string;
}

export interface AdminConflict {
  current_blob_sha?: string;
  message?: string;
}

export interface AdminWorkspaceProps {
  locale: AdminLocale;
  draft: string;
  validation: AdminValidation | null;
  preview: AdminPreview | null;
  status: AdminStatus | null;
  snippet: AdminSnippet | string | null;
  conflict: boolean | AdminConflict | null;
  busy: boolean;
  authenticated: boolean;
  githubOperationsReady: boolean;
  notice: string;
  onDraftChange: (draft: string) => void;
  onValidate: () => void;
  onPreview: () => void;
  onSave: () => void;
  onCopy: () => void;
  onDispatch: () => void;
  onLogout: () => void;
  onLocaleChange?: (locale: AdminLocale) => void;
  guidedView?: ReactNode;
  embeddingProfileView?: ReactNode;
  characterAssetView?: ReactNode;
  publicationView?: ReactNode;
  workspaceMode?: AdminWorkspaceMode;
  onWorkspaceModeChange?: (mode: AdminWorkspaceMode) => void;
}

const COPY = {
  "zh-TW": {
    title: "RepoNPC 管理工作區",
    subtitle: "設定 AI 模型與資料來源，打造專屬的知識庫問答助手。",
    guideMessage: "跟著步驟設定，很快就能完成囉！",
    help: "使用說明",
    administrator: "管理員",
    language: "介面語言",
    displaySettings: "顯示設定",
    interfaceSize: "介面大小",
    scaleLabels: {
      standard: "標準（100%）",
      comfortable: "舒適（預設，112.5%）",
      large: "大型（125%）",
    },
    authRequired: "請先登入管理員工作階段，才能編輯公開設定。",
    draftHeading: "公開設定草稿",
    draftLabel: "reponpc.yml 原始 YAML",
    draftHelp: "這份草稿尚未寫入 GitHub。儲存前請先驗證內容。",
    validate: "驗證設定",
    preview: "預覽變更",
    save: "儲存到 GitHub",
    logout: "登出",
    validationHeading: "驗證結果",
    valid: "設定驗證通過。",
    invalid: "設定驗證失敗，請修正下列欄位。",
    errors: "錯誤",
    warnings: "警告",
    noIssues: "目前沒有欄位錯誤或警告。",
    previewHeading: "未儲存預覽",
    unsaved: "以下內容只代表目前草稿，尚未寫入公開設定。",
    profile: "個人檔案",
    character: "角色",
    cards: "卡片",
    cardAlt: "未儲存的 RepoNPC 卡片預覽",
    characterAlt: "未儲存的角色預覽",
    previewFailed: "圖片預覽無法顯示，請重新產生預覽。",
    statusHeading: "發布狀態",
    activeBundle: "目前網站資料版本",
    previousBundle: "上一個網站資料版本",
    pinnedBundle: "固定使用的資料版本",
    lastChecked: "上次檢查",
    updateError: "更新錯誤",
    none: "無",
    dispatch: "要求重新發布索引",
    snippetHeading: "README 複製片段",
    snippetLabel: "可直接貼上的 Markdown",
    copy: "複製片段",
    conflict: "設定已在其他地方變更；為避免覆寫，儲存已停用。",
    busy: "處理中…",
    copyReady: "片段已準備好。",
    guidedMode: "引導設定",
    characterMode: "角色與動畫",
    advancedMode: "進階：編輯原始 YAML",
  },
  en: {
    title: "RepoNPC admin workspace",
    subtitle:
      "Set up AI models and sources for your evidence-backed portfolio assistant.",
    guideMessage: "Follow the steps—you'll have a working draft soon.",
    help: "Setup guide",
    administrator: "Administrator",
    language: "Interface language",
    displaySettings: "Display settings",
    interfaceSize: "Interface size",
    scaleLabels: {
      standard: "Standard (100%)",
      comfortable: "Comfortable (default, 112.5%)",
      large: "Large (125%)",
    },
    authRequired:
      "Sign in to an admin session before editing public configuration.",
    draftHeading: "Public configuration draft",
    draftLabel: "Raw reponpc.yml YAML",
    draftHelp:
      "This draft has not been written to GitHub. Validate it before saving.",
    validate: "Validate configuration",
    preview: "Preview changes",
    save: "Save to GitHub",
    logout: "Log out",
    validationHeading: "Validation result",
    valid: "Configuration validation passed.",
    invalid: "Configuration validation failed. Fix the fields below.",
    errors: "Errors",
    warnings: "Warnings",
    noIssues: "There are no field errors or warnings.",
    previewHeading: "Unsaved preview",
    unsaved:
      "This preview represents the current draft only; it is not published.",
    profile: "Profile",
    character: "Character",
    cards: "Cards",
    cardAlt: "Unsaved RepoNPC card preview",
    characterAlt: "Unsaved character preview",
    previewFailed:
      "The image preview could not be shown. Generate the preview again.",
    statusHeading: "Publication status",
    activeBundle: "Current website data version",
    previousBundle: "Previous website data version",
    pinnedBundle: "Pinned website data version",
    lastChecked: "Last checked",
    updateError: "Update error",
    none: "None",
    dispatch: "Request index publication",
    snippetHeading: "README copy snippet",
    snippetLabel: "Markdown ready to paste",
    copy: "Copy snippet",
    conflict:
      "The configuration changed elsewhere; saving is disabled to prevent an overwrite.",
    busy: "Working…",
    copyReady: "Snippet is ready.",
    guidedMode: "Guided setup",
    characterMode: "Character & animation",
    advancedMode: "Advanced: edit raw YAML",
  },
} as const;

function isConflict(conflict: AdminWorkspaceProps["conflict"]): boolean {
  return Boolean(conflict);
}

function issueList(
  issues: ValidationIssue[] | undefined,
  defaultSeverity: "error" | "warning",
): ValidationIssue[] {
  return (issues ?? []).map((issue) => ({
    ...issue,
    severity: issue.severity ?? defaultSeverity,
  }));
}

function profileForLocale(
  profile: AdminPreview["profile"],
  locale: AdminLocale,
): PreviewProfile | null {
  if (!profile) return null;
  if (typeof (profile as PreviewProfile).display_name === "string") {
    return profile as PreviewProfile;
  }
  const localized = profile as Record<string, PreviewProfile>;
  return localized[locale] ?? null;
}

function snippetText(snippet: AdminWorkspaceProps["snippet"]): string {
  return typeof snippet === "string" ? snippet : (snippet?.markdown ?? "");
}

function cardEntries(
  cards: AdminPreview["cards"],
): Array<[string, PreviewCard]> {
  return cards
    ? Object.entries(cards).filter((entry): entry is [string, PreviewCard] =>
        Boolean(entry[1]),
      )
    : [];
}

export function AdminWorkspace({
  locale,
  draft,
  validation,
  preview,
  status,
  snippet,
  conflict,
  busy,
  authenticated,
  githubOperationsReady,
  notice,
  onDraftChange,
  onValidate,
  onPreview,
  onSave,
  onCopy,
  onDispatch,
  onLogout,
  onLocaleChange,
  guidedView,
  embeddingProfileView,
  characterAssetView,
  publicationView,
  workspaceMode = guidedView ? "guided" : "advanced",
  onWorkspaceModeChange,
}: AdminWorkspaceProps) {
  const copy = COPY[locale];
  const [uiScale, setUiScale] = useState<AdminUiScale>(readAdminUiScale);
  const displaySettingsRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    function closeOutside(event: PointerEvent) {
      const panel = displaySettingsRef.current;
      if (
        panel?.open &&
        event.target instanceof Node &&
        !panel.contains(event.target)
      )
        panel.open = false;
    }
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);
  const errors = issueList(validation?.errors, "error");
  const warnings = issueList(validation?.warnings, "warning");
  const hasConflict = isConflict(conflict);
  const saveDisabled =
    !authenticated ||
    !githubOperationsReady ||
    busy ||
    hasConflict ||
    validation?.valid !== true;
  const profile = profileForLocale(preview?.profile, locale);
  const snippetValue = snippetText(snippet);
  const dispatchDisabled = !authenticated || !githubOperationsReady || busy;

  useEffect(() => {
    applyAdminUiScale(uiScale);
    persistAdminUiScale(uiScale);
  }, [uiScale]);

  function handleDraftChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onDraftChange(event.target.value);
  }

  return (
    <main aria-busy={busy} className="admin-workspace" lang={locale}>
      <header className="admin-workspace__header">
        <div className="admin-workspace__brand">
          <h1 className="admin-workspace__title">{copy.title}</h1>
          <p className="admin-workspace__subtitle">{copy.subtitle}</p>
        </div>
        <div className="admin-workspace__guide" aria-hidden="true">
          <span className="admin-workspace__npc">
            <span />
          </span>
          <span className="admin-workspace__speech">{copy.guideMessage}</span>
        </div>
        <div className="admin-workspace__utilities">
          {onLocaleChange && (
            <div
              aria-label={copy.language}
              className="admin-workspace__locale"
              role="group"
            >
              {(["zh-TW", "en"] as const).map((option) => (
                <button
                  aria-label={option === "zh-TW" ? "繁體中文" : "English"}
                  aria-pressed={locale === option}
                  key={option}
                  onClick={() => onLocaleChange(option)}
                  type="button"
                >
                  {option === "zh-TW" ? "中" : "EN"}
                </button>
              ))}
            </div>
          )}
          <details
            className="admin-display-settings"
            ref={displaySettingsRef}
            onKeyDown={(event) => {
              if (event.key === "Escape" && event.currentTarget.open) {
                event.preventDefault();
                event.currentTarget.open = false;
                event.currentTarget.querySelector("summary")?.focus();
              }
            }}
          >
            <summary aria-label={copy.displaySettings}>
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M4 7h10M18 7h2M10 17h10M4 17h2M14 4v6M10 14v6" />
              </svg>
              <span>{copy.displaySettings}</span>
            </summary>
            <div className="admin-display-settings__panel">
              <label htmlFor="admin-interface-scale">
                {copy.interfaceSize}
                <select
                  disabled={busy}
                  id="admin-interface-scale"
                  onChange={(event) =>
                    setUiScale(event.target.value as AdminUiScale)
                  }
                  value={uiScale}
                >
                  {ADMIN_UI_SCALES.map((scale) => (
                    <option key={scale} value={scale}>
                      {copy.scaleLabels[scale]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </details>
          <a
            className="admin-workspace__help"
            href={
              workspaceMode === "advanced"
                ? "#admin-draft-heading"
                : workspaceMode === "character"
                  ? "#admin-character-converter-heading"
                  : "#guided-onboarding-heading"
            }
          >
            <span aria-hidden="true">?</span>
            {copy.help}
          </a>
          {authenticated && (
            <>
              <span className="admin-workspace__owner">
                <span aria-hidden="true">R</span>
                {copy.administrator}
              </span>
              <button
                className="admin-workspace__logout"
                disabled={busy}
                onClick={onLogout}
                type="button"
              >
                {copy.logout}
              </button>
            </>
          )}
        </div>
      </header>

      {guidedView && (
        <nav aria-label={copy.title} className="admin-workspace__mode-switch">
          <button
            aria-pressed={workspaceMode === "guided"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("guided")}
            type="button"
          >
            {copy.guidedMode}
          </button>
          <button
            aria-pressed={workspaceMode === "character"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("character")}
            type="button"
          >
            {copy.characterMode}
          </button>
          {publicationView && (
            <button
              type="button"
              aria-pressed={workspaceMode === "publish"}
              onClick={() => onWorkspaceModeChange?.("publish")}
            >
              {locale === "zh-TW" ? "預覽與分享" : "Preview & share"}
            </button>
          )}
          <button
            aria-pressed={workspaceMode === "advanced"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("advanced")}
            type="button"
          >
            {copy.advancedMode}
          </button>
        </nav>
      )}

      {notice && (!guidedView || workspaceMode !== "guided") && (
        <p className="admin-workspace__notice" role="alert">
          {notice}
        </p>
      )}

      {authenticated &&
        (!guidedView || workspaceMode === "advanced") &&
        embeddingProfileView}

      {authenticated && workspaceMode === "character" && characterAssetView}

      {!authenticated && (
        <p role="alert" className="admin-workspace__auth-message">
          {copy.authRequired}
        </p>
      )}

      {guidedView && workspaceMode === "guided" && guidedView}
      {authenticated && workspaceMode === "publish" && publicationView}

      {(!guidedView || workspaceMode === "advanced") && (
        <>
          <section
            aria-labelledby="admin-draft-heading"
            className="admin-surface"
          >
            <h2 id="admin-draft-heading">{copy.draftHeading}</h2>
            <label htmlFor="admin-config-draft">{copy.draftLabel}</label>
            <p id="admin-draft-help">{copy.draftHelp}</p>
            <textarea
              aria-describedby="admin-draft-help"
              disabled={!authenticated || busy}
              id="admin-config-draft"
              onChange={handleDraftChange}
              rows={18}
              value={draft}
            />
            <div
              className="admin-workspace__actions"
              aria-label={copy.draftHeading}
            >
              <button
                disabled={!authenticated || busy}
                onClick={onValidate}
                type="button"
              >
                {copy.validate}
              </button>
              <button
                disabled={!authenticated || busy}
                onClick={onPreview}
                type="button"
              >
                {copy.preview}
              </button>
              <button
                aria-describedby={hasConflict ? "admin-conflict" : undefined}
                disabled={saveDisabled}
                onClick={onSave}
                type="button"
              >
                {copy.save}
              </button>
            </div>
            {busy && <p role="status">{copy.busy}</p>}
          </section>

          <section
            aria-labelledby="admin-validation-heading"
            className="admin-surface"
          >
            <h2 id="admin-validation-heading">{copy.validationHeading}</h2>
            {validation?.valid === true && errors.length === 0 && (
              <p role="status">{copy.valid}</p>
            )}
            {validation?.valid === false && <p role="alert">{copy.invalid}</p>}
            {errors.length > 0 && (
              <IssueList heading={copy.errors} issues={errors} role="alert" />
            )}
            {warnings.length > 0 && (
              <IssueList
                heading={copy.warnings}
                issues={warnings}
                role="status"
              />
            )}
            {validation &&
              errors.length === 0 &&
              warnings.length === 0 &&
              validation.valid !== false && <p>{copy.noIssues}</p>}
          </section>

          {hasConflict && (
            <p
              id="admin-conflict"
              role="alert"
              className="admin-workspace__conflict"
            >
              {conflict && typeof conflict === "object" && conflict.message
                ? conflict.message
                : copy.conflict}
            </p>
          )}

          {preview && (
            <section
              aria-labelledby="admin-preview-heading"
              className="admin-surface"
            >
              <h2 id="admin-preview-heading">{copy.previewHeading}</h2>
              <p role="status">{copy.unsaved}</p>
              {profile && (
                <article aria-labelledby="admin-preview-profile-heading">
                  <h3 id="admin-preview-profile-heading">{copy.profile}</h3>
                  <h4>{profile.display_name}</h4>
                  <p>{profile.headline}</p>
                  <p>{profile.bio}</p>
                  {profile.greeting && <p>{profile.greeting}</p>}
                </article>
              )}
              {preview.character?.png_base64 && (
                <article aria-labelledby="admin-preview-character-heading">
                  <h3 id="admin-preview-character-heading">{copy.character}</h3>
                  <p>{preview.character.mode}</p>
                  <Base64PngCanvas
                    failureText={copy.previewFailed}
                    height={448}
                    label={copy.characterAlt}
                    pngBase64={preview.character.png_base64}
                    width={256}
                  />
                </article>
              )}
              {cardEntries(preview.cards).length > 0 && (
                <article aria-labelledby="admin-preview-cards-heading">
                  <h3 id="admin-preview-cards-heading">{copy.cards}</h3>
                  <ul>
                    {cardEntries(preview.cards).map(([variant, card]) =>
                      card.png_base64 ? (
                        <li key={variant}>
                          <figure>
                            <figcaption>{variant}</figcaption>
                            <Base64PngCanvas
                              failureText={copy.previewFailed}
                              height={180}
                              label={`${copy.cardAlt}: ${variant}`}
                              pngBase64={card.png_base64}
                              width={600}
                            />
                          </figure>
                        </li>
                      ) : null,
                    )}
                  </ul>
                </article>
              )}
            </section>
          )}

          <section
            aria-labelledby="admin-status-heading"
            className="admin-surface"
          >
            <h2 id="admin-status-heading">{copy.statusHeading}</h2>
            <dl>
              <StatusRow
                label={copy.activeBundle}
                value={status?.active_bundle_id}
                fallback={copy.none}
              />
              <StatusRow
                label={copy.previousBundle}
                value={status?.previous_bundle_id}
                fallback={copy.none}
              />
              <StatusRow
                label={copy.pinnedBundle}
                value={status?.pinned_bundle_id}
                fallback={copy.none}
              />
              <StatusRow
                label={copy.lastChecked}
                value={status?.last_checked_at}
                fallback={copy.none}
              />
              <StatusRow
                label={copy.updateError}
                value={status?.update_error}
                fallback={copy.none}
              />
            </dl>
            <button
              disabled={dispatchDisabled}
              onClick={onDispatch}
              type="button"
            >
              {copy.dispatch}
            </button>
          </section>

          {snippetValue && (
            <section
              aria-labelledby="admin-snippet-heading"
              className="admin-surface"
            >
              <h2 id="admin-snippet-heading">{copy.snippetHeading}</h2>
              <label htmlFor="admin-readme-snippet">{copy.snippetLabel}</label>
              <textarea
                id="admin-readme-snippet"
                readOnly
                rows={4}
                value={snippetValue}
              />
              <button disabled={busy} onClick={onCopy} type="button">
                {copy.copy}
              </button>
              <p role="status">{copy.copyReady}</p>
            </section>
          )}
        </>
      )}
    </main>
  );
}

function IssueList({
  heading,
  issues,
  role,
}: {
  heading: string;
  issues: ValidationIssue[];
  role: "alert" | "status";
}) {
  return (
    <div aria-label={heading} role={role}>
      <h3>{heading}</h3>
      <ul>
        {issues.map((issue, index) => (
          <li key={`${issue.path}-${issue.code ?? "issue"}-${index}`}>
            <strong>{issue.path}</strong>: {issue.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

function StatusRow({
  label,
  value,
  fallback,
}: {
  label: string;
  value: unknown;
  fallback: string;
}) {
  const text = typeof value === "string" && value.length > 0 ? value : fallback;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{text}</dd>
    </div>
  );
}
