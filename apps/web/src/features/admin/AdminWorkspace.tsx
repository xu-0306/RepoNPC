import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import { Button, Dialog, DialogTrigger, Popover } from "react-aria-components";
import "../../p4-w4.css";

import { Base64PngCanvas } from "./Base64PngCanvas";
import { CharacterRenderer } from "../character/CharacterRenderer";
import type { PublicProfile } from "../../app/publicTypes";
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
  | "maintenance"
  | "advanced";

const WORKSPACE_HEADINGS: Record<AdminWorkspaceMode, string> = {
  advanced: "admin-draft-heading",
  character: "admin-character-converter-heading",
  guided: "guided-onboarding-heading",
  publish: "local-publication-heading",
  maintenance: "admin-maintenance-heading",
};

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
  png_url?: string;
  sha256?: string;
}

export interface PreviewCard {
  png_base64?: string;
  png_url?: string;
  svg_base64?: string;
  svg_url?: string;
  gif_base64?: string;
  gif_url?: string;
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
}

export interface AdminSnippet {
  markdown: string;
  asset_url?: string;
  target_url?: string;
}

export interface AdminWorkspaceProps {
  locale: AdminLocale;
  draft: string;
  validation: AdminValidation | null;
  preview: AdminPreview | null;
  status: AdminStatus | null;
  snippet: AdminSnippet | string | null;
  busy: boolean;
  authenticated: boolean;
  notice: string;
  onDraftChange: (draft: string) => void;
  onValidate: () => void;
  onPreview: () => void;
  onCopy: () => void;
  onLogout: () => void;
  onLocaleChange?: (locale: AdminLocale) => void;
  guidedView?: ReactNode;
  questRail?: ReactNode;
  embeddingProfileView?: ReactNode;
  characterAssetView?: ReactNode;
  publicationView?: ReactNode;
  maintenanceView?: ReactNode;
  activeCharacter?: PublicProfile["character"] | null;
  workspaceMode?: AdminWorkspaceMode;
  onWorkspaceModeChange?: (mode: AdminWorkspaceMode) => void;
}

