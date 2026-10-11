export async function checkApprovedFaqVisitor(tab) {
  const checks = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  const button = name => tab.playwright.getByRole("button", { name, exact: true });
  const read = () => tab.playwright.evaluate(() => ({
    counts: JSON.parse(document.querySelector('[aria-label="Public request counts"]').textContent),
    answers: document.querySelectorAll(".turn--assistant").length,
    text: document.body.textContent,
    questions: Array.from(document.querySelectorAll(".visitor-suggestion-list button")).map(node => ({ text: node.textContent.trim().replace(/\s*↗$/, ""), disabled: node.disabled })),
  }));
  const wait = async predicate => {
    const deadline = Date.now() + 10000;
    while (Date.now() < deadline) {
      const state = await read();
      if (predicate(state)) return state;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error("Visitor FAQ state did not update");
  };
  await wait(state => state.questions.some(item => item.text === "已核准的問題" && !item.disabled));
  await button("已核准的問題").click();
  let state = await wait(state => state.answers === 1);
  verify(state.text.includes("APPROVED_ZH_ANSWER") && state.counts.faq === 1 && state.counts.chat === 0, "approved chip shows instant validated answer while chat is unavailable");
  await tab.playwright.getByText("來源", { exact: true }).click();
  verify((await tab.playwright.domSnapshot()).includes("S1: Synthetic evidence"), "instant answer keeps collapsible verified citations");
  await button("Toggle approval fixture").click();
  await button("已核准的問題").click();
  state = await wait(state => state.answers === 2);
  verify(state.counts.faq === 1 && state.counts.chat === 0, "mid-session withdrawal remains cached until FAQ/profile reload");
  await button("English").click();
  state = await wait(state => state.questions.length === 0 && state.counts.faq === 2);
  verify(state.answers === 2, "refreshed withdrawn FAQ removes chips without appending an answer");
  await button("Toggle approval fixture").click();
  await button("Delay next FAQ fixture").click();
  await button("繁體中文").click();
  await wait(state => state.counts.held);
  await button("English").click();
  await wait(state => state.questions.some(item => item.text === "Approved question" && !item.disabled));
  await button("Release FAQ fixture").click();
  state = await wait(state => !state.counts.held);
  verify(state.answers === 2 && state.questions.every(item => item.text === "Approved question"), "late initial FAQ response cannot replace the new locale");
  await button("Switch visitor bundle fixture").click();
  await button("繁體中文").click();
  await wait(state => state.questions.some(item => item.text === "已核准的問題" && !item.disabled));
  await button("English").click();
  await wait(state => state.questions.some(item => item.text === "Approved question" && !item.disabled));
  const before = (await read()).counts.faq;
  await button("Approved question").click();
  state = await wait(state => state.answers === 3);
  verify(state.text.includes("APPROVED_EN_ANSWER") && state.counts.faq === before && state.counts.chat === 0, "current English cached approval serves without another request");
  await tab.playwright.getByRole("textbox", { name: "Your question", exact: true }).fill("Approved question");
  await button("Ask question").click();
  state = await wait(state => state.answers === 4);
  verify(state.counts.faq === before && state.counts.chat === 0, "offline typed questions match the cached FAQ without a request");
  return { passed: checks.length, checks };
}
