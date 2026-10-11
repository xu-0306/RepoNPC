import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { PagesSharePanel, type PagesSharingState } from "./PagesSharePanel";

const configuredState: PagesSharingState = {
  pages_url: "https://fixture.github.io/project/",
  configured: true,
  verified: true,
  verified_at: "2026-09-29T00:00:01Z",
  verified_content_sha256: "a".repeat(64),
};

describe("PagesSharePanel", () => {
  it.each(["zh-TW", "en"] as const)(
    "%s renders accessible URL help and the native export link",
    (locale) => {
      const request = vi.fn(
        async <T,>(): Promise<T> => null as T,
      ) as unknown as <T>(path: string, options?: RequestInit) => Promise<T>;
      const markup = renderToStaticMarkup(
        <PagesSharePanel
          locale={locale}
          request={request}
          observedState={configuredState}
          onStateChange={vi.fn()}
          onOperationPendingChange={vi.fn()}
        />,
      );

      expect(markup).toContain('aria-describedby="pages-share-url-help"');
      expect(markup).toContain('id="pages-share-url-help"');
      expect(markup).not.toContain("A1");
      expect(markup).toContain('download="PAGES_SHARING_GUIDE.md"');
      expect(markup).toMatch(
        /<a\b(?=[^>]*href="\/api\/admin\/sharing\/export")(?=[^>]*download="reponpc-site\.zip")[^>]*>/,
      );
      expect(markup).toContain(`value="${configuredState.pages_url}"`);
      expect(markup).toContain("export-manifest.json");
      expect(markup).not.toContain("reponpc-manifest.json");
      expect(markup).not.toContain("createObjectURL");
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("does not render an export link before a Pages URL is configured", () => {
    const markup = renderToStaticMarkup(
      <PagesSharePanel
        locale="en"
        request={
          vi.fn() as unknown as <T>(
            path: string,
            options?: RequestInit,
          ) => Promise<T>
        }
        observedState={{
          pages_url: null,
          configured: false,
          verified: false,
          verified_at: null,
          verified_content_sha256: null,
        }}
        onStateChange={vi.fn()}
        onOperationPendingChange={vi.fn()}
      />,
    );

    expect(markup).not.toContain('href="/api/admin/sharing/export"');
  });
});
