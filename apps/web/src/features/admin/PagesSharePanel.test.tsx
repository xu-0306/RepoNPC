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

const unconfiguredState: PagesSharingState = {
  pages_url: null,
  configured: false,
  verified: false,
  verified_at: null,
  verified_content_sha256: null,
};

describe("PagesSharePanel", () => {
  it.each([
    [
      "zh-TW",
      "目前是本機試用模式，無法儲存 Pages 網址。要用 GitHub Pages 分享，請改用正式模式啟動 RepoNPC。",
      "儲存",
    ],
    [
      "en",
      "RepoNPC is running in local trial mode, so the Pages URL cannot be saved. To share with GitHub Pages, start RepoNPC in production mode.",
      "Save",
    ],
  ] as const)(
    "%s explains and locks Pages saving in local trial mode",
    (locale, note, save) => {
      const request = vi.fn(async () => {
        throw new Error("Unexpected Pages request");
      });
      const markup = renderToStaticMarkup(
        <PagesSharePanel
          locale={locale}
          request={request}
          observedState={unconfiguredState}
          onStateChange={vi.fn()}
          onOperationPendingChange={vi.fn()}
          publicSharingAvailable={false}
        />,
      );

      expect(markup).toContain(
        `</h2><p role="note" id="pages-share-local-note">${note}</p>`,
      );
      const input = markup.match(
        /<input\b[^>]*\bid="pages-share-url"[^>]*>/,
      )?.[0];
      expect(input).toContain('disabled=""');
      expect(input).toContain(
        'aria-describedby="pages-share-url-help pages-share-local-note"',
      );
      const saveButton = markup.match(
        new RegExp(`<button\\b[^>]*>${save}</button>`),
      )?.[0];
      expect(saveButton).toContain('disabled=""');
      expect(request).not.toHaveBeenCalled();
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s keeps Pages editing unchanged when sharing is omitted or available",
    (locale) => {
      const request = vi.fn(async () => {
        throw new Error("Unexpected Pages request");
      });
      const props = {
        locale,
        request,
        observedState: unconfiguredState,
        onStateChange: vi.fn(),
        onOperationPendingChange: vi.fn(),
      };
      const defaultMarkup = renderToStaticMarkup(
        <PagesSharePanel {...props} />,
      );
      const availableMarkup = renderToStaticMarkup(
        <PagesSharePanel {...props} publicSharingAvailable={true} />,
      );

      expect(availableMarkup).toBe(defaultMarkup);
      for (const markup of [defaultMarkup, availableMarkup]) {
        expect(markup).not.toContain(
          "目前是本機試用模式，無法儲存 Pages 網址。要用 GitHub Pages 分享，請改用正式模式啟動 RepoNPC。",
        );
        expect(markup).not.toContain(
          "RepoNPC is running in local trial mode, so the Pages URL cannot be saved. To share with GitHub Pages, start RepoNPC in production mode.",
        );
        expect(markup).not.toContain("pages-share-local-note");
        const input = markup.match(
          /<input\b[^>]*\bid="pages-share-url"[^>]*>/,
        )?.[0];
        expect(input).toBeDefined();
        expect(input).not.toContain("disabled");
        expect(input).toContain('aria-describedby="pages-share-url-help"');
      }
      expect(request).not.toHaveBeenCalled();
    },
  );

  it("keeps the saved site download and local trial note together", () => {
    const markup = renderToStaticMarkup(
      <PagesSharePanel
        locale="en"
        request={vi.fn(async () => {
          throw new Error("Unexpected Pages request");
        })}
        observedState={configuredState}
        onStateChange={vi.fn()}
        onOperationPendingChange={vi.fn()}
        publicSharingAvailable={false}
      />,
    );

    expect(markup).toContain(
      '<a data-testid="pages-site-download" download="reponpc-site.zip" href="/api/admin/sharing/export">Download site archive</a>',
    );
    expect(markup).toContain(
      '<p role="note" id="pages-share-local-note">RepoNPC is running in local trial mode, so the Pages URL cannot be saved. To share with GitHub Pages, start RepoNPC in production mode.</p>',
    );
  });

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
