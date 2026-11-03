import type { ReactElement, ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LANGUAGES,
  chromeLocale,
  endonym,
  type LanguageTag,
} from "../i18n/languages";
import { messageLocale, messages } from "../i18n/messages";
import { VisitorApp } from "./VisitorApp";
import { VisitorPage } from "./VisitorPage";
import { VisitorConversation } from "./VisitorConversation";
import { languageProfile, siteSets } from "./siteLanguages.test-cases";
import type { SceneTokens } from "./publicTypes";

const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as (() => unknown)[],
}));
vi.mock("react", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react")>()),
  useId: () => `language-test-${hooks.cursor++}`,
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
  useCallback: (callback: unknown) => callback,
  useEffect: (effect: () => unknown, dependencies?: unknown[]) => {
    const index = hooks.cursor++;
    const previous = hooks.values[index] as unknown[] | undefined;
    if (
      !dependencies ||
      !previous ||
      dependencies.some(
        (value, position) => !Object.is(value, previous[position]),
      )
    ) {
      hooks.effects.push(() => {
        hooks.values[index] = dependencies;
        return effect();
      });
    }
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

const stored = new Map<string, string>();
const storage = { getItem: vi.fn(), setItem: vi.fn() };
const cleanups: (() => void)[] = [];
beforeEach(() => {
  hooks.values = [];
  hooks.effects = [];
  stored.clear();
  data.profile.mockReset();
  data.faq.mockReset();
  data.status.mockReset().mockResolvedValue({ chat_available: true });
  storage.getItem
    .mockReset()
    .mockImplementation((key: string) => stored.get(key) ?? null);
  storage.setItem
    .mockReset()
    .mockImplementation((key: string, value: string) => stored.set(key, value));
  vi.stubGlobal("document", { documentElement: { lang: "en", dataset: {} } });
  vi.stubGlobal("window", {
    localStorage: storage,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    setTimeout: vi.fn(() => 1),
    clearTimeout: vi.fn(),
    matchMedia: () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  });
});
afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  vi.unstubAllGlobals();
});

type PageProps = Parameters<typeof VisitorPage>[0];
function render(): PageProps {
  hooks.cursor = 0;
  hooks.effects = [];
  const props = VisitorApp().props as PageProps;
  for (const effect of hooks.effects.splice(0)) {
    const cleanup = effect();
    if (typeof cleanup === "function") cleanups.push(cleanup as () => void);
  }
  return props;
}

function elements(
  node: ReactNode,
  type: string,
): ReactElement<Record<string, unknown>>[] {
  if (Array.isArray(node))
    return node.flatMap((child) => elements(child, type));
  if (!node || typeof node !== "object" || !("props" in node)) return [];
  const element = node as ReactElement<Record<string, unknown>>;
  return [
    ...(element.type === type ? [element] : []),
    ...elements(element.props.children as ReactNode, type),
  ];
}

function page(props: PageProps) {
  return VisitorPage(props);
}

async function loaded(tag: LanguageTag) {
  await vi.waitFor(() => {
    const props = render();
    expect(props.profile?.locale).toBe(tag);
    expect(props.locale).toBe(tag);
    expect(document.documentElement.lang).toBe(tag);
  });
}

