export async function checkGatewaySimplification(tab) {
  const checks = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  const button = (name) => tab.playwright.getByRole("button", { name, exact: true });
  const wait = async (text) => {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const state = await tab.playwright.domSnapshot();
      if (state.includes(text)) return state;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Timed out: ${text}`);
  };
  const observed = () => tab.playwright.evaluate(() => ({
    logs: document.querySelector('[aria-label="Observed synthetic requests"]')?.textContent,
    checked: [...document.querySelectorAll('input[type="checkbox"]')].map(input => input.checked),
    facts: [...document.querySelectorAll('dl div')].map(row => row.textContent),
  }));

  await wait("尚無擁有者回報的外網檢查");
  await button("啟動 Visitor Gateway").click();
  await wait("執行中");
  for (const name of ["使用非 tailnet 的獨立外網檢查", "開啟公開狀態頁與個人資料頁",
    "實際使用聊天並檢查引用來源", "確認管理、模型與未知路徑無法從公開入口存取"]) {
    await tab.playwright.getByRole("checkbox", { name, exact: true }).click();
  }
  await button("記錄擁有者回報檢查").click();
  await wait("目前 listener 啟動期間已由擁有者回報檢查完成");
  let state = await observed();
  const proofLine = state.logs.split("\n").find(line => line.includes("/verify"));
  const proof = JSON.parse(proofLine.slice(proofLine.indexOf("{")));
  verify(Object.keys(proof).sort().join(",") === "external_checks_confirmed,revision" && proof.external_checks_confirmed === true,
    "Chinese verification sends only revision and owner confirmation");
  verify(state.checked.every(value => !value), "successful report resets native checklist");
  await button("Activate next bundle").click();
  await button("重新整理狀態").click();
  let content = await wait("fixture-bundle-two");
  verify(content.includes("目前 listener 啟動期間已由擁有者回報檢查完成"), "bundle activation retains dated report");
  await button("Observe local failure").click();
  await button("重新整理狀態").click();
  await wait("先在本機準備可用版本");
  state = await observed();
  verify(state.facts[0].includes("未就緒") && state.facts[2].includes("就緒") && !state.facts[2].includes("未就緒"),
    "local readiness and external observation remain separate facts");
  await button("English fixture").click();
  content = await wait("Owner-confirmed external checks");
  verify(content.includes("Bundle and local readiness changes do not clear this dated observation"), "English explains the same dated semantics");
  await button("Restore local readiness").click();
  await button("Refresh status").click();
  await button("Hold next mutation").click();
  await button("Stop local gateway").click();
  content = await wait('button "Refresh status" [disabled]');
  verify(content.includes('button "Stop local gateway" [disabled]') && content.includes('button "Record owner-reported check" [disabled]'),
    "pending mutation disables duplicate actions and verification");
  await button("Release mutation").click();
  await wait("No owner-reported external check is recorded");
  verify((await observed()).facts[3].includes("Stopped"), "stop clears the dated report and listener fact");
  await button("Start visitor gateway").click();
  await wait("Running");
  for (const name of ["Check from an independent network outside your tailnet", "Open the public status and profile pages",
    "Use chat and inspect its citations", "Confirm admin, model, and unknown paths are unavailable publicly"]) {
    await tab.playwright.getByRole("checkbox", { name, exact: true }).click();
  }
  await button("Record owner-reported check").click();
  await wait("The owner reported completing the checks");
  state = await observed();
  verify(state.logs.split("\n").filter(line => line.includes("/verify")).length === 2, "English records exactly one equivalent report");
  await button("Conflict next mutation").click();
  await button("Stop local gateway").click();
  await wait("changed elsewhere");
  verify((await observed()).facts[3].includes("Running"), "stale revision cannot stop the listener");
  await button("Stop local gateway").click();
  await wait("No owner-reported external check is recorded");
  await tab.playwright.getByRole("textbox", { name: "Tailscale Funnel visitor origin", exact: true }).fill("https://next-fixture.ts.net");
  await button("Save origins").click();
  await wait("next-fixture.ts.net");
  verify((await observed()).logs.includes('"gateway_origin":"https://next-fixture.ts.net"'), "stopped configuration uses existing revision and clears report");
  verify((await tab.playwright.domSnapshot()).includes('button "Record owner-reported check" [disabled]'), "listener must be ready before confirmation");
  return checks;
}
