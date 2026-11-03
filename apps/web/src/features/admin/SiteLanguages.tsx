import { useEffect, useId, useRef } from "react";

import {
  LANGUAGES,
  chromeLocale,
  endonym,
  type LanguageTag,
} from "../../i18n/languages";
import { CheckboxField } from "./CheckboxField";
import { useConfirmDialog } from "./ConfirmDialog";
import type { GuidedOnboardingState, SiteLocales } from "./guidedOnboarding";

const COPY = {
  "zh-TW": {
    title: "網站語言",
    hint: "至少選擇一種語言。最後一種語言無法取消選取。欄位會依此順序顯示。",
    up: "上移",
    down: "下移",
    default: "預設語言",
    remove: "移除語言",
    description:
      "此語言已有文字。移除後將刪除這些欄位的文字，並需要重新確認貢獻內容。",
  },
  en: {
    title: "Site languages",
    hint: "Select at least one language. The last language cannot be unchecked. Fields follow this order.",
    up: "Move up",
    down: "Move down",
    default: "Default language",
    remove: "Remove language",
    description:
      "This language contains text. Removing it drops that text and requires contribution confirmation again.",
  },
} as const;

export function SiteLanguages({
  locale,
  state,
  disabled,
  onChange,
}: {
  locale: LanguageTag;
  state: GuidedOnboardingState;
  disabled: boolean;
  onChange: (locales: SiteLocales) => void;
}) {
  const copy = COPY[chromeLocale(locale)];
  const id = useId();
  const [dialog, confirm] = useConfirmDialog(locale);
  const pendingFocus = useRef<string | null>(null);
  const { supported } = state.locales;
  const siteKey = supported.join(",");
  useEffect(() => {
    if (pendingFocus.current) {
      document
        .getElementById(pendingFocus.current)
        ?.focus({ preventScroll: true });
      pendingFocus.current = null;
    }
  }, [siteKey]);
  const ordered = [
    ...supported,
    ...LANGUAGES.map(({ tag }) => tag).filter(
      (tag) => !supported.includes(tag),
    ),
  ];

  function holdsText(tag: LanguageTag) {
    return [
      state.profile.headline,
      state.profile.bio,
      state.profile.greeting,
      ...state.repositories.flatMap((repository) =>
        [
          repository.proposal,
          repository.previousContribution,
          repository.confirmedContribution,
        ].flatMap((proposal) =>
          proposal
            ? [
                proposal.role,
                proposal.summary,
                ...proposal.claims.map((claim) => claim.statement),
              ]
            : [],
        ),
      ),
    ].some((text) => Boolean(text[tag]?.trim()));
  }

  async function toggle(tag: LanguageTag) {
    if (disabled) return;
    if (!supported.includes(tag)) {
      onChange({ ...state.locales, supported: [...supported, tag] });
      return;
    }
    if (supported.length === 1) return;
    if (
      holdsText(tag) &&
      !(await confirm({
        title: `${copy.remove} (${endonym(tag)})`,
        description: copy.description,
        confirmLabel: copy.remove,
        destructive: true,
      }))
    )
      return;
    const next = supported.filter((language) => language !== tag);
    onChange({
      default: state.locales.default === tag ? next[0] : state.locales.default,
      supported: next,
    });
  }

  function move(index: number, offset: number, focusId: string) {
    if (disabled || index + offset < 0 || index + offset >= supported.length)
      return;
    const next = [...supported];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    pendingFocus.current = focusId;
    onChange({ ...state.locales, supported: next });
  }

  return (
    <fieldset
      className="site-languages"
      disabled={disabled}
      aria-describedby={`${id}-hint`}
    >
      <legend>{copy.title}</legend>
      <p id={`${id}-hint`} className="guided-onboarding__disabled-reason">
        {copy.hint}
      </p>
      {ordered.map((tag) => {
        const index = supported.indexOf(tag);
        return (
          <div className="site-languages__row" key={tag}>
            <CheckboxField
              checked={index !== -1}
              disabled={disabled || (index !== -1 && supported.length === 1)}
              aria-describedby={`${id}-hint`}
              onChange={() => void toggle(tag)}
            >
              {endonym(tag)}
            </CheckboxField>
            {index !== -1 && (
              <div className="profile-translation__actions">
                <button
                  className="px-button px-button--secondary"
                  type="button"
                  id={`${id}-${tag}-up`}
                  aria-label={`${copy.up} (${endonym(tag)})`}
                  aria-disabled={index === 0}
                  onClick={() => move(index, -1, `${id}-${tag}-up`)}
                >
                  {copy.up}
                </button>
                <button
                  className="px-button px-button--secondary"
                  type="button"
                  id={`${id}-${tag}-down`}
                  aria-label={`${copy.down} (${endonym(tag)})`}
                  aria-disabled={index === supported.length - 1}
                  onClick={() => move(index, 1, `${id}-${tag}-down`)}
                >
                  {copy.down}
                </button>
              </div>
            )}
          </div>
        );
      })}
      <label htmlFor={`${id}-default`}>{copy.default}</label>
      <select
        className="px-field"
        id={`${id}-default`}
        value={state.locales.default}
        onChange={(event) =>
          onChange({
            ...state.locales,
            default: event.target.value as LanguageTag,
          })
        }
      >
        {supported.map((tag) => (
          <option value={tag} key={tag}>
            {endonym(tag)}
          </option>
        ))}
      </select>
      {dialog}
    </fieldset>
  );
}
