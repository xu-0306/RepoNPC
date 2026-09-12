import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ChatProfilePanel } from "./ChatProfilePanel";
import { EmbeddingProfilePanel } from "./EmbeddingProfilePanel";
import { modelProbeError } from "./modelProbeError";

describe("model test diagnostics", () => {
  it.each(["zh-TW", "en"] as const)(
    "keeps the provider's original language and HTTP evidence in %s",
    (locale) => {
      const props = {
        locale,
        connections: [
          {
            connection_id: "fixture",
            display_name: "Fixture service",
            provider: "openai_compatible" as const,
            revision: 1,
            source: "managed" as const,
            endpoint_configured: true,
            key_configured: true,
            status: "configured",
          },
        ],
        pending: false,
        error: "",
        onRefresh: vi.fn(),
        onCreate: vi.fn(),
        onProbe: vi.fn(),
        onActivate: vi.fn(),
        onDelete: vi.fn(),
      };
      const profile = {
        profile_id: "fixture",
        model_id: "fixture-model",
        active: false,
        status: "probe_failed" as const,
        last_error_code: "PROVIDER_HTTP_402",
        last_error_message: "Requested tier requires project credits: ABC-92.",
        last_probed_at: "2026-09-12T00:00:00Z",
      };
      const chat = renderToStaticMarkup(
        <ChatProfilePanel
          {...props}
          onUpdate={vi.fn()}
          profiles={[
            {
              ...profile,
              connection_id: "fixture",
              connection_revision: 1,
              observed_model_id: null,
            },
          ]}
        />,
      );
      const embedding = renderToStaticMarkup(
        <EmbeddingProfilePanel
          {...props}
          catalog={[]}
          installedModels={[]}
          onOllamaPull={vi.fn()}
          onOllamaDelete={vi.fn()}
          profiles={[
            {
              ...profile,
              provider: "openai_compatible",
              connection_reference: "fixture",
              dimension: 2,
              normalized: true,
              last_error_code: "PROVIDER_HTTP_503",
              last_error_message:
                "Serveur temporairement indisponible: nœud 7.",
            },
          ]}
        />,
      );
      expect(chat).toMatch(/<p role="alert"[^>]*>HTTP 402[^<]+<\/p>/);
      expect(embedding).toMatch(/<p role="alert"[^>]*>HTTP 503[^<]+<\/p>/);
      expect(chat).toContain(
        "HTTP 402: Requested tier requires project credits: ABC-92.",
      );
      expect(embedding).toContain(
        "HTTP 503: Serveur temporairement indisponible: nœud 7.",
      );
      expect(chat).not.toContain("檢查帳戶餘額或方案");
      expect(chat).not.toContain("Check your balance or plan");
      for (const markup of [chat, embedding]) {
        expect(markup).toContain(
          `type="submit">${locale === "zh-TW" ? "新增模型" : "Add model"}</button>`,
        );
        expect(markup).not.toContain("新增待測模型");
        expect(markup).not.toContain("to test</button>");
      }
    },
  );

  it.each([401, 402, 403, 404, 408, 413, 422, 429, 500, 502, 503, 504, 418])(
    "displays the actual HTTP %s in both languages",
    (status) => {
      for (const locale of ["zh-TW", "en"] as const) {
        expect(modelProbeError(locale, `PROVIDER_HTTP_${status}`)).toContain(
          `HTTP ${status}`,
        );
      }
    },
  );

  it("distinguishes transport failures without inventing HTTP status", () => {
    expect(modelProbeError("zh-TW", "PROVIDER_TIMEOUT")).toContain("逾時");
    expect(modelProbeError("en", "PROVIDER_UNAVAILABLE")).toContain(
      "Could not connect",
    );
    expect(modelProbeError("zh-TW", "PROVIDER_TIMEOUT")).not.toContain("HTTP");
    expect(modelProbeError("en", "PROVIDER_INVALID_RESPONSE")).toContain(
      "could not obtain a usable model response",
    );
  });

  it.each(["zh-TW", "en"] as const)(
    "shows application parse evidence without disguising it as a provider error in %s",
    (locale) => {
      const diagnostic =
        "RepoNPC response check: HTTP 200; finish_reason=length: the response reached the output limit.";
      expect(
        modelProbeError(locale, "PROVIDER_INVALID_RESPONSE", diagnostic),
      ).toContain(diagnostic);
      expect(
        modelProbeError(locale, "PROVIDER_INVALID_RESPONSE"),
      ).not.toContain("HTTP 200");
    },
  );

  it("reports missing text honestly instead of guessing a reason", () => {
    expect(modelProbeError("zh-TW", "PROVIDER_HTTP_402")).toBe(
      "HTTP 402: 未提供可顯示的錯誤文字。",
    );
    expect(modelProbeError("en", "PROVIDER_HTTP_503", "  ")).toBe(
      "HTTP 503: No displayable error message was provided.",
    );
  });

  it("preserves original whitespace and treats message markup as text", () => {
    const message = '<img src=x onerror="alert(1)">\nUnknown Ω-900';
    const markup = renderToStaticMarkup(
      <p role="alert">
        {modelProbeError("zh-TW", "PROVIDER_HTTP_418", message)}
      </p>,
    );
    expect(markup).toContain("HTTP 418: &lt;img");
    expect(markup).toContain("\nUnknown Ω-900");
    expect(markup).not.toContain("<img");
  });

  it.each([
    "CHAT_PROBE_FAILED",
    "EMBEDDING_PROBE_FAILED",
    "PROVIDER_HTTP_999",
    "PROVIDER_HTTP_402<script>private</script>",
    "toString",
    "__proto__",
  ])("safely explains legacy or unknown code %s", (code) => {
    expect(modelProbeError("zh-TW", code)).toContain("請重新測試");
    expect(modelProbeError("en", code)).toContain("Test again");
    expect(modelProbeError("en", code)).not.toContain(code);
  });
});
