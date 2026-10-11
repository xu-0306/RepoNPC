import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  GitHubShareGuide,
  type GitHubShareGuideProps,
} from "./GitHubShareGuide";
import { cardMarkdown, verifiedPagesMarkdown } from "./sharing";

function props(
  locale: "zh-TW" | "en",
  verifiedPagesUrl: string | null,
): GitHubShareGuideProps {
  const publicUrl = "https://legacy.example.test/visitor";
  return {
    locale,
    verifiedPagesUrl,
    publicUrl,
    account: "fixture",
    profileStatus: "ready",
    imageStatus: "ready",
    repositoryUrl: null,
    profileUrl: null,
    readmeUrl: null,
    createUrl: null,
    filename: "reponpc-card.gif",
    markdown: cardMarkdown(publicUrl, locale),
    cardReady: true,
    busy: false,
    notice: "",
    onAccountChange: vi.fn(),
    onPublicUrlChange: vi.fn(),
    onCheckProfile: vi.fn(),
    onCheckImage: vi.fn(),
    onDownload: vi.fn(),
    onCopy: vi.fn(),
  };
}

describe("Pages and legacy README routes", () => {
  it.each(["zh-TW", "en"] as const)(
    "keeps an unverified Pages site separate from the usable advanced route in %s",
    (locale) => {
      const input = props(locale, null);
      const markup = renderToStaticMarkup(<GitHubShareGuide {...input} />);
      expect(markup).toContain('href="#pages-share-panel-heading"');
      expect(markup).not.toContain('id="github-share-pages-markdown"');
      const legacy = markup.match(
        /<details><summary>[^<]+<\/summary>([\s\S]*?)<\/details>/,
      )?.[1];
      expect(legacy).toContain('id="github-share-public-url"');
      expect(legacy).toContain('id="github-share-markdown"');
      expect(legacy).toContain(input.publicUrl);
      expect(legacy).not.toMatch(/<button[^>]*disabled/);
      expect(input.onCopy).not.toHaveBeenCalled();
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "shows only verified Pages Markdown in the primary field in %s",
    (locale) => {
      const url = "https://fixture.github.io/project/";
      const markup = renderToStaticMarkup(
        <GitHubShareGuide {...props(locale, url)} />,
      );
      const field = markup.match(
        /<textarea[^>]*id="github-share-pages-markdown"[^>]*>([\s\S]*?)<\/textarea>/,
      )?.[1];
      expect(field).toBe(
        verifiedPagesMarkdown(url, locale)
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;"),
      );
      expect(field).not.toContain("legacy.example.test");
      expect(markup).toContain('id="github-share-public-url"');
      expect(markup).not.toContain('href="#pages-share-panel-heading"');
    },
  );

  it("retains legacy validation and disabled-copy guidance", () => {
    const input = props("en", null);
    input.publicUrl = "http://localhost:8090";
    input.markdown = cardMarkdown(input.publicUrl, "en");
    const markup = renderToStaticMarkup(<GitHubShareGuide {...input} />);
    expect(markup).toMatch(
      /<button[^>]*disabled=""[^>]*>Copy text for README<\/button>/,
    );
    expect(markup).toContain('aria-describedby="github-share-markdown-status"');
    expect(markup).toContain('href="#pages-share-panel-heading"');
  });
});

it.each(["zh-TW", "en"] as const)(
  "copies each displayed route exactly and focuses the existing Pages heading in %s",
  (locale) => {
    const input = props(locale, "https://fixture.github.io/project/");
    const nodes = (node: ReactNode): ReactElement<Record<string, unknown>>[] =>
      Children.toArray(node).flatMap((child) =>
        isValidElement<Record<string, unknown>>(child)
          ? [child, ...nodes(child.props.children as ReactNode)]
          : [],
      );
    const tree = nodes(GitHubShareGuide(input));
    const fields = tree.filter((node) => node.type === "textarea");
    const copies = tree.filter(
      (node) =>
        node.type === "button" &&
        node.props.children ===
          (locale === "zh-TW"
            ? "複製要貼進 README 的文字"
            : "Copy text for README"),
    );
    expect(copies).toHaveLength(2);
    copies.forEach((button, index) => {
      (button.props.onClick as () => void)();
      expect(input.onCopy).toHaveBeenNthCalledWith(
        index + 1,
        fields[index].props.value,
      );
    });
    const heading = { tabIndex: 0, focus: vi.fn(), scrollIntoView: vi.fn() };
    vi.stubGlobal("document", {
      getElementById: vi.fn().mockReturnValue(heading),
    });
    try {
      const link = nodes(GitHubShareGuide(props(locale, null))).find(
        (node) => node.props.href === "#pages-share-panel-heading",
      )!;
      (link.props.onClick as () => void)();
      expect(document.getElementById).toHaveBeenCalledWith(
        "pages-share-panel-heading",
      );
      expect(heading.tabIndex).toBe(-1);
      expect(heading.focus).toHaveBeenCalledWith({ preventScroll: true });
      expect(heading.scrollIntoView).toHaveBeenCalledWith({
        block: "start",
        behavior: "instant",
      });
    } finally {
      vi.unstubAllGlobals();
    }
  },
);
