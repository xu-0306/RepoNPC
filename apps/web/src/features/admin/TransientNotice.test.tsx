import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TransientNotice } from "./TransientNotice";

describe("confirmed service save notice", () => {
  it.each(["服務已更新", "Service updated"])(
    "announces %s without moving focus",
    (message) => {
      const markup = renderToStaticMarkup(
        <TransientNotice message={message} />,
      );
      expect(markup).toContain('role="status"');
      expect(markup).toContain('aria-live="polite"');
      expect(markup).toContain(message);
      expect(markup).not.toContain("autofocus");
    },
  );
});
