import type { LocalizedText } from "./guidedOnboarding";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LANGUAGES, deriveConverter } from "../../i18n/languages";
import { planLanguages } from "../../i18n/plan";
import { blankSiteState } from "./__fixtures__/siteLanguages";
const initialLanguages = LANGUAGES.filter(({ tag }) =>
  initialGuidedOnboardingState(false, "zh-TW").locales.supported.includes(tag),
);
import {
  initialGuidedOnboardingState,
  serializeGuidedOnboarding,
  type GuidedProfile,
} from "./guidedOnboarding";
import {
  emptyProfileTranslationItems,
  PROFILE_FIELDS,
  profileLanguages,
  profileTranslationBody,
  profileTranslationSource,
  requestProfileTranslation,
  useProfileTranslation,
  type ProfileTranslationItem,
  type TranslateProfile,
} from "./profileTranslation";

const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  refs: [] as Array<{ current: unknown }>,
  effects: [] as Array<{
    dependencies: unknown[];
    cleanup: (() => void) | void;
  }>,
  stateIndex: 0,
  refIndex: 0,
  effectIndex: 0,
}));
vi.mock("react", async (original) => ({
  ...(await original<typeof import("react")>()),
  useState(initial: unknown) {
    const index = hooks.stateIndex++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return [
      hooks.values[index],
      (next: unknown) => {
        hooks.values[index] =
          typeof next === "function" ? next(hooks.values[index]) : next;
      },
    ];
  },
  useRef(initial: unknown) {
    const index = hooks.refIndex++;
    return (hooks.refs[index] ??= { current: initial });
  },
  useEffect(effect: () => (() => void) | void, dependencies: unknown[]) {
    const index = hooks.effectIndex++;
    const previous = hooks.effects[index];
    if (
      !previous ||
      dependencies.some(
        (value, at) => !Object.is(value, previous.dependencies[at]),
      )
    ) {
      previous?.cleanup?.();
      hooks.effects[index] = { dependencies, cleanup: effect() };
    }
  },
}));

beforeEach(() => {
  hooks.values = [];
  hooks.refs = [];
  hooks.effects = [];
});
afterEach(() => {
  hooks.effects.forEach(({ cleanup }) => cleanup?.());
});

function profile(): GuidedProfile {
  return {
    ...initialGuidedOnboardingState().profile,
    displayName: "Owner",
    githubLogin: "another-owner",
    headline: { "zh-TW": "", en: "" } as LocalizedText,
    bio: { "zh-TW": "", en: "" } as LocalizedText,
    greeting: { "zh-TW": "", en: "" } as LocalizedText,
  };
}

function translated(items: ProfileTranslationItem[]) {
  return {
    items: items.map((item, index) => ({
      field: item.field,
      target_locale: item.target_locale,
      text: `Translated ${item.field} ${index}`,
      method: deriveConverter(item.source_locale, item.target_locale)
        ? "converted"
        : "model",
      confirmed: false,
    })),
  };
}