describe.each(siteSets.map((supported) => ({ supported })))(
  "visitor site $supported",
  ({ supported }) => {
    it.each(["empty", "stored", "invalid", "throws", "write throws"])(
      "discovers, toggles and remounts accessibly when storage is %s",
      async (mode) => {
        const fallback = supported[0]!;
        const browserChoice = supported.at(-1)!;
        vi.stubGlobal("navigator", {
          languages: ["x-not-registered", `${browserChoice}-x-browser`],
        });
        document.documentElement.lang = fallback;
        if (mode === "stored") stored.set("reponpc.locale", fallback);
        if (mode === "invalid")
          stored.set(
            "reponpc.locale",
            LANGUAGES.find(({ tag }) => !supported.includes(tag))?.tag ??
              "__proto__",
          );
        if (mode === "throws")
          Object.defineProperty(window, "localStorage", {
            get() {
              throw new Error("disabled");
            },
          });
        if (mode === "write throws")
          storage.setItem.mockImplementation(() => {
            throw new Error("full");
          });
        data.profile.mockImplementation(async (tag?: LanguageTag) =>
          languageProfile(tag ?? fallback, supported),
        );
        data.faq.mockImplementation(async (tag: LanguageTag) => ({
          bundle_id: "fixture-bundle",
          locale: tag,
          entries: [],
        }));
        const initial = mode === "stored" ? fallback : browserChoice;
        render();
        await loaded(initial);
        expect(data.profile.mock.calls.map(([tag]) => tag)).toEqual(
          initial === fallback ? [undefined] : [undefined, initial],
        );
        expect(data.faq.mock.calls[0]?.[0]).toBe(initial);
        expect(storage.setItem).not.toHaveBeenCalled();

        const tree = page(render());
        const nav = elements(tree, "nav").find(
          (element) => element.props.className === "visitor-language-switcher",
        );
        if (supported.length === 1) expect(nav).toBeUndefined();
        else {
          expect(nav?.props["aria-label"]).toBe(
            messages[initial].languageLabel,
          );
          const buttons = elements(nav, "button");
          expect(buttons.map((button) => button.props.children)).toEqual(
            supported.map(endonym),
          );
          expect(buttons.map((button) => button.props.lang)).toEqual(supported);
          for (const [index, button] of buttons.entries()) {
            expect(button.props.type).toBe("button");
            expect(button.props["aria-pressed"]).toBe(
              supported[index] === initial,
            );
            expect(button.props.disabled).toBeUndefined();
            (button.props.onClick as () => void)();
            await loaded(supported[index]!);
            expect(data.faq.mock.lastCall?.[0]).toBe(supported[index]);
          }
        }
        render().onLocaleChange(browserChoice);
        await loaded(browserChoice);
        if (mode !== "throws" && mode !== "write throws") {
          expect(storage.setItem).toHaveBeenLastCalledWith(
            "reponpc.locale",
            browserChoice,
          );
          expect(stored.get("reponpc.locale")).toBe(browserChoice);
        }

        const html = renderToStaticMarkup(<VisitorPage {...render()} />);
        expect(html).toContain(`lang="${messageLocale(browserChoice)}"`);
        expect(html).toContain(
          `<section class="visitor-profile-card" lang="${browserChoice}">`,
        );
        expect(html).toContain(
          `<li class="visitor-project-card" lang="${browserChoice}">`,
        );
        expect(html).toContain(messages[browserChoice].send);
        expect(html).toContain(`${browserChoice} biography`);

        for (const cleanup of cleanups.splice(0)) cleanup();
        hooks.values = [];
        data.profile.mockClear();
        vi.stubGlobal("navigator", { languages: [fallback] });
        render();
        const persisted = mode !== "throws" && mode !== "write throws";
        await loaded(persisted ? browserChoice : fallback);
        expect(data.profile.mock.calls[0]?.[0]).toBeUndefined();
      },
    );

    it("falls back to the site default when browser and storage do not match", async () => {
      vi.stubGlobal("navigator", { languages: ["x-not-registered"] });
      stored.set("reponpc.locale", "invalid");
      data.profile.mockImplementation(async (tag?: LanguageTag) =>
        languageProfile(tag ?? supported[0]!, supported),
      );
      data.faq.mockResolvedValue(null);
      render();
      await loaded(supported[0]!);
      expect(data.profile).toHaveBeenCalledTimes(1);
    });
  },
);

