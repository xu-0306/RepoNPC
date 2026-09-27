// AC-077 browser check. The server fixture seeds the terminal batch; every
// product mutation in this checker still travels through the rendered UI.
export async function checkR11Recovery(tab) {
  const checks = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  const button = (name) =>
    tab.playwright.getByRole("button", { name, exact: true });
  const snapshot = () => tab.playwright.domSnapshot();
  const waitFor = async (predicate, name, timeoutMs = 30000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await predicate()) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`${name} timed out`);
  };
  const waitForText = (text, name = text) =>
    waitFor(async () => (await snapshot()).includes(text), name);

  await waitFor(
    async () => (await button("設定 AI 並開始").count()) === 1,
    "intro",
  );
  await button("設定 AI 並開始").click();
  await waitForText("完成模型設定並選擇專案", "model setup");
  await button("完成模型設定並選擇專案").click();

  const account = tab.playwright.getByRole("textbox", {
    name: "GitHub 使用者名稱或個人檔案 URL",
    exact: true,
  });
  await waitFor(
    async () => (await account.count()) === 1,
    "repository discovery",
  );
  await account.fill("fixture");
  await button("探索專案").click();
  await waitForText("fixture/fails-once", "synthetic repositories");
  await tab.playwright
    .getByRole("checkbox", { name: /alpha fixture\/alpha$/ })
    .check();
  await tab.playwright
    .getByRole("checkbox", { name: /fails-once fixture\/fails-once$/ })
    .check();
  await button("確認選取並繼續分析").click();
  await waitForText("開始批次分析", "analysis step");

  // Confirmed selection clears only in-memory batch state. Reloading now
  // exercises the authenticated active lookup and its recovery=true branch.
  await tab.reload();
  await waitForText("可恢復的最近批次", "Chinese recovery after reload");
  let dom = await snapshot();
  verify(dom.includes("重新分析此專案"), "Chinese reanalyze control");
  verify(dom.includes("使用目前模型重新分析"), "Chinese current-model control");
  verify(dom.includes("重試需要確認的項目"), "Chinese retry control");

  await button("English").click();
  await waitForText("Recent recoverable batch", "English recovery");
  dom = await snapshot();
  verify(dom.includes("Reanalyze this project"), "English reanalyze control");
  verify(
    dom.includes("Reanalyze with current models"),
    "English current-model control",
  );
  verify(
    dom.includes("Retry items that need confirmation"),
    "English retry control",
  );

  await tab.reload();
  await waitForText("可恢復的最近批次", "recovery after second reload");
  verify(
    (await snapshot()).includes("重新分析此專案"),
    "recovery actions survive second reload",
  );

  await button("不再顯示這個批次").click();
  await waitFor(async () => {
    const current = await snapshot();
    return !current.includes("可恢復的最近批次");
  }, "dismissed recovery");
  await tab.reload();
  await waitFor(async () => {
    const current = await snapshot();
    return !current.includes("可恢復的最近批次");
  }, "dismissal after reload");

  const origin = new URL(await tab.url()).origin;
  await tab.goto(`${origin}/`);
  await tab.playwright.waitForTimeout(300);
  await tab.goto(`${origin}/admin`);
  await waitFor(async () => {
    const current = await snapshot();
    return !current.includes("可恢復的最近批次");
  }, "dismissal on another page");
  verify(true, "dismissal remains absent on another page");

  return { checks };
}
