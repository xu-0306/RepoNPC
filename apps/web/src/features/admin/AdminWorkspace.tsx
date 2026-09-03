import type { ChangeEvent, ReactNode } from "react";

export type AdminLocale = "zh-TW" | "en";

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
  guidedView?: ReactNode;
  githubConnectionView?: ReactNode;
  embeddingProfileView?: ReactNode;
  advancedMode?: boolean;
  onAdvancedModeChange?: (advanced: boolean) => void;
}

const COPY = {
  "zh-TW": {
    title: "RepoNPC 管理工作區",
    authRequired: "請先登入管理員工作階段，才能編輯公開設定。",
    draftHeading: "公開設定草稿",
    draftLabel: "reponpc.yml 原始 YAML",
    draftHelp: "這份草稿尚未寫入 GitHub。儲存前請先驗證內容。",
    validate: "驗證設定",
    preview: "預覽變更",
    save: "儲存設定",
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
    statusHeading: "發布狀態",
    activeBundle: "目前 bundle",
    previousBundle: "上一個 bundle",
    pinnedBundle: "固定 bundle",
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
    advancedMode: "進階：編輯原始 YAML",
  },
  en: {
    title: "RepoNPC admin workspace",
    authRequired:
      "Sign in to an admin session before editing public configuration.",
    draftHeading: "Public configuration draft",
    draftLabel: "Raw reponpc.yml YAML",
    draftHelp:
      "This draft has not been written to GitHub. Validate it before saving.",
    validate: "Validate configuration",
    preview: "Preview changes",
    save: "Save configuration",
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
    statusHeading: "Publication status",
    activeBundle: "Active bundle",
    previousBundle: "Previous bundle",
    pinnedBundle: "Pinned bundle",
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
  guidedView,
  githubConnectionView,
  embeddingProfileView,
  advancedMode = false,
  onAdvancedModeChange,
}: AdminWorkspaceProps) {
  const copy = COPY[locale];
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

  function handleDraftChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onDraftChange(event.target.value);
  }

  return (
    <main aria-busy={busy} className="admin-workspace" lang={locale}>
      <header className="admin-workspace__header">
        <div>
          <p className="eyebrow">RepoNPC</p>
          <h1 className="admin-workspace__title">{copy.title}</h1>
        </div>
        {authenticated && (
          <button disabled={busy} onClick={onLogout} type="button">
            {copy.logout}
          </button>
        )}
      </header>

      {notice && (!guidedView || advancedMode) && (
        <p className="admin-workspace__notice" role="alert">
          {notice}
        </p>
      )}

      {authenticated && githubConnectionView}
      {authenticated && embeddingProfileView}

      {!authenticated && (
        <p role="alert" className="admin-workspace__auth-message">
          {copy.authRequired}
        </p>
      )}

      {guidedView && (
        <nav aria-label={copy.title} className="admin-workspace__mode-switch">
          <button
            aria-pressed={!advancedMode}
            disabled={busy}
            onClick={() => onAdvancedModeChange?.(false)}
            type="button"
          >
            {copy.guidedMode}
          </button>
          <button
            aria-pressed={advancedMode}
            disabled={busy}
            onClick={() => onAdvancedModeChange?.(true)}
            type="button"
          >
            {copy.advancedMode}
          </button>
        </nav>
      )}

      {guidedView && !advancedMode && guidedView}

      {(!guidedView || advancedMode) && (
        <>
          <section aria-labelledby="admin-draft-heading">
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

          <section aria-labelledby="admin-validation-heading">
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
            <section aria-labelledby="admin-preview-heading">
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
                  <img
                    alt={copy.characterAlt}
                    height={224}
                    src={`data:image/png;base64,${preview.character.png_base64}`}
                    width={128}
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
                            <img
                              alt={`${copy.cardAlt}: ${variant}`}
                              height={180}
                              src={`data:image/png;base64,${card.png_base64}`}
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

          <section aria-labelledby="admin-status-heading">
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
            <section aria-labelledby="admin-snippet-heading">
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