function deferred() {
  let resolve!: (value: unknown) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<unknown>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function harness(initial: GuidedProfile, translate: TranslateProfile) {
  const options = {
    profile: initial,
    active: true,
    reset: false,
    modelGeneration: 1,
    enabled: true,
    modelEnabled: true,
    translate,
    onChange: vi.fn((next: GuidedProfile) => {
      options.profile = next;
    }),
  };
  return {
    options,
    render: function useTranslationHarness() {
      hooks.stateIndex = hooks.refIndex = hooks.effectIndex = 0;
      return useProfileTranslation(options);
    },
  };
}

describe("profile translation contract", () => {
  it.each(LANGUAGES)(
    "keeps a site order starting with $tag, independent of the admin locale",
    ({ tag }) => {
      const supported = [
        tag,
        ...LANGUAGES.filter((language) => language.tag !== tag).map(
          (language) => language.tag,
        ),
      ];
      expect(
        profileLanguages(supported).map((language) => language.tag),
      ).toEqual(supported);
    },
  );

  it.each(initialLanguages)(
    "sends column $tag as the source regardless of its writing system",
    async ({ tag }) => {
      for (const text of [
        "I maintain public tools.",
        "中文放在此欄，保留 `code` 🧪",
      ]) {
        const current = profile();
        for (const field of PROFILE_FIELDS) current[field][tag] = text;
        const items = emptyProfileTranslationItems(current);
        expect(items).toEqual(
          PROFILE_FIELDS.flatMap((field) =>
            initialLanguages
              .filter((language) => language.tag !== tag)
              .map((target) => ({
                field,
                source_locale: tag,
                target_locale: target.tag,
                text,
              })),
          ),
        );
        const request = vi.fn().mockResolvedValue(translated(items));
        const controller = new AbortController();
        await requestProfileTranslation(request, items, controller.signal);
        expect(request).toHaveBeenCalledExactlyOnceWith(
          "/api/admin/onboarding/profile/translate",
          {
            method: "POST",
            signal: controller.signal,
            body: JSON.stringify({ items }),
          },
        );
      }
    },
  );

  it("skips both-empty and both-filled fields and uses the filled side per field", () => {
    const current = profile();
    expect(emptyProfileTranslationItems(current)).toEqual([]);
    PROFILE_FIELDS.forEach((field, index) => {
      current[field][initialLanguages[index % initialLanguages.length].tag] =
        `Source ${field}`;
    });
    current.greeting = {
      "zh-TW": "Already filled",
      en: "Keep this exact text",
    } as LocalizedText;
    const items = emptyProfileTranslationItems(current);
    expect(items).toHaveLength(2);
    for (const item of items) {
      expect(current[item.field][item.target_locale]).toBe("");
      expect(item.text).toBe(current[item.field][item.source_locale]);
      expect(item.source_locale).not.toBe(item.target_locale);
    }
    expect(items.map((item) => item.source_locale)).toEqual(
      initialLanguages.map(({ tag }) => tag),
    );
  });

  it.each([
    "missing",
    "extra",
    "field",
    "locale",
    "blank",
    "type",
    "length",
    "method",
    "confirmed",
  ])("rejects a %s response before applying any field", (mutation) => {
    const current = profile();
    for (const field of PROFILE_FIELDS)
      current[field][initialLanguages[0].tag] = field;
    const items = emptyProfileTranslationItems(current);
    const response = translated(items);
    switch (mutation) {
      case "missing":
        response.items.pop();
        break;
      case "extra":
        response.items.push(response.items[0]);
        break;
      case "field":
        response.items[1].field = response.items[0].field;
        break;
      case "locale":
        response.items[1].target_locale = items[1].source_locale;
        break;
      case "blank":
        response.items[1].text = " \n ";
        break;
      case "type":
        Object.assign(response.items[1], { text: 42 });
        break;
      case "length":
        response.items[1].text = "界".repeat(2001);
        break;
      case "method":
        response.items[1].method = "fallback";
        break;
      case "confirmed":
        response.items[1].confirmed = true;
        break;
    }
    expect(profileTranslationBody(response, items)).toBeNull();
  });

  it("accepts the complete unconfirmed response, including a scalar-length boundary", () => {
    const current = profile();
    current.bio.en = "Source";
    const items = emptyProfileTranslationItems(current);
    const response = translated(items);
    response.items[0].text = "🧪".repeat(2000);
    expect(profileTranslationBody(response, items)).toEqual(response.items);
    for (const malformed of [null, [], {}, { items: null }, { items: [null] }])
      expect(profileTranslationBody(malformed, items)).toBeNull();
  });
});

describe("profile translation lifecycle", () => {
  it.each(
    LANGUAGES.filter((language) => "derive" in language).map((language) => ({
      target: language.tag,
      source: LANGUAGES.find(
        ({ tag }) =>
          tag === ("derive" in language ? language.derive.from : undefined),
      )!.tag,
    })),
  )(
    "converts $source to $target without an accepted model, counts proposals, reviews and restores them",
    async ({ source, target }) => {
      const current = blankSiteState([source, target]).profile;
      for (const field of PROFILE_FIELDS)
        current[field][source] = `Different source ${field}`;
      const translate = vi.fn(async (items: ProfileTranslationItem[]) =>
        translated(items),
      );
      const view = harness(current, translate);
      view.options.modelEnabled = false;
      await view.render().run(emptyProfileTranslationItems(current));
      expect(translate).toHaveBeenCalledTimes(1);
      expect(
        translate.mock.calls[0][0].map((item) => item.target_locale),
      ).toEqual(PROFILE_FIELDS.map(() => target));
      expect(view.render().unreviewedCount).toBe(PROFILE_FIELDS.length);
      for (const field of PROFILE_FIELDS)
        expect(view.render().review(field, target)?.method).toBe("converted");
      view.render().markReviewed("headline", target);
      expect(view.render().unreviewedCount).toBe(PROFILE_FIELDS.length - 1);
      view.render().restore("bio", target);
      expect(view.options.profile.bio[target]).toBe("");
      expect(view.render().unreviewedCount).toBe(PROFILE_FIELDS.length - 2);
      view.render().edit("greeting", target, "Owner's own revision");
      expect(view.render().unreviewedCount).toBe(0);
    },
  );

  it("fills a registry-wide form in requests of at most six without overwriting a filled field", async () => {
    const supported = LANGUAGES.map(({ tag }) => tag);
    const source = supported.find((tag) => tag === "en")!;
    const current = blankSiteState(supported).profile;
    for (const field of PROFILE_FIELDS)
      current[field][source] = `Keep exact ${field}`;
    const translate = vi.fn(async (items: ProfileTranslationItem[]) =>
      translated(items),
    );
    const view = harness(current, translate);
    await view.render().fillEmpty();
    const allItems = translate.mock.calls.flatMap(([batch]) => batch);
    expect(translate).toHaveBeenCalledTimes(2);
    expect(allItems).toHaveLength(
      PROFILE_FIELDS.length * (supported.length - 1),
    );
    for (const item of allItems) {
      const derived = planLanguages(supported).derived.find(
        (pair) => pair.target === item.target_locale,
      );
      if (derived) expect(item.source_locale).toBe(derived.source);
    }
    for (const [batch] of translate.mock.calls)
      expect(batch.length).toBeLessThanOrEqual(6);
    expect(view.render().unreviewedCount).toBe(
      PROFILE_FIELDS.length * (supported.length - 1),
    );
    for (const field of PROFILE_FIELDS) {
      expect(view.options.profile[field][source]).toBe(current[field][source]);
      for (const tag of supported)
        expect(view.options.profile[field][tag]).not.toBe("");
    }
  });

  it("rejects a model response for a derive pair and blocks model items while no model is accepted", async () => {
    const target = LANGUAGES.find((language) => "derive" in language)!;
    const source = LANGUAGES.find(
      ({ tag }) => tag === ("derive" in target ? target.derive.from : ""),
    )!.tag;
    const current = blankSiteState([source, target.tag]).profile;
    current.bio[source] = "Another source value";
    const items = emptyProfileTranslationItems(current);
    const response = translated(items);
    response.items[0].method = "model";
    expect(profileTranslationBody(response, items)).toBeNull();
    const modelProfile = profile();
    modelProfile.bio.en = "Model source";
    const translate = vi.fn();
    const view = harness(modelProfile, translate);
    view.options.modelEnabled = false;
    await view.render().run(emptyProfileTranslationItems(modelProfile));
    expect(translate).not.toHaveBeenCalled();
  });

  it("aborts when a language is removed and never resurrects the removed review or text", async () => {
    const supported = LANGUAGES.map(({ tag }) => tag);
    const current = blankSiteState(supported).profile;
    const target = supported[supported.length - 1];
    current.bio[supported[0]] = "Owner's original public biography";
    const pending = deferred();
    const translate = vi.fn<TranslateProfile>(() => pending.promise);
    const view = harness(current, translate);
    const items = emptyProfileTranslationItems(current).filter(
      (item) => item.target_locale === target,
    );
    const request = view.render().run(items);
    view.options.profile = blankSiteState(
      supported.filter((tag) => tag !== target),
    ).profile;
    view.render();
    expect(translate.mock.calls[0][1].aborted).toBe(true);
    pending.resolve(translated(items));
    await request;
    expect(view.options.onChange).not.toHaveBeenCalled();
    expect(Object.keys(view.options.profile.bio)).not.toContain(target);
    expect(view.render().unreviewedCount).toBe(0);
  });

  it("clears proposal review state when the journey starts over", async () => {
    const current = profile();
    current.bio.en = "A public biography";
    const view = harness(current, async (items) => translated(items));
    await view.render().run(emptyProfileTranslationItems(current));
    expect(view.render().unreviewedCount).toBe(1);
    view.options.reset = true;
    view.options.active = false;
    view.render();
    expect(view.render().unreviewedCount).toBe(0);
    expect(view.render().status).toBeNull();
  });

  it("ignores an old request's finally while a newer generation is pending", async () => {
    const current = profile();
    current.headline.en = "Another introduction";
    const old = deferred();
    const recent = deferred();
    const translate = vi
      .fn<TranslateProfile>()
      .mockReturnValueOnce(old.promise)
      .mockReturnValueOnce(recent.promise);
    const view = harness(current, translate);
    const items = emptyProfileTranslationItems(current);
    const oldPending = view.render().run(items);
    view.options.active = false;
    view.render();
    view.options.active = true;
    view.render();
    const newPending = view.render().run(items);
    old.resolve(translated(items));
    await oldPending;
    expect(view.render().pending).toBe(true);
    expect(view.options.onChange).not.toHaveBeenCalled();
    recent.resolve(translated(items));
    await newPending;
    expect(view.render().pending).toBe(false);
    expect(view.options.onChange).toHaveBeenCalledTimes(1);
    expect(view.render().unreviewedCount).toBe(1);
  });

  it.each(initialLanguages)(
    "fills only empty targets from $tag in one request and restores an empty previous value",
    async ({ tag }) => {
      const current = profile();
      for (const field of PROFILE_FIELDS)
        current[field][tag] = `Owner text ${field}`;
      current.greeting = {
        "zh-TW": "Exact greeting",
        en: "Untouched greeting",
      } as LocalizedText;
      const translate = vi.fn(async (items: ProfileTranslationItem[]) =>
        translated(items),
      );
      const view = harness(current, translate);
      await view.render().run(emptyProfileTranslationItems(current));
      expect(translate).toHaveBeenCalledTimes(1);
      expect(translate.mock.calls[0][0]).toHaveLength(2);
      expect(view.options.profile.greeting).toEqual(current.greeting);
      const target = initialLanguages.find(
        (language) => language.tag !== tag,
      )!.tag;
      expect(view.render().unreviewedCount).toBe(2);
      expect(view.render().review("headline", target)?.previousText).toBe("");
      view.render().restore("headline", target);
      expect(view.options.profile.headline[target]).toBe("");
      expect(view.render().unreviewedCount).toBe(1);
      expect(view.render().status).toEqual({ kind: "restored" });
    },
  );

  it.each(["edit", "review"] as const)(
    "clears an unreviewed marker on %s and keeps translation metadata out of saved profile data",
    async (action) => {
      const current = profile();
      current.bio.en = "Owner wrote this";
      const view = harness(current, async (items) => translated(items));
      await view.render().run(emptyProfileTranslationItems(current));
      const item = emptyProfileTranslationItems(current)[0];
      expect(view.render().unreviewedCount).toBe(1);
      if (action === "edit")
        view.render().edit(item.field, item.target_locale, "Owner revision");
      else view.render().markReviewed(item.field, item.target_locale);
      expect(view.render().unreviewedCount).toBe(0);
      const saved = JSON.parse(
        serializeGuidedOnboarding({
          ...initialGuidedOnboardingState(),
          profile: view.options.profile,
        }),
      );
      expect(Object.keys(saved.profile).sort()).toEqual(
        Object.keys(current).sort(),
      );
      for (const field of PROFILE_FIELDS)
        expect(Object.keys(saved.profile[field]).sort()).toEqual(
          initialLanguages.map(({ tag }) => tag).sort(),
        );
      expect(JSON.stringify(saved.profile)).not.toMatch(
        /previousText|translatedText|reviewed|method|confirmed/,
      );
    },
  );

  it("restores a filled target exactly after retranslation", async () => {
    const current = profile();
    current.headline = {
      "zh-TW": " \n原值\n ",
      en: "Another source",
    } as LocalizedText;
    const item = profileTranslationSource(
      current,
      "headline",
      initialLanguages[0].tag,
    )!;
    const view = harness(current, async (items) => translated(items));
    await view.render().run([item]);
    expect(view.options.profile.headline[item.target_locale]).not.toBe(
      current.headline[item.target_locale],
    );
    view.render().markReviewed(item.field, item.target_locale);
    view.render().restore(item.field, item.target_locale);
    expect(view.options.profile.headline[item.target_locale]).toBe(
      current.headline[item.target_locale],
    );
    expect(view.render().unreviewedCount).toBe(0);
  });

  it.each(["source", "target", "reverted source"])(
    "discards only the field with an edited %s",
    async (side) => {
      const current = profile();
      current.headline.en = "Source headline";
      current.bio.en = "Source biography";
      const items = emptyProfileTranslationItems(current);
      const response = deferred();
      const view = harness(current, () => response.promise);
      const pending = view.render().run(items);
      expect(view.render().pending).toBe(true);
      const item = items[0];
      const editedLocale =
        side === "target" ? item.target_locale : item.source_locale;
      view.render().edit(item.field, editedLocale, "Owner changed this");
      if (side === "reverted source")
        view.render().edit(item.field, editedLocale, item.text);
      response.resolve(translated(items));
      await pending;
      expect(view.options.profile.headline[item.target_locale]).toBe(
        side === "target" ? "Owner changed this" : "",
      );
      expect(view.options.profile.bio[items[1].target_locale]).toBe(
        "Translated bio 1",
      );
      expect(view.render().unreviewedCount).toBe(1);
      expect(view.render().status).toEqual({
        kind: "translated",
        applied: 1,
        discarded: 1,
      });
      expect(view.render().pending).toBe(false);
    },
  );

  it.each(["unmount", "leave", "model"])(
    "aborts on %s and ignores delayed success, failure and cleanup",
    async (action) => {
      for (const fail of [false, true]) {
        const current = profile();
        current.greeting.en = "Hello from another owner";
        const response = deferred();
        const translate = vi.fn<TranslateProfile>(() => response.promise);
        const view = harness(current, translate);
        const items = emptyProfileTranslationItems(current);
        const pending = view.render().run(items);
        const signal = translate.mock.calls[0][1] as AbortSignal;
        if (action === "unmount")
          hooks.effects.forEach(({ cleanup }) => cleanup?.());
        else {
          if (action === "leave") view.options.active = false;
          else view.options.modelGeneration += 1;
          view.render();
        }
        expect(signal.aborted).toBe(true);
        if (fail) response.reject(new Error("PROVIDER_TIMEOUT"));
        else response.resolve(translated(items));
        await pending;
        expect(view.options.onChange).not.toHaveBeenCalled();
        expect(view.render().errorCode).toBe("");
        hooks.values = [];
        hooks.refs = [];
        hooks.effects = [];
      }
    },
  );

  it("starts no request for no work, no accepted model, or an already pending request", async () => {
    const current = profile();
    current.bio.en = "A different source";
    const response = deferred();
    const translate = vi.fn(() => response.promise);
    const view = harness(current, translate);
    const items = emptyProfileTranslationItems(current);
    await view.render().run([]);
    view.options.enabled = false;
    await view.render().run(items);
    expect(translate).not.toHaveBeenCalled();
    view.options.enabled = true;
    const pending = view.render().run(items);
    await view.render().run(items);
    expect(translate).toHaveBeenCalledTimes(1);
    response.resolve(translated(items));
    await pending;
  });

  it.each([
    "PROVIDER_TIMEOUT",
    "PROVIDER_ERROR",
    "PROVIDER_OUTPUT_SCHEMA_INVALID",
    "CONFIG_INVALID",
  ])("keeps original data on %s", async (code) => {
    const current = profile();
    current.greeting.en = "Source greeting";
    const view = harness(current, async () => {
      throw new Error(code);
    });
    await view.render().run(emptyProfileTranslationItems(current));
    expect(view.options.profile).toEqual(current);
    expect(view.render().unreviewedCount).toBe(0);
    expect(view.render().errorCode).toBe(code);
    expect(view.render().pending).toBe(false);
  });
});
