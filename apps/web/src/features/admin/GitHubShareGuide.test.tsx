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
import { verifiedPagesMarkdown } from "./sharing";

function props(
  locale: "zh-TW" | "en",
  verifiedPagesUrl: string | null,
): GitHubShareGuideProps {
  return {
    locale,
    verifiedPagesUrl,
    account: "fixture",
    profileStatus: "ready",
    imageStatus: "ready",
    repositoryUrl: null,
    profileUrl: null,
    readmeUrl: null,
    createUrl: null,
    filename: "reponpc-card.gif",
    cardReady: true,
    busy: false,
    notice: "",
    onAccountChange: vi.fn(),
    onCheckProfile: vi.fn(),
    onCheckImage: vi.fn(),
    onDownload: vi.fn(),
    onDownloadReadme: vi.fn(),
    onPreviewReadme: vi.fn(),
    readmePreview: null,
    onCopy: vi.fn(),
  };
}

describe("Verified Pages README route", () => {
  it.each(["zh-TW", "en"] as const)(
    "offers the complete README first with placement and preservation guidance in %s",
    (locale) => {
      const input = props(locale, "https://fixture.github.io/project/");
      const markup = renderToStaticMarkup(<GitHubShareGuide {...input} />);
      const label =
        locale === "zh-TW" ? "下載 README.md" : "Download README.md";
      expect(markup).toMatch(new RegExp(`<button[^>]*>${label}<\\/button>`));
      expect(markup.indexOf(label)).toBeLessThan(
        markup.indexOf('data-stage="profile"'),
      );
      expect(markup).toContain(
        'aria-describedby="github-share-readme-placement github-share-readme-download-status"',
      );
      expect(markup).toContain(
        locale === "zh-TW"
          ? "README.md 必須放在「與 GitHub 帳號同名的公開儲存庫」根目錄"
          : "README.md must be at the root of a public repository with the same name as your GitHub account",
      );
      expect(markup).toContain(
        locale === "zh-TW" ? "不會自動覆寫" : "never overwrites",
      );
      const unavailable = renderToStaticMarkup(
        <GitHubShareGuide {...props(locale, null)} />,
      );
      expect(unavailable).toMatch(
        new RegExp(`<button[^>]*disabled=""[^>]*>${label}<\\/button>`),
      );
      expect(unavailable).toContain(
        locale === "zh-TW"
          ? "先到第 3 段上傳並核對"
          : "Upload and verify your Pages site in section 3",
      );
      expect(unavailable).not.toContain('id="github-share-markdown"');
      expect(input.onDownloadReadme).not.toHaveBeenCalled();
    },
  );

  it("keeps busy README actions focusable and blocks their handlers", () => {
    const input = { ...props("en", "https://fixture.github.io/"), busy: true };
    const nodes = (node: ReactNode): ReactElement<Record<string, unknown>>[] =>
      Children.toArray(node).flatMap((child) =>
        isValidElement<Record<string, unknown>>(child)
          ? [child, ...nodes(child.props.children as ReactNode)]
          : [],
      );
    const actions = nodes(GitHubShareGuide(input)).filter(
      (node) =>
        node.type === "button" &&
        ["Download README.md", "Preview README content"].includes(
          String(node.props.children),
        ),
    );
    expect(actions).toHaveLength(2);
    for (const button of actions) {
      expect(button.props.disabled).toBe(false);
      expect(button.props["aria-disabled"]).toBe(true);
      (button.props.onClick as () => void)();
    }
    expect(input.onDownloadReadme).not.toHaveBeenCalled();
    expect(input.onPreviewReadme).not.toHaveBeenCalled();
    input.busy = false;
    nodes(GitHubShareGuide(input))
      .filter(
        (node) =>
          node.type === "button" &&
          ["Download README.md", "Preview README content"].includes(
            String(node.props.children),
          ),
      )
      .forEach((button) => (button.props.onClick as () => void)());
    expect(input.onDownloadReadme).toHaveBeenCalledOnce();
    expect(input.onPreviewReadme).toHaveBeenCalledOnce();
  });
  it.each(["zh-TW", "en"] as const)(
    "requires Pages verification before offering a card link in %s",
    (locale) => {
      const input = props(locale, null);
      const markup = renderToStaticMarkup(<GitHubShareGuide {...input} />);
      expect(markup).toContain('href="#pages-share-panel-heading"');
      expect(markup).not.toContain('id="github-share-pages-markdown"');
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
      expect(markup).not.toContain('id="github-share-public-url"');
      expect(markup).not.toContain('href="#pages-share-panel-heading"');
    },
  );
});

it.each(["zh-TW", "en"] as const)(
  "copies the displayed Pages link exactly and focuses the existing Pages heading in %s",
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
    expect(copies).toHaveLength(1);
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
