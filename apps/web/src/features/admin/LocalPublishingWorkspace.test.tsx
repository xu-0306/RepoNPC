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
        locale === "zh-TW" ? "內容草稿會保留" : "Your content draft is kept",
      );
      const reason = markup.match(
        /<p id="local-prepare-reason">([\s\S]*?)<\/p>/,
      )?.[1];
      expect(reason).toContain(
        locale === "zh-TW"
          ? "先設定並測試兩種模型"
          : "Set up and test both models",
      );
      expect(reason).toContain(
        locale === "zh-TW" ? "前往設定模型" : "Set up models",
      );
      expect(markup).not.toContain(
        locale === "zh-TW"
          ? "請先在模型設定選好並測試"
          : "Select and test both the answer",
      );
      expect(markup).toContain('aria-describedby="local-prepare-reason"');
    },
  );
});
