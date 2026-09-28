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
    questions: Array.from(document.querySelectorAll(".suggestion-list button")).map(node => ({ text: node.textContent, disabled: node.disabled })),
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
  verify(state.text.includes("APPROVED_ZH_ANSWER") && state.counts.faq === 2 && state.counts.chat === 0, "approved chip shows instant validated answer while chat is unavailable");
  await tab.playwright.getByText("來源", { exact: true }).click();
  verify((await tab.playwright.domSnapshot()).includes("S1: Synthetic evidence"), "instant answer keeps collapsible verified citations");
  await button("Delay next FAQ fixture").click();
  await button("已核准的問題").click();
  state = await wait(state => state.counts.held);
  verify(state.questions.every(item => item.disabled) && state.counts.faq === 3, "pending approval lookup prevents duplicate selection");
  await button("English").click();
  await wait(state => state.questions.some(item => item.text === "Approved question" && !item.disabled));
  await button("繁體中文").click();
  await wait(state => state.questions.some(item => item.text === "已核准的問題" && !item.disabled));
  await button("Release FAQ fixture").click();
  state = await wait(state => !state.counts.held);
  verify(state.answers === 1 && state.questions.some(item => !item.disabled), "late reply after zh-en-zh cannot append an outdated answer or strand controls");
  await button("Toggle approval fixture").click();
  await button("已核准的問題").click();
  state = await wait(state => state.questions.length === 0);
  verify(state.answers === 1 && state.counts.chat === 0, "fresh rejection removes cached chip without serving it or calling a model");
  await button("Toggle approval fixture").click();
  await button("English").click();
  await wait(state => state.questions.some(item => item.text === "Approved question"));
  await button("Switch visitor bundle fixture").click();
  const before = (await read()).counts.faq;
  await button("Approved question").click();
  state = await wait(state => state.counts.faq >= before + 2 && state.questions.some(item => item.text === "Approved question" && !item.disabled));
  verify(state.answers === 1, "bundle mismatch reloads profile and withholds the previous approval");
  await button("Approved question").click();
  state = await wait(state => state.answers === 2);
  verify(state.text.includes("APPROVED_EN_ANSWER") && state.counts.chat === 0, "current English approval serves after profile reload without generation");
  return { passed: checks.length, checks };
}
