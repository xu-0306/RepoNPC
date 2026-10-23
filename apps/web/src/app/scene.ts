import type { CSSProperties } from "react";
import type { PublicScene } from "./publicTypes";

export const VISITOR_MODE_STORAGE_KEY = "reponpc.visitor.mode";
export type VisitorMode = "system" | "light" | "dark";

declare global {
  interface Window {
    RepoNPCSceneMode?: {
      get: () => VisitorMode;
      set: (mode: VisitorMode) => boolean;
      configure: (
        ownerMode: VisitorMode,
        visitorToggle: boolean,
      ) => VisitorMode;
    };
  }
}

/** Closed role mapping: do not turn profile keys into arbitrary CSS properties. */
export function sceneThemeStyle(
  scene: PublicScene | null | undefined,
): CSSProperties {
  if (!scene) return {};
  return {
    "--scene-light-background": scene.themes.light.background,
    "--scene-light-surface": scene.themes.light.surface,
    "--scene-light-surface_alt": scene.themes.light.surface_alt,
    "--scene-light-ink": scene.themes.light.ink,
    "--scene-light-muted_ink": scene.themes.light.muted_ink,
    "--scene-light-accent": scene.themes.light.accent,
    "--scene-light-accent_ink": scene.themes.light.accent_ink,
    "--scene-light-border": scene.themes.light.border,
    "--scene-light-stage": scene.themes.light.stage,
    "--scene-light-focus": scene.themes.light.focus,
    "--scene-light-sky": scene.themes.light.sky,
    "--scene-light-horizon": scene.themes.light.horizon,
    "--scene-light-hill_far": scene.themes.light.hill_far,
    "--scene-light-hill_near": scene.themes.light.hill_near,
    "--scene-light-grass": scene.themes.light.grass,
    "--scene-light-ground": scene.themes.light.ground,
    "--scene-light-wood": scene.themes.light.wood,
    "--scene-light-celestial": scene.themes.light.celestial,
    "--scene-dark-background": scene.themes.dark.background,
    "--scene-dark-surface": scene.themes.dark.surface,
    "--scene-dark-surface_alt": scene.themes.dark.surface_alt,
    "--scene-dark-ink": scene.themes.dark.ink,
    "--scene-dark-muted_ink": scene.themes.dark.muted_ink,
    "--scene-dark-accent": scene.themes.dark.accent,
    "--scene-dark-accent_ink": scene.themes.dark.accent_ink,
    "--scene-dark-border": scene.themes.dark.border,
    "--scene-dark-stage": scene.themes.dark.stage,
    "--scene-dark-focus": scene.themes.dark.focus,
    "--scene-dark-sky": scene.themes.dark.sky,
    "--scene-dark-horizon": scene.themes.dark.horizon,
    "--scene-dark-hill_far": scene.themes.dark.hill_far,
    "--scene-dark-hill_near": scene.themes.dark.hill_near,
    "--scene-dark-grass": scene.themes.dark.grass,
    "--scene-dark-ground": scene.themes.dark.ground,
    "--scene-dark-wood": scene.themes.dark.wood,
    "--scene-dark-celestial": scene.themes.dark.celestial,
  } as CSSProperties;
}

export function sceneThemesForScheme(
  scene: PublicScene,
  schemeId: string,
): PublicScene["themes"] {
  return (
    scene.schemes.find((scheme) => scheme.id === schemeId)?.themes ??
    scene.themes
  );
}

export function readVisitorMode(): VisitorMode {
  if (typeof document === "undefined") return "system";
  const scripted = window.RepoNPCSceneMode?.get();
  if (scripted) return scripted;
  const root = document.documentElement;
  const ownerMode = root.dataset.ownerMode;
  if (root.dataset.visitorToggle !== "true") {
    return ownerMode === "light" || ownerMode === "dark" ? ownerMode : "system";
  }
  const selectedMode = root.dataset.visitorMode;
  if (selectedMode === "light" || selectedMode === "dark") return selectedMode;
  return ownerMode === "light" || ownerMode === "dark" ? ownerMode : "system";
}

export function setVisitorMode(mode: VisitorMode): boolean {
  return window.RepoNPCSceneMode?.set(mode) ?? false;
}

export function syncVisitorPolicy(
  ownerMode: VisitorMode,
  visitorToggle: boolean,
): VisitorMode {
  if (typeof document === "undefined") return ownerMode;
  const root = document.documentElement;
  root.dataset.ownerMode = ownerMode;
  root.dataset.visitorToggle = String(visitorToggle);
  const current = window.RepoNPCSceneMode?.configure(ownerMode, visitorToggle);
  if (current) return current;
  if (!visitorToggle) {
    if (ownerMode === "system") root.removeAttribute("data-visitor-mode");
    else root.dataset.visitorMode = ownerMode;
  }
  return readVisitorMode();
}
