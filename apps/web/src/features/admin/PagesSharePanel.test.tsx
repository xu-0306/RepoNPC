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
  it.each(["zh-TW", "en"] as const)(
    "%s allows Pages editing and keeps the empty URL save guard",
    (locale) => {
      const request = vi.fn(async () => {
        throw new Error("Unexpected Pages request");
      });
      for (const observedState of [unconfiguredState, configuredState]) {
        const markup = renderToStaticMarkup(
          <PagesSharePanel
            locale={locale}
            request={request}
            observedState={observedState}
            onStateChange={vi.fn()}
            onOperationPendingChange={vi.fn()}
          />,
        );
        const input = markup.match(
          /<input\b[^>]*\bid="pages-share-url"[^>]*>/,
        )?.[0];
        expect(input).toBeDefined();
        expect(input).not.toContain("disabled");
        expect(input).toContain('aria-describedby="pages-share-url-help"');
        expect(markup).not.toMatch(/試用|trial|正式模式|production mode/i);
        expect(markup).not.toContain("pages-share-local-note");
        const save = locale === "zh-TW" ? "儲存" : "Save";
        const saveButton = markup.match(
          new RegExp(`<button\\b[^>]*>${save}</button>`),
        )?.[0];
        expect(saveButton).toContain('disabled=""');
      }
      expect(request).not.toHaveBeenCalled();
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s keeps Pages editable without a public GitHub account",
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
        <PagesSharePanel {...props} account="" />,
      );
      expect(availableMarkup).toBe(defaultMarkup);
      for (const markup of [defaultMarkup, availableMarkup]) {
        expect(markup).not.toMatch(/試用|trial|正式模式|production mode/i);
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

  it("keeps the saved site download available without a mode warning", () => {
    const markup = renderToStaticMarkup(
      <PagesSharePanel
        locale="en"
        request={vi.fn(async () => {
          throw new Error("Unexpected Pages request");
        })}
        observedState={configuredState}
        onStateChange={vi.fn()}
        onOperationPendingChange={vi.fn()}
      />,
    );

    expect(markup).toContain(
      '<a data-testid="pages-site-download" download="reponpc-site.zip" href="/api/admin/sharing/export">Download website ZIP file</a>',
    );
    expect(markup).not.toMatch(/試用|trial|正式模式|production mode/i);
    expect(markup).not.toContain("pages-share-local-note");
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

it.each(["zh-TW", "en"] as const)(
  "links to the website repository controls in %s",
  (locale) => {
    for (const [account, pagesUrl, repository] of [
      [
        "fixture",
        "https://fixture.github.io/project/",
        "https://github.com/fixture/project",
      ],
      [
        "another-owner",
        "https://another-owner.github.io/",
        "https://github.com/another-owner/another-owner.github.io",
      ],
      ["", "https://fixture.github.io/project/", null],
      ["fixture", "https://other.github.io/project/", null],
    ] as const) {
      const markup = renderToStaticMarkup(
        <PagesSharePanel
          locale={locale}
          account={account}
          observedState={{ ...configuredState, pages_url: pagesUrl }}
          request={async <T,>() => null as T}
          onStateChange={vi.fn()}
          onOperationPendingChange={vi.fn()}
        />,
      );
      const links = markup.match(/<a[^>]*target="_blank"[^>]*>/g) ?? [];
      expect(links).toHaveLength(3);
      for (const [index, suffix] of [
        "",
        "/settings/pages",
        "/upload",
      ].entries()) {
        expect(links[index]).toContain(
          `href="${index && repository ? repository + suffix : "https://github.com/new"}"`,
        );
        expect(links[index]).toContain('rel="noopener noreferrer"');
      }
    }
  },
);
