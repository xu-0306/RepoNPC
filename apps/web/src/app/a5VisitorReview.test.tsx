import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { VisitorPage } from "./VisitorPage";
import { VisitorConversation, type VisitorTurn } from "./VisitorConversation";
import { sceneThemesForScheme, sceneThemeStyle } from "./scene";
import type {
  PublicProfile,
  PublicScene,
  VisitorPageProps,
} from "./publicTypes";

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
const scene: PublicScene = {
  revision: 7,
  scheme: { id: "fixture-added-scheme", version: 1 },
  color_mode: "dark",
  visitor_mode_toggle: false,
  visitor_scheme_choice: true,
  themes: { light: tokens, dark: tokens },
  npc_plate: { light: false, dark: true },
  schemes: [
    {
      id: "fixture-added-scheme",
      version: 1,
      label: { "zh-TW": "測試", en: "Fixture" },
      themes: { light: tokens, dark: tokens },
      npc_plate: { light: false, dark: true },
    },
  ],
  background_url: null,
  background_scaling: "smooth",
  background_focus: { x: 35, y: 65 },
  background_dim: "none",
};
const profile: PublicProfile = {
  schema_version: 1,
  locale: "en",
  profile: {
    display_name: "Fixture owner",
    headline: "Fixture headline",
    bio: "Fixture bio",
    greeting: "Fixture greeting",
    location: null,
    avatar_url: null,
    links: [],
  },
  repositories: [
    {
      slug: "fixture/project",
      summary: "Fixture project",
      role: "Owner statement",
      tags: [],
      demo_url: null,
    },
  ],
  suggested_questions: [],
  character: {
    mode: "custom",
    asset_url: "/api/public/character.png",
    revision: 7,
    frame_duration_ms: 240,
    movement: "none",
    scene,
  },
  index: {
    version: "fixture-bundle",
    built_at: "2026-09-29T00:00:00Z",
    repository_count: 1,
  },
};
const noop = () => undefined;
function page(overrides: Partial<VisitorPageProps> = {}) {
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

describe("Main's independent shared visitor review", () => {
  it("uses current FAQ admission for answer suggestions, including chat pending", () => {
    const turn: VisitorTurn = {
      id: "offline-answer",
      role: "assistant",
      content: "Try one of these questions.",
      suggestedQuestions: ["Current approved FAQ", "Stale FAQ"],
    };
    const markup = renderToStaticMarkup(
      page({
        chatAvailable: false,
        offlineFaqAvailable: true,
        turns: [turn],
        canAskSuggestion: (question) => question === "Current approved FAQ",
      }),
    );
    const buttons = markup.match(
      /<ul class="answer-suggestions">([\s\S]*?)<\/ul>/,
    )?.[1];
    expect(buttons).toContain(
      '<button type="button">Current approved FAQ</button>',
    );
    expect(buttons).toContain(
      '<button disabled="" type="button">Stale FAQ</button>',
    );

    const pendingMarkup = renderToStaticMarkup(
      page({
        chatAvailable: false,
        offlineFaqAvailable: true,
        turns: [turn],
        canAskSuggestion: () => true,
        pending: true,
      }),
    );
    const pendingButtons = pendingMarkup.match(
      /<ul class="answer-suggestions">([\s\S]*?)<\/ul>/,
    )?.[1];
    expect(pendingButtons).toContain(
      '<button disabled="" type="button">Current approved FAQ</button>',
    );
  });

  it("ignores unknown theme keys and maps exactly the eighteen roles in both variants", () => {
    const injected = structuredClone(scene);
    Object.assign(injected.themes.light, {
      "background-image": "url(https://invalid.example)",
      glow: "canary",
    });
    const mapped = sceneThemeStyle(injected);
    const expected = ["light", "dark"].flatMap((variant) =>
      Object.keys(tokens).map((role) => `--scene-${variant}-${role}`),
    );
    expect(Object.keys(mapped).sort()).toEqual(expected.sort());
    expect(JSON.stringify(mapped)).not.toContain("canary");
    expect(JSON.stringify(mapped)).not.toContain("invalid.example");
    expect(sceneThemeStyle(null)).toEqual({});
  });

  it("selects an arbitrary catalog scheme and falls back for unknown ids", () => {
    const alternate = {
      ...scene.schemes[0],
      id: "another_fixture",
      themes: {
        light: { ...tokens, sky: "#bbccdd" },
        dark: { ...tokens, sky: "#112233" },
      },
    };
    const value = { ...scene, schemes: [...scene.schemes, alternate] };
    expect(sceneThemesForScheme(value, alternate.id)).toBe(alternate.themes);
    expect(sceneThemesForScheme(value, "unknown_fixture")).toBe(value.themes);
    expect(sceneThemesForScheme(value, scene.scheme.id)).toStrictEqual(
      scene.themes,
    );
  });

  it("keeps two preview instances' semantic IDs and explicit modes isolated", () => {
    const markup = renderToStaticMarkup(
      <>
        {page({ mode: "preview", previewMode: "light" })}
        {page({ mode: "preview", previewMode: "dark" })}
      </>,
    );
    const ids = [...markup.matchAll(/\sid="([^"]+)"/g)].map(
      (match) => match[1],
    );
    expect(new Set(ids).size).toBe(ids.length);
    for (const target of [
      ...markup.matchAll(/(?:aria-controls|aria-labelledby|for)="([^"]+)"/g),
    ]) {
      for (const id of target[1].split(" ")) expect(ids).toContain(id);
    }
    expect(markup).toContain('data-preview-mode="light"');
    expect(markup).toContain('data-preview-mode="dark"');
    expect(markup).not.toContain("reponpc.visitor.mode");
  });

  it("preserves absent repository metadata and displays a real zero snapshot", () => {
    const absent = renderToStaticMarkup(page());
    expect(absent).not.toContain('class="visitor-repo-metadata"');
    const present = renderToStaticMarkup(
      page({
        profile: {
          ...profile,
          repositories: [
            {
              ...profile.repositories[0],
              language: "Python",
              stars: 0,
              forks: 0,
            },
          ],
        },
      }),
    );
    expect(present).toContain("Python");
    expect(present.match(/<dd>0<\/dd>/g)).toHaveLength(2);
  });

  it("hides the welcome hero after a question and retains both semantic messages", () => {
    expect(renderToStaticMarkup(page())).toContain('class="visitor-hero"');
    const markup = renderToStaticMarkup(
      page({
        turns: [
          { id: "q", role: "user", content: "Fixture question" },
          { id: "a", role: "assistant", content: "Fixture answer" },
        ],
      }),
    );
    expect(markup).not.toContain('class="visitor-hero"');
    expect(markup).toContain("Fixture question");
    expect(markup).toContain("Fixture answer");
  });

  it("animates only the newest answer and freezes every answer for reduced motion", () => {
    const render = (reducedMotion: boolean) =>
      renderToStaticMarkup(
        <VisitorConversation
          chatAvailable
          locale="en"
          onRetry={noop}
          pending
          characterState="talk"
          reducedMotion={reducedMotion}
          turns={[
            { id: "old", role: "assistant", content: "Old answer" },
            { id: "new", role: "assistant", content: "New answer" },
          ]}
        />,
      );
    const normal = render(false);
    expect(normal.match(/data-reduced-motion="false"/g)).toHaveLength(1);
    expect(normal.match(/data-reduced-motion="true"/g)).toHaveLength(1);
    expect(render(true)).not.toContain('data-reduced-motion="false"');
  });

  it.each(["zh-TW", "en"] as const)(
    "uses the published animation timing for the newest idle/talk/offline answer in %s",
    (locale) => {
      for (const characterState of ["idle", "talk", "offline"] as const) {
        for (const reducedMotion of [false, true]) {
          const markup = renderToStaticMarkup(
            page({
              locale,
              characterState,
              reducedMotion,
              chatAvailable: characterState !== "offline",
              turns: [
                { id: "old", role: "assistant", content: "Old answer" },
                { id: "latest", role: "assistant", content: "Latest answer" },
              ],
            }),
          );
          const answers = markup.match(
            /<ol aria-live="polite" class="conversation">([\s\S]*?)<\/ol>/,
          )?.[1];
          expect(answers).toBeDefined();
          expect(
            answers?.match(/--character-animation-duration:960ms/g),
          ).toHaveLength(2);
          if (reducedMotion) {
            expect(answers).not.toContain('data-reduced-motion="false"');
          } else {
            expect(answers?.match(/data-reduced-motion="false"/g)).toHaveLength(
              1,
            );
            expect(answers?.match(/data-reduced-motion="true"/g)).toHaveLength(
              1,
            );
          }
          expect(answers).toContain(`data-character-state="${characterState}"`);
        }
      }
    },
  );
});