describe("visitor content languages", () => {
  it.each(LANGUAGES)(
    "uses registry chrome for scheme labels and preview samples in $tag",
    async ({ tag }) => {
      vi.stubGlobal("navigator", { languages: [tag] });
      const profile = languageProfile(
        tag,
        LANGUAGES.map((language) => language.tag),
      );
      const tokens: SceneTokens = {
        background: "#111111",
        surface: "#111111",
        surface_alt: "#111111",
        ink: "#111111",
        muted_ink: "#111111",
        accent: "#111111",
        accent_ink: "#111111",
        border: "#111111",
        stage: "#111111",
        focus: "#111111",
        sky: "#111111",
        horizon: "#111111",
        hill_far: "#111111",
        hill_near: "#111111",
        grass: "#111111",
        ground: "#111111",
        wood: "#111111",
        celestial: "#111111",
      };
      const themes = { light: tokens, dark: tokens };
      const npc_plate = { light: false, dark: false };
      const label = Object.fromEntries(
        LANGUAGES.map((language) => [
          chromeLocale(language.tag),
          `${chromeLocale(language.tag)} scheme`,
        ]),
      ) as Record<ReturnType<typeof chromeLocale>, string>;
      profile.character.scene = {
        revision: 0,
        scheme: { id: "fixture_scheme", version: 1 },
        color_mode: "system",
        visitor_mode_toggle: true,
        visitor_scheme_choice: true,
        themes,
        npc_plate,
        schemes: [
          { id: "fixture_scheme", version: 1, label, themes, npc_plate },
        ],
        background_url: null,
        background_scaling: "smooth",
        background_focus: { x: 50, y: 50 },
        background_dim: "none",
      };
      data.profile.mockResolvedValue(profile);
      data.faq.mockResolvedValue(null);
      render();
      await loaded(tag);
      const trigger = elements(page(render()), "button").find((element) =>
        String(element.props.className).includes("visitor-appearance-trigger"),
      );
      expect(trigger?.props["aria-label"]).toBe(messages[tag].appearance);
      (trigger!.props.onClick as () => void)();
      const html = renderToStaticMarkup(page(render()));
      expect(html).toContain(
        `<span lang="${chromeLocale(tag)}">${label[chromeLocale(tag)]}</span>`,
      );
      const sample = renderToStaticMarkup(
        <VisitorPage
          {...render()}
          profile={null}
          sceneOverride={null}
          sampleContent
          sampleConversation
        />,
      );
      expect(sample).toMatch(
        new RegExp(
          `<h1 id="[^"]+-dialogue-title" lang="${chromeLocale(tag)}">`,
        ),
      );
      expect(sample).toContain(`<p lang="${chromeLocale(tag)}">`);
    },
  );

  it.each(LANGUAGES)(
    "sends the selected $tag from the app to live chat",
    async ({ tag }) => {
      vi.stubGlobal("navigator", { languages: [tag] });
      data.profile.mockResolvedValue(languageProfile(tag, [tag]));
      data.faq.mockResolvedValue(null);
      const send = vi.fn<typeof fetch>(
        async () =>
          new Response(
            'event: complete\ndata: {"insufficient_evidence":true}\n\n',
          ),
      );
      vi.stubGlobal("fetch", send);
      render();
      await loaded(tag);
      render().onQuestionChange("A portfolio question?");
      render().onSubmit();
      await vi.waitFor(() => expect(render().pending).toBe(false));
      expect(send).toHaveBeenCalledTimes(1);
      expect(send.mock.calls[0]?.[0]).toBe("/api/public/chat/stream");
      expect(
        JSON.parse((send.mock.calls[0]?.[1] as RequestInit).body as string)
          .locale,
      ).toBe(tag);
      expect(render().turns.every((turn) => turn.locale === tag)).toBe(true);
    },
  );

  it.each(LANGUAGES)(
    "uses approved FAQ content, chrome non-answers and empty/error states in $tag",
    async ({ tag }) => {
      vi.stubGlobal("navigator", { languages: [tag] });
      data.profile.mockResolvedValue(languageProfile(tag, [tag]));
      data.status.mockResolvedValue({ chat_available: false });
      const question = `${tag} approved question`;
      data.faq.mockResolvedValue({
        bundle_id: "fixture-bundle",
        locale: tag,
        entries: [
          {
            question,
            variants: [],
            answer_markdown: `${tag} published answer`,
            citations: [],
          },
        ],
      });
      render();
      await loaded(tag);
      await vi.waitFor(() => expect(render().offlineFaqAvailable).toBe(true));
      render().onSelectSuggestion(question);
      expect(render().turns.at(-1)?.locale).toBe(tag);
      const answered = renderToStaticMarkup(<VisitorPage {...render()} />);
      expect(answered).toContain(
        `<p lang="${tag}">${tag} published answer</p>`,
      );
      render().onQuestionChange("Unapproved question");
      render().onSubmit();
      const noMatch = renderToStaticMarkup(<VisitorPage {...render()} />);
      expect(noMatch).toContain(
        `<p lang="${messageLocale(tag)}">${messages[tag].offlineFaqNoMatch}</p>`,
      );
      const unavailable = renderToStaticMarkup(
        <VisitorPage {...render()} profile={null} profileError />,
      );
      expect(unavailable).toContain(messages[tag].profileUnavailable);
      expect(unavailable).toContain(messages[tag].noProjects);
      expect(unavailable).not.toContain("visitor-language-switcher");
    },
  );

  it.each(LANGUAGES)(
    "preserves $tag content while chrome follows a different selection",
    ({ tag }) => {
      const selected = LANGUAGES.find((entry) => entry.tag !== tag)!.tag;
      hooks.cursor = 0;
      const markup = renderToStaticMarkup(
        <VisitorConversation
          chatAvailable
          locale={selected}
          pending={false}
          onRetry={vi.fn()}
          turns={[
            {
              id: "answer",
              role: "assistant",
              locale: tag,
              content: `${tag} answer`,
              suggestedQuestions: [`${tag} question`],
            },
            {
              id: "error",
              role: "assistant",
              locale: tag,
              content: "ignored",
              contentKey: "genericError",
            },
          ]}
        />,
      );
      expect(markup).toContain(`<p lang="${tag}">${tag} answer</p>`);
      expect(markup).toContain(
        `<button lang="${tag}" type="button">${tag} question</button>`,
      );
      expect(markup).toContain(
        `<p lang="${messageLocale(selected)}">${messages[selected].genericError}</p>`,
      );
    },
  );
});