const COPY = {
  "zh-TW": {
    title: "RepoNPC 管理工作區",
    brand: "RepoNPC",
    subtitle: "像素工坊",
    publishMode: "預覽與分享",
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
    draftHelp: "先驗證並預覽這份草稿，再到分享工作區儲存在本機。",
    validate: "驗證設定",
    preview: "預覽變更",
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
    none: "無",
    snippetHeading: "README 複製片段",
    snippetLabel: "可直接貼上的 Markdown",
    copy: "複製片段",
    busy: "處理中…",
    copyReady: "片段已準備好。",
    guidedMode: "引導設定",
    characterMode: "角色與動畫",
    advancedMode: "進階：編輯原始 YAML",
    maintenanceMode: "維護",
    modelInfo: "模型與裝置資訊",
  },
  en: {
    title: "RepoNPC admin workspace",
    brand: "RepoNPC",
    subtitle: "Pixel Workshop",
    publishMode: "Preview & share",
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
      "Check and preview this draft, then save it locally in the sharing workspace.",
    validate: "Check configuration",
    preview: "Preview changes",
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
    none: "None",
    snippetHeading: "README copy snippet",
    snippetLabel: "Markdown ready to paste",
    copy: "Copy snippet",
    busy: "Working…",
    copyReady: "Snippet is ready.",
    guidedMode: "Guided setup",
    characterMode: "Character & animation",
    advancedMode: "Advanced: edit raw YAML",
    maintenanceMode: "Maintenance",
    modelInfo: "Models and device information",
  },
} as const;

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
  busy,
  authenticated,
  notice,
  onDraftChange,
  onValidate,
  onPreview,
  onCopy,
  onLogout,
  onLocaleChange,
  guidedView,
  questRail,
  embeddingProfileView,
  characterAssetView,
  publicationView,
  maintenanceView,
  activeCharacter,
  workspaceMode = guidedView ? "guided" : "advanced",
  onWorkspaceModeChange,
}: AdminWorkspaceProps) {
  const copy = COPY[locale];
  const [uiScale, setUiScale] = useState<AdminUiScale>(readAdminUiScale);
  const previousMode = useRef(workspaceMode);
  useEffect(() => {
    if (previousMode.current === workspaceMode) return;
    previousMode.current = workspaceMode;
    const heading = document.getElementById(WORKSPACE_HEADINGS[workspaceMode]);
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      heading.scrollIntoView({ block: "start", behavior: "instant" });
    }
  }, [workspaceMode]);
  const errors = issueList(validation?.errors, "error");
  const warnings = issueList(validation?.warnings, "warning");
  const profile = profileForLocale(preview?.profile, locale);
  const snippetValue = snippetText(snippet);

  useEffect(() => {
    applyAdminUiScale(uiScale);
    persistAdminUiScale(uiScale);
  }, [uiScale]);

  function handleDraftChange(event: ChangeEvent<HTMLTextAreaElement>) {
    onDraftChange(event.target.value);
  }

  return (
    <div
      aria-busy={busy}
      className="admin-workspace"
      lang={locale}
      onFocusCapture={(event) => {
        const target = event.target as HTMLElement;
        requestAnimationFrame(() => {
          const rect = target.getBoundingClientRect();
          const hit = document.elementFromPoint(
            rect.left + rect.width / 2,
            rect.top + rect.height / 2,
          );
          if (hit && (target === hit || target.contains(hit))) return;
          target.scrollIntoView({ block: "center", behavior: "instant" });
        });
      }}
      ref={(root) => {
        if (!root) return;
        const actions = root.querySelectorAll<HTMLElement>(
          ".p4-w1-confirm, .guided-analysis__actions",
        );
        const reserve = () => {
          const height = Math.max(
            0,
            ...Array.from(actions, (bar) => {
              const style = getComputedStyle(bar);
              return style.position === "fixed"
                ? bar.getBoundingClientRect().height +
                    (parseFloat(style.bottom) || 0) +
                    16
                : 0;
            }),
          );
          root.style.setProperty("--px-owner-actions-space", `${height}px`);
        };
        const observer =
          typeof ResizeObserver === "undefined"
            ? null
            : new ResizeObserver(reserve);
        actions.forEach((bar) => observer?.observe(bar));
        reserve();
        const reveal = (event: Event) => {
          const target = event.target as HTMLDetailsElement;
          if (target.open && target.classList.contains("px-info"))
            requestAnimationFrame(() =>
              requestAnimationFrame(() =>
                target.scrollIntoView({ block: "center", behavior: "instant" }),
              ),
            );
        };
        root.addEventListener("toggle", reveal, true);
        return () => {
          root.removeEventListener("toggle", reveal, true);
          observer?.disconnect();
        };
      }}
    >
      <header className="admin-workspace__header">
        <div className="admin-workspace__brand">
          <span className="admin-workspace__logo" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="m12 3 9 5v8l-9 5-9-5V8Z" />
              <path d="m3 8 9 5 9-5M12 13v8M7.5 5.5l9 5" />
            </svg>
          </span>
          <div>
            <h1 aria-label={copy.title} className="admin-workspace__title">
              {copy.brand}
            </h1>
            <p className="admin-workspace__subtitle">{copy.subtitle}</p>
          </div>
        </div>
        <div className="admin-workspace__scene px-scene" aria-hidden="true">
          <span className="px-scene__horizon" />
          <span className="px-scene__celestial" />
          <span className="px-scene__hill-far" />
          <span className="px-scene__hill-near" />
          <span className="px-scene__grass" />
          <span className="px-scene__ground" />
          <span className="px-scene__sign" />
          {activeCharacter && (
            <span className="px-scene__npc">
              <CharacterRenderer
                assetUrl={`/api/public/character.png?rev=${activeCharacter.revision}`}
                state="idle"
                stateLabel=""
                reducedMotion
                frame={0}
              />
            </span>
          )}
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
                  className="px-button px-button--quiet"
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
          <DialogTrigger>
            <Button
              className="admin-display-settings px-button px-button--quiet"
              aria-label={copy.displaySettings}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24">
                <path d="M4 7h10M18 7h2M10 17h10M4 17h2M14 4v6M10 14v6" />
              </svg>
              <span className="admin-workspace__utility-label">
                {copy.displaySettings}
              </span>
            </Button>
            <Popover
              className="admin-display-settings__popover px-panel"
              placement="bottom end"
              offset={8}
            >
              <Dialog
                className="admin-display-settings__panel"
                aria-label={copy.displaySettings}
                lang={locale}
              >
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
              </Dialog>
            </Popover>
          </DialogTrigger>
          <a
            className="admin-workspace__help"
            href={`#${WORKSPACE_HEADINGS[workspaceMode]}`}
          >
            <span aria-hidden="true">?</span>
            <span className="admin-workspace__utility-label">{copy.help}</span>
          </a>
          {authenticated && (
            <>
              <span
                aria-label={copy.administrator}
                className="admin-workspace__owner px-badge"
              >
                <span aria-hidden="true">R</span>
                <span className="admin-workspace__utility-label">
                  {copy.administrator}
                </span>
              </span>
              <button
                className="admin-workspace__logout px-button px-button--quiet"
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
        <nav aria-label={copy.title} className="admin-workspace__modes">
          <button
            className="px-tab"
            aria-pressed={workspaceMode === "guided"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("guided")}
            type="button"
          >
            {copy.guidedMode}
          </button>
          <button
            className="px-tab"
            aria-pressed={workspaceMode === "character"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("character")}
            type="button"
          >
            {copy.characterMode}
          </button>
          {publicationView && (
            <button
              className="px-tab"
              type="button"
              disabled={busy}
              aria-pressed={workspaceMode === "publish"}
              onClick={() => onWorkspaceModeChange?.("publish")}
            >
              {copy.publishMode}
            </button>
          )}
          <button
            className="px-tab admin-workspace__advanced-tab"
            aria-pressed={workspaceMode === "advanced"}
            disabled={busy}
            onClick={() => onWorkspaceModeChange?.("advanced")}
            type="button"
          >
            {copy.advancedMode}
          </button>
          {maintenanceView && (
            <button
              className="px-tab"
              aria-pressed={workspaceMode === "maintenance"}
              disabled={busy}
              onClick={() => onWorkspaceModeChange?.("maintenance")}
              type="button"
            >
              {copy.maintenanceMode}
            </button>
          )}
        </nav>
      )}

      <div className="admin-workspace__layout">
        {authenticated && questRail}
        <main className="admin-workspace__content">
          {notice && (!guidedView || workspaceMode !== "guided") && (
            <p className="admin-workspace__notice" role="alert">
              {notice}
            </p>
          )}

          {authenticated && workspaceMode === "character" && characterAssetView}

          {!authenticated && (
            <p role="alert" className="admin-workspace__auth-message">
              {copy.authRequired}
            </p>
          )}

          {guidedView && workspaceMode === "guided" && guidedView}
          {authenticated && workspaceMode === "publish" && publicationView}
          {authenticated && workspaceMode === "maintenance" && maintenanceView}

          {(!guidedView || workspaceMode === "advanced") && (
            <>
              <section
                aria-labelledby="admin-draft-heading"
                className="admin-workspace__yaml px-panel px-panel--raised"
              >
                <h2 id="admin-draft-heading">{copy.draftHeading}</h2>
                <label htmlFor="admin-config-draft">{copy.draftLabel}</label>
                <p id="admin-draft-help">{copy.draftHelp}</p>
                <textarea
                  className="px-field"
                  aria-describedby="admin-draft-help"
                  disabled={!authenticated || busy}
                  id="admin-config-draft"
                  onChange={handleDraftChange}
                  rows={10}
                  value={draft}
                />
                <div
                  className="admin-workspace__actions"
                  aria-label={copy.draftHeading}
                >
                  <button
                    className="px-button px-button--primary"
                    disabled={!authenticated || busy}
                    onClick={onValidate}
                    type="button"
                  >
                    {copy.validate}
                  </button>
                  <button
                    className="px-button px-button--secondary"
                    disabled={!authenticated || busy}
                    onClick={onPreview}
                    type="button"
                  >
                    {copy.preview}
                  </button>
                </div>
                {busy && <p role="status">{copy.busy}</p>}
              </section>

              <section
                aria-labelledby="admin-validation-heading"
                className="admin-workspace__yaml-result px-panel"
              >
                <h2 id="admin-validation-heading">{copy.validationHeading}</h2>
                {validation?.valid === true && errors.length === 0 && (
                  <p role="status">{copy.valid}</p>
                )}
                {validation?.valid === false && (
                  <p role="alert">{copy.invalid}</p>
                )}
                {errors.length > 0 && (
                  <IssueList
                    heading={copy.errors}
                    issues={errors}
                    role="alert"
                  />
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

              {preview && (
                <section
                  aria-labelledby="admin-preview-heading"
                  className="admin-workspace__yaml-preview px-panel"
                >
                  <h2 id="admin-preview-heading">{copy.previewHeading}</h2>
                  <p
                    className="admin-workspace__preview-banner px-badge"
                    role="status"
                  >
                    {copy.unsaved}
                  </p>
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
                      <h3 id="admin-preview-character-heading">
                        {copy.character}
                      </h3>
                      <p>{preview.character.mode}</p>
                      <Base64PngCanvas
                        failureText={copy.previewFailed}
                        height={448}
                        label={copy.characterAlt}
                        pngBase64={preview.character.png_base64}
                        pngUrl={preview.character.png_url}
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
                                  pngUrl={card.png_url}
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
                className="admin-workspace__yaml-status px-panel"
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
                </dl>
              </section>

              {snippetValue && (
                <section
                  aria-labelledby="admin-snippet-heading"
                  className="admin-workspace__yaml-snippet px-panel"
                >
                  <h2 id="admin-snippet-heading">{copy.snippetHeading}</h2>
                  <label htmlFor="admin-readme-snippet">
                    {copy.snippetLabel}
                  </label>
                  <textarea
                    className="px-field"
                    id="admin-readme-snippet"
                    readOnly
                    rows={4}
                    value={snippetValue}
                  />
                  <button
                    className="px-button px-button--secondary"
                    disabled={busy}
                    onClick={onCopy}
                    type="button"
                  >
                    {copy.copy}
                  </button>
                  <p role="status">{copy.copyReady}</p>
                </section>
              )}
              {authenticated && embeddingProfileView && (
                <details className="admin-workspace__yaml-model-info px-info">
                  <summary>ⓘ {copy.modelInfo}</summary>
                  {embeddingProfileView}
                </details>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export function DraftValidation({
  locale,
  validation,
}: {
  locale: AdminLocale;
  validation: AdminValidation | null;
}) {
  if (!validation) return null;
  const copy = COPY[locale];
  const errors = validation.errors ?? [];
  const warnings = validation.warnings ?? [];
  return (
    <div>
      <span
        className="px-badge"
        role={errors.length || validation.valid === false ? "alert" : "status"}
      >
        {copy.errors}: {errors.length} · {copy.warnings}: {warnings.length}
      </span>
      {(errors.length > 0 || warnings.length > 0) && (
        <details className="px-info">
          <summary>ⓘ {copy.validationHeading}</summary>
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
        </details>
      )}
    </div>
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
