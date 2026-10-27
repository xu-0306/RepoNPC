export async function checkReviewedFaq(tab) {
  const checks = [];
  const verify = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  const snapshot = () => tab.playwright.domSnapshot();
  const button = name => tab.playwright.getByRole("button", { name, exact: true });
  const wait = async (text) => {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const value = await snapshot(); if (value.includes(text)) return value;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out: ${text}`);
  };
  const waitExport = async (count) => {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const value = await tab.playwright.evaluate(() => document.querySelector('[aria-label="Exported FAQ"]')?.textContent);
      if (value && JSON.parse(value).entries.length === count) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error("Export state did not update");
  };
  await wait("涵蓋檢查與常見問答審核");
  await button("使用模型檢查六個標準問題").click();
  let content = await wait("涵蓋檢查已完成");
  verify(content.includes("部分回答") && content.includes("沒有相關內容"), "coverage uses three result states");
  verify(content.includes("尚未檢查"), "suggested candidate stays ungenerated");
  await tab.playwright.getByRole("button", { name: "核准", exact: true }).nth(0).click();
  await wait("已核准");
  await button("下載已核准常見問答 JSON").click();
  await waitExport(1);
  let observation = await tab.playwright.evaluate(() => ({ logs: document.querySelector('[aria-label="Recorded operations"]')?.textContent,
    exported: document.querySelector('[aria-label="Exported FAQ"]')?.textContent }));
  verify((observation.logs.match(/generate:/g) ?? []).length === 6, "explicit check generates six registry questions");
  verify(JSON.parse(observation.exported).entries.length === 1 && !observation.exported.includes("reason_codes"), "export includes approved answers only");
  await tab.playwright.getByRole("button", { name: "拒絕", exact: true }).nth(0).click();
  await wait("已拒絕");
  await tab.playwright.getByRole("button", { name: "使用模型重新生成", exact: true }).nth(0).click();
  await wait("待審核");
  await tab.playwright.getByRole("button", { name: "補一段自述", exact: true }).nth(0).click();
  content = await wait("新增自述");
  verify(content.includes("負責內容 (繁體中文)"), "Chinese gap opens responsibility claim editor");
  await button("Return to FAQ").click();
  await tab.playwright.getByRole("button", { name: "改寫為我的自述", exact: true }).nth(0).click();
  content = await wait("新增自述");
  verify(content.includes("負責內容 (繁體中文)"), "Chinese rewrite reuses the preselected claim editor");
  await button("Return to FAQ").click();
  await button("中文 / English").click();
  await wait("Coverage and FAQ review");
  await button("Check six standard questions with models").click();
  await wait("Coverage checked.");
  await tab.playwright.getByRole("button", { name: "Add my statement to fill gap", exact: true }).nth(0).click();
  content = await wait("Add my statement");
  verify(content.includes("Responsibilities (English)"), "English gap opens responsibility claim editor");
  await button("Return to FAQ").click();
  await tab.playwright.getByRole("button", { name: "Rewrite as my statement", exact: true }).nth(0).click();
  content = await wait("Add my statement");
  verify(content.includes("Responsibilities (English)"), "rewrite reuses the existing preselected claim editor");
  await button("Return to FAQ").click();
  content = await wait("Coverage and FAQ review");
  verify(content.includes("the new answer may not cite this statement"), "owner is told normal regeneration does not guarantee new-statement citation");
  await tab.playwright.getByRole("button", { name: "Approve", exact: true }).nth(0).click();
  await wait("Approved");
  await button("Switch bundle fixture").click();
  await wait("The version changed.");
  await button("Download approved FAQ JSON").click();
  await waitExport(0);
  observation = await tab.playwright.evaluate(() => ({ exported: document.querySelector('[aria-label="Exported FAQ"]')?.textContent,
    disabled: Array.from(document.querySelectorAll("button")).find(node => node.textContent === "Check projects and update NPC")?.disabled }));
  verify(JSON.parse(observation.exported).entries.length === 0, "bundle switch withholds previous approvals from export");
  verify(observation.disabled === false, "coverage never gates update publication");
  await button("中文 / English").click();
  await wait("涵蓋檢查與常見問答審核");
  await button("Delay next generation fixture").click();
  await tab.playwright.getByRole("button", { name: "使用模型重新生成", exact: true }).nth(0).click();
  await wait("generation:held");
  await button("中文 / English").click();
  await wait("Coverage and FAQ review");
  await button("Release delayed generation fixture").click();
  await button("Refresh review queue").click();
  const localeState = await tab.playwright.evaluate(() => ({
    questions: Array.from(document.querySelectorAll('[aria-labelledby="faq-heading"] article h3')).map(node => node.textContent),
    disabled: Array.from(document.querySelectorAll("button")).find(node => node.textContent === "Refresh review queue")?.disabled,
  }));
  verify(localeState.disabled === false && localeState.questions.every(question => question.startsWith("en:")), "late generation cannot replace new locale or strand busy state");
  return { checks, passed: checks.length };
}
