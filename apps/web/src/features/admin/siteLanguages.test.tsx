import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import {
  LANGUAGES,
  chromeLocale,
  endonym,
  type LanguageTag,
} from "../../i18n/languages";
import { CheckboxField } from "./CheckboxField";
import { ConfirmDialogView } from "./ConfirmDialog";
import { SiteLanguages } from "./SiteLanguages";
import { guidedOnboardingReducer, type SiteLocales } from "./guidedOnboarding";
import {
  ADMIN_CHROMES,
  blankSiteState,
  siteState,
} from "./__fixtures__/siteLanguages";

const hooks = vi.hoisted(() => ({
  values: [] as unknown[],
  refs: [] as Array<{ current: unknown }>,
  effects: [] as Array<() => unknown>,
  cursor: 0,
  refCursor: 0,
  id: 0,
}));
vi.mock("react", async (original) => ({
  ...(await original<typeof import("react")>()),
  useId: () => `language-control-${hooks.id++}`,
  useCallback: (callback: unknown) => callback,
  useEffect: (effect: () => unknown) => hooks.effects.push(effect),
  useState(initial: unknown) {
    const index = hooks.cursor++;
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
    return (hooks.refs[hooks.refCursor++] ??= { current: initial });
  },
}));
beforeEach(() => {
  hooks.values = [];
  hooks.refs = [];
  hooks.cursor = hooks.refCursor = hooks.id = 0;
});
afterEach(() => vi.unstubAllGlobals());

function elements(node: ReactNode): ReactElement<Record<string, unknown>>[] {
  return Children.toArray(node).flatMap((child) =>
    isValidElement<Record<string, unknown>>(child)
      ? [child, ...elements(child.props.children as ReactNode)]
      : [],
  );
}

function harness(
  locale: LanguageTag,
  initial = blankSiteState([LANGUAGES[0].tag]),
) {
  const input = {
    locale,
    state: initial,
    disabled: false,
    onChange: vi.fn((locales: SiteLocales) => {
      input.state = guidedOnboardingReducer(input.state, {
        type: "SET_LOCALES",
        locales,
      });
    }),
  };
  return {
    input,
    render() {
      hooks.cursor = hooks.refCursor = 0;
      hooks.effects = [];
      return elements(SiteLanguages(input));
    },
    checkbox(tag: LanguageTag) {
      return this.render().find(
        (node) =>
          node.type === CheckboxField && node.props.children === endonym(tag),
      )!;
    },
  };
}

