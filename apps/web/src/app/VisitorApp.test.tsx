import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VisitorApp } from "./VisitorApp";
import { VisitorPage } from "./VisitorPage";
import { VisitorConversation } from "./VisitorConversation";
import { messages, type Locale } from "../i18n/messages";
import type { PublicFaq, PublicProfile } from "./publicTypes";

// Follow the existing Node hook harness: exercise real handlers, SSE and page
// rendering while keeping browser effects separate from explicit test actions.
const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  cursor: 0,
  effects: [] as (() => unknown)[],
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return {
    ...react,
    useEffect: (effect: () => unknown) => hooks.effects.push(effect),
    useCallback: (callback: unknown) => callback,
    useState: (initial: unknown) => {
      const index = hooks.cursor++;
      if (!(index in hooks.values))
        hooks.values[index] =
          typeof initial === "function" ? initial() : initial;
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
  };
});

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

const frame = (name: string, payload: object) =>
  `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`;
const reply = (
  text: string,
  insufficient: boolean,
  suggestions: string[] = [],
  kind?: unknown,
) =>
  new Response(
    frame("metadata", {}) +
      frame("token", { delta: text }) +
      frame("complete", {
        insufficient_evidence: insufficient,
        suggested_questions: suggestions,
        no_match_kind: kind,
      }),
  );

const cleanups: (() => void)[] = [];
beforeEach(() => {
  hooks.values = [];
  hooks.cursor = 0;
  hooks.effects = [];
  vi.stubGlobal("window", {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    matchMedia: () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
    setTimeout: vi.fn(() => 1),
    clearTimeout: vi.fn(),
    localStorage: { getItem: () => null, removeItem: vi.fn() },
  });
  vi.stubGlobal("document", { documentElement: { lang: "", dataset: {} } });
});
afterEach(() => {
  for (const cleanup of cleanups.splice(0)) cleanup();
  vi.unstubAllGlobals();
});

async function app(
  locale: Locale,
  suggestions: string[],
  faqQuestions: string[] = [],
  online = true,
) {
  const profile: PublicProfile = {
    schema_version: 1,
    locale,
    profile: {
      display_name: "Fixture owner",
      headline: "Headline",
      bio: "Bio",
      greeting: "Greeting",
      location: null,
      avatar_url: null,
      links: [],
    },
    repositories: [],
    suggested_questions: suggestions,
    character: {
      mode: "custom",
      asset_url: "/api/public/character.png",
      revision: 1,
      frame_duration_ms: 160,
      movement: "none",
    },
    index: { version: "fixture", built_at: "2026-10-19", repository_count: 0 },
  };
  const faq: PublicFaq = {
    bundle_id: "fixture",
    locale,
    entries: faqQuestions.map((question, index) => ({
      entry_id: `faq-${index}`,
      question,
      variants: [],
      answer_markdown: "Approved answer",
      citations: [],
    })),
  };
  data.profile.mockResolvedValue(profile);
  data.faq.mockResolvedValue(faq);
  data.status.mockResolvedValue({ chat_available: online });
  const render = () => {
    hooks.cursor = 0;
    hooks.effects = [];
    return VisitorApp().props as Parameters<typeof VisitorPage>[0];
  };
  render().onLocaleChange(locale);
  render();
  for (const effect of hooks.effects.slice()) {
    const cleanup = effect();
    if (typeof cleanup === "function") cleanups.push(cleanup as () => void);
  }
  await vi.waitFor(() => expect(render().profile).toEqual(profile));
  const markup = () => renderToStaticMarkup(<VisitorPage {...render()} />);
  const submit = async (question: string) => {
    render().onQuestionChange(question);
    render().onSubmit();
    await vi.waitFor(() => expect(render().pending).toBe(false));
  };
  return { render, markup, submit };
}

