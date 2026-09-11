import { createRequire } from "node:module";
import { describe, expect, it } from "vitest";

import { LocalLaunchAccessPanel } from "../../apps/web/src/features/admin/LocalLaunchAccessPanel";

const webRequire = createRequire(
  new URL("../../apps/web/package.json", import.meta.url),
);
const { createElement } = webRequire("react");
const { renderToStaticMarkup } = webRequire("react-dom/server");

function renderPanel(locale: "zh-TW" | "en", state: "checking" | "relaunch") {
  return renderToStaticMarkup(
    createElement(LocalLaunchAccessPanel, { locale, state }),
  );
}

describe("LocalLaunchAccessPanel", () => {
  it.each([
    ["zh-TW", "正在確認本機管理工作階段…"],
    ["en", "Checking the local admin session…"],
  ] as const)(
    "announces the %s checking state semantically",
    (locale, message) => {
      const markup = renderPanel(locale, "checking");

      expect(markup).toContain('role="status"');
      expect(markup).toContain('aria-live="polite"');
      expect(markup).toContain(message);
    },
  );

  it.each([
    ["zh-TW", "請透過本機啟動器重新開啟 RepoNPC", "重新執行啟動器後再試一次"],
    [
      "en",
      "Reopen RepoNPC through the local launcher",
      "run the launcher again",
    ],
  ] as const)(
    "provides clear %s relaunch guidance",
    (locale, heading, guidance) => {
      const markup = renderPanel(locale, "relaunch");

      expect(markup).toContain("<section");
      expect(markup).toContain(heading);
      expect(markup).toContain(guidance);
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "does not render forbidden access controls for %s",
    (locale) => {
      const checkingMarkup = renderPanel(locale, "checking");
      const relaunchMarkup = renderPanel(locale, "relaunch");
      const markup = `${checkingMarkup}${relaunchMarkup}`;

      expect(markup).not.toMatch(/<(form|input|button|a)\b/i);
      expect(markup).not.toMatch(/github|password|setup code/i);
      expect(markup).not.toContain("local-launch=");
    },
  );
});

