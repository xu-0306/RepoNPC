import type { SuggestedClaim } from "./guidedOnboarding";

export type ClaimKind = SuggestedClaim["kind"];
export function ClaimEditor({
  locale,
  id,
  kind,
  statement,
  disabled,
  onChange,
}: {
  locale: "zh-TW" | "en";
  id: string;
  kind: ClaimKind;
  statement: { "zh-TW": string; en: string };
  disabled?: boolean;
  onChange: (
    kind: ClaimKind,
    statement: { "zh-TW": string; en: string },
  ) => void;
}) {
  const zh = locale === "zh-TW";
  const kinds: Record<ClaimKind, string> = {
    role: zh ? "角色" : "Role",
    responsibility: zh ? "負責事項" : "Responsibility",
    achievement: zh ? "成果" : "Outcome",
    context: zh ? "背景與期間" : "Context and duration",
  };
  return (
    <fieldset disabled={disabled}>
      <legend>{zh ? "作者陳述" : "Owner statement"}</legend>
      <label htmlFor={`${id}-kind`}>{zh ? "陳述種類" : "Statement kind"}</label>
      <select
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
      {(["zh-TW", "en"] as const).map((language) => (
        <label key={language} htmlFor={`${id}-${language}`}>
          {zh ? "作者陳述" : "Owner statement"} ({language})
          <textarea
            id={`${id}-${language}`}
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
