import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { PublicScene, SceneTokens } from "../../app/publicTypes";
import { AppearancePanel, type SceneAppearanceState } from "./AppearancePanel";
import { LocalPublishingWorkspace } from "./LocalPublishingWorkspace";
import { VisitorGatewayPanel } from "./VisitorGatewayPanel";

const tokens = Object.fromEntries(
  [
    "background",
    "surface",
    "surface_alt",
    "ink",
    "muted_ink",
    "accent",
    "accent_ink",
    "border",
    "stage",
    "focus",
    "sky",
    "horizon",
    "hill_far",
    "hill_near",
    "grass",
    "ground",
    "wood",
    "celestial",
  ].map((role) => [role, "var(--px-ink)"]),
) as unknown as SceneTokens;
const settings = {
  color_scheme: "synthetic-scheme",
  color_mode: "system" as const,
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  accent: null,
  background: "none",
  focus: { x: 50, y: 50 },
  dim: "none" as const,
  scaling: "smooth" as const,
};
const scene: PublicScene = {
  revision: 1,
  scheme: { id: settings.color_scheme, version: 1 },
  color_mode: "system",
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  themes: { light: tokens, dark: tokens },
  npc_plate: { light: false, dark: false },
  schemes: [],
  background_url: null,
  background_scaling: "smooth",
  background_focus: settings.focus,
  background_dim: "none",
};
const state: SceneAppearanceState = {
  source_bundle_id: "synthetic",
  source_character_revision: 1,
  character_revision: 1,
  appearance_revision: 1,
  sprite_sha256: "a".repeat(64),
  draft_revision: "synthetic-draft",
  issued_revision: 1,
  scene,
  settings,
  defaults: settings,
  schemes: [
    {
      id: settings.color_scheme,
      version: 1,
      labels: { "zh-TW": "測試", en: "Synthetic" },
      themes: scene.themes,
    },
  ],
};
const request = vi.fn(
  (...args: [string, RequestInit?]) => {
    void args;
    return Promise.resolve({});
  },
) as unknown as <T>(path: string, options?: RequestInit) => Promise<T>;

describe("P4 w3 pixel publication", () => {
  it.each(["zh-TW", "en"] as const)(
    "keeps the preview action, sequence, names and locked semantics in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <LocalPublishingWorkspace
          locale={locale}
          content="synthetic draft"
          spriteBase64={null}
          revision={null}
          initialAccount="synthetic"
          selection={null}
          request={request}
          onStored={vi.fn()}
          onCreateDraft={vi.fn()}
          repositories={[]}
          onAddClaim={vi.fn()}
        />,
      );
      expect(markup).toContain('class="publication-local px-panel"');
      expect(markup).toContain('class="px-button px-button--primary"');
      expect(markup).toContain('aria-labelledby="local-publication-heading"');
      expect(markup.indexOf('id="publication-appearance"')).toBeLessThan(
        markup.indexOf('id="visitor-gateway-heading"'),
      );
      expect(markup).toContain(
        locale === "zh-TW" ? "預覽作品集與卡片" : "Preview portfolio and card",
      );
      expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
      const gateway = renderToStaticMarkup(
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          publicSharingAvailable={false}
        />,
      );
      expect(gateway).toContain('class="visitor-gateway__lock px-badge"');
      expect(gateway).toContain(locale === "zh-TW" ? "已鎖定" : "Locked:");
      expect(gateway).toContain(
        'aria-disabled="true" class="visitor-gateway__origins" disabled=""',
      );
      expect(request).not.toHaveBeenCalled();
    },
  );

  it.each([true, false])(
    "keeps both switch values and a hidden, named FileTrigger when permission is %s",
    (enabled) => {
      const markup = renderToStaticMarkup(
        <AppearancePanel
          locale="en"
          initialState={{
            ...state,
            settings: {
              ...settings,
              visitor_mode_toggle: enabled,
              visitor_scheme_choice: enabled,
            },
          }}
          request={request}
          onStateChange={vi.fn()}
        />,
      );
      expect(
        markup.match(
          new RegExp(`role="switch" aria-checked="${enabled}"`, "g"),
        ),
      ).toHaveLength(2);
      expect(markup.match(/type="file"/g)).toHaveLength(1);
      expect(markup).toContain(
        'type="file" style="display:none" accept="image/png,image/webp,.png,.webp"',
      );
      expect(markup).toMatch(
        /<button[^>]*data-react-aria-pressable="true"[^>]*>Choose a PNG or WebP image<\/button>/,
      );
    },
  );

  it("keeps token-only page styles, normal-flow disclosures and native scheme radios", () => {
    const markup = renderToStaticMarkup(
      <AppearancePanel
        locale="en"
        initialState={state}
        request={request}
        onStateChange={vi.fn()}
      />,
    );
    expect(markup).toContain('class="scene-appearance"');
    expect(markup).toContain('class="px-button px-button--primary"');
    expect(markup).toContain('role="switch"');
    expect(markup).toContain('type="radio"');
    expect(markup).not.toContain("Choose File");
    expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
  });
});
