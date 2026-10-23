import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties } from "react";
import type { RefObject } from "react";
import { CharacterRenderer } from "../features/character/CharacterRenderer";
import { messages } from "../i18n/messages";
import { VisitorConversation } from "./VisitorConversation";
import {
  sceneThemesForScheme,
  sceneThemeStyle,
  type VisitorMode,
} from "./scene";
import { isStaticExport } from "./visitorData";
import type { PublicScene, VisitorPageProps } from "./publicTypes";

interface ExtendedProps extends VisitorPageProps {
  visitorMode?: VisitorMode;
  visitorScheme?: string;
  onVisitorModeChange?: (mode: VisitorMode) => void;
  backgroundUrlOverride?: string | null;
  compactPreview?: boolean;
  previewHeroRef?: RefObject<HTMLElement | null>;
}

export function VisitorPage(props: ExtendedProps) {
  const {
    locale,
    onLocaleChange,
    profile,
    profileError,
    onRetryProfile,
    chatAvailable,
    offlineFaqAvailable = false,
    pending,
    onRecheckStatus,
    characterState,
    reducedMotion,
    turns,
    onRetry,
    question,
    onQuestionChange,
    onSubmit,
    onCancel,
    suggestions,
    canAskSuggestion,
    onSelectSuggestion,
    profileErrorRef,
    chatStatusRef,
    questionInputRef,
    mode = "visitor",
    previewMode,
    visitorMode = "system",
    visitorScheme,
    onVisitorModeChange,
    sceneOverride,
    backgroundUrlOverride,
    previewHeroRef,
    sampleConversation = false,
    previewKeepHero = false,
    showFocusFrame = false,
    sampleContent = false,
    compactPreview = false,
  } = props;
  const copy = messages[locale];
  const generatedId = useId().replaceAll(":", "");
  const idPrefix = mode === "preview" ? `preview-${generatedId}` : generatedId;
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const scene: PublicScene | null =
    sceneOverride === undefined
      ? (profile?.character.scene ?? null)
      : sceneOverride;
  const backgroundUrl =
    backgroundUrlOverride === undefined
      ? (scene?.background_url ?? null)
      : backgroundUrlOverride;
  const safeBackground =
    backgroundUrlOverride === undefined
      ? publicBackgroundUrl(backgroundUrl, scene?.revision)
      : previewBackgroundUrl(backgroundUrlOverride);
  const canChooseScheme = mode === "visitor" && scene?.visitor_scheme_choice;
  const chosenScheme = canChooseScheme
    ? scene.schemes.find((scheme) => scheme.id === visitorScheme)
    : undefined;
  const sceneStyle = sceneThemeStyle(
    scene && canChooseScheme
      ? { ...scene, themes: sceneThemesForScheme(scene, visitorScheme ?? "") }
      : scene,
  );
  const npcPlate = chosenScheme?.npc_plate ?? scene?.npc_plate;
  const sceneDim =
    scene?.background_dim === "auto"
      ? "none"
      : (scene?.background_dim ?? "none");
  const heroStyle = {
    ...sceneStyle,
    "--scene-hero-image": safeBackground ? `url("${safeBackground}")` : "none",
    "--scene-dim-opacity": `var(--scene-dim-opacity-${sceneDim})`,
    "--scene-focus-x": `${scene?.background_focus.x ?? 50}%`,
    "--scene-focus-y": `${scene?.background_focus.y ?? 50}%`,
    "--scene-background-scaling":
      scene?.background_scaling === "pixelated" ? "pixelated" : "auto",
  } as CSSProperties;
  const canToggleMode =
    mode === "visitor" && scene?.visitor_mode_toggle !== false;
  const suggestionsList = [...new Set(suggestions)].slice(0, 8);
  const visibleTurns = sampleConversation ? sampleTurns(locale) : turns;
  const showHero =
    visibleTurns.length === 0 || (mode === "preview" && previewKeepHero);
  const titleId = `${idPrefix}-profile-title`;
  const chatId = `${idPrefix}-chat-title`;
  const inputId = `${idPrefix}-portfolio-question`;
  const PageRoot = mode === "preview" ? "div" : "main";

  useEffect(() => {
    if (!sidebarOpen) return;
    const sidebar = sidebarRef.current;
    const focusable = sidebar
      ? Array.from(
          sidebar.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        )
      : [];
    focusable[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSidebarOpen(false);
        menuButtonRef.current?.focus();
        return;
      }
      if (event.key !== "Tab" || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sidebarOpen]);

  function closeSidebar() {
    setSidebarOpen(false);
    menuButtonRef.current?.focus();
  }

  return (
    <PageRoot
      className="visitor-page"
      data-compact-preview={compactPreview ? "true" : undefined}
      data-preview={mode === "preview" ? "true" : undefined}
      data-preview-mode={mode === "preview" ? previewMode : undefined}
      data-npc-plate-light={npcPlate?.light}
      data-npc-plate-dark={npcPlate?.dark}
      lang={locale}
      style={heroStyle}
    >
      {mode === "preview" && (
        <p className="visitor-preview-banner" role="note">
          {copy.visitorPreview}
        </p>
      )}
      <header className="visitor-topbar">
        <a
          className="visitor-brand"
          href={isStaticExport() ? "./" : "/"}
          aria-label="RepoNPC"
        >
          <span aria-hidden="true" className="visitor-brand__mark">
            R
          </span>
          <span>RepoNPC</span>
        </a>
        <button
          aria-expanded={sidebarOpen}
          aria-controls={`${idPrefix}-sidebar`}
          className="visitor-menu-button"
          ref={menuButtonRef}
          onClick={() => setSidebarOpen((open) => !open)}
          type="button"
        >
          {sidebarOpen ? copy.menuClose : copy.menuOpen}
        </button>
        <div className="visitor-npc-status" role="status">
          <CharacterRenderer
            assetUrl={characterAssetUrl(profile)}
            className="visitor-npc-status__avatar"
            frameDurationMs={profile?.character.frame_duration_ms}
            movement={profile?.character.movement}
            reducedMotion={reducedMotion}
            state={characterState}
            stateLabel={
              copy[
                `character${capitalize(characterState)}` as keyof typeof copy
              ] as string
            }
          />
          <span
            aria-hidden="true"
            className={`visitor-npc-status__dot${chatAvailable ? " visitor-npc-status__dot--online" : ""}`}
          />
          <span className="visitor-npc-status__label">
            <span>{chatAvailable ? copy.npcOnline : copy.npcResting}</span>
          </span>
        </div>
        <div className="visitor-topbar__controls">
          <nav
            aria-label={copy.languageLabel}
            className="visitor-language-switcher"
          >
            {(["zh-TW", "en"] as const).map((option) => (
              <button
                aria-pressed={locale === option}
                key={option}
                onClick={() => onLocaleChange(option)}
                type="button"
              >
                {messages[option].languageName}
              </button>
            ))}
          </nav>
          {canToggleMode && (
            <fieldset className="visitor-mode-control">
              <legend>{locale === "zh-TW" ? "顯示模式" : "Color mode"}</legend>
              {(["system", "light", "dark"] as const).map((option) => (
                <button
                  aria-pressed={visitorMode === option}
                  key={option}
                  onClick={() => onVisitorModeChange?.(option)}
                  type="button"
                >
                  {option === "system"
                    ? copy.modeSystem
                    : option === "light"
                      ? copy.modeLight
                      : copy.modeDark}
                </button>
              ))}
            </fieldset>
          )}
        </div>
      </header>

      <div className="visitor-layout">
        <aside
          aria-modal={sidebarOpen ? true : undefined}
          aria-labelledby={titleId}
          className={`visitor-sidebar${sidebarOpen ? " visitor-sidebar--open" : ""}`}
          id={`${idPrefix}-sidebar`}
          ref={sidebarRef}
          role={sidebarOpen ? "dialog" : undefined}
        >
          {sidebarOpen && (
            <button
              className="visitor-sidebar__close"
              onClick={closeSidebar}
              type="button"
            >
              {copy.menuClose}
            </button>
          )}
          <section className="visitor-profile-card">
            <div className="visitor-profile-card__avatar" aria-hidden="true">
              {(profile?.profile.display_name ?? "R")
                .slice(0, 1)
                .toLocaleUpperCase(locale)}
            </div>
            <h2 id={titleId}>{profile?.profile.display_name ?? "RepoNPC"}</h2>
            <p className="visitor-profile-card__headline">
              {profile?.profile.headline ?? copy.subtitle}
            </p>
            {profile?.profile.location && <p>{profile.profile.location}</p>}
            {profile?.profile.links.length ? (
              <nav
                aria-label={copy.linksTitle}
                className="visitor-profile-links"
              >
                {profile.profile.links.map((link) => (
                  <a
                    href={link.url}
                    key={link.url}
                    rel="noopener noreferrer"
                    target="_blank"
                  >
                    {link.label}
                  </a>
                ))}
              </nav>
            ) : null}
          </section>
          <section className="visitor-about-card">
            <h3>{copy.about}</h3>
            <p>
              {profile?.profile.bio ??
                (sampleContent ? sampleAbout(locale) : copy.profileLoading)}
            </p>
          </section>
          <section
            className="visitor-projects"
            aria-labelledby={`${idPrefix}-projects-title`}
          >
            <h3 id={`${idPrefix}-projects-title`}>{copy.projectsTitle}</h3>
            {profile?.repositories.length ? (
              <ul className="visitor-project-list">
                {profile.repositories.map((repository) => (
                  <li className="visitor-project-card" key={repository.slug}>
                    <h4>{repository.slug}</h4>
                    <p>{repository.summary}</p>
                    <p className="visitor-project-card__role">
                      {repository.role}
                    </p>
                    {(repository.language ||
                      repository.stars != null ||
                      repository.forks != null) && (
                      <dl className="visitor-repo-metadata">
                        {repository.language && (
                          <MetadataPair
                            label={copy.languageMetadata}
                            value={repository.language}
                          />
                        )}
                        {repository.stars != null && (
                          <MetadataPair
                            label={copy.starsMetadata}
                            value={repository.stars.toLocaleString(locale)}
                          />
                        )}
                        {repository.forks != null && (
                          <MetadataPair
                            label={copy.forksMetadata}
                            value={repository.forks.toLocaleString(locale)}
                          />
                        )}
                      </dl>
                    )}
                    {repository.tags.length > 0 && (
                      <ul aria-label={copy.tagsLabel} className="visitor-tags">
                        {repository.tags.map((tag) => (
                          <li key={tag}>{tag}</li>
                        ))}
                      </ul>
                    )}
                    {repository.demo_url && (
                      <a
                        href={repository.demo_url}
                        rel="noopener noreferrer"
                        target="_blank"
                      >
                        {copy.demoLink}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                {sampleContent ? sampleProject(locale) : copy.profileLoading}
              </p>
            )}
          </section>
        </aside>

        <div className="visitor-content">
          {showHero && (
            <section
              className="visitor-hero"
              aria-label={copy.title}
              ref={previewHeroRef}
            >
              <div className="visitor-hero__copy">
                <p className="visitor-eyebrow">{copy.subtitle}</p>
                <h1>{copy.title}</h1>
                <p>
                  {profile?.profile.greeting ??
                    (sampleContent ? sampleGreeting(locale) : "")}
                </p>
                {profileError && (
                  <div className="visitor-alert">
                    <p ref={profileErrorRef} role="alert" tabIndex={-1}>
                      {copy.profileUnavailable}
                    </p>
                    <button onClick={onRetryProfile} type="button">
                      {copy.retryProfile}
                    </button>
                  </div>
                )}
                {!profile && !profileError && (
                  <p role="status">{copy.profileLoading}</p>
                )}
              </div>
              <div className="visitor-hero__stage">
                <CharacterRenderer
                  assetUrl={characterAssetUrl(profile)}
                  className="visitor-hero__character"
                  frameDurationMs={profile?.character.frame_duration_ms}
                  movement={profile?.character.movement}
                  reducedMotion={reducedMotion}
                  state={characterState}
                  stateLabel={
                    copy[
                      `character${capitalize(characterState)}` as keyof typeof copy
                    ] as string
                  }
                />
              </div>
              {mode === "preview" && showFocusFrame && (
                <div aria-hidden="true" className="visitor-focus-frame">
                  <span />
                </div>
              )}
            </section>
          )}

          <section aria-labelledby={chatId} className="visitor-chat-panel">
            <div className="visitor-chat-heading">
              <div>
                <p className="visitor-eyebrow">RepoNPC</p>
                <h2 id={chatId}>{copy.chatTitle}</h2>
              </div>
              <div className="visitor-chat-status">
                <p
                  ref={chatStatusRef}
                  role="status"
                  tabIndex={!chatAvailable ? -1 : undefined}
                >
                  {chatAvailable ? copy.statusReady : copy.statusUnavailable}
                </p>
                {!chatAvailable && (
                  <button onClick={onRecheckStatus} type="button">
                    {copy.recheckStatus}
                  </button>
                )}
              </div>
            </div>
            <VisitorConversation
              chatAvailable={chatAvailable}
              locale={locale}
              ownerName={profile?.profile.display_name}
              onRetry={onRetry}
              canAskSuggestion={canAskSuggestion}
              pending={pending}
              turns={visibleTurns}
              characterAssetUrl={characterAssetUrl(profile)}
              characterFrameDurationMs={profile?.character.frame_duration_ms}
              characterMovement={profile?.character.movement}
              characterState={characterState}
              reducedMotion={reducedMotion}
            />
            {visibleTurns.length === 0 && (
              <div className="visitor-welcome-card">
                <span
                  aria-hidden="true"
                  className="visitor-welcome-card__spark"
                >
                  ✦
                </span>
                <h3>{copy.visitorWelcome}</h3>
                <p>{copy.visitorWelcomeText}</p>
              </div>
            )}
            {suggestionsList.length > 0 && (
              <div className="visitor-suggestions">
                <h3>{copy.suggested}</h3>
                <div className="visitor-suggestion-list">
                  {suggestionsList.map((suggestion) => (
                    <button
                      disabled={pending || !canAskSuggestion(suggestion)}
                      key={suggestion}
                      onClick={() => onSelectSuggestion(suggestion)}
                      type="button"
                    >
                      {suggestion}
                      <span aria-hidden="true"> ↗</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <form
              className="visitor-question-form"
              onSubmit={(event) => {
                event.preventDefault();
                onSubmit();
              }}
            >
              <label htmlFor={inputId}>{copy.inputLabel}</label>
              <div className="visitor-question-form__input">
                <textarea
                  disabled={
                    (!chatAvailable && !offlineFaqAvailable) ||
                    pending ||
                    mode === "preview"
                  }
                  id={inputId}
                  maxLength={4000}
                  onChange={(event) => onQuestionChange(event.target.value)}
                  placeholder={copy.inputPlaceholder}
                  ref={questionInputRef}
                  rows={2}
                  value={question}
                />
                <button
                  disabled={
                    !question.trim() ||
                    (!chatAvailable && !offlineFaqAvailable) ||
                    pending ||
                    mode === "preview"
                  }
                  type="submit"
                >
                  {pending ? copy.processingSending : copy.send}
                </button>
                {pending && onCancel && (
                  <button type="button" onClick={onCancel}>
                    {copy.processingCancel}
                  </button>
                )}
              </div>
              <p className="visitor-question-hint">
                {copy.questionEvidenceHint}
              </p>
            </form>
          </section>
        </div>
      </div>
    </PageRoot>
  );
}

function MetadataPair({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function publicBackgroundUrl(
  value: string | null,
  revision?: number,
): string | null {
  if (!value || typeof window === "undefined") return null;
  if (isStaticExport()) {
    return /^\.\/scene\/[0-9a-f]{64}\.(?:png|webp)$/.test(value) ? value : null;
  }
  try {
    const url = new URL(value, window.location.origin);
    if (
      url.origin !== window.location.origin ||
      url.pathname !== "/api/public/scene-background" ||
      url.searchParams.get("rev") !== String(revision) ||
      [...url.searchParams.keys()].some((key) => key !== "rev")
    )
      return null;
    return `${url.pathname}?rev=${encodeURIComponent(String(revision))}`;
  } catch {
    return null;
  }
}

function characterAssetUrl(profile: VisitorPageProps["profile"]): string {
  if (isStaticExport()) return "./character.png";
  return profile
    ? `/api/public/character.png?rev=${profile.character.revision}`
    : "/api/public/character.png";
}

function previewBackgroundUrl(value: string | null): string | null {
  if (!value || typeof window === "undefined") return null;
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) return null;
    if (
      url.pathname.startsWith("/api/public/scene-background") &&
      /^\d+$/.test(url.searchParams.get("rev") ?? "") &&
      [...url.searchParams.keys()].every((key) => key === "rev")
    ) {
      return `${url.pathname}?rev=${encodeURIComponent(url.searchParams.get("rev") ?? "")}`;
    }
    if (
      /^\/api\/admin\/assets\/scene\/background-drafts\/[A-Za-z0-9_-]{32,64}$/.test(
        url.pathname,
      ) &&
      !url.search
    ) {
      return url.pathname;
    }
    return null;
  } catch {
    return null;
  }
}

function sampleGreeting(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "我是作品集導覽員，可以依照已驗證的專案資料回答問題。"
    : "I’m your portfolio guide. Ask me about the verified project information.";
}

function sampleAbout(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "這裡會介紹擁有者的專業背景、興趣與作品集方向。"
    : "This space introduces the owner’s background, interests and portfolio focus.";
}

function sampleProject(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "專案摘要會顯示在這裡。"
    : "Project summaries appear here.";
}

function sampleTurns(locale: "zh-TW" | "en"): VisitorPageProps["turns"] {
  return locale === "zh-TW"
    ? [
        { id: "sample-user", role: "user", content: "這個作品集有哪些重點？" },
        {
          id: "sample-assistant",
          role: "assistant",
          content: "我可以根據已發布的專案資料，帶你了解作品集中的重點。",
          citations: [],
        },
      ]
    : [
        {
          id: "sample-user",
          role: "user",
          content: "What are the portfolio highlights?",
        },
        {
          id: "sample-assistant",
          role: "assistant",
          content: "I can guide you through the published project information.",
          citations: [],
        },
      ];
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
