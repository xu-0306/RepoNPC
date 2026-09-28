import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  VisitorGatewayPanel,
  visitorGatewayErrorMessage,
} from "./VisitorGatewayPanel";
import type { VisitorGatewayRequest } from "./VisitorGatewayPanel";

describe("visitor gateway panel", () => {
  it.each(["zh-TW", "en"] as const)(
    "%s keeps origins and owner checks as labeled native controls",
    (locale) => {
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as VisitorGatewayRequest;
      const markup = renderToStaticMarkup(
        <VisitorGatewayPanel locale={locale} request={request} />,
      );

      expect(markup).toContain('aria-labelledby="visitor-gateway-heading"');
      expect(markup).toContain('for="visitor-gateway-origin"');
      expect(markup).toContain('for="visitor-pages-origin"');
      expect(markup).toContain('type="url"');
      expect(markup).toContain(
        "tailscale funnel --bg --https=443 http://127.0.0.1:&lt;visitor-port&gt;",
      );
      expect(markup).toContain("tailscale funnel --https=443 off");
      expect(markup).toContain("visitor-port");
      expect(markup).not.toContain("reset</code>");
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("maps only known gateway errors to actionable safe copy", () => {
    expect(visitorGatewayErrorMessage("GATEWAY_CONFLICT", "en")).toContain(
      "changed elsewhere",
    );
    expect(
      visitorGatewayErrorMessage("GATEWAY_VERIFICATION_STALE", "zh-TW"),
    ).toContain("重新完成檢查清單");

    const unknown = visitorGatewayErrorMessage(
      "PRIVATE_PROVIDER_URL_AND_EXCEPTION_TEXT",
      "en",
    );
    expect(unknown).toContain("could not be completed");
    expect(unknown).not.toContain("PRIVATE_PROVIDER_URL");
  });
});
