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
    "explains local trial mode at the top and numbers the steps like the sections in %s",
    (locale) => {
      const zh = locale === "zh-TW";
      const render = (publicSharingAvailable?: boolean) =>
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
            publicSharingAvailable={publicSharingAvailable}
          />,
        );
      const trial = render(false);
      const production = render();
      const banner = zh
        ? "目前是本機試用模式：可以預覽、儲存草稿並在這台電腦試聊，但不能公開分享，也無法產生 README。"
        : "Local trial mode: you can preview, save a draft and try chat on this computer, but you can&#x27;t share publicly or create a README.";
      expect(trial).toContain(banner);
      expect(trial).toContain("REPONPC_DEPLOYMENT_PROFILE=production");
      expect(production).not.toContain(banner);
      expect(production).not.toContain("REPONPC_DEPLOYMENT_PROFILE");
      for (const markup of [trial, production]) {
        // Chips use the same numbers as the section headings and reach every section.
        for (const target of [
          "#local-publication-heading",
          "#publication-appearance",
          "#visitor-gateway-heading",
          "#pages-share-panel-heading",
          "#github-share-guide-heading",
        ])
          expect(markup).toContain(`href="${target}"`);
        expect(markup).toContain(zh ? "2 訪客連線" : "2 Visitor connection");
        expect(markup).toContain("3 Pages");
        expect(markup).toContain("4 README");
        expect(markup).not.toMatch(/01 預覽|01 Preview|03 分享|03 Share/);
      }
    },
  );
});
