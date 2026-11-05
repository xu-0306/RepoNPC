import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { LocalPublishingWorkspace } from "./LocalPublishingWorkspace";

describe("publication setup guidance", () => {
  it.each(["zh-TW", "en"] as const)(
    "shows loading and a keyboard-accessible model action in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <LocalPublishingWorkspace
          locale={locale}
          content="schema_version: 1"
          spriteBase64={null}
          revision={null}
          initialAccount="fixture"
          selection={null}
          request={async <T,>() => ({}) as T}
          onStored={vi.fn()}
          onCreateDraft={vi.fn()}
          onConfigureModels={vi.fn()}
          repositories={[]}
          onAddClaim={vi.fn()}
        />,
      );
      expect(markup).toContain(
        locale === "zh-TW"
          ? "正在讀取本機發布狀態…"
          : "Loading local publication status…",
      );
      expect(markup).not.toContain(
        locale === "zh-TW"
          ? "目前無法確認本機發布狀態"
          : "The local publication status is unknown",
      );
      expect(markup).toContain(
        locale === "zh-TW"
          ? '<button class="px-button px-button--secondary" type="button">前往設定模型</button>'
          : '<button class="px-button px-button--secondary" type="button">Set up models</button>',
      );
      expect(markup).toContain(
        locale === "zh-TW"
          ? "內容草稿會保留"
          : "RepoNPC keeps your content draft",
      );
      const reason = markup.match(
        /<p id="local-prepare-reason">([\s\S]*?)<\/p>/,
      )?.[1];
      expect(reason).toContain(
        locale === "zh-TW"
          ? "先設定並測試兩種模型"
          : "Set up and test both models",
      );
      expect(reason).not.toContain(
        locale === "zh-TW" ? "前往設定模型" : "Set up models",
      );
      expect(markup).toMatch(
        locale === "zh-TW"
          ? /<div class="publication-status px-panel px-panel--inset">[\s\S]*<button class="px-button px-button--secondary" type="button">前往設定模型<\/button>/
          : /<div class="publication-status px-panel px-panel--inset">[\s\S]*<button class="px-button px-button--secondary" type="button">Set up models<\/button>/,
      );
      expect(markup).not.toContain(
        locale === "zh-TW"
          ? "請先在模型設定選好並測試"
          : "Select and test both the answer",
      );
      expect(markup).toContain('aria-describedby="local-prepare-reason"');
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "offers sharing and numbers the steps like the sections in %s",
    (locale) => {
      const zh = locale === "zh-TW";
      const render = () =>
        renderToStaticMarkup(
          <LocalPublishingWorkspace
            locale={locale}
            content="schema_version: 1"
            spriteBase64={null}
            revision={null}
            initialAccount="fixture"
            selection={null}
            request={async <T,>() => ({}) as T}
            onStored={vi.fn()}
            onCreateDraft={vi.fn()}
            repositories={[]}
            onAddClaim={vi.fn()}
          />,
        );
      const markup = render();
      expect(markup).not.toMatch(/試用|trial|正式模式|production mode/i);
      expect(markup).not.toContain("REPONPC_DEPLOYMENT_PROFILE");
      expect(markup).not.toContain("pages-share-local-note");
      expect(markup).toMatch(/<input[^>]*id="pages-share-url"[^>]*>/);
      expect(
        markup.match(/<input[^>]*id="pages-share-url"[^>]*>/)?.[0],
      ).not.toContain("disabled");
      {
        // Chips use the same numbers as the section headings and reach every section.
        for (const target of [
          "#local-publication-heading",
          "#publication-appearance",
          "#visitor-gateway-heading",
          "#pages-share-panel-heading",
          "#github-share-guide-heading",
        ])
          expect(markup).toContain(`href="${target}"`);
        expect(markup).toContain("2 Pages");
        expect(markup).toContain("3 README");
        expect(markup).toContain(
          zh ? "4 即時聊天（選填）" : "4 Live chat (optional)",
        );
        expect(markup).not.toContain(zh ? "訪客連線" : "Visitor connection");
        expect(markup).not.toMatch(/01 預覽|01 Preview|03 分享|03 Share/);
        // One Pages input, no second Pages field, and the optional live chat
        // section comes last, after Pages and README (ADR-081).
        expect(markup.match(/id="pages-share-url"/g)).toHaveLength(1);
        expect(markup).not.toContain("visitor-pages-origin");
        expect(markup).not.toMatch(/Pages domain|Pages 網域/);
        const positions = [
          "pages-share-panel-heading",
          "github-share-guide-heading",
          "visitor-gateway-heading",
        ].map((id) => markup.indexOf(`<h2 id="${id}"`));
        expect(positions.every((position) => position > 0)).toBe(true);
        expect(positions).toEqual([...positions].sort((a, b) => a - b));
        expect(markup.lastIndexOf("</section>")).toBeGreaterThan(positions[2]);
        // Visible text only. The uploaded file name and the Funnel command
        // help (a known debt) keep their technical names.
        const visible = markup
          .replace(/<[^>]*>/g, " ")
          .replace(/export-manifest\.json/g, "")
          .replace(/REPONPC_VISITOR_GATEWAY_PORT/g, "");
        expect(visible).not.toMatch(/gateway|manifest/i);
      }
    },
  );
});