describe("visitor no-match UX", () => {
  it.each(["zh-TW", "en"] as const)(
    "keeps exactly one page h1 on the non-preview visitor page in %s",
    async (locale) => {
      const view = await app(locale, ["Next?"]);
      const markup = view.markup();
      expect(markup.match(/<h1\b/g)).toHaveLength(1);
      expect(markup).toMatch(/<h1 id="[^"]+-dialogue-title">Greeting<\/h1>/);
      expect(markup.match(/<main\b/g)).toHaveLength(1);
      expect(markup).not.toContain('data-preview="true"');
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "shows temporary copy and asks the same question again without no-match history in %s",
    async (locale) => {
      const text =
        locale === "zh-TW"
          ? "這次沒能整理出可靠的回答，請再問一次。"
          : "I couldn't put together a reliable answer this time. Please ask again.";
      const send = vi
        .fn()
        .mockResolvedValueOnce(reply(text, true, [], "temporary"))
        .mockResolvedValueOnce(reply("Answered", false));
      vi.stubGlobal("fetch", send);
      const view = await app(locale, ["Next?"]);
      await view.submit("Same question?");
      expect(send).toHaveBeenCalledTimes(1);
      expect(view.render().characterState).toBe("idle");
      expect(view.render().suggestions).toEqual(["Next?"]);
      expect(view.render().turns[1].suggestedQuestions).toEqual([]);
      expect(view.render().turns[1].contactLink).toBeUndefined();
      expect(view.markup()).toContain(text.replaceAll("'", "&#x27;"));
      expect(view.markup()).toContain(
        `<button type="button">${messages[locale].askAgain}</button>`,
      );
      expect(view.markup()).not.toContain('class="answer-suggestions"');
      const props = view.render();
      const conversation = VisitorConversation({ ...props });
      const assistant = conversation!.props.children[1];
      const button = assistant.props.children.find(
        (child: { type?: string } | null | false) =>
          child && child.type === "button",
      );
      button.props.onClick();
      await vi.waitFor(() => expect(view.render().pending).toBe(false));
      expect(send).toHaveBeenCalledTimes(2);
      expect(JSON.parse(send.mock.calls[1][1].body)).toEqual({
        message: "Same question?",
        locale,
        history: [],
      });
      expect(view.render().characterState).toBe("success");
    },
  );

  it.each([
    "no_content",
    "UNKNOWN",
    "Temporary",
    "__proto__",
    null,
    1,
    {},
    ["temporary"],
    undefined,
  ])("accepts only exact kinds and treats %j as no_content", async (kind) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(reply("No content", true, ["Next?"], kind)),
    );
    const view = await app("en", ["Next?"]);
    await view.submit("Question");
    expect(view.render().turns[1].noMatchKind).toBe("no_content");
    expect(view.render().turns[1].suggestedQuestions).toEqual(["Next?"]);
    expect(view.render().suggestions).toEqual([]);
    expect(view.render().characterState).toBe("idle");
    expect(view.markup()).not.toContain(messages.en.askAgain);
    expect(view.markup()).not.toContain(messages.en.retry);
  });

  it.each(["zh-TW", "en"] as const)(
    "keeps no-match idle, removes only latest duplicates, restores suggestions and excludes no-match history in %s",
    async (locale) => {
      const next = locale === "en" ? "Explore architecture?" : "探索架構？";
      const other = locale === "en" ? "Show the sources?" : "看看來源？";
      const send = vi
        .fn()
        .mockResolvedValueOnce(reply("No match", true, [next, next]))
        .mockResolvedValueOnce(reply("Answered", false))
        .mockResolvedValueOnce(reply("Another answer", false));
      vi.stubGlobal("fetch", send);
      const view = await app(locale, [next, next, other], [other, other]);
      expect(view.render().suggestions).toEqual([other, next]);
      await view.submit("Unsupported topic");
      expect(view.render().characterState).toBe("idle");
      expect(view.render().suggestions).toEqual([other]);
      expect(view.markup().match(/class="answer-suggestions"/g)).toHaveLength(
        1,
      );
      expect(
        view.markup().split(`<button type="button">${next}</button>`).length -
          1,
      ).toBe(1);
      expect(view.markup()).toContain(
        `<h3 class="px-label">${messages[locale].suggested}</h3>`,
      );
      await view.submit("Supported topic");
      expect(JSON.parse(send.mock.calls[1][1].body).history).toEqual([]);
      expect(view.render().characterState).toBe("success");
      expect(view.render().suggestions).toEqual([other, next]);
      expect(view.render().turns[1].suggestedQuestions).toEqual([next, next]);
      await view.submit("Follow up");
      expect(JSON.parse(send.mock.calls[2][1].body)).toEqual({
        message: "Follow up",
        locale,
        history: [
          { role: "user", content: "Supported topic" },
          { role: "assistant", content: "Answered" },
        ],
      });
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "hides the empty suggestion section and restores it after an answer in %s",
    async (locale) => {
      const send = vi
        .fn()
        .mockResolvedValueOnce(reply("No match", true, ["Next?", "Next?"]))
        .mockResolvedValueOnce(reply("Answer", false));
      vi.stubGlobal("fetch", send);
      const view = await app(locale, ["Next?", "Next?"], ["Next?"]);
      await view.submit("No evidence");
      expect(view.render().suggestions).toEqual([]);
      expect(view.markup()).not.toContain('class="visitor-suggestions"');
      expect(view.markup()).not.toContain(
        `<h3 class="px-label">${messages[locale].suggested}</h3>`,
      );
      await view.submit("Found evidence");
      expect(view.render().suggestions).toEqual(["Next?"]);
      expect(view.markup()).toContain('class="visitor-suggestions"');
      expect(view.markup()).toContain(
        `<h3 class="px-label">${messages[locale].suggested}</h3>`,
      );
      expect(view.markup()).toContain('class="answer-suggestions"');
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "uses offline copy according to displayed suggestions and retains FAQ success/history in %s",
    async (locale) => {
      const view = await app(locale, [], [], false);
      await view.submit("Unknown question");
      expect(view.render().turns[1].content).toBe(
        messages[locale].offlineFaqNoMatchWithoutSuggestions,
      );
      expect(view.render().characterState).toBe("idle");
      expect(view.markup()).not.toContain('class="answer-suggestions"');
      hooks.values = [];
      const offline = await app(locale, [], ["Approved?"], false);
      await offline.submit("Unknown question");
      expect(offline.render().turns[1].content).toBe(
        messages[locale].offlineFaqNoMatch,
      );
      expect(offline.render().characterState).toBe("idle");
      await offline.submit("Approved?");
      expect(offline.render().characterState).toBe("success");
      hooks.values = [];
      const online = await app(locale, [], ["Approved?"]);
      online.render().onSelectSuggestion("Approved?");
      expect(online.render().characterState).toBe("success");
      const send = vi.fn().mockResolvedValue(reply("Live answer", false));
      vi.stubGlobal("fetch", send);
      await online.submit("Follow up");
      expect(JSON.parse(send.mock.calls[0][1].body).history).toEqual([
        { role: "user", content: "Approved?" },
        { role: "assistant", content: "Approved answer" },
      ]);
    },
  );
});

describe("resting approved questions", () => {
  it.each(["zh-TW", "en"] as const)(
    "shows an admitted FAQ question enabled in %s",
    async (locale) => {
      const approved =
        locale === "zh-TW" ? "這個專案做什麼？" : "What does this project do?";
      const view = await app(locale, [], [approved], false);
      const block = view
        .markup()
        .match(/<div class="visitor-resting-faq">([\s\S]*?)<\/div>/)?.[1];
      expect(block).toContain(messages[locale].dialogueFaqLabel);
      expect(block).toContain(`type="button">${approved}</button>`);
      expect(block).not.toContain("disabled");
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "omits non-FAQ suggestions from the approved block in %s",
    async (locale) => {
      const approved =
        locale === "zh-TW" ? "已核准的問題？" : "An approved question?";
      const unapproved =
        locale === "zh-TW" ? "未核准的問題？" : "An unapproved question?";
      const view = await app(locale, [unapproved], [approved], false);
      const block = view
        .markup()
        .match(/<div class="visitor-resting-faq">([\s\S]*?)<\/div>/)?.[1];
      expect(block).toContain(approved);
      expect(block).not.toContain(unapproved);
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "hides the whole approved block when no suggestion qualifies in %s",
    async (locale) => {
      const view = await app(locale, ["Not an approved FAQ?"], [], false);
      expect(view.markup()).not.toContain('class="visitor-resting-faq"');
      expect(view.markup()).not.toContain(messages[locale].dialogueFaqLabel);
    },
  );
});

describe("locale changes in conversation history", () => {
  it.each(["zh-TW", "en"] as const)(
    "localizes app-owned offline non-answers with suggestions in %s",
    async (locale) => {
      const view = await app(locale, [], ["Approved?"], false);
      await view.submit("Unknown question");
      const next = locale === "zh-TW" ? "en" : "zh-TW";
      view.render().onLocaleChange(next);
      expect(view.markup()).toContain(messages[next].offlineFaqNoMatch);
      expect(view.markup()).not.toContain(messages[locale].offlineFaqNoMatch);
      expect(view.render().turns[0].content).toBe("Unknown question");
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "localizes app-owned offline non-answers without suggestions in %s",
    async (locale) => {
      const view = await app(locale, [], [], false);
      await view.submit("Unknown question");
      const next = locale === "zh-TW" ? "en" : "zh-TW";
      view.render().onLocaleChange(next);
      expect(view.markup()).toContain(
        messages[next].offlineFaqNoMatchWithoutSuggestions,
      );
      expect(view.markup()).not.toContain(
        messages[locale].offlineFaqNoMatchWithoutSuggestions,
      );
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "localizes the app-owned failure message in %s",
    async (locale) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockRejectedValue(new Error("Fixture failure")),
      );
      const view = await app(locale, []);
      await view.submit("Question before failure");
      const next = locale === "zh-TW" ? "en" : "zh-TW";
      view.render().onLocaleChange(next);
      expect(view.markup()).toContain(messages[next].genericError);
      expect(view.markup()).not.toContain(messages[locale].genericError);
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "localizes the app-owned cancellation message in %s",
    async (locale) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(() => new Promise<Response>(() => undefined)),
      );
      const view = await app(locale, []);
      view.render().onQuestionChange("Question to cancel");
      view.render().onSubmit();
      expect(view.render().pending).toBe(true);
      view.render().onCancel?.();
      const next = locale === "zh-TW" ? "en" : "zh-TW";
      view.render().onLocaleChange(next);
      expect(view.markup()).toContain(messages[next].processingCancelled);
      expect(view.markup()).not.toContain(messages[locale].processingCancelled);
      expect(view.render().pending).toBe(false);
    },
  );

  it("preserves actual NPC content even when it equals an app-owned message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(reply(messages["zh-TW"].genericError, false)),
    );
    const view = await app("zh-TW", []);
    await view.submit("保留實際對話");
    view.render().onLocaleChange("en");
    expect(view.markup()).toContain(messages["zh-TW"].genericError);
    expect(view.markup()).not.toContain(messages.en.genericError);
    expect(view.render().turns[0].content).toBe("保留實際對話");
  });
});
