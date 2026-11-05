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
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          pagesOrigin={null}
        />,
      );

      expect(markup).toContain('aria-labelledby="visitor-gateway-heading"');
      expect(markup).toContain('for="visitor-gateway-origin"');
      // The Pages address is never typed here (ADR-081): it comes from the
      // saved Pages URL, so there is no second Pages field or label.
      expect(markup).not.toContain('for="visitor-pages-origin"');
      expect(markup).not.toContain('id="visitor-pages-origin"');
      expect(markup).not.toMatch(/Pages domain|Pages 網域/);
      expect(markup.match(/<input[^>]*type="url"/g)).toHaveLength(1);
      // Nothing is left that points at the removed field.
      expect(markup).not.toContain("visitor-pages-origin");
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
    "%s offers sharing without a mode warning",
    (locale) => {
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as VisitorGatewayRequest;
      const markup = renderToStaticMarkup(
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          pagesOrigin={null}
        />,
      );
      expect(markup).not.toMatch(/試用|trial|正式模式|production mode/i);
      expect(markup).not.toContain('role="note"');
      expect(markup).toContain('for="visitor-gateway-origin"');
      expect(markup).toContain(locale === "zh-TW" ? "啟動" : "Start");
      expect(request).not.toHaveBeenCalled();
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s is the last, optional section and says what visitors get without it",
    (locale) => {
      const zh = locale === "zh-TW";
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as VisitorGatewayRequest;
      const markup = renderToStaticMarkup(
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          pagesOrigin="https://account.github.io"
        />,
      );
      const heading = /<h2 id="visitor-gateway-heading">([^<]*)<\/h2>/.exec(
        markup,
      )?.[1];
      expect(heading).toBe(
        zh ? "4. 即時聊天（選填）" : "4. Live chat (optional)",
      );
      expect(markup).toContain(zh ? "選填" : "Optional");
      // What the visitor gets without it, and what it adds.
      expect(markup).toContain(
        zh
          ? "不做這一段，訪客也能打開你的聊天頁，看到常見問答和「休息中」訊息。"
          : "Skip this section and visitors can still open your chat page. They see the FAQ and a resting message.",
      );
      expect(markup).toContain(
        zh
          ? "訪客可在你的電腦開機時得到即時回答"
          : "visitors get live answers while this computer is on",
      );
      // Collapsed until a Funnel URL is saved: no `open` attribute without status.
      expect(markup).toMatch(/<details class="visitor-gateway__setup"[^>]*>/);
      expect(markup).not.toMatch(
        /<details class="visitor-gateway__setup"[^>]*\bopen=/,
      );
      // The fixed term stays exactly as agreed and no jargon is added.
      expect(markup).toContain("Funnel URL");
      // Visible text only: class names and ids keep their code names, and the
      // Funnel command help still names its environment variable (known debt).
      const visible = markup
        .replace(/<[^>]*>/g, " ")
        .replace(/REPONPC_VISITOR_GATEWAY_PORT/g, "");
      expect(visible).not.toMatch(/gateway|manifest/i);
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
        <VisitorGatewayPanel
          locale={locale}
          request={request}
          pagesOrigin={null}
        />,
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