it.each(ADMIN_CHROMES)(
  "uses native keyboard controls and guards the last language in %s",
  (locale) => {
    const view = harness(locale);
    const controls = view.render();
    expect(controls.filter((node) => node.type === CheckboxField)).toHaveLength(
      LANGUAGES.length,
    );
    expect(view.checkbox(LANGUAGES[0].tag).props.disabled).toBe(true);
    expect(
      view.checkbox(LANGUAGES[0].tag).props["aria-describedby"],
    ).toBeTruthy();
    (view.checkbox(LANGUAGES[0].tag).props.onChange as () => void)();
    expect(view.input.onChange).not.toHaveBeenCalled();
    const html = renderToStaticMarkup(<SiteLanguages {...view.input} />);
    expect(html.match(/type="checkbox"/g)).toHaveLength(LANGUAGES.length);
    expect(html).toContain(
      chromeLocale(locale) === "en"
        ? "The last language cannot be unchecked"
        : "最後一種語言無法取消選取",
    );
    expect(html).toContain('<select class="px-field"');
    expect(html).not.toMatch(/tabindex="-\d/);
    for (const node of controls.filter(
      (element) => element.type === "button",
    )) {
      expect(node.props.type).toBe("button");
      expect(node.props["aria-label"]).toBeTruthy();
    }
  },
);

it.each(ADMIN_CHROMES)(
  "selects every registry language, changes order and default, and adds empty fields in %s",
  (locale) => {
    const view = harness(locale);
    for (const { tag } of LANGUAGES.slice(1)) {
      (view.checkbox(tag).props.onChange as () => void)();
      expect(view.input.state.locales.supported).toContain(tag);
      for (const field of ["headline", "bio", "greeting"] as const)
        expect(view.input.state.profile[field][tag]).toBe("");
    }
    const last = LANGUAGES[LANGUAGES.length - 1].tag;
    const up = view
      .render()
      .find(
        (node) =>
          node.type === "button" &&
          node.props["aria-label"] ===
            `${chromeLocale(locale) === "en" ? "Move up" : "上移"} (${endonym(last)})`,
      )!;
    (up.props.onClick as () => void)();
    const expected = LANGUAGES.map(({ tag }) => tag);
    [expected[expected.length - 2], expected[expected.length - 1]] = [
      expected[expected.length - 1],
      expected[expected.length - 2],
    ];
    expect(view.input.state.locales.supported).toEqual(expected);
    const down = view
      .render()
      .find(
        (node) =>
          node.type === "button" &&
          node.props["aria-label"] ===
            `${chromeLocale(locale) === "en" ? "Move down" : "下移"} (${endonym(last)})`,
      )!;
    (down.props.onClick as () => void)();
    expect(view.input.state.locales.supported).toEqual(
      LANGUAGES.map(({ tag }) => tag),
    );
    const select = view.render().find((node) => node.type === "select")!;
    (select.props.onChange as (event: unknown) => void)({
      target: { value: last },
    });
    expect(view.input.state.locales.default).toBe(last);
    expect(view.input.state.locales.supported).toContain(last);
  },
);

it.each(ADMIN_CHROMES)(
  "keeps all language text until removal confirmation and restores the default invariant in %s",
  async (locale) => {
    const supported = LANGUAGES.map(({ tag }) => tag);
    const view = harness(locale, siteState(supported));
    const target = view.input.state.locales.default;
    const original = structuredClone(view.input.state);
    for (const confirmed of [false, true]) {
      (view.checkbox(target).props.onChange as () => void)();
      expect(view.input.state).toEqual(original);
      const dialog = view
        .render()
        .find((node) => node.type === ConfirmDialogView)!;
      expect(dialog.props.destructive).toBe(true);
      expect(dialog.props.title).toContain(endonym(target));
      (dialog.props.onClose as (value: boolean) => void)(confirmed);
      await Promise.resolve();
      if (!confirmed) expect(view.input.state).toEqual(original);
    }
    expect(view.input.state.locales.supported).toEqual(
      supported.filter((tag) => tag !== target),
    );
    expect(view.input.state.locales.default).toBe(supported[0]);
    for (const field of ["headline", "bio", "greeting"] as const)
      expect(Object.keys(view.input.state.profile[field])).not.toContain(
        target,
      );
    const repository = view.input.state.repositories[0];
    expect(repository.confirmedContribution).toBeNull();
    for (const text of [
      repository.proposal!.role,
      repository.proposal!.summary,
      repository.proposal!.claims[0].statement,
    ])
      expect(Object.keys(text)).not.toContain(target);
  },
);

it("confirms removal when only a contribution contains text, and drops an empty language immediately", async () => {
  const supported = LANGUAGES.map(({ tag }) => tag);
  const state = siteState(supported);
  const target = supported[1];
  for (const field of ["headline", "bio", "greeting"] as const)
    state.profile[field][target] = "";
  const view = harness(LANGUAGES[0].tag, state);
  (view.checkbox(target).props.onChange as () => void)();
  const dialog = view.render().find((node) => node.type === ConfirmDialogView)!;
  expect(dialog).toBeDefined();
  (dialog.props.onClose as (value: boolean) => void)(false);
  await Promise.resolve();
  view.input.state.repositories = [];
  (view.checkbox(target).props.onChange as () => void)();
  expect(view.input.state.locales.supported).not.toContain(target);
  expect(
    view.render().find((node) => node.type === ConfirmDialogView),
  ).toBeUndefined();
});

it("keeps the move action focused after reordering, including at the boundary, without scrolling", () => {
  const supported = LANGUAGES.map(({ tag }) => tag);
  const view = harness(LANGUAGES[0].tag, blankSiteState(supported));
  const focus = vi.fn();
  const getElementById = vi.fn(() => ({ focus }));
  vi.stubGlobal("document", { getElementById });
  const tag = supported[1];
  const move = view
    .render()
    .find(
      (node) =>
        node.type === "button" &&
        node.props["aria-label"] === `上移 (${endonym(tag)})`,
    )!;
  (move.props.onClick as () => void)();
  view.render();
  for (const effect of hooks.effects) effect();
  expect(getElementById).toHaveBeenCalledWith(move.props.id);
  expect(focus).toHaveBeenCalledExactlyOnceWith({ preventScroll: true });
  const boundary = view
    .render()
    .find(
      (node) =>
        node.type === "button" &&
        node.props["aria-label"] === `上移 (${endonym(tag)})`,
    )!;
  expect(boundary.props["aria-disabled"]).toBe(true);
  (boundary.props.onClick as () => void)();
  expect(view.input.state.locales.supported[0]).toBe(tag);
  expect(view.input.onChange).toHaveBeenCalledTimes(1);
});
