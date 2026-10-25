import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  VisitorGatewayPanel,
  visitorGatewayErrorMessage,
} from "./VisitorGatewayPanel";
import {
  funnelHttpsPort,
  parseVisitorPort,
  withFunnelPort,
} from "./visitorGatewayPort";
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

  it.each(["zh-TW", "en"] as const)(
    "%s labels the public entry port and local visitor port controls",
    (locale) => {
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as VisitorGatewayRequest;
      const markup = renderToStaticMarkup(
        <VisitorGatewayPanel locale={locale} request={request} />,
      );
      const funnelLabel = locale === "zh-TW" ? "公開連接埠" : "Public port";
      const localLabel = locale === "zh-TW" ? "本機連接埠" : "Local port";

      expect(markup).toContain(`>${funnelLabel}<`);
      expect(markup).toContain('for="visitor-funnel-port"');
      expect(markup).toContain('id="visitor-funnel-port"');
      expect(markup).toContain('value="443"');
      expect(markup).toContain('<option value="8443">8443</option>');
      expect(markup).toContain('<option value="10000">10000</option>');
      expect(markup).toContain(`>${localLabel}<`);
      expect(markup).toContain('for="visitor-local-port"');
      expect(markup).toContain('id="visitor-local-port"');
      // A text input keeps mistyped values visible (and invalid) instead of
      // collapsing them to "" which would mean "clear to the default".
      expect(markup).toMatch(
        /<input(?=[^>]*id="visitor-local-port")(?=[^>]*type="text")(?=[^>]*pattern="\[0-9\]\*")[^>]*>/,
      );
      expect(markup).not.toContain('type="number"');
      expect(markup).toContain('inputMode="numeric"');
      expect(markup).toContain('min="1024"');
      expect(markup).toContain('max="65535"');
      expect(markup).not.toContain("Using the default");
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("rewrites only the Funnel port of the visitor origin", () => {
    expect(withFunnelPort("https://host.example.ts.net:10000", "443")).toBe(
      "https://host.example.ts.net",
    );
    expect(withFunnelPort("https://host.example.ts.net", "10000")).toBe(
      "https://host.example.ts.net:10000",
    );
    expect(withFunnelPort("https://host.example.ts.net:443", "8443")).toBe(
      "https://host.example.ts.net:8443",
    );
    expect(withFunnelPort(" https://host.example.ts.net/ ", "8443")).toBe(
      "https://host.example.ts.net:8443",
    );
    expect(withFunnelPort("https://host.example.ts.net/x/", "10000")).toBe(
      "https://host.example.ts.net:10000",
    );
    expect(withFunnelPort("http://host.example.ts.net:8443", "10000")).toBe(
      "http://host.example.ts.net:8443",
    );
    expect(withFunnelPort("not a url", "10000")).toBe("not a url");
    expect(withFunnelPort("", "443")).toBe("");
  });

  it("accepts only whole local ports from 1024 to 65535", () => {
    expect(parseVisitorPort("1024")).toBe(1024);
    expect(parseVisitorPort(" 65535 ")).toBe(65535);
    expect(parseVisitorPort("1023")).toBeNull();
    expect(parseVisitorPort("65536")).toBeNull();
    expect(parseVisitorPort("8001.5")).toBeNull();
    expect(parseVisitorPort("")).toBeNull();
    expect(parseVisitorPort("80a")).toBeNull();
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
