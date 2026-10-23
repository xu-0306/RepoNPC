import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VisitorApp } from "./VisitorApp";
import { VisitorPage } from "./VisitorPage";
import { readVisitorScheme, syncVisitorPolicy } from "./scene";
import type { PublicProfile, PublicScene } from "./publicTypes";

const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as (() => unknown)[],
}));
vi.mock("react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react")>()),
  useEffect: (effect: () => unknown) => hooks.effects.push(effect),
  useCallback: (callback: unknown) => callback,
  useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values))
      hooks.values[index] = typeof initial === "function" ? initial() : initial;
    return [
      hooks.values[index],
      (next: unknown) => {
        hooks.values[index] =
          typeof next === "function" ? next(hooks.values[index]) : next;
      },
    ];
  },
  useRef: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = { current: initial };
    return hooks.values[index];
  },
}));
const data = vi.hoisted(() => ({
  profile: vi.fn(),
  faq: vi.fn(),
  status: vi.fn(),
}));
vi.mock("./visitorData", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./visitorData")>()),
  fetchPublicProfile: data.profile,
  fetchPublicFaq: data.faq,
  fetchPublicStatus: data.status,
  isStaticExport: () => false,
}));

const tokens = {
  background: "#f2f3f4",
  surface: "#ffffff",
  surface_alt: "#eeeeee",
  ink: "#111111",
  muted_ink: "#333333",
  accent: "#224466",
  accent_ink: "#ffffff",
  border: "#555555",
  stage: "#ffffff",
  focus: "#224466",
  sky: "#cceeff",
  horizon: "#ddeeff",
  hill_far: "#aabbcc",
  hill_near: "#667788",
  grass: "#334422",
  ground: "#776644",
  wood: "#554422",
  celestial: "#ffeecc",
};
const alternate = {
  id: "fixture_other",
  version: 1,
  label: { "zh-TW": "測試", en: "Fixture" },
  themes: {
    light: { ...tokens, stage: "#bacdef" },
    dark: { ...tokens, sky: "#123456" },
  },
  npc_plate: { light: true, dark: false },
};
const scene: PublicScene = {
  revision: 1,
  scheme: { id: "fixture_default", version: 1 },
  color_mode: "system",
  visitor_mode_toggle: true,
  visitor_scheme_choice: true,
  themes: { light: tokens, dark: tokens },
  npc_plate: { light: false, dark: true },
  schemes: [
    {
      id: "fixture_default",
      version: 1,
      label: { "zh-TW": "預設", en: "Default" },
      themes: { light: tokens, dark: tokens },
      npc_plate: { light: false, dark: true },
    },
    alternate,
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
    display_name: "Owner",
    headline: "Headline",
    bio: "Bio",
    greeting: "Greeting",
    location: null,
    avatar_url: null,
    links: [],
  },
  repositories: [],
  suggested_questions: [],
  character: {
    mode: "custom",
    asset_url: "/api/public/character.png",
    revision: 1,
    frame_duration_ms: 160,
    movement: "none",
    scene,
  },
  index: { version: "fixture", built_at: "2026-10-23", repository_count: 0 },
};
type PageProps = Parameters<typeof VisitorPage>[0];
const noop = () => undefined;
function page(overrides: Partial<PageProps> = {}) {
  return (
    <VisitorPage
      locale="en"
      onLocaleChange={noop}
      profile={profile}
      profileError={false}
      onRetryProfile={noop}
      chatAvailable
      pending={false}
      onRecheckStatus={noop}
      characterState="idle"
      reducedMotion
      turns={[]}
      onRetry={noop}
      question=""
      onQuestionChange={noop}
      onSubmit={noop}
      suggestions={[]}
      canAskSuggestion={() => false}
      onSelectSuggestion={noop}
      {...overrides}
    />
  );
}

const cleanups: (() => void)[] = [];
let chosen = alternate.id;
let configuredScene = scene;
beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
  hooks.effects = [];
  chosen = alternate.id;
  configuredScene = scene;
  const events = new EventTarget();
  const dataset: Record<string, string> = {};
  vi.stubGlobal("document", {
    documentElement: {
      lang: "en",
      dataset,
      removeAttribute: (name: string) => {
        delete dataset[
          name
            .replace(/^data-/, "")
            .replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase())
        ];
      },
    },
  });
  vi.stubGlobal("window", {
    matchMedia: () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
    dispatchEvent: events.dispatchEvent.bind(events),
    setTimeout: vi.fn(() => 1),
    clearTimeout: vi.fn(),
    RepoNPCSceneMode: {
      get: () => "system",
      set: () => true,
      getScheme: () =>
        configuredScene.visitor_scheme_choice &&
        configuredScene.schemes.some((item) => item.id === chosen)
          ? chosen
          : configuredScene.scheme.id,
      setScheme: (id: string | null) => {
        chosen = id ?? configuredScene.scheme.id;
        window.dispatchEvent(new Event("reponpc:visitor-scheme-change"));
        return true;
      },
      configure: vi.fn(() => "system"),
    },
  });
});
afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  vi.unstubAllGlobals();
});

