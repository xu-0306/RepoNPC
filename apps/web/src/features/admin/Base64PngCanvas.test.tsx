import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Base64PngCanvas } from "./Base64PngCanvas";

describe("Base64PngCanvas", () => {
  it("exposes an accessible CSP-safe canvas instead of a blocked data URL", () => {
    const markup = renderToStaticMarkup(
      <Base64PngCanvas
        failureText="Preview unavailable"
        height={448}
        label="Character sheet"
        pngBase64="example-bytes"
        width={256}
      />,
    );

    expect(markup).toContain('role="img"');
    expect(markup).toContain('aria-label="Character sheet"');
    expect(markup).toContain('width="256"');
    expect(markup).toContain('height="448"');
    expect(markup).not.toContain("data:image/");
    expect(markup).not.toContain("example-bytes");
  });

  it("marks animated frames with the selected state", () => {
    const markup = renderToStaticMarkup(
      <Base64PngCanvas
        failureText="Preview unavailable"
        height={64}
        label="Talk"
        pngBase64="example-bytes"
        state="talk"
        width={64}
      />,
    );

    expect(markup).toContain('data-character-state="talk"');
    expect(markup).toContain('aria-label="Talk"');
  });
});
