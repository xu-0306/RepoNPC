// Run with the documented browser runtime against analysis-card-review.tsx.
export async function checkAnalysisCards(tab, viewport) {
  const checks = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  for (const locale of ["zh-TW", "en"]) {
    const chinese = locale === "zh-TW";
    const first = chinese ? "共用的輸入解析" : "Shared input parsing";
    const second = chinese ? "文件說明使用條件" : "Docs explain usage conditions";
    const missing = chinese ? "部分出處不在這次結果中" : "Some sources are not in this result";
    const info = chinese ? "AI 整理，僅供你參考" : "AI summary, for your reference";
    const privacy = chinese ? "不會公開，也不會自動寫進作品集。" : "Never public, never added to your portfolio automatically.";
    for (const width of [375, 768, 1024, 1440]) {
      await viewport.set({ width, height: 900 });
      const toggle = tab.playwright.getByRole("button", { name: first, exact: true });
      await toggle.press("Enter");
      const opened = await tab.playwright.evaluate(() => {
        const row = document.querySelector(".guided-analysis__highlight");
        const button = row.querySelector(".guided-analysis__toggle");
        const body = row.querySelector(".guided-analysis__body");
        const links = [...row.querySelectorAll("a")];
        return {
          expanded: button.getAttribute("aria-expanded") === "true" && !body.hidden,
          focused: document.activeElement === button,
          links: links.length === 3 && links.every((a) => a.href.startsWith("https://github.com/") && a.target === "_blank" && a.rel.includes("noopener")),
          path: body.querySelector("a").textContent,
          more: row.querySelector(".guided-analysis__more")?.textContent,
          hasScript: !!row.querySelector("script"),
        };
      });
      verify(opened.expanded && opened.focused && opened.links && opened.path.startsWith("src/parser.ts:4-12") && opened.more === "+1" && !opened.hasScript, `${locale}/${width}: keyboard expansion, focus, GitHub links, +1, escaped statement`);
      await toggle.press("Enter");
      const secondToggle = tab.playwright.getByRole("button", { name: second, exact: true });
      await secondToggle.press("Enter");
      verify((await tab.playwright.domSnapshot()).includes(missing), `${locale}/${width}: partly missing sources are disclosed`);
      await secondToggle.press("Enter");
      const infoButton = tab.playwright.getByRole("button", { name: info, exact: true });
      await infoButton.press("Enter");
      verify((await tab.playwright.domSnapshot()).includes(privacy), `${locale}/${width}: privacy popover opens from the keyboard`);
      await tab.playwright.getByRole("dialog").press("Escape");
      const dismissed = await tab.playwright.evaluate(() => ({
        closed: !document.querySelector(".guided-analysis__popover"),
        focused: document.activeElement?.classList.contains("guided-analysis__info") ?? false,
      }));
      verify(dismissed.closed && dismissed.focused, `${locale}/${width}: Escape closes the popover and returns focus`);
      const layout = await tab.playwright.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        rows: document.querySelectorAll(".guided-analysis__highlight").length,
        collapsed: [...document.querySelectorAll(".guided-analysis__toggle")].every((e) => e.getAttribute("aria-expanded") === "false"),
        controls: [...document.querySelectorAll(".guided-analysis__toggle")].every((e) => e.getBoundingClientRect().height >= 44),
        removed: !document.querySelector("pre, .guided-onboarding__interpretation, .guided-onboarding__sources"),
      }));
      verify(!layout.overflow && layout.rows === 2 && layout.collapsed && layout.controls && layout.removed, `${locale}/${width}: no overflow, two collapsed rows, 44px controls, no excerpts`);
    }
    await tab.playwright.getByRole("button", { name: "中文 / English", exact: true }).press("Enter");
  }
  await tab.playwright.getByRole("button", { name: "下一步：描述我的貢獻", exact: true }).press("Enter");
  const contribution = await tab.playwright.domSnapshot();
  verify(contribution.includes("你的貢獻說明") && contribution.includes("0/1") && !contribution.includes("此專案的貢獻已由你確認"), "next step requires owner input and does not confirm a contribution");
  await tab.playwright.getByRole("button", { name: "返回", exact: true }).press("Enter");
  verify((await tab.playwright.domSnapshot()).includes("共用的輸入解析"), "back navigation preserves analysis results");
  await viewport.reset();
  return checks;
}
