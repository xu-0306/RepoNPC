import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type {
  PublicProfile,
  PublicScene,
  SceneTokens,
} from "../../app/publicTypes";
import {
  computeCoverCrop,
  previewScaleForWidth,
  ScenePreview,
  type ScenePreviewSettings,
  type SceneSchemeOption,
} from "./ScenePreview";
import {
  AppearancePanel,
  isCurrentAppearanceState,
  localizedPreviewNotice,
  matchesAppearanceProfile,
} from "./AppearancePanel";

const lightTokens: SceneTokens = {
  background: "#ffffff",
  surface: "#f7f7f7",
  surface_alt: "#ededed",
  ink: "#161616",
  muted_ink: "#4b4b4b",
  accent: "#343434",
  accent_ink: "#ffffff",
  border: "#6b6b6b",
  stage: "#dddddd",
  focus: "#4c4c4c",
  sky: "#ffffff",
  horizon: "#bbbbbb",
  hill_far: "#999999",
  hill_near: "#333333",
  grass: "#888888",
  ground: "#222222",
  wood: "#444444",
  celestial: "#aaaaaa",
};
const darkTokens: SceneTokens = {
  background: "#151515",
  surface: "#202020",
  surface_alt: "#2a2a2a",
  ink: "#f7f7f7",
  muted_ink: "#c9c9c9",
  accent: "#d7d7d7",
  accent_ink: "#171717",
  border: "#b8b8b8",
  stage: "#383838",
  focus: "#e1e1e1",
  sky: "#101020",
  horizon: "#222233",
  hill_far: "#444455",
  hill_near: "#181828",
  grass: "#555533",
  ground: "#222222",
  wood: "#666655",
  celestial: "#ddddcc",
};
const scene: PublicScene = {
  revision: 12,
  scheme: { id: "neutral", version: 1 },
  color_mode: "system",
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  themes: { light: lightTokens, dark: darkTokens },
  npc_plate: { light: false, dark: true },
  schemes: [
    {
      id: "neutral",
      version: 1,
      label: { "zh-TW": "測試", en: "Fixture" },
      themes: { light: lightTokens, dark: darkTokens },
      npc_plate: { light: false, dark: true },
    },
  ],
  background_url: null,
  background_scaling: "smooth",
  background_focus: { x: 50, y: 50 },
  background_dim: "none",
};
const profile: PublicProfile = {
  schema_version: 1,
  locale: "en",
  profile: {
    display_name: "Example owner",
    headline: "Portfolio guide",
    bio: "Example profile content.",
    greeting: "Welcome.",
    location: null,
    avatar_url: null,
    links: [],
  },
  repositories: [],
  suggested_questions: [],
  character: {
    mode: "builtin",
    asset_url: "/api/public/character.png",
    revision: 12,
    frame_duration_ms: 160,
    movement: "subtle",
    scene,
  },
  index: {
    version: "fixture",
    built_at: "2026-09-29T00:00:00Z",
    repository_count: 0,
  },
};
const schemes: SceneSchemeOption[] = [
  "neutral",
  "ocean",
  "forest",
  "sunset",
  "lavender",
].map((id, index) => ({
  id,
  version: index + 1,
  labels: { "zh-TW": `方案 ${index + 1}`, en: `Scheme ${index + 1}` },
  themes: { light: lightTokens, dark: darkTokens },
}));
const settings: ScenePreviewSettings = {
  color_scheme: "neutral",
  color_mode: "system",
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  accent: null,
  background: "none",
  focus: { x: 40, y: 55 },
  dim: "none",
  scaling: "smooth",
};

