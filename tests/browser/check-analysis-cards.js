// Run with the documented browser runtime against analysis-card-review.tsx.
export async function checkAnalysisCards(tab, viewport) {
  const checks = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  for (const locale of ["zh-TW", "en"]) {
    const chinese = locale === "zh-TW";
    const sources = chinese ? "查看專案依據（1 個來源）" : "View project evidence (1 source)";
    const full = chinese ? "閱讀完整解讀" : "Read the full interpretation";
    for (const width of [375, 768, 1024, 1440]) {
      await viewport.set({ width, height: 900 });
      const source = tab.playwright.getByText(sources, { exact: true }).nth(0);
      await source.press("Enter");
      const opened = await tab.playwright.evaluate(() => {
        const first = document.querySelector(".guided-onboarding__interpretation");
        return {
          open: first.querySelector(".guided-onboarding__sources").open,
          path: first.querySelector(".guided-onboarding__source strong").textContent,
          hasScript: !!first.querySelector("script"),
          focused: document.activeElement === first.querySelector("summary"),
        };
      });
      verify(opened.open && opened.focused && opened.path === "src/parser.ts:4-12" && !opened.hasScript, `${locale}/${width}: keyboard sources, focus, correct evidence, escaped excerpt`);
      await source.press("Space");
      await tab.playwright.getByText(full, { exact: true }).press("Enter");
      const expanded = await tab.playwright.evaluate(() => {
        const text = document.querySelectorAll(".guided-onboarding__interpretation-text")[1];
        return text.querySelector("details").open && getComputedStyle(text.querySelector(".guided-onboarding__interpretation-preview")).display === "none";
      });
      verify(expanded, `${locale}/${width}: full interpretation replaces preview`);
      await tab.playwright.getByText(full, { exact: true }).press("Enter");
      const layout = await tab.playwright.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        cards: document.querySelectorAll(".guided-onboarding__interpretation").length,
        closed: [...document.querySelectorAll(".guided-onboarding__sources")].every((e) => !e.open),
        controls: [...document.querySelectorAll(".guided-onboarding__sources > summary")].every((e) => e.getBoundingClientRect().height >= 44),
      }));
      verify(!layout.overflow && layout.cards === 2 && layout.closed && layout.controls, `${locale}/${width}: no overflow, two cards, collapsed sources, 44px controls`);
    }
    await tab.playwright.getByRole("button", { name: "中文 / English", exact: true }).press("Enter");
  }
  await tab.playwright.getByRole("button", { name: "下一步：描述我的貢獻", exact: true }).press("Enter");
  const contribution = await tab.playwright.domSnapshot();
  verify(contribution.includes("你的貢獻說明") && contribution.includes("0/1") && !contribution.includes("此專案的貢獻已由你確認"), "next step requires owner input and does not confirm a contribution");
  await tab.playwright.getByRole("button", { name: "返回", exact: true }).press("Enter");
  verify((await tab.playwright.domSnapshot()).includes("AI 整理・尚未確認"), "back navigation preserves analysis results");
  await viewport.reset();
  return checks;
}
