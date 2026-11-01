import { useEffect, useId, useRef, useState } from "react";
import type { CSSProperties, RefObject } from "react";

import { CharacterRenderer } from "../features/character/CharacterRenderer";
import { messages } from "../i18n/messages";
import { VisitorConversation } from "./VisitorConversation";
import {
  sceneSwatchStyle,
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
  onVisitorSchemeChange?: (scheme: string) => void;
  backgroundUrlOverride?: string | null;
  compactPreview?: boolean;
  previewHeroRef?: RefObject<HTMLDivElement | null>;
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
    onVisitorSchemeChange,
    sceneOverride,
    backgroundUrlOverride,
    previewHeroRef,
    sampleConversation = false,
    showFocusFrame = false,
    sampleContent = false,
    compactPreview = false,
  } = props;
  const copy = messages[locale];
  const generatedId = useId().replaceAll(":", "");
  const idPrefix = mode === "preview" ? `preview-${generatedId}` : generatedId;
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const projectsTriggerRef = useRef<HTMLButtonElement>(null);
  const projectsDialogRef = useRef<HTMLDialogElement>(null);
  const appearanceTriggerRef = useRef<HTMLButtonElement>(null);
  const appearancePanelRef = useRef<HTMLElement>(null);
  const conversationScrollRef = useRef<HTMLDivElement>(null);
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
  const canChooseScheme =
    mode === "visitor" && scene?.visitor_scheme_choice === true;
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
    "--scene-background-image": safeBackground
      ? `url("${safeBackground}")`
      : "none",
    "--scene-dim-opacity": `var(--scene-dim-opacity-${sceneDim})`,
    "--scene-focus-x": `${scene?.background_focus.x ?? 50}%`,
    "--scene-focus-y": `${scene?.background_focus.y ?? 50}%`,
    "--scene-background-scaling":
      scene?.background_scaling === "pixelated" ? "pixelated" : "auto",
  } as CSSProperties;
  const canToggleMode =
    mode === "visitor" && scene?.visitor_mode_toggle !== false;
  const showAppearance =
    mode === "visitor" && (canChooseScheme || canToggleMode);
  const suggestionsList = [...new Set(suggestions)].slice(0, 8);
  const visibleTurns = sampleConversation ? sampleTurns(locale) : turns;
  const latestTurn = visibleTurns.at(-1);
  const hasRestingState = !chatAvailable;
  const restingSuggestions = suggestionsList
    .filter(canAskSuggestion)
    .slice(0, 3);
  const titleId = `${idPrefix}-profile-title`;
  const chatId = `${idPrefix}-chat-title`;
  const inputId = `${idPrefix}-portfolio-question`;
  const dialogId = `${idPrefix}-projects-dialog`;
  const appearanceId = `${idPrefix}-appearance-panel`;
  const PageRoot = mode === "preview" ? "div" : "main";
  const DialogueHeading = mode === "preview" ? "h2" : "h1";
  const dialogueTitle =
    pending || characterState === "think"
      ? copy.dialogueThinking
      : hasRestingState
        ? copy.dialogueResting
        : (profile?.profile.greeting ??
          (sampleContent ? sampleGreeting(locale) : copy.dialogueAvailable));
  const dialogueBody = hasRestingState
    ? copy.dialogueFaq
    : (profile?.profile.headline ?? copy.dialoguePrompt);

  useEffect(() => {
    const dialog = projectsDialogRef.current;
    if (!dialog) return;
    if (projectsOpen) {
      if (!dialog.open) {
        if (typeof dialog.showModal === "function") dialog.showModal();
        else dialog.setAttribute("open", "");
      }
      dialog
        .querySelector<HTMLElement>(
          'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
        )
        ?.focus();
      return;
    }
    if (dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [projectsOpen]);

  useEffect(() => {
    if (!projectsOpen) return;
    const dialog = projectsDialogRef.current;
    if (!dialog) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeProjects();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (!focusable.length) return;
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
    dialog.addEventListener("keydown", onKeyDown);
    return () => dialog.removeEventListener("keydown", onKeyDown);
  }, [projectsOpen]);

  useEffect(() => {
    if (!appearanceOpen) return;
    const panel = appearancePanelRef.current;
    if (!panel) return;
    panel
      .querySelector<HTMLElement>('[aria-pressed="true"], input:checked')
      ?.focus();
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (
        !panel.contains(target) &&
        !appearanceTriggerRef.current?.contains(target)
      ) {
        closeAppearance();
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeAppearance();
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [appearanceOpen]);

  useEffect(() => {
    const scroll = conversationScrollRef.current;
    if (scroll) scroll.scrollTop = scroll.scrollHeight;
  }, [latestTurn?.content, latestTurn?.id, visibleTurns.length, pending]);

  function closeProjects() {
    setProjectsOpen(false);
    projectsTriggerRef.current?.focus();
  }

  function closeAppearance() {
    setAppearanceOpen(false);
    appearanceTriggerRef.current?.focus();
  }

  function projectCards() {
    if (!profile?.repositories.length) {
      return <p>{sampleContent ? sampleProject(locale) : copy.noProjects}</p>;
    }
    return (
      <ul className="visitor-project-list">
        {profile.repositories.map((repository) => (
          <li className="visitor-project-card" key={repository.slug}>
            <h3 className="px-display">{repository.slug}</h3>
            <p>{repository.summary}</p>
            <p className="visitor-project-card__role">{repository.role}</p>
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
    );
  }

  return (
    <PageRoot
      className="visitor-page px-body"
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
        <div className="visitor-topbar__brand-group">
          <a
            className="visitor-brand px-display"
            href={isStaticExport() ? "./" : "/"}
            aria-label="RepoNPC"
          >
            <span aria-hidden="true" className="visitor-brand__mark">
              R
            </span>
            <span>RepoNPC</span>
          </a>
          <button
            aria-expanded={projectsOpen}
            aria-controls={dialogId}
            className="visitor-projects-trigger px-button px-button--secondary"
            ref={projectsTriggerRef}
            onClick={() => setProjectsOpen((open) => !open)}
            type="button"
          >
            {copy.projectsButton}
          </button>
        </div>
        <div className="visitor-topbar__controls">
          <nav
            aria-label={copy.languageLabel}
            className="visitor-language-switcher"
          >
            {(["zh-TW", "en"] as const).map((option) => (
              <button
                aria-pressed={locale === option}
                className="px-chip"
                key={option}
                onClick={() => onLocaleChange(option)}
                type="button"
              >
                {messages[option].languageName}
              </button>
            ))}
          </nav>
          {showAppearance && (
            <button
              aria-controls={appearanceId}
              aria-expanded={appearanceOpen}
              aria-label={copy.appearance}
              className="visitor-appearance-trigger px-button px-button--secondary"
              ref={appearanceTriggerRef}
              onClick={() => setAppearanceOpen((open) => !open)}
              type="button"
            >
              <span aria-hidden="true">✦</span>
              <span>{copy.appearance}</span>
            </button>
          )}
        </div>
      </header>

      {showAppearance && appearanceOpen && (
        <section
          aria-labelledby={`${appearanceId}-title`}
          className="visitor-appearance-panel px-panel"
          id={appearanceId}
          ref={appearancePanelRef}
          role="dialog"
        >
          <div className="visitor-appearance-panel__heading">
            <h2 className="px-display" id={`${appearanceId}-title`}>
              {copy.appearance}
            </h2>
            <button
              aria-label={copy.appearanceClose}
              className="px-button px-button--quiet"
              onClick={closeAppearance}
              type="button"
            >
              ×
            </button>
          </div>
          {canChooseScheme && scene && (
            <fieldset className="visitor-scheme-choices">
              <legend className="px-label">{copy.schemeChoiceLabel}</legend>
              <div className="visitor-scheme-choices__grid">
                {scene.schemes.map((scheme) => (
                  <button
                    aria-pressed={
                      scheme.id === (visitorScheme ?? scene.scheme.id)
                    }
                    className="visitor-scheme-choice px-chip"
                    key={scheme.id}
                    onClick={() => {
                      if (onVisitorSchemeChange)
                        onVisitorSchemeChange(scheme.id);
                      else window.RepoNPCSceneMode?.setScheme(scheme.id);
                    }}
                    style={sceneSwatchStyle(scheme)}
                    type="button"
                  >
                    <span
                      aria-hidden="true"
                      className="visitor-scheme-swatch"
                    />
                    <span>{scheme.label[locale]}</span>
                  </button>
                ))}
              </div>
            </fieldset>
          )}
          {canToggleMode && (
            <fieldset className="visitor-mode-control">
              <legend className="px-label">{copy.modeLabel}</legend>
              <div className="visitor-mode-control__choices">
                {(["system", "light", "dark"] as const).map((option) => (
                  <button
                    aria-pressed={visitorMode === option}
                    className="px-chip"
                    key={option}
                    onClick={() => {
                      if (onVisitorModeChange) onVisitorModeChange(option);
                      else window.RepoNPCSceneMode?.set(option);
                    }}
                    type="button"
                  >
                    {option === "system"
                      ? copy.modeSystem
                      : option === "light"
                        ? copy.modeLight
                        : copy.modeDark}
                  </button>
                ))}
              </div>
            </fieldset>
          )}
        </section>
      )}

      <div className="visitor-layout">
        <section aria-label={copy.sceneTitle} className="visitor-adventure">
          <div
            className={`px-scene visitor-stage${safeBackground ? " visitor-stage--image" : ""}`}
            ref={previewHeroRef}
          >
            <div aria-hidden="true" className="px-scene__stars" />
            <div aria-hidden="true" className="px-scene__celestial" />
            <div aria-hidden="true" className="px-scene__horizon" />
            <div aria-hidden="true" className="px-scene__hill-far" />
            <div aria-hidden="true" className="px-scene__hill-near" />
            <div aria-hidden="true" className="px-scene__grass" />
            <div aria-hidden="true" className="px-scene__ground" />
            <div aria-hidden="true" className="px-scene__sign" />
            <div className="visitor-stage__npc">
              <CharacterRenderer
                assetUrl={characterAssetUrl(profile)}
                className="visitor-stage__character"
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
          </div>
          <section
            aria-labelledby={`${idPrefix}-dialogue-title`}
            className="px-dialog visitor-dialog"
          >
            <div className="px-tab px-display">
              RepoNPC{" "}
              <span className="px-badge">
                {stateBadge(copy, characterState, hasRestingState)}
              </span>
            </div>
            <DialogueHeading id={`${idPrefix}-dialogue-title`}>
              {dialogueTitle}
            </DialogueHeading>
            <p>{dialogueBody}</p>
            {hasRestingState && restingSuggestions.length > 0 && (
              <div className="visitor-resting-faq">
                <span className="px-label">{copy.dialogueFaqLabel}</span>
                <div>
                  {restingSuggestions.map((suggestion) => (
                    <button
                      className="px-chip"
                      disabled={pending || !canAskSuggestion(suggestion)}
                      key={suggestion}
                      onClick={() => onSelectSuggestion(suggestion)}
                      type="button"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>
        </section>

        <section aria-labelledby={chatId} className="visitor-log px-panel">
          <header className="visitor-log__heading">
            <div>
              <p className="visitor-eyebrow">{copy.sceneTitle}</p>
              <h2 className="px-display" id={chatId}>
                {copy.chatTitle}
              </h2>
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
                <button
                  className="px-button px-button--quiet"
                  onClick={onRecheckStatus}
                  type="button"
                >
                  {copy.recheckStatus}
                </button>
              )}
            </div>
          </header>
          <div className="visitor-log__scroll" ref={conversationScrollRef}>
            {profileError && (
              <div className="visitor-alert">
                <p ref={profileErrorRef} role="alert" tabIndex={-1}>
                  {copy.profileUnavailable}
                </p>
                <button
                  className="px-button px-button--secondary"
                  onClick={onRetryProfile}
                  type="button"
                >
                  {copy.retryProfile}
                </button>
              </div>
            )}
            {!profile && !profileError && (
              <p className="visitor-loading" role="status">
                {copy.profileLoading}
              </p>
            )}
            {suggestionsList.length > 0 && (
              <div className="visitor-suggestions" aria-label={copy.suggested}>
                <h3 className="px-label">{copy.suggested}</h3>
                <div className="visitor-suggestion-list">
                  {suggestionsList.map((suggestion) => (
                    <button
                      className="px-chip"
                      disabled={pending || !canAskSuggestion(suggestion)}
                      key={suggestion}
                      onClick={() => onSelectSuggestion(suggestion)}
                      type="button"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}
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
              <div className="visitor-welcome-card px-panel--inset">
                <h3 className="px-label">{copy.visitorWelcome}</h3>
                <p>{copy.visitorWelcomeText}</p>
              </div>
            )}
          </div>
          <form
            className="visitor-question-form"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            <label className="px-label" htmlFor={inputId}>
              {copy.inputLabel}
            </label>
            <div className="visitor-question-form__input">
              <textarea
                className="px-field"
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
                className="px-button px-button--primary"
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
                <button
                  className="px-button px-button--secondary"
                  onClick={onCancel}
                  type="button"
                >
                  {copy.processingCancel}
                </button>
              )}
            </div>
            <p className="visitor-question-hint px-meta">
              {copy.questionEvidenceHint}
            </p>
          </form>
        </section>
      </div>

      <dialog
        aria-labelledby={titleId}
        className="visitor-projects-dialog"
        id={dialogId}
        onCancel={(event) => {
          event.preventDefault();
          closeProjects();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) closeProjects();
        }}
        ref={projectsDialogRef}
      >
        <div className="visitor-projects-dialog__inner">
          <div className="visitor-projects-dialog__heading">
            <h2 className="px-display" id={titleId}>
              {copy.projectsButton}
            </h2>
            <button
              aria-label={copy.projectsClose}
              className="px-button px-button--quiet"
              onClick={closeProjects}
              type="button"
            >
              ×
            </button>
          </div>
          <section className="visitor-profile-card">
            <h3 className="px-display">
              {profile?.profile.display_name ?? "RepoNPC"}
            </h3>
            <p className="visitor-profile-card__headline">
              {profile?.profile.headline ?? copy.subtitle}
            </p>
            <p>
              {profile?.profile.bio ??
                (sampleContent ? sampleAbout(locale) : copy.profileLoading)}
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
          <section
            aria-labelledby={`${idPrefix}-projects-title`}
            className="visitor-projects"
          >
            <h3 className="px-display" id={`${idPrefix}-projects-title`}>
              {copy.projectsTitle}
            </h3>
            {projectCards()}
          </section>
        </div>
      </dialog>
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

function stateBadge(
  copy: (typeof messages)[keyof typeof messages],
  state: string,
  resting: boolean,
) {
  if (resting) return copy.restingBadge;
  if (state === "think") return copy.statusThinking;
  return copy.statusAvailable;
}

function publicBackgroundUrl(
  value: string | null,
  revision?: number,
): string | null {
  if (!value || typeof window === "undefined") return null;
  if (isStaticExport())
    return /^\.\/scene\/[0-9a-f]{64}\.(?:png|webp)$/.test(value) ? value : null;
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
    )
      return `${url.pathname}?rev=${encodeURIComponent(url.searchParams.get("rev") ?? "")}`;
    if (
      /^\/api\/admin\/assets\/scene\/background-drafts\/[A-Za-z0-9_-]{32,64}$/.test(
        url.pathname,
      ) &&
      !url.search
    )
      return url.pathname;
    return null;
  } catch {
    return null;
  }
}

function sampleGreeting(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "我是你的作品導覽員，可以依照已發布的資料回答問題。"
    : "I’m your portfolio guide. Ask me about the verified project information.";
}

function sampleAbout(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "這裡會介紹作品背景、興趣與作品方向。"
    : "This space introduces the owner’s background, interests and portfolio focus.";
}

function sampleProject(locale: "zh-TW" | "en"): string {
  return locale === "zh-TW"
    ? "作品摘要會顯示在這裡。"
    : "Project summaries appear here.";
}

function sampleTurns(locale: "zh-TW" | "en"): VisitorPageProps["turns"] {
  return locale === "zh-TW"
    ? [
        { id: "sample-user", role: "user", content: "這個作品解決什麼問題？" },
        {
          id: "sample-assistant",
          role: "assistant",
          content: "我可以依照已發布的資料，帶你了解作品的重點。",
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