describe("owner scene preview", () => {
  it("fits the selected reference viewport without changing its logical width", () => {
    expect(previewScaleForWidth(1440, 360)).toBe(0.25);
    expect(previewScaleForWidth(375, 360)).toBe(0.96);
    expect(previewScaleForWidth(375, 420)).toBe(1);
  });

  it("binds a preview profile to locale, active bundle, and character revision", () => {
    const state = {
      source_bundle_id: "bundle-current",
      character_revision: 12,
    };
    const current = {
      ...profile,
      index: { ...profile.index, version: "bundle-current" },
    };

    expect(matchesAppearanceProfile(current, state, "en")).toBe(true);
    expect(matchesAppearanceProfile(profile, state, "en")).toBe(false);
    expect(matchesAppearanceProfile(current, state, "zh-TW")).toBe(false);
    expect(
      matchesAppearanceProfile(
        { ...current, character: { ...current.character, revision: 13 } },
        state,
        "en",
      ),
    ).toBe(false);
  });

  it("blocks one render of preview/apply while incoming status is newer", () => {
    const state = {
      source_bundle_id: "bundle-current",
      source_character_revision: 12,
      character_revision: 12,
      appearance_revision: 12,
      sprite_sha256: "a".repeat(64),
      draft_revision: "draft-old",
    };
    expect(isCurrentAppearanceState(state, state)).toBe(true);
    expect(
      isCurrentAppearanceState(state, {
        ...state,
        draft_revision: "draft-new",
      }),
    ).toBe(false);
    expect(
      isCurrentAppearanceState(state, {
        ...state,
        source_bundle_id: "bundle-next",
      }),
    ).toBe(false);
  });

  it.each([
    ["en", "High", "Adjusted to High", "An opaque stage plate is required."],
    ["zh-TW", "高", "調整為 高", "使用不透明舞台底板，確保角色與背景分離。"],
  ] as const)(
    "localizes stage plate details in %s",
    (locale, value, adjustedLabel, reason) => {
      expect(
        localizedPreviewNotice(locale, {
          kind: "stage_plate",
          adjusted_value: "high",
          reason: "An opaque stage plate is required.",
        }),
      ).toEqual({ adjustedLabel, reason });
    },
  );

  it.each([
    ["zh-TW", "取消變更"],
    ["en", "Cancel changes"],
  ] as const)("exposes named native cancellation in %s", (locale, label) => {
    const markup = renderToStaticMarkup(
      <AppearancePanel
        locale={locale}
        initialState={{
          source_bundle_id: "fixture",
          source_character_revision: 12,
          character_revision: 12,
          appearance_revision: 12,
          sprite_sha256: "a".repeat(64),
          draft_revision: "fixture-draft",
          issued_revision: 12,
          scene,
          settings,
          defaults: settings,
          schemes,
        }}
        request={async () => {
          throw new Error("SSR must not perform private requests");
        }}
        onStateChange={() => {
          throw new Error("Cancellation must not publish during SSR");
        }}
      />,
    );
    expect(markup).toContain(
      `<button disabled="" type="button">${label}</button>`,
    );
    expect(markup).toContain('type="file"');
  });

  it("uses ten real visitor page miniatures for the five light/dark scheme pairs", () => {
    const markup = renderToStaticMarkup(
      <ScenePreview
        appliedScene={scene}
        desktopFrameLabel="Desktop crop"
        focusCoordinatesLabel="Current focus"
        focusLabel="Focus position"
        focusTitle="Background focus"
        locale="en"
        onFocusChange={() => undefined}
        onSchemeChange={() => undefined}
        phoneFrameLabel="Phone crop"
        profile={profile}
        proposalPending
        proposedScene={scene}
        schemes={schemes}
        settings={settings}
      />,
    );

    expect(markup.match(/class="visitor-page px-body"/g)).toHaveLength(13);
    expect(markup.match(/data-compact-preview="true"/g)).toHaveLength(10);
    expect(markup.match(/data-preview-mode="light"/g)).toHaveLength(8);
    // The main preview and two geometry probes use light; the gallery contributes five of each.
    expect(markup.match(/data-preview-mode="dark"/g)).toHaveLength(5);
    expect(
      markup.match(/class="character-renderer visitor-turn__avatar"/g)?.length,
    ).toBeGreaterThanOrEqual(11);
    expect(markup).toContain("Preview reduced motion");
    expect(markup).toContain("Show crop focus frame (50%, 50%)");
    expect(markup).toContain("What are the portfolio highlights?");
    expect(markup).toContain('class="scene-preview__focus-map"');
    expect(markup).toContain(
      'class="scene-preview__logical-page scene-preview__reference-layout scene-preview__reference-layout--desktop"',
    );
    expect(markup).toContain("width:1440px");
    expect(markup).toContain('class="scene-preview__geometry-probes"');
    expect(markup).toContain(
      'class="scene-preview__geometry-probe scene-preview__geometry-probe--phone scene-preview__reference-layout scene-preview__reference-layout--phone"',
    );
    expect(markup).toContain("Desktop crop");
    expect(markup).toContain("Phone crop");
    expect(markup.match(/inert=""/g)).toHaveLength(6);
    expect(markup.match(/name="[^"]+-scene-preview-scheme"/g)).toHaveLength(5);
    expect(markup).toContain('name="scene-preview-conversation"');
    expect(markup).toContain('name="scene-preview-availability"');
    expect(markup).toContain("Empty welcome");
    expect(markup).toContain("Available");
    expect(markup).toContain("Resting");
    expect(markup).not.toContain("<main");
  });

  it("uses the natural image bounds and measured hero ratios for cover crops", () => {
    expect(computeCoverCrop(1600, 900, 16 / 9, { x: 50, y: 50 })).toEqual({
      left: 0,
      top: 0,
      width: 100,
      height: 100,
    });
    expect(computeCoverCrop(1600, 900, 1, { x: 100, y: 50 })).toEqual({
      left: 43.75,
      top: 0,
      width: 56.25,
      height: 100,
    });
    expect(computeCoverCrop(900, 1600, 1, { x: 50, y: 0 })).toEqual({
      left: 0,
      top: 0,
      width: 100,
      height: 56.25,
    });
  });
});
