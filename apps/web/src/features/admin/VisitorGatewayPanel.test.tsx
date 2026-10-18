import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  VisitorGatewayPanel,
  visitorGatewayErrorMessage,
} from "./VisitorGatewayPanel";
import { funnelHttpsPort } from "./visitorGatewayPort";
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
      expect(markup).toContain('aria-describedby="visitor-pages-origin-help"');
      expect(markup).toContain('id="visitor-pages-origin-help"');
      expect(markup).not.toContain("Listener");
      expect(markup).toContain('type="url"');
      // No origin is configured yet, so no Funnel port may be assumed.
      expect(markup).toContain(
        "tailscale funnel --bg --https=&lt;https-port&gt; http://127.0.0.1:&lt;visitor-port&gt;",
      );
      expect(markup).toContain(
        "tailscale funnel --https=&lt;https-port&gt; off",
      );
      expect(markup).not.toContain("--https=443");
      expect(markup).toContain("10000");
      expect(markup).toContain("visitor-port");
      expect(markup).not.toContain("reset</code>");
      expect(request).not.toHaveBeenCalled();
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s explains trial mode only when sharing is unavailable",
    (locale) => {
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as VisitorGatewayRequest;
      const trial = renderToStaticMarkup(
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          publicSharingAvailable={false}
        />,
      );
      const production = renderToStaticMarkup(
        <VisitorGatewayPanel locale={locale} request={request} />,
      );
      const notice = locale === "zh-TW" ? "本機試用模式" : "local trial mode";

      expect(trial).toContain('role="note"');
      expect(trial).toContain(notice);
      expect(trial).toContain(
        locale === "zh-TW" ? "正式模式" : "production mode",
      );
      expect(production).not.toContain(notice);
      expect(production).not.toContain('role="note"');
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("takes the Funnel port only from a usable HTTPS visitor origin", () => {
    expect(funnelHttpsPort("https://host.example.ts.net:10000")).toBe("10000");
    expect(funnelHttpsPort("https://host.example.ts.net:8443")).toBe("8443");
    expect(funnelHttpsPort("https://host.example.ts.net")).toBe("443");
    expect(funnelHttpsPort(" https://host.example.ts.net:443 ")).toBe("443");
    expect(funnelHttpsPort("https://host.example.ts.net:9000")).toBeNull();
    expect(funnelHttpsPort("http://host.example.ts.net:10000")).toBeNull();
    expect(funnelHttpsPort("")).toBeNull();
    expect(funnelHttpsPort("not a url")).toBeNull();
  });

  it("maps only known gateway errors to actionable safe copy", () => {
    expect(visitorGatewayErrorMessage("GATEWAY_CONFLICT", "en")).toContain(
      "changed elsewhere",
    );
    expect(visitorGatewayErrorMessage("GATEWAY_UNAVAILABLE", "en")).toContain(
      "port",
    );

    const unknown = visitorGatewayErrorMessage(
      "PRIVATE_PROVIDER_URL_AND_EXCEPTION_TEXT",
      "en",
    );
    expect(unknown).toContain("could not be completed");
    expect(unknown).not.toContain("PRIVATE_PROVIDER_URL");
  });
});
