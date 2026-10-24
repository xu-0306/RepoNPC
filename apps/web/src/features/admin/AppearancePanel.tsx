import { useEffect, useMemo, useRef, useState } from "react";
import type { DragEvent as ReactDragEvent } from "react";
import { Button, FileTrigger } from "react-aria-components";

import type { PublicProfile, PublicScene } from "../../app/publicTypes";
import type { ScenePreviewSettings, SceneSchemeOption } from "./ScenePreview";
import { ScenePreview } from "./ScenePreview";
import "./scene.css";
import "../../p4-w3.css";

export interface SceneAppearanceState {
  source_bundle_id: string;
  source_character_revision: number;
  character_revision: number;
  appearance_revision: number;
  sprite_sha256: string;
  draft_revision: string | null;
  issued_revision: number;
  scene: PublicScene;
  settings: ScenePreviewSettings | null;
  defaults: ScenePreviewSettings;
  schemes: SceneSchemeOption[];
}

type SceneAppearanceIdentity = Pick<
  SceneAppearanceState,
  | "source_bundle_id"
  | "source_character_revision"
  | "character_revision"
  | "appearance_revision"
  | "sprite_sha256"
  | "draft_revision"
>;

interface PreviewNotice {
  kind: string;
  variant?: "light" | "dark";
  adjusted_value?: string;
  reason?: string;
}

type OperationKind = "upload" | "remove" | "preview" | "apply" | "cancel";

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

