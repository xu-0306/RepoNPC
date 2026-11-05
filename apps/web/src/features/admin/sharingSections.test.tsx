import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import {
  GitHubShareGuide,
  type GitHubShareGuideProps,
} from "./GitHubShareGuide";
import { PagesSharePanel, type PagesSharingState } from "./PagesSharePanel";
import {
  SHARING_SECTIONS,
  sectionNumber,
  sectionRef,
  sectionTitle,
} from "./sharingSections";
import {
  VisitorGatewayPanel,
  visitorGatewayErrorMessage,
  type VisitorGatewayRequest,
} from "./VisitorGatewayPanel";

const LOCALES = ["zh-TW", "en"] as const;

function guideProps(
  locale: "zh-TW" | "en",
  overrides: Partial<GitHubShareGuideProps> = {},
): GitHubShareGuideProps {
  return {
    locale,
    verifiedPagesUrl: null,
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
    ...overrides,
  };
}

const request = vi.fn(async () => {
  throw new Error("Unexpected request");
});

const pagesState: PagesSharingState = {
  pages_url: "https://fixture.github.io/project/",
  configured: true,
  verified: false,
  verified_at: null,
  verified_content_sha256: null,
};

function pagesMarkup(
  locale: "zh-TW" | "en",
  state: PagesSharingState | null = pagesState,
) {
  return renderToStaticMarkup(
    <PagesSharePanel
      locale={locale}
      request={request}
      observedState={state}
      onStateChange={vi.fn()}
      onOperationPendingChange={vi.fn()}
    />,
  );
}

function guideMarkup(
  locale: "zh-TW" | "en",
  overrides: Partial<GitHubShareGuideProps> = {},
) {
  return renderToStaticMarkup(
    <GitHubShareGuide {...guideProps(locale, overrides)} />,
  );
}

function gatewayMarkup(locale: "zh-TW" | "en") {
  return renderToStaticMarkup(
    <VisitorGatewayPanel
      locale={locale}
      request={request as unknown as VisitorGatewayRequest}
      pagesOrigin={null}
    />,
  );
}

function headingNumber(markup: string, id: string): number {
  const match = new RegExp(`<h2 id="${id}">(\\d+)\\. `).exec(markup);
  expect(match, `heading ${id} has a number`).not.toBeNull();
  return Number(match![1]);
}

/** Every "section N" / 「第 N 段」 mention in rendered text. */
function sectionMentions(markup: string): number[] {
  return [...markup.matchAll(/section (\d+)|第 (\d+) 段/g)].map((match) =>
    Number(match[1] ?? match[2]),
  );
}

describe("sharing section numbers", () => {
  it("numbers the sections in the order they are shown", () => {
    expect(SHARING_SECTIONS).toEqual([
      "prepare",
      "pages",
      "profile",
      "liveChat",
    ]);
    expect(SHARING_SECTIONS.map(sectionNumber)).toEqual([1, 2, 3, 4]);
    expect(sectionTitle("pages", "GitHub Pages")).toBe("2. GitHub Pages");
    expect(sectionRef("en", "pages")).toBe("section 2");
    expect(sectionRef("zh-TW", "profile")).toBe("第 3 段");
    expect(sectionRef("es", "liveChat")).toBe("section 4");
  });

  it.each(LOCALES)(
    "%s headings carry the numbers the helper reports, in order",
    (locale) => {
      const pages = headingNumber(
        pagesMarkup(locale),
        "pages-share-panel-heading",
      );
      const profile = headingNumber(
        guideMarkup(locale),
        "github-share-guide-heading",
      );
      const liveChat = headingNumber(
        gatewayMarkup(locale),
        "visitor-gateway-heading",
      );
      expect([pages, profile, liveChat]).toEqual([
        sectionNumber("pages"),
        sectionNumber("profile"),
        sectionNumber("liveChat"),
      ]);
      expect(pages).toBeLessThan(profile);
      expect(profile).toBeLessThan(liveChat);
    },
  );

  it.each(LOCALES)(
    "%s every text that names a section names the rendered Pages heading",
    (locale) => {
      const pages = headingNumber(
        pagesMarkup(locale),
        "pages-share-panel-heading",
      );
      const markups = [
        guideMarkup(locale),
        guideMarkup(locale, { pagesConfigured: true }),
        guideMarkup(locale, {
          verifiedPagesUrl: "https://fixture.github.io/project/",
          pagesConfigured: true,
        }),
        guideMarkup(locale, {
          profileStatus: "missing",
          imageStatus: "missing",
        }),
        gatewayMarkup(locale),
        visitorGatewayErrorMessage("GATEWAY_CONFIGURATION_INVALID", locale),
      ];
      const mentions = markups.flatMap(sectionMentions);
      // Not vacuous: the Pages section is named in several places.
      expect(mentions.length).toBeGreaterThanOrEqual(4);
      expect(new Set(mentions)).toEqual(new Set([pages]));
    },
  );
});

describe("live chat status line in the README section", () => {
  it.each(LOCALES)(
    "%s shows off, on, or nothing for an old server",
    (locale) => {
      const zh = locale === "zh-TW";
      const none = guideMarkup(locale);
      expect(none).not.toContain("live-chat-status");

      const off = guideMarkup(locale, { liveChatOrigin: null });
      expect(off).toContain('data-testid="live-chat-status"');
      expect(off).toContain(
        zh
          ? "即時聊天：未開啟。訪客會看到常見問答和「休息中」訊息。"
          : "Live chat: off. Visitors see the FAQ and a resting message.",
      );

      const on = guideMarkup(locale, {
        liveChatOrigin: "https://host.example.ts.net",
      });
      expect(on).toContain(zh ? "即時聊天：已開啟。" : "Live chat: on.");
      expect(on).not.toContain(zh ? "未開啟" : "Live chat: off");
    },
  );
});

describe("the Pages section has one input and needs no live chat", () => {
  it.each(LOCALES)("%s is editable with live chat off and on", (locale) => {
    for (const liveChat of [null, "https://host.example.ts.net"]) {
      const markup = pagesMarkup(locale, {
        ...pagesState,
        pages_origin: "https://fixture.github.io",
        live_chat_origin: liveChat,
      });
      expect(markup.match(/<input\b/g)).toHaveLength(1);
      const input = markup.match(
        /<input\b[^>]*\bid="pages-share-url"[^>]*>/,
      )?.[0];
      expect(input).toBeDefined();
      expect(input).not.toContain("disabled");
      expect(markup).toContain(locale === "zh-TW" ? "Pages 網址" : "Pages URL");
      expect(markup).not.toMatch(
        /Pages 網域|Pages domain|same domain|同一個網域|上一步|previous step/i,
      );
    }
  });

  it.each(LOCALES)(
    "%s works with an older server that omits both fields",
    (locale) => {
      const markup = pagesMarkup(locale, pagesState);
      expect(markup).toMatch(/<input\b[^>]*\bid="pages-share-url"/);
    },
  );
});
