import "../../p4-w2.css";

import { chromeLocale, endonym, type LanguageTag } from "../../i18n/languages";
import {
  localizedTags,
  type SuggestedClaim,
  type LocalizedText,
} from "./guidedOnboarding";

export type ClaimKind = SuggestedClaim["kind"];
export function ClaimEditor({
  locale,
  id,
  kind,
  statement,
  supported = localizedTags(statement),
  disabled,
  onChange,
}: {
  locale: LanguageTag;
  id: string;
  kind: ClaimKind;
  statement: LocalizedText;
  supported?: LanguageTag[];
  disabled?: boolean;
  onChange: (kind: ClaimKind, statement: LocalizedText) => void;
}) {
  const zh = chromeLocale(locale) === "zh-TW";
  const kinds: Record<ClaimKind, string> = {
    role: zh ? "角色" : "Role",
    responsibility: zh ? "負責事項" : "Responsibility",
    achievement: zh ? "成果" : "Outcome",
    context: zh ? "背景與期間" : "Context and duration",
  };
  return (
    <fieldset className="p4-w2-claim p4-w2__fields" disabled={disabled}>
      <legend>{zh ? "作者陳述" : "Owner statement"}</legend>
      <label htmlFor={`${id}-kind`}>{zh ? "陳述種類" : "Statement kind"}</label>
      <select
        className="px-field"
        id={`${id}-kind`}
        value={kind}
        onChange={(event) =>
          onChange(event.target.value as ClaimKind, statement)
        }
      >
        {Object.entries(kinds).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      {supported.map((language) => (
        <label key={language} htmlFor={`${id}-${language}`}>
          {zh ? "作者陳述" : "Owner statement"} ({endonym(language)})
          <textarea
            className="px-field"
            id={`${id}-${language}`}
            lang={language}
            required
            maxLength={4000}
            rows={3}
            value={statement[language]}
            onChange={(event) =>
              onChange(kind, { ...statement, [language]: event.target.value })
            }
          />
        </label>
      ))}
    </fieldset>
  );
}
