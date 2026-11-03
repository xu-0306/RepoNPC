import type { LanguageTag as Locale } from "../../i18n/languages";

export function InfoParagraphs({
  text,
  locale,
  id,
}: {
  text: string;
  locale: Locale;
  id?: string;
}) {
  return (
    <div id={id}>
      {Array.from(
        new Intl.Segmenter(locale, { granularity: "sentence" }).segment(text),
        ({ segment, index }) => (
          <p key={index}>{segment}</p>
        ),
      )}
    </div>
  );
}
