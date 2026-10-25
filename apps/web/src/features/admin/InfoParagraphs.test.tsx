import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { InfoParagraphs } from "./InfoParagraphs";

it.each([
  ["en", "Use README.md. Nothing uploads automatically. Keep your text."],
  ["zh-TW", "使用 README.md。仍需手動上傳。保留原文。"],
] as const)(
  "splits %s guidance without dropping text or splitting the filename",
  (locale, text) => {
    const html = renderToStaticMarkup(
      <InfoParagraphs id="help" locale={locale} text={text} />,
    );
    const paragraphs = [...html.matchAll(/<p>(.*?)<\/p>/g)].map(
      (match) => match[1],
    );
    expect(paragraphs).toHaveLength(3);
    expect(paragraphs.join("")).toBe(text);
    expect(paragraphs[0]).toContain("README.md");
    expect(html).toContain('id="help"');
  },
);

it("escapes untrusted text", () => {
  const html = renderToStaticMarkup(
    <InfoParagraphs locale="en" text={'<img src="x">'} />,
  );
  expect(html).toContain("&lt;img");
  expect(html).not.toContain("<img");
});
