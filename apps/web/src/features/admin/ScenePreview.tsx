import { useEffect, useId, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

import {
  CharacterRenderer,
  type CharacterState,
} from "../character/CharacterRenderer";
import { messages } from "../../i18n/messages";
import { VisitorPage } from "../../app/VisitorPage";
import type {
  PublicProfile,
  PublicScene,
  SceneTokens,
} from "../../app/publicTypes";
import type { VisitorMode } from "../../app/scene";

export interface SceneSchemeOption {
  id: string;
  version: number;
  labels: Record<"zh-TW" | "en", string>;
  themes: { light: SceneTokens; dark: SceneTokens };
}

export interface ScenePreviewSettings {
  color_scheme: string;
  color_mode: VisitorMode;
  visitor_mode_toggle: boolean;
  visitor_scheme_choice: boolean;
  accent: string | null;
  background: string;
  focus: { x: number; y: number };
  dim: "auto" | "none" | "low" | "medium" | "high";
  scaling: "smooth" | "pixelated";
}

const CHARACTER_STATES: readonly CharacterState[] = [
  "idle",
  "walk",
  "listen",
  "think",
  "talk",
  "success",
  "offline",
];
const DESKTOP_REFERENCE_WIDTH = 1440;
const PHONE_REFERENCE_WIDTH = 375;

export function ScenePreview({
  locale,
  profile,
  appliedScene,
  proposedScene,
  schemes,
  settings,
  proposalPending,
  onSchemeChange,
  onFocusChange,
  focusTitle,
  focusLabel,
  focusCoordinatesLabel,
  desktopFrameLabel,
  phoneFrameLabel,
}: {
  locale: "zh-TW" | "en";
  profile: PublicProfile;
  appliedScene: PublicScene;
  proposedScene: PublicScene | null;
  schemes: SceneSchemeOption[];
  settings: ScenePreviewSettings;
  proposalPending: boolean;
  onSchemeChange: (schemeId: string) => void;
  onFocusChange: (focus: ScenePreviewSettings["focus"]) => void;
  focusTitle: string;
  focusLabel: string;
  focusCoordinatesLabel: string;
  desktopFrameLabel: string;
  phoneFrameLabel: string;
}) {
  const idPrefix = useId().replaceAll(":", "");
  const [viewport, setViewport] = useState<"desktop" | "mobile">("desktop");
  const [variant, setVariant] = useState<"light" | "dark">("light");
  const [characterState, setCharacterState] = useState<CharacterState>("idle");
  const [conversationMode, setConversationMode] = useState<
    "empty" | "conversation"
  >("conversation");
  const [chatAvailable, setChatAvailable] = useState(true);
  const [showProposal, setShowProposal] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(prefersReducedMotion);
  const [showFocusFrame, setShowFocusFrame] = useState(true);
  const [imageDimensions, setImageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [frameRatios, setFrameRatios] = useState<{
    desktop: number;
    phone: number;
  } | null>(null);
  const desktopHeroRef = useRef<HTMLDivElement | null>(null);
  const phoneHeroRef = useRef<HTMLDivElement | null>(null);
  const visibleViewportRef = useRef<HTMLDivElement | null>(null);
  const focusImageRef = useRef<HTMLImageElement | null>(null);
  const focusMapRef = useRef<HTMLDivElement | null>(null);
  const focusDragging = useRef(false);
  const referenceWidth =
    viewport === "desktop" ? DESKTOP_REFERENCE_WIDTH : PHONE_REFERENCE_WIDTH;
  const [visibleScale, setVisibleScale] = useState(1);
  const [logicalViewportHeight, setLogicalViewportHeight] = useState(800);
  const zh = locale === "zh-TW";
  const selectedScheme = schemes.find(
    (scheme) => scheme.id === settings.color_scheme,
  );
  const provisionalScene = selectedScheme
    ? sceneForScheme(selectedScheme, appliedScene, settings)
    : appliedScene;
  const selectedScene = showProposal
    ? (proposedScene ?? provisionalScene)
    : appliedScene;
  const protectedBackground = backgroundForPreview(
    showProposal ? settings.background : "current",
    profile,
  );
  const selectedFocus = showProposal
    ? settings.focus
    : selectedScene.background_focus;
  const modeLabel = (mode: "light" | "dark") =>
    mode === "light" ? messages[locale].modeLight : messages[locale].modeDark;

  useEffect(() => {
    const measure = () => {
      const availableWidth =
        visibleViewportRef.current?.clientWidth ?? referenceWidth;
      setVisibleScale(previewScaleForWidth(referenceWidth, availableWidth));
      setLogicalViewportHeight(window.innerHeight);
    };
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(measure);
    if (visibleViewportRef.current)
      observer?.observe(visibleViewportRef.current);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [referenceWidth]);

  useEffect(() => {
    setShowProposal(proposalPending);
  }, [proposalPending, settings]);

  useEffect(() => {
    let current = true;
    setImageDimensions(null);
    if (!protectedBackground) return () => undefined;

    const image = new Image();
    image.onload = () => {
      if (current && image.naturalWidth > 0 && image.naturalHeight > 0) {
        setImageDimensions({
          width: image.naturalWidth,
          height: image.naturalHeight,
        });
      }
    };
    image.onerror = () => {
      if (current) setImageDimensions(null);
    };
    image.src = protectedBackground;
    return () => {
      current = false;
      image.onload = null;
      image.onerror = null;
    };
  }, [protectedBackground]);

  useEffect(() => {
    const measure = () => {
      const desktop = desktopHeroRef.current?.getBoundingClientRect();
      const phone = phoneHeroRef.current?.getBoundingClientRect();
      if (
        !desktop?.width ||
        !desktop.height ||
        !phone?.width ||
        !phone.height
      ) {
        return;
      }
      const next = {
        desktop: desktop.width / desktop.height,
        phone: phone.width / phone.height,
      };
      setFrameRatios((current) =>
        current &&
        Math.abs(current.desktop - next.desktop) < 0.0001 &&
        Math.abs(current.phone - next.phone) < 0.0001
          ? current
          : next,
      );
    };
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(measure);
    if (desktopHeroRef.current) observer?.observe(desktopHeroRef.current);
    if (phoneHeroRef.current) observer?.observe(phoneHeroRef.current);
    measure();
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [profile, locale, protectedBackground, selectedScene]);

  function updateFocusFromPointer(event: ReactPointerEvent<HTMLDivElement>) {
    const rect = (
      imageDimensions ? focusImageRef.current : focusMapRef.current
    )?.getBoundingClientRect();
    if (!rect?.width || !rect.height) return;
    onFocusChange({
      x: clampPercent(((event.clientX - rect.left) / rect.width) * 100),
      y: clampPercent(((event.clientY - rect.top) / rect.height) * 100),
    });
  }

  function cropStyle(ratio: number | undefined) {
    if (!imageDimensions || !ratio) return undefined;
    const crop = computeCoverCrop(
      imageDimensions.width,
      imageDimensions.height,
      ratio,
      selectedFocus,
    );
    return {
      left: `${crop.left}%`,
      top: `${crop.top}%`,
      width: `${crop.width}%`,
      height: `${crop.height}%`,
    };
  }

  return (
    <section className="scene-preview" aria-labelledby="scene-preview-title">
      <div className="scene-preview__heading">
        <div>
          <h3 id="scene-preview-title">
            {zh ? "訪客頁面預覽" : "Visitor page preview"}
          </h3>
          <p>
            {zh
              ? "預覽使用目前已發布角色；範例對話不會呼叫模型，也不會儲存訪客偏好。"
              : "Preview uses the currently published character. Example conversation does not call a model or store visitor preferences."}
          </p>
        </div>
        <div className="scene-preview__controls">
          <fieldset>
            <legend>{zh ? "畫面" : "Viewport"}</legend>
            <button
              aria-pressed={viewport === "desktop"}
              onClick={() => setViewport("desktop")}
              type="button"
            >
              {zh ? "桌面" : "Desktop"}
            </button>
            <button
              aria-pressed={viewport === "mobile"}
              onClick={() => setViewport("mobile")}
              type="button"
            >
              {zh ? "手機" : "Mobile"}
            </button>
          </fieldset>
          <fieldset>
            <legend>{zh ? "套用狀態" : "Appearance"}</legend>
            <button
              aria-pressed={!showProposal}
              onClick={() => setShowProposal(false)}
              type="button"
            >
              {zh ? "目前" : "Applied"}
            </button>
            <button
              aria-pressed={showProposal}
              onClick={() => setShowProposal(true)}
              type="button"
            >
              {zh ? "提案" : "Proposed"}
            </button>
          </fieldset>
          <fieldset>
            <legend>{zh ? "色彩版本" : "Color variant"}</legend>
            <button
              aria-pressed={variant === "light"}
              onClick={() => setVariant("light")}
              type="button"
            >
              {modeLabel("light")}
            </button>
            <button
              aria-pressed={variant === "dark"}
              onClick={() => setVariant("dark")}
              type="button"
            >
              {modeLabel("dark")}
            </button>
          </fieldset>
          <fieldset>
            <legend>{zh ? "歡迎畫面" : "Conversation"}</legend>
            <label>
              <input
                checked={conversationMode === "empty"}
                name="scene-preview-conversation"
                onChange={() => setConversationMode("empty")}
                type="radio"
              />
              {zh ? "空白歡迎畫面" : "Empty welcome"}
            </label>
            <label>
              <input
                checked={conversationMode === "conversation"}
                name="scene-preview-conversation"
                onChange={() => setConversationMode("conversation")}
                type="radio"
              />
              {zh ? "對話中" : "In conversation"}
            </label>
          </fieldset>
          <fieldset>
            <legend>{zh ? "聊天狀態" : "Chat availability"}</legend>
            <label>
              <input
                checked={chatAvailable}
                name="scene-preview-availability"
                onChange={() => setChatAvailable(true)}
                type="radio"
              />
              {zh ? "可使用" : "Available"}
            </label>
            <label>
              <input
                checked={!chatAvailable}
                name="scene-preview-availability"
                onChange={() => setChatAvailable(false)}
                type="radio"
              />
              {zh ? "休息中" : "Resting"}
            </label>
          </fieldset>
        </div>
      </div>
      <div className="scene-preview__options">
        <label>
          <input
            checked={reducedMotion}
            onChange={(event) => setReducedMotion(event.target.checked)}
            type="checkbox"
          />
          {zh ? "預覽減少動態" : "Preview reduced motion"}
        </label>
        <label>
          <input
            checked={showFocusFrame}
            onChange={(event) => setShowFocusFrame(event.target.checked)}
            type="checkbox"
          />
          {zh
            ? `顯示取景框（${selectedFocus.x}%, ${selectedFocus.y}%）`
            : `Show crop focus frame (${selectedFocus.x}%, ${selectedFocus.y}%)`}
        </label>
      </div>
      <div
        ref={visibleViewportRef}
        className={`scene-preview__viewport scene-preview__viewport--${viewport}`}
      >
        <div
          className="scene-preview__scaled-viewport"
          style={{
            height: `${logicalViewportHeight * visibleScale}px`,
            width: `${referenceWidth * visibleScale}px`,
          }}
        >
          <div
            className={`scene-preview__logical-page scene-preview__reference-layout scene-preview__reference-layout--${viewport === "mobile" ? "phone" : "desktop"}`}
            style={{
              height: `${logicalViewportHeight}px`,
              transform: `scale(${visibleScale})`,
              width: `${referenceWidth}px`,
            }}
          >
            <VisitorPage
              canAskSuggestion={() => false}
              chatAvailable={chatAvailable}
              characterState={characterState}
              locale={locale}
              mode="preview"
              onLocaleChange={() => undefined}
              onQuestionChange={() => undefined}
              onRecheckStatus={() => undefined}
              onRetry={() => undefined}
              onRetryProfile={() => undefined}
              onSelectSuggestion={() => undefined}
              onSubmit={() => undefined}
              pending={false}
              previewMode={variant}
              profile={profile}
              profileError={false}
              question=""
              reducedMotion={reducedMotion}
              sampleContent
              sampleConversation={conversationMode === "conversation"}
              showFocusFrame={showFocusFrame}
              sceneOverride={{ ...selectedScene, visitor_mode_toggle: false }}
              backgroundUrlOverride={protectedBackground}
              suggestions={profile.suggested_questions}
              turns={[]}
            />
          </div>
        </div>
      </div>
      <fieldset className="scene-preview__focus">
        <legend>{focusTitle}</legend>
        <div
          aria-describedby={`${idPrefix}-focus-coordinates`}
          aria-label={focusTitle}
          className="scene-preview__focus-map"
          onKeyDown={(event) => {
            const step = event.shiftKey ? 10 : 1;
            let next = selectedFocus;
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
              event.preventDefault();
              next = {
                ...selectedFocus,
                x: clampPercent(
                  selectedFocus.x + (event.key === "ArrowRight" ? step : -step),
                ),
              };
            } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              next = {
                ...selectedFocus,
                y: clampPercent(
                  selectedFocus.y + (event.key === "ArrowDown" ? step : -step),
                ),
              };
            }
            if (next !== selectedFocus) onFocusChange(next);
          }}
          onPointerDown={(event) => {
            focusDragging.current = true;
            event.currentTarget.setPointerCapture(event.pointerId);
            updateFocusFromPointer(event);
          }}
          onPointerMove={(event) => {
            if (focusDragging.current) updateFocusFromPointer(event);
          }}
          onPointerUp={(event) => {
            focusDragging.current = false;
            if (event.currentTarget.hasPointerCapture(event.pointerId)) {
              event.currentTarget.releasePointerCapture(event.pointerId);
            }
          }}
          onPointerCancel={() => {
            focusDragging.current = false;
          }}
          onLostPointerCapture={() => {
            focusDragging.current = false;
          }}
          ref={focusMapRef}
          role="group"
          tabIndex={0}
        >
          {protectedBackground ? (
            <img
              alt=""
              className="scene-preview__focus-source"
              draggable={false}
              ref={focusImageRef}
              src={protectedBackground}
              onError={(event) => {
                if (
                  event.currentTarget.getAttribute("src") ===
                  protectedBackground
                ) {
                  setImageDimensions(null);
                }
              }}
            />
          ) : (
            <div className="scene-preview__focus-empty" />
          )}
          {imageDimensions && (
            <>
              <span
                aria-hidden="true"
                className="scene-preview__crop scene-preview__crop--desktop"
                style={cropStyle(frameRatios?.desktop)}
              />
              <span
                aria-hidden="true"
                className="scene-preview__crop scene-preview__crop--phone"
                style={cropStyle(frameRatios?.phone)}
              />
              <span
                aria-hidden="true"
                className="scene-preview__focus-point"
                style={{
                  left: `${selectedFocus.x}%`,
                  top: `${selectedFocus.y}%`,
                }}
              />
            </>
          )}
        </div>
        <div
          className="scene-preview__crop-legend"
          role="group"
          aria-label={zh ? "裁切畫面比例" : "Crop viewport ratios"}
        >
          <span>
            <i
              aria-hidden="true"
              className="scene-preview__crop-key scene-preview__crop-key--desktop"
            />
            {desktopFrameLabel}
            {frameRatios ? ` · ${frameRatios.desktop.toFixed(2)}:1` : ""}
          </span>
          <span>
            <i
              aria-hidden="true"
              className="scene-preview__crop-key scene-preview__crop-key--phone"
            />
            {phoneFrameLabel}
            {frameRatios ? ` · ${frameRatios.phone.toFixed(2)}:1` : ""}
          </span>
        </div>
        <p className="scene-preview__focus-help">
          {protectedBackground
            ? focusLabel
            : zh
              ? "加入背景圖片後即可拖曳圖片調整取景；滑桿仍可設定位置。"
              : "Add a background to drag focus over the image; the sliders remain available."}
        </p>
        <p
          aria-live="polite"
          className="scene-preview__focus-coordinates"
          id={`${idPrefix}-focus-coordinates`}
          role="status"
        >
          {focusCoordinatesLabel}: {selectedFocus.x}%, {selectedFocus.y}%
        </p>
      </fieldset>
      <fieldset className="scene-preview__states">
        <legend>{zh ? "角色狀態" : "Character state"}</legend>
        {CHARACTER_STATES.map((state) => (
          <button
            aria-pressed={characterState === state}
            key={state}
            onClick={() => setCharacterState(state)}
            type="button"
          >
            {
              messages[locale][
                ("character" +
                  capitalize(state)) as keyof (typeof messages)["en"]
              ] as string
            }
          </button>
        ))}
      </fieldset>
      <div
        className="scene-preview__sprites"
        role="group"
        aria-label={zh ? "角色預覽" : "Character preview"}
      >
        {CHARACTER_STATES.map((state) => (
          <figure key={state}>
            <CharacterRenderer
              assetUrl={`/api/public/character.png?rev=${profile.character.revision}`}
              frameDurationMs={profile.character.frame_duration_ms}
              movement={profile.character.movement}
              reducedMotion={reducedMotion || state !== characterState}
              state={state}
              stateLabel={
                messages[locale][
                  ("character" +
                    capitalize(state)) as keyof (typeof messages)["en"]
                ] as string
              }
            />
            <figcaption>
              {
                messages[locale][
                  ("character" +
                    capitalize(state)) as keyof (typeof messages)["en"]
                ] as string
              }
            </figcaption>
          </figure>
        ))}
      </div>
      <fieldset className="scene-preview__scheme-gallery">
        <legend id="scene-preview-schemes-title">
          {zh ? "配色方案" : "Color schemes"}
        </legend>
        <p>
          {zh
            ? "每張縮圖都是訪客頁面的即時預覽，左側淺色、右側深色；選擇後預覽會立即更新。內容為範例。"
            : "Each tile is a live visitor-page preview, light on the left and dark on the right. Selecting one updates the preview. Content is sample text."}
        </p>
        <div className="scene-preview__scheme-list">
          {schemes.map((scheme) => {
            const scene = sceneForScheme(scheme, selectedScene, settings);
            return (
              <article className="scene-preview__scheme-card" key={scheme.id}>
                <span className="scene-preview__scheme-choice">
                  <input
                    checked={settings.color_scheme === scheme.id}
                    id={`${idPrefix}-scene-preview-scheme-${scheme.id}`}
                    name={`${idPrefix}-scene-preview-scheme`}
                    onChange={() => onSchemeChange(scheme.id)}
                    type="radio"
                  />
                  <label
                    htmlFor={`${idPrefix}-scene-preview-scheme-${scheme.id}`}
                  >
                    {scheme.labels[locale]}
                  </label>
                </span>
                <div
                  aria-hidden="true"
                  className="scene-preview__miniatures"
                  inert
                >
                  {(["light", "dark"] as const).map((theme) => (
                    <div
                      className={`scene-preview__miniature scene-preview__miniature--${theme}`}
                      key={theme}
                    >
                      <span className="scene-preview__miniature-label">
                        {modeLabel(theme)}
                      </span>
                      <div className="scene-preview__miniature-canvas">
                        <VisitorPage
                          canAskSuggestion={() => false}
                          chatAvailable={chatAvailable}
                          characterState="idle"
                          locale={locale}
                          mode="preview"
                          onLocaleChange={() => undefined}
                          onQuestionChange={() => undefined}
                          onRecheckStatus={() => undefined}
                          onRetry={() => undefined}
                          onRetryProfile={() => undefined}
                          onSelectSuggestion={() => undefined}
                          onSubmit={() => undefined}
                          pending={false}
                          previewMode={theme}
                          profile={profile}
                          profileError={false}
                          question=""
                          reducedMotion={reducedMotion}
                          sampleContent
                          sampleConversation={
                            conversationMode === "conversation"
                          }
                          sceneOverride={scene}
                          backgroundUrlOverride={protectedBackground}
                          suggestions={profile.suggested_questions}
                          turns={[]}
                          compactPreview
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      </fieldset>
      <div className="scene-preview__geometry-probes" aria-hidden="true" inert>
        <div
          className="scene-preview__geometry-probe scene-preview__geometry-probe--desktop scene-preview__reference-layout scene-preview__reference-layout--desktop"
          style={{ width: `${DESKTOP_REFERENCE_WIDTH}px` }}
        >
          <VisitorPage
            canAskSuggestion={() => false}
            chatAvailable={chatAvailable}
            characterState={characterState}
            locale={locale}
            mode="preview"
            onLocaleChange={() => undefined}
            onQuestionChange={() => undefined}
            onRecheckStatus={() => undefined}
            onRetry={() => undefined}
            onRetryProfile={() => undefined}
            onSelectSuggestion={() => undefined}
            onSubmit={() => undefined}
            pending={false}
            previewMode={variant}
            previewHeroRef={desktopHeroRef}
            profile={profile}
            profileError={false}
            question=""
            reducedMotion
            sampleContent
            sceneOverride={{ ...selectedScene, visitor_mode_toggle: false }}
            backgroundUrlOverride={protectedBackground}
            suggestions={profile.suggested_questions}
            turns={[]}
          />
        </div>
        <div
          className="scene-preview__geometry-probe scene-preview__geometry-probe--phone scene-preview__reference-layout scene-preview__reference-layout--phone"
          style={{ width: `${PHONE_REFERENCE_WIDTH}px` }}
        >
          <VisitorPage
            canAskSuggestion={() => false}
            chatAvailable={chatAvailable}
            characterState={characterState}
            locale={locale}
            mode="preview"
            onLocaleChange={() => undefined}
            onQuestionChange={() => undefined}
            onRecheckStatus={() => undefined}
            onRetry={() => undefined}
            onRetryProfile={() => undefined}
            onSelectSuggestion={() => undefined}
            onSubmit={() => undefined}
            pending={false}
            previewMode={variant}
            previewHeroRef={phoneHeroRef}
            profile={profile}
            profileError={false}
            question=""
            reducedMotion
            sampleContent
            sceneOverride={{ ...selectedScene, visitor_mode_toggle: false }}
            backgroundUrlOverride={protectedBackground}
            suggestions={profile.suggested_questions}
            turns={[]}
          />
        </div>
      </div>
    </section>
  );
}

function sceneForScheme(
  scheme: SceneSchemeOption,
  base: PublicScene,
  settings: ScenePreviewSettings,
): PublicScene {
  return {
    ...base,
    scheme: { id: scheme.id, version: scheme.version },
    color_mode: "system",
    visitor_mode_toggle: false,
    themes: scheme.themes,
    background_dim:
      settings.dim === "auto" ? base.background_dim : settings.dim,
    background_scaling: settings.scaling,
    background_focus: settings.focus,
  };
}

function backgroundForPreview(
  background: string,
  profile: PublicProfile,
): string | null {
  if (background === "none") return null;
  if (background.startsWith("draft:")) {
    const id = background.slice("draft:".length);
    return /^[A-Za-z0-9_-]{32,64}$/.test(id)
      ? "/api/admin/assets/scene/background-drafts/" + id
      : null;
  }
  return profile.character.scene?.background_url ?? null;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

// eslint-disable-next-line react-refresh/only-export-components -- pure geometry is exported for its focused unit test
export function computeCoverCrop(
  imageWidth: number,
  imageHeight: number,
  targetRatio: number,
  focus: ScenePreviewSettings["focus"],
) {
  const cropWidth = Math.min(imageWidth, imageHeight * targetRatio);
  const cropHeight = Math.min(imageHeight, imageWidth / targetRatio);
  return {
    left: ((imageWidth - cropWidth) * focus.x) / imageWidth,
    top: ((imageHeight - cropHeight) * focus.y) / imageHeight,
    width: (cropWidth / imageWidth) * 100,
    height: (cropHeight / imageHeight) * 100,
  };
}

function clampPercent(value: number): number {
  return Math.round(Math.min(100, Math.max(0, value)));
}

// eslint-disable-next-line react-refresh/only-export-components -- pure viewport calculation is covered by the scene preview test
export function previewScaleForWidth(
  referenceWidth: number,
  availableWidth: number,
): number {
  if (referenceWidth <= 0 || availableWidth <= 0) return 1;
  return Math.min(1, availableWidth / referenceWidth);
}
