import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CheckboxField } from "./CheckboxField";

describe("CheckboxField", () => {
  it("associates each generated label with its own native checkbox", () => {
    const markup = renderToStaticMarkup(
      <>
        <CheckboxField defaultChecked>更換服務網址</CheckboxField>
        <CheckboxField>Use no key</CheckboxField>
      </>,
    );
    const ids = [...markup.matchAll(/<input[^>]* id="([^"]+)"/g)].map(
      (match) => match[1],
    );
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(2);
    for (const id of ids) expect(markup).toContain(`for="${id}"`);
    expect(markup.match(/type="checkbox"/g)).toHaveLength(2);
    expect(markup).toContain('class="checkbox-field__text"');
  });

  it("keeps disabled state, explicit identifiers and rich text labels", () => {
    const markup = renderToStaticMarkup(
      <CheckboxField id="repository-choice" disabled aria-describedby="reason">
        <strong>Repository name</strong>
        <code>owner/project</code>
      </CheckboxField>,
    );
    expect(markup).toContain('for="repository-choice"');
    expect(markup).toContain('disabled=""');
    expect(markup).toContain('aria-describedby="reason"');
    expect(markup).toContain("<strong>Repository name</strong>");
  });
});