export function AppearancePanel({
  locale,
  initialState,
  request,
  onStateChange,
  applyDisabled = false,
}: {
  locale: "zh-TW" | "en";
  initialState: SceneAppearanceState;
  request: Request;
  onStateChange: (state: SceneAppearanceState) => void;
  applyDisabled?: boolean;
}) {
  const copy = appearanceCopy[locale];
  const [state, setState] = useState(initialState);
  const [settings, setSettings] = useState<ScenePreviewSettings>(
    initialState.settings ?? initialState.defaults,
  );
  const settingsRef = useRef(settings);
  const acceptedSceneIdentity = useRef(sceneIdentity(initialState));
  const [dirty, setDirty] = useState(false);
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [profileUnavailable, setProfileUnavailable] = useState(false);
  const [proposalScene, setProposalScene] = useState<PublicScene | null>(null);
  const [proposalSettingsIdentity, setProposalSettingsIdentity] = useState<
    string | null
  >(null);
  const [notices, setNotices] = useState<PreviewNotice[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [dropActive, setDropActive] = useState(false);
  const operation = useRef<AbortController | null>(null);
  const operationKind = useRef<OperationKind | null>(null);
  const previewAttemptedIdentity = useRef<string | null>(null);
  const previewRequest = useRef<() => void>(() => undefined);
  const privateDraftId = useRef<string | null>(null);
  const settingsIdentity = JSON.stringify(settings);
  const selectedScheme = useMemo(
    () => state.schemes.find((scheme) => scheme.id === settings.color_scheme),
    [settings.color_scheme, state.schemes],
  );
  const accentValue =
    settings.accent ?? selectedScheme?.themes.light.accent ?? "";
  const hasPrivateReceipt = state.settings !== null;
  const matchingProfile =
    isCurrentAppearanceState(state, initialState) &&
    matchesAppearanceProfile(profile, state, locale)
      ? profile
      : null;

  useEffect(() => {
    setBusy(false);
    setNotice("");
    previewAttemptedIdentity.current = null;
    return () => {
      operation.current?.abort();
      operation.current = null;
      operationKind.current = null;
    };
  }, [locale, request]);

  useEffect(() => {
    setState(initialState);
    const nextIdentity = sceneIdentity(initialState);
    if (acceptedSceneIdentity.current === nextIdentity) return;
    operation.current?.abort();
    operation.current = null;
    operationKind.current = null;
    setBusy(false);
    acceptedSceneIdentity.current = nextIdentity;
    previewAttemptedIdentity.current = null;
    const nextSettings = initialState.settings ?? initialState.defaults;
    settingsRef.current = nextSettings;
    setSettings(nextSettings);
    setDirty(false);
    setProposalScene(null);
    setProposalSettingsIdentity(null);
    setNotices([]);
  }, [initialState]);

  useEffect(() => {
    const controller = new AbortController();
    setProfile(null);
    setProfileUnavailable(false);
    void request<PublicProfile>(
      "/api/public/profile?locale=" + encodeURIComponent(locale),
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setProfile(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setProfileUnavailable(true);
      });
    return () => controller.abort();
  }, [locale, request, state.character_revision, state.source_bundle_id]);

  useEffect(() => {
    if (
      !dirty ||
      !matchingProfile ||
      busy ||
      proposalSettingsIdentity === settingsIdentity ||
      previewAttemptedIdentity.current === settingsIdentity
    ) {
      return;
    }
    const timer = window.setTimeout(() => {
      if (JSON.stringify(settingsRef.current) === settingsIdentity) {
        previewRequest.current();
      }
    }, 180);
    return () => window.clearTimeout(timer);
  }, [
    busy,
    dirty,
    matchingProfile,
    proposalSettingsIdentity,
    settingsIdentity,
  ]);

  function update(patch: Partial<ScenePreviewSettings>) {
    if (operationKind.current === "preview" && operation.current) {
      operation.current.abort();
      operation.current = null;
      operationKind.current = null;
      setBusy(false);
    }
    previewAttemptedIdentity.current = null;
    const next = { ...settingsRef.current, ...patch };
    settingsRef.current = next;
    setSettings(next);
    setDirty(true);
    setProposalScene(null);
    setProposalSettingsIdentity(null);
    setNotices([]);
    setNotice("");
  }

  function begin(kind: OperationKind) {
    if (operationKind.current === "preview" && operation.current) {
      operation.current.abort();
      operation.current = null;
      operationKind.current = null;
      setBusy(false);
    }
    if (operation.current) return null;
    const controller = new AbortController();
    operation.current = controller;
    operationKind.current = kind;
    setBusy(true);
    setNotice("");
    return controller;
  }

  function finish(controller: AbortController) {
    if (operation.current !== controller) return;
    operation.current = null;
    operationKind.current = null;
    setBusy(false);
  }

  async function uploadBackground(file: File) {
    const controller = begin("upload");
    if (!controller) return;
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await request<{ draft_id: string }>(
        "/api/admin/assets/scene/background-drafts",
        { method: "POST", body: form, signal: controller.signal },
      );
      if (operation.current !== controller) return;
      privateDraftId.current = result.draft_id;
      update({ background: "draft:" + result.draft_id });
    } catch (error) {
      if (operation.current === controller)
        setNotice(error instanceof Error ? error.message : copy.requestFailed);
    } finally {
      finish(controller);
    }
  }

  async function removeBackground() {
    if (operation.current && operationKind.current !== "preview") return;
    const draftId =
      privateDraftId.current ?? selectedDraftId(settings.background);
    update({ background: "none" });
    if (!draftId) return;
    const controller = begin("remove");
    if (!controller) return;
    try {
      await request<void>(
        "/api/admin/assets/scene/background-drafts/" +
          encodeURIComponent(draftId),
        { method: "DELETE", signal: controller.signal },
      );
      if (operation.current === controller) privateDraftId.current = null;
    } catch (error) {
      if (operation.current === controller)
        setNotice(error instanceof Error ? error.message : copy.requestFailed);
    } finally {
      finish(controller);
    }
  }

  async function preview() {
    const controller = begin("preview");
    if (!controller) return;
    const proposedSettings = {
      ...settingsRef.current,
      focus: { ...settingsRef.current.focus },
    };
    const settingsIdentity = JSON.stringify(proposedSettings);
    previewAttemptedIdentity.current = settingsIdentity;
    try {
      const result = await request<{
        scene: PublicScene;
        notices: PreviewNotice[];
      }>("/api/admin/scene/preview", {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify(proposedSettings),
      });
      if (operation.current !== controller) return;
      if (JSON.stringify(settingsRef.current) !== settingsIdentity) {
        setProposalScene(null);
        setProposalSettingsIdentity(null);
        setNotices([]);
        setNotice(copy.previewOutdated);
        return;
      }
      setProposalScene(result.scene);
      setProposalSettingsIdentity(settingsIdentity);
      setNotices(result.notices ?? []);
    } catch (error) {
      if (operation.current === controller) {
        setNotice(error instanceof Error ? error.message : copy.requestFailed);
        setProposalScene(null);
      }
    } finally {
      finish(controller);
    }
  }

  previewRequest.current = () => {
    void preview();
  };

  async function apply() {
    if (operation.current) return;
    if (!matchingProfile) {
      setNotice(copy.profileUnavailable);
      return;
    }
    if (applyDisabled) {
      setNotice(copy.saveDraftFirst);
      return;
    }
    const appliedSettings = {
      ...settingsRef.current,
      focus: { ...settingsRef.current.focus },
    };
    const settingsIdentity = JSON.stringify(appliedSettings);
    if (!proposalScene || proposalSettingsIdentity !== settingsIdentity) {
      setNotice(copy.previewOutdated);
      setProposalScene(null);
      setProposalSettingsIdentity(null);
      return;
    }
    const controller = begin("apply");
    if (!controller) return;
    try {
      const result = await request<{
        scene_state?: SceneAppearanceState;
      }>("/api/admin/scene", {
        method: "PUT",
        signal: controller.signal,
        body: JSON.stringify({
          proposal: appliedSettings,
          expected: {
            source_bundle_id: state.source_bundle_id,
            source_character_revision: state.source_character_revision,
            character_revision: state.character_revision,
            appearance_revision: state.appearance_revision,
            draft_revision: state.draft_revision,
            sprite_sha256: state.sprite_sha256,
          },
        }),
      });
      const updated =
        result.scene_state ??
        (
          await request<{ scene_state: SceneAppearanceState }>(
            "/api/admin/portfolio/status",
            { signal: controller.signal },
          )
        ).scene_state;
      if (operation.current !== controller) return;
      setState(updated);
      acceptedSceneIdentity.current = sceneIdentity(updated);
      onStateChange(updated);
      if (JSON.stringify(settingsRef.current) === settingsIdentity) {
        const nextSettings = updated.settings ?? updated.defaults;
        settingsRef.current = nextSettings;
        setSettings(nextSettings);
        setDirty(false);
        setNotice(copy.applied);
      } else {
        setDirty(true);
        setNotice(copy.appliedWithEdits);
      }
      setProposalScene(null);
      setProposalSettingsIdentity(null);
      setNotices([]);
    } catch (error) {
      if (operation.current === controller)
        setNotice(error instanceof Error ? error.message : copy.requestFailed);
    } finally {
      finish(controller);
    }
  }

  function resetDefaults() {
    update(state.defaults);
  }

  async function cancelChanges() {
    const controller = begin("cancel");
    if (!controller) return;
    const draftId =
      privateDraftId.current ?? selectedDraftId(settingsRef.current.background);
    const next = state.settings ?? state.defaults;
    settingsRef.current = next;
    setSettings(next);
    setDirty(false);
    setProposalScene(null);
    setProposalSettingsIdentity(null);
    setNotices([]);
    try {
      if (draftId) {
        await request<void>(
          "/api/admin/assets/scene/background-drafts/" +
            encodeURIComponent(draftId),
          { method: "DELETE", signal: controller.signal },
        );
      }
      if (operation.current === controller) {
        privateDraftId.current = null;
        setNotice(copy.cancelled);
      }
    } catch (error) {
      if (operation.current === controller)
        setNotice(error instanceof Error ? error.message : copy.requestFailed);
    } finally {
      finish(controller);
    }
  }

  return (
    <section
      className="scene-appearance"
      lang={locale}
      aria-labelledby="scene-appearance-title"
    >
      <header className="scene-appearance__header">
        <div>
          <h2 id="scene-appearance-title">{copy.title}</h2>
          <details className="publication-info px-info">
            <summary>ⓘ {copy.noModel}</summary>
            <p>{copy.description}</p>
          </details>
          <p className="scene-appearance__revision">
            {copy.revision}: {state.character_revision} ·{" "}
            {copy.appearanceRevision}: {state.appearance_revision}
          </p>
        </div>
      </header>

      {!hasPrivateReceipt && (
        <p className="scene-appearance__unknown" role="note">
          {copy.receiptMissing}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {profileUnavailable && <p role="alert">{copy.profileUnavailable}</p>}
      {!matchingProfile && !profileUnavailable && (
        <p role="status">
          {locale === "zh-TW"
            ? "正在讀取與場景版本相符的作品集…"
            : "Loading the portfolio for this scene revision…"}
        </p>
      )}

      {matchingProfile && (
        <ScenePreview
          appliedScene={state.scene}
          desktopFrameLabel={copy.desktopFrame}
          focusCoordinatesLabel={copy.focusCoordinates}
          focusLabel={copy.focusPicker}
          focusTitle={copy.focus}
          locale={locale}
          onFocusChange={(focus) => update({ focus })}
          onSchemeChange={(color_scheme) => update({ color_scheme })}
          phoneFrameLabel={copy.phoneFrame}
          profile={matchingProfile}
          proposalPending={dirty}
          proposedScene={proposalScene}
          schemes={state.schemes}
          settings={settings}
        />
      )}
      <div className="scene-appearance__form">
        {!matchingProfile && (
          <fieldset>
            <legend>{copy.scheme}</legend>
            <div className="scene-appearance__radio-row">
              {state.schemes.map((scheme) => (
                <label key={scheme.id}>
                  <input
                    className="px-field"
                    checked={settings.color_scheme === scheme.id}
                    name="appearance-color-scheme"
                    onChange={() => update({ color_scheme: scheme.id })}
                    type="radio"
                  />
                  {scheme.labels[locale]}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        <div className="scene-appearance__controls-grid">
          <label>
            {copy.mode}
            <select
              className="px-field"
              value={settings.color_mode}
              onChange={(event) =>
                update({
                  color_mode: event.target
                    .value as ScenePreviewSettings["color_mode"],
                })
              }
            >
              <option value="system">{copy.system}</option>
              <option value="light">{copy.light}</option>
              <option value="dark">{copy.dark}</option>
            </select>
          </label>
          <label className="scene-appearance__toggle">
            <input
              className="px-field"
              checked={settings.visitor_mode_toggle}
              role="switch"
              aria-checked={settings.visitor_mode_toggle}
              onChange={(event) =>
                update({ visitor_mode_toggle: event.target.checked })
              }
              type="checkbox"
            />
            {copy.toggle}
          </label>
          <label className="scene-appearance__toggle">
            <input
              className="px-field"
              checked={settings.visitor_scheme_choice}
              role="switch"
              aria-checked={settings.visitor_scheme_choice}
              onChange={(event) =>
                update({ visitor_scheme_choice: event.target.checked })
              }
              type="checkbox"
            />
            {copy.schemeChoice}
          </label>
        </div>
        <details className="scene-appearance__advanced">
          <summary>
            {locale === "zh-TW" ? "進階：強調色" : "Advanced: accent color"}
          </summary>
          <label>
            {copy.accent}
            <input
              className="px-field"
              aria-label={copy.accent}
              disabled={!selectedScheme}
              onChange={(event) =>
                update({ accent: event.target.value.toLowerCase() })
              }
              type="color"
              value={accentValue}
            />
          </label>
          <button
            className="px-button px-button--secondary"
            onClick={() => update({ accent: null })}
            type="button"
          >
            {copy.useSchemeAccent}
          </button>
        </details>

        <fieldset
          className={`scene-appearance__upload-zone${dropActive ? " scene-appearance__upload-zone--active" : ""}`}
          data-drag-active={dropActive ? "true" : undefined}
          disabled={busy && operationKind.current !== "preview"}
          onDragEnter={() => setDropActive(true)}
          onDragOver={(event) => {
            event.preventDefault();
            setDropActive(true);
          }}
          onDragLeave={(event) => {
            if (
              !(event.relatedTarget instanceof Node) ||
              !event.currentTarget.contains(event.relatedTarget)
            ) {
              setDropActive(false);
            }
          }}
          onDrop={(event: ReactDragEvent<HTMLFieldSetElement>) => {
            event.preventDefault();
            setDropActive(false);
            const file = event.dataTransfer.files[0];
            if (file) void uploadBackground(file);
          }}
        >
          <legend>{copy.background}</legend>
          <div className="scene-appearance__radio-row">
            <label>
              <input
                className="px-field"
                checked={settings.background === "current"}
                name="appearance-background"
                onChange={() => update({ background: "current" })}
                type="radio"
              />
              {copy.backgroundCurrent}
            </label>
            <label>
              <input
                className="px-field"
                checked={settings.background === "none"}
                name="appearance-background"
                onChange={() => update({ background: "none" })}
                type="radio"
              />
              {copy.backgroundNone}
            </label>
            {settings.background.startsWith("draft:") && (
              <span>{copy.backgroundDraftSelected}</span>
            )}
          </div>
          <FileTrigger
            acceptedFileTypes={["image/png", "image/webp", ".png", ".webp"]}
            onSelect={(files) => {
              const file = files?.[0];
              if (file) void uploadBackground(file);
            }}
          >
            <Button
              className="px-button px-button--secondary"
              isDisabled={busy && operationKind.current !== "preview"}
            >
              {copy.upload}
            </Button>
          </FileTrigger>
          <button
            className="px-button px-button--secondary"
            disabled={
              (busy && operationKind.current !== "preview") ||
              settings.background === "none"
            }
            onClick={() => void removeBackground()}
            type="button"
          >
            {copy.removeBackground}
          </button>
          <p className="scene-appearance__drop-hint">{copy.dropHint}</p>
        </fieldset>

        <fieldset>
          <legend>{copy.focus}</legend>
          <label>
            {copy.horizontal} ({settings.focus.x}%)
            <input
              className="px-field"
              max="100"
              min="0"
              onChange={(event) =>
                update({
                  focus: { ...settings.focus, x: Number(event.target.value) },
                })
              }
              type="range"
              value={settings.focus.x}
            />
          </label>
          <label>
            {copy.vertical} ({settings.focus.y}%)
            <input
              className="px-field"
              max="100"
              min="0"
              onChange={(event) =>
                update({
                  focus: { ...settings.focus, y: Number(event.target.value) },
                })
              }
              type="range"
              value={settings.focus.y}
            />
          </label>
          <p>{copy.focusPicker}</p>
        </fieldset>

        <div className="scene-appearance__controls-grid">
          <label>
            {copy.dim}
            <select
              className="px-field"
              value={settings.dim}
              onChange={(event) =>
                update({
                  dim: event.target.value as ScenePreviewSettings["dim"],
                })
              }
            >
              {(["auto", "none", "low", "medium", "high"] as const).map(
                (dim) => (
                  <option key={dim} value={dim}>
                    {copy[dim]}
                  </option>
                ),
              )}
            </select>
          </label>
          <label>
            {copy.scaling}
            <select
              className="px-field"
              value={settings.scaling}
              onChange={(event) =>
                update({
                  scaling: event.target
                    .value as ScenePreviewSettings["scaling"],
                })
              }
            >
              <option value="smooth">{copy.smooth}</option>
              <option value="pixelated">{copy.pixelated}</option>
            </select>
          </label>
        </div>
      </div>

      <div className="publication-actions">
        <button
          className="px-button px-button--secondary"
          disabled={busy && operationKind.current !== "preview"}
          onClick={resetDefaults}
          type="button"
        >
          {copy.reset}
        </button>
        <button
          className="px-button px-button--secondary"
          disabled={
            (busy && operationKind.current !== "preview") ||
            (!dirty && !privateDraftId.current)
          }
          onClick={() => void cancelChanges()}
          type="button"
        >
          {copy.cancel}
        </button>
      </div>
      <footer className="scene-appearance__actions">
        <button
          className="px-button px-button--secondary"
          disabled={busy || !dirty || !matchingProfile}
          onClick={() => void preview()}
          type="button"
        >
          {copy.preview}
        </button>
        <button
          className="px-button px-button--primary"
          disabled={
            busy ||
            applyDisabled ||
            !matchingProfile ||
            !dirty ||
            !proposalScene ||
            proposalSettingsIdentity !== JSON.stringify(settings)
          }
          onClick={() => void apply()}
          type="button"
        >
          {copy.apply}
        </button>
      </footer>
      {applyDisabled && <p role="status">{copy.saveDraftFirst}</p>}

      {notices.length > 0 && (
        <div className="scene-appearance__notices" role="status">
          <h3>{copy.notices}</h3>
          <ul>
            {notices.map((item, index) => {
              const localized = localizedPreviewNotice(locale, item);
              return (
                <li key={index}>
                  {item.variant ? copy[item.variant] + ": " : ""}
                  {noticeCopy(copy, item.kind)}
                  {localized.adjustedLabel && (
                    <span> {localized.adjustedLabel}</span>
                  )}
                  {localized.reason && (
                    <span className="scene-appearance__notice-reason">
                      {" "}
                      {localized.reason}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

export function matchesAppearanceProfile(
  profile: PublicProfile | null,
  state: Pick<SceneAppearanceState, "source_bundle_id" | "character_revision">,
  locale: "zh-TW" | "en",
): profile is PublicProfile {
  return (
    profile !== null &&
    profile.locale === locale &&
    profile.index.version === state.source_bundle_id &&
    profile.character.revision === state.character_revision
  );
}

export function isCurrentAppearanceState(
  state: SceneAppearanceIdentity,
  incoming: SceneAppearanceIdentity,
): boolean {
  return (
    sceneIdentity(state) === sceneIdentity(incoming) &&
    state.draft_revision === incoming.draft_revision
  );
}

function selectedDraftId(background: string): string | null {
  if (!background.startsWith("draft:")) return null;
  const id = background.slice("draft:".length);
  return /^[A-Za-z0-9_-]{32,64}$/.test(id) ? id : null;
}

function sceneIdentity(state: SceneAppearanceIdentity): string {
  return JSON.stringify([
    state.source_bundle_id,
    state.source_character_revision,
    state.character_revision,
    state.appearance_revision,
    state.sprite_sha256,
  ]);
}

type AppearanceCopy = {
  [Key in keyof typeof appearanceCopy.en]: string;
};

function adjustedValueCopy(
  copy: AppearanceCopy,
  item: PreviewNotice,
): string | null {
  const value = item.adjusted_value;
  if (typeof value !== "string") return null;
  if (/^#[0-9a-fA-F]{6}$/.test(value)) return value.toLowerCase();
  if (
    ["background_dim_adjusted", "stage_plate"].includes(item.kind) &&
    ["none", "low", "medium", "high"].includes(value)
  ) {
    return copy[value as "none" | "low" | "medium" | "high"];
  }
  return null;
}

function noticeCopy(copy: AppearanceCopy, kind: string): string {
  const values: Record<string, string> = {
    accent_adjusted: copy.noticeAccentAdjusted,
    stage_adjusted: copy.noticeStageAdjusted,
    stage_plate: copy.noticeStagePlate,
    background_dim_adjusted: copy.noticeDimAdjusted,
    background_dim_unresolved: copy.noticeBackgroundDim,
    image_upscaled: copy.noticeImageUpscaled,
    strong_crop: copy.noticeStrongCrop,
  };
  return values[kind] ?? copy.noticeGeneric;
}

function noticeReasonCopy(
  copy: AppearanceCopy,
  item: PreviewNotice,
  locale: "zh-TW" | "en",
): string {
  if (locale === "en" && item.reason) return item.reason;
  const values: Record<string, string> = {
    accent_adjusted: copy.reasonAccentAdjusted,
    stage_adjusted: copy.reasonStageAdjusted,
    stage_plate: copy.reasonStagePlate,
    background_dim_adjusted: copy.reasonDimAdjusted,
    background_dim_unresolved: copy.reasonDimAdjusted,
    image_upscaled: copy.reasonImageUpscaled,
    strong_crop: copy.reasonStrongCrop,
  };
  return values[item.kind] ?? "";
}

// eslint-disable-next-line react-refresh/only-export-components -- tested localization helper used by the component above
export function localizedPreviewNotice(
  locale: "zh-TW" | "en",
  item: PreviewNotice,
): { adjustedLabel: string | null; reason: string } {
  const copy = appearanceCopy[locale];
  const adjustedValue = adjustedValueCopy(copy, item);
  return {
    adjustedLabel: adjustedValue ? `${copy.adjustedTo} ${adjustedValue}` : null,
    reason: noticeReasonCopy(copy, item, locale),
  };
}

const appearanceCopy = {
  "zh-TW": {
    title: "訪客外觀",
    description:
      "調整訪客頁面的配色與背景。套用外觀只更新場景，不會重新準備或重新索引專案。",
    receiptMissing:
      "目前版本保留了已發布的場景，但沒有可還原的原始外觀設定。預覽和套用前請明確選擇新設定。",
    scheme: "配色方案",
    mode: "預設色彩模式",
    toggle: "允許訪客切換模式",
    schemeChoice: "允許訪客切換配色",
    accent: "自訂強調色",
    useSchemeAccent: "使用方案色彩",
    background: "背景圖片",
    backgroundCurrent: "沿用目前圖片",
    backgroundNone: "不使用圖片",
    backgroundDraftSelected: "已選取上傳圖片",
    upload: "選擇 PNG 或 WebP 圖片",
    dropHint: "也可以拖放 PNG 或 WebP（640×360 至 2560×1600，最大 2 MB）。",
    removeBackground: "移除背景",
    focus: "背景取景位置",
    horizontal: "水平",
    vertical: "垂直",
    focusPicker: "點擊或拖曳圖片設定取景；滑桿也支援方向鍵。",
    focusCoordinates: "目前取景位置",
    desktopFrame: "桌面裁切",
    phoneFrame: "手機裁切",
    dim: "背景明暗",
    scaling: "圖片縮放方式",
    smooth: "平滑縮放",
    pixelated: "像素風格",
    preview: "預覽外觀",
    apply: "套用外觀",
    saveDraftFirst: "請先儲存本機草稿，再套用外觀。",
    reset: "還原預設值",
    cancel: "取消變更",
    cancelled: "變更已取消，私人圖片草稿已刪除；公開外觀沒有變更。",
    applied: "外觀已套用；其他已儲存內容沒有發布。",
    appliedWithEdits: "已套用預覽時的設定；較新的編輯尚未套用。",
    previewOutdated: "設定在預覽期間已變更，請重新預覽。",
    noModel: "預覽和套用不會呼叫模型。",
    revision: "角色版本",
    appearanceRevision: "外觀版本",
    profileUnavailable: "無法載入目前訪客頁面，請稍後重試。",
    requestFailed: "操作未完成，請檢查輸入內容或服務狀態後重試。",
    notices: "預覽調整提示",
    light: "淺色",
    dark: "深色",
    system: "系統",
    auto: "自動",
    none: "無",
    low: "低",
    medium: "中",
    high: "高",
    noticeAccentAdjusted: "此色彩版本的強調色已調整，以符合對比要求。",
    noticeStageAdjusted: "此色彩版本的角色舞台顏色已調整，以符合對比要求。",
    noticeStagePlate: "角色舞台使用不透明底板，確保角色清楚分離。",
    noticeDimAdjusted: "此色彩版本的背景明暗已提高。",
    noticeBackgroundDim: "此背景需要較深明暗設定以保持角色清晰。",
    noticeImageUpscaled: "這張圖片在訪客頁面可能會放大顯示。",
    noticeStrongCrop: "目前取景會裁切較多圖片內容。",
    noticeGeneric: "場景已安全調整。",
    adjustedTo: "調整為",
    reasonAccentAdjusted: "強調色明暗已微調，以符合文字對比要求。",
    reasonStageAdjusted: "舞台明暗已調整，讓角色邊緣保持清楚。",
    reasonStagePlate: "使用不透明舞台底板，確保角色與背景分離。",
    reasonDimAdjusted: "背景加深以維持角色在圖片上的辨識度。",
    reasonImageUpscaled: "圖片可能會在訪客頁面放大。",
    reasonStrongCrop: "目前取景會裁切較多圖片內容。",
  },
  en: {
    title: "Visitor appearance",
    description:
      "Choose the visitor page colors and background. Applying appearance changes only the scene; it does not prepare or reindex projects.",
    receiptMissing:
      "The published scene is available, but its original appearance settings are not. Choose new settings explicitly before previewing or applying.",
    scheme: "Color scheme",
    mode: "Default color mode",
    toggle: "Let visitors switch modes",
    schemeChoice: "Let visitors choose a colour scheme",
    accent: "Custom accent",
    useSchemeAccent: "Use scheme colors",
    background: "Background image",
    backgroundCurrent: "Keep current image",
    backgroundNone: "No image",
    backgroundDraftSelected: "Uploaded image selected",
    upload: "Choose a PNG or WebP image",
    dropHint:
      "You can also drop a PNG or WebP (640×360 to 2560×1600, up to 2 MB).",
    removeBackground: "Remove background",
    focus: "Background focus",
    horizontal: "Horizontal",
    vertical: "Vertical",
    focusPicker:
      "Click or drag the image to set focus; the sliders also support arrow keys.",
    focusCoordinates: "Current focus",
    desktopFrame: "Desktop crop",
    phoneFrame: "Phone crop",
    dim: "Background dimming",
    scaling: "Image scaling",
    smooth: "Smooth",
    pixelated: "Pixelated",
    preview: "Preview appearance",
    apply: "Apply appearance",
    saveDraftFirst: "Save the local draft before applying appearance.",
    reset: "Reset to defaults",
    cancel: "Cancel changes",
    cancelled:
      "Changes cancelled and the private image draft deleted. Published appearance is unchanged.",
    applied: "Appearance applied. Other saved content was not published.",
    appliedWithEdits:
      "The previewed settings were applied; newer edits are still pending.",
    previewOutdated:
      "Settings changed during preview. Preview again before applying.",
    noModel: "Preview and apply do not call a model.",
    revision: "Character revision",
    appearanceRevision: "Appearance revision",
    profileUnavailable:
      "Could not load the current visitor page. Try again shortly.",
    requestFailed:
      "The operation could not be completed. Check the input or service status and try again.",
    notices: "Preview adjustments",
    light: "Light",
    dark: "Dark",
    system: "System",
    auto: "Auto",
    none: "None",
    low: "Low",
    medium: "Medium",
    high: "High",
    noticeAccentAdjusted:
      "The accent color was adjusted for this color variant to meet contrast requirements.",
    noticeStageAdjusted:
      "The character stage color was adjusted for this color variant to meet contrast requirements.",
    noticeStagePlate:
      "An opaque stage plate keeps the character clearly separated.",
    noticeDimAdjusted:
      "Background dimming was increased for this color variant.",
    noticeBackgroundDim:
      "This background needs stronger dimming to keep the character clear.",
    noticeImageUpscaled: "This image may be enlarged on the visitor page.",
    noticeStrongCrop: "The selected focus crops a larger part of the image.",
    noticeGeneric: "The scene was adjusted safely.",
    adjustedTo: "Adjusted to",
    reasonAccentAdjusted:
      "The accent lightness was fine-tuned to meet text contrast requirements.",
    reasonStageAdjusted:
      "The stage lightness changed to keep the character edge distinct.",
    reasonStagePlate:
      "An opaque stage plate keeps the character separate from the background.",
    reasonDimAdjusted:
      "The background was dimmed to keep the character recognizable over the image.",
    reasonImageUpscaled: "The image may be enlarged on the visitor page.",
    reasonStrongCrop: "The current focus crops a larger part of the image.",
  },
} as const;
