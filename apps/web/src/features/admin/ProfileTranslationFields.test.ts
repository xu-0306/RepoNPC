import { afterEach, describe, expect, it, vi } from "vitest";

import { fitHeight } from "./profileTranslation";

function textarea(
  scrollHeight: number,
  offsetHeight: number,
  clientHeight: number,
) {
  return {
    scrollHeight,
    offsetHeight,
    clientHeight,
    style: { height: "" },
  } as unknown as HTMLTextAreaElement;
}

describe("profile textarea auto-fit fallback", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("fits the height to the content, borders included, without field-sizing", () => {
    vi.stubGlobal("CSS", { supports: () => false });
    const element = textarea(120, 60, 56);
    fitHeight(element);
    expect(element.style.height).toBe("124px");
  });

  it("leaves the height to the browser when field-sizing is supported", () => {
    vi.stubGlobal("CSS", { supports: () => true });
    const element = textarea(120, 60, 56);
    fitHeight(element);
    expect(element.style.height).toBe("");
  });

  it("ignores a detached element", () => {
    expect(() => fitHeight(null)).not.toThrow();
  });
});
