// Run against admin-events-review.tsx using the documented browser tab API.
// Every state change goes through a visible fixture or production UI control.
export async function checkAdminEvents(tab) {
  const results = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    results.push(name);
  };
  const button = (name) =>
    tab.playwright.getByRole("button", { name, exact: true });
  const model = (revision) =>
    tab.playwright.getByText(`synthetic-model-revision-${revision}`, {
      exact: true,
    });
  const refresh = () =>
    tab.playwright
      .getByRole("region", { name: "可用的 AI 服務", exact: true })
      .getByRole("button", { name: "重新整理", exact: true })
      .click();
  await button("進階：編輯原始 YAML").click();
  await button("預覽變更").click();
  verify(
    (await tab.playwright
      .getByRole("heading", { name: "Synthetic preview A", exact: true })
      .count()) === 1,
    "preview renders",
  );
  // Read only the visible synthetic draft, so repeated runs change its value.
  const previousDraft = await tab.playwright.evaluate(
    () => document.querySelector("#admin-config-draft").value,
  );
  await tab.playwright
    .getByRole("textbox", { name: "reponpc.yml 原始 YAML", exact: true })
    .fill(previousDraft + "\n# synthetic edit");
  verify(
    (await tab.playwright
      .getByRole("heading", { name: "Synthetic preview A", exact: true })
      .count()) === 0,
    "editing removes stale preview",
  );
  const embedding = tab.playwright.getByRole("region", {
    name: "資料查找模型",
    exact: true,
  });
  await embedding.locator("summary").filter({ hasText: "新增模型" }).click();
  await embedding
    .getByRole("combobox", { name: "服務", exact: true })
    .selectOption("fixture-ollama");
  await tab.playwright
    .locator("summary")
    .filter({ hasText: "查看此服務的已安裝模型" })
    .click();
  await button("讀取模型清單").click();
  verify((await model(1).count()) === 1, "initial model list renders");
  await button("Simulate external service revision").click();
  await refresh();
  verify((await model(1).count()) === 0, "service revision clears old models");
  await button("讀取模型清單").click();
  verify(
    (await model(2).count()) === 1,
    "explicit reload returns current models",
  );
  await tab.playwright
    .getByRole("checkbox", { name: "Delay installed response", exact: true })
    .check();
  await button("讀取模型清單").click();
  await button("Simulate external service revision").click();
  await refresh();
  await button("Release installed response").click();
  verify(
    (await model(2).count()) === 0,
    "late response from old revision is ignored",
  );
  await tab.playwright
    .getByRole("checkbox", { name: "Delay installed response", exact: true })
    .uncheck();
  await button("讀取模型清單").click();
  verify(
    (await model(3).count()) === 1,
    "new request works after ignoring stale response",
  );
  return results;
}