async function app(value = scene) {
  configuredScene = value;
  const document = {
    ...profile,
    character: { ...profile.character, scene: value },
  };
  data.profile.mockResolvedValue(document);
  data.faq.mockResolvedValue(null);
  data.status.mockResolvedValue({ chat_available: false });
  const render = () => {
    hooks.cursor = 0;
    hooks.effects = [];
    return VisitorApp().props as PageProps;
  };
  render();
  for (const effect of hooks.effects.slice()) {
    const cleanup = effect();
    if (typeof cleanup === "function") cleanups.push(cleanup as () => void);
  }
  await vi.waitFor(() => expect(render().profile).toEqual(document));
  return render;
}

describe("P1 visitor scheme data flow", () => {
  it("keeps the stored scheme's inline tokens and plate after the profile loads", async () => {
    const render = await app();
    expect(window.RepoNPCSceneMode?.configure).toHaveBeenCalledWith(
      "system",
      true,
      scene.scheme.id,
      true,
      scene.schemes.map((item) => item.id),
    );
    expect(render().visitorScheme).toBe(alternate.id);
    const html = renderToStaticMarkup(<VisitorPage {...render()} />);
    expect(html).toContain("--scene-light-stage:#bacdef");
    expect(html).toContain("--scene-dark-sky:#123456");
    expect(html).toContain('data-npc-plate-light="true"');
    expect(html).toContain('data-npc-plate-dark="false"');
  });

  it("updates inline tokens and the plate on a scheme event", async () => {
    const render = await app();
    window.RepoNPCSceneMode?.setScheme(scene.scheme.id);
    expect(render().visitorScheme).toBe(scene.scheme.id);
    const html = renderToStaticMarkup(<VisitorPage {...render()} />);
    expect(html).toContain("--scene-light-stage:#ffffff");
    expect(html).toContain('data-npc-plate-light="false"');
    expect(html).toContain('data-npc-plate-dark="true"');
  });

  it("falls back for unknown ids and ignores storage with choice off or in owner preview", () => {
    for (const override of [
      { visitorScheme: "fixture_unknown" },
      {
        visitorScheme: alternate.id,
        sceneOverride: { ...scene, visitor_scheme_choice: false },
      },
      {
        visitorScheme: alternate.id,
        mode: "preview" as const,
        previewMode: "dark" as const,
      },
    ]) {
      const html = renderToStaticMarkup(page(override));
      expect(html).toContain("--scene-light-stage:#ffffff");
      expect(html).toContain('data-npc-plate-light="false"');
      expect(html).not.toContain("--scene-dark-sky:#123456");
    }
  });

  it("honours disabled policy in the app and preserves preview-specific owner tokens", async () => {
    const render = await app({ ...scene, visitor_scheme_choice: false });
    expect(render().visitorScheme).toBe(scene.scheme.id);
    const ownerScene = { ...scene, themes: alternate.themes };
    const html = renderToStaticMarkup(
      page({
        mode: "preview",
        sceneOverride: ownerScene,
        visitorScheme: "fixture_unknown",
      }),
    );
    expect(html).toContain("--scene-light-stage:#bacdef");
  });

  it("reads the pre-paint attributes without an API and reconciles forbidden/unknown choices", () => {
    delete window.RepoNPCSceneMode;
    Object.assign(document.documentElement.dataset, {
      defaultScheme: scene.scheme.id,
      visitorSchemeChoice: "true",
      visitorScheme: alternate.id,
    });
    expect(readVisitorScheme()).toBe(alternate.id);
    syncVisitorPolicy("system", true, scene.scheme.id, true, [scene.scheme.id]);
    expect(readVisitorScheme()).toBe(scene.scheme.id);
    document.documentElement.dataset.visitorScheme = alternate.id;
    syncVisitorPolicy("system", true, scene.scheme.id, false, [
      scene.scheme.id,
      alternate.id,
    ]);
    expect(readVisitorScheme()).toBe(scene.scheme.id);
  });
});
