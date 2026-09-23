// Production AdminPage + FastAPI recovery acceptance. Test-only controls expose
// secret-free server observations; every product action still travels through
// the rendered UI and production API routes.
export async function checkAnalysisRecovery(tab, options = {}) {
  const reconciliationMode = options.reconciliationMode ?? "running";
  const releaseStaleSnapshot = options.releaseStaleSnapshot === true;
  const checks = [];
  let delayedStatusTransitions = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  const button = (name) =>
    tab.playwright.getByRole("button", { name, exact: true });
  const buttonUnavailable = (name) =>
    tab.playwright.evaluate((label) => {
      const candidate = Array.from(document.querySelectorAll("button")).find(
        (candidate) => candidate.textContent?.trim() === label,
      );
      return candidate ? candidate.disabled : true;
    }, name);
  const snapshot = () => tab.playwright.domSnapshot();
  const waitFor = async (predicate, name, timeoutMs = 30000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const value = await predicate();
      if (value) return value;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(name + " timed out");
  };
  const waitForText = (value, name = value, timeoutMs) =>
    waitFor(async () => (await snapshot()).includes(value), name, timeoutMs);
  const state = async () => {
    const previous = await tab.playwright.evaluate(() =>
      Number(
        document.querySelector('[aria-label="Browser acceptance controls"]')
          ?.dataset.stateVersion || "0",
      ),
    );
    await button("Refresh acceptance state").click();
    return waitFor(
      () =>
        tab.playwright.evaluate((expectedVersion) => {
          const controls = document.querySelector(
            '[aria-label="Browser acceptance controls"]',
          );
          if (Number(controls?.dataset.stateVersion || "0") <= expectedVersion)
            return null;
          const value = document.querySelector(
            "[data-browser-state]",
          )?.textContent;
          return value && value !== "{}" ? JSON.parse(value) : null;
        }, previous),
      "acceptance observations",
    );
  };
  const captureBatchSnapshot = async () => {
    const before = await tab.playwright.evaluate(() =>
      JSON.parse(
        document.querySelector("[data-browser-batch-snapshots]")?.textContent ??
          "[]",
      ),
    );
    await button("Capture production batch snapshot").click();
    return waitFor(
      () =>
        tab.playwright.evaluate((expectedCount) => {
          const snapshots = JSON.parse(
            document.querySelector("[data-browser-batch-snapshots]")
              ?.textContent ?? "[]",
          );
          return snapshots.length > expectedCount
            ? snapshots[snapshots.length - 1]
            : null;
        }, before.length),
      "production batch snapshot",
    );
  };
  const currentBatchStatus = () =>
    tab.playwright.evaluate(
      () =>
        document.querySelector("section[data-batch-status]")?.dataset
          .batchStatus,
    );

  await waitFor(
    () =>
      tab.playwright.evaluate(
        () => document.documentElement.dataset.browserFaultReady === "true",
      ),
    "fault injection service worker",
  );
  await waitFor(
    async () => (await button("設定 AI 並開始").count()) === 1,
    "intro",
  );
  await button("設定 AI 並開始").click();
  await waitFor(
    async () => (await button("完成模型設定並選擇專案").count()) === 1,
    "model selection",
  );
  const selectedModels = await snapshot();
  verify(
    selectedModels.includes("browser-chat-a"),
    "initial chat model selected",
  );
  verify(
    selectedModels.includes("browser-embedding"),
    "embedding model selected",
  );
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
  await waitForText("fixture/fails-once", "fixture repositories");
  for (const slug of ["fixture/alpha", "fixture/beta", "fixture/fails-once"]) {
    const escaped = slug.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&");
    await tab.playwright
      .getByRole("checkbox", { name: new RegExp(escaped + "$") })
      .check();
  }
  await button("確認選取並繼續分析").click();
  await waitFor(
    async () => (await button("開始批次分析").count()) === 1,
    "preflight",
  );
  await button("開始批次分析").click();
  await waitForText(
    "已處理 3/3；成功 2；進行中 0；失敗 1",
    "initial partial result",
  );
  let dom = await snapshot();
  verify(
    dom.includes("src/main.py:1-2") && dom.includes("src/main.py:4-5"),
    "exact evidence paths and line ranges rendered",
  );
  verify(
    dom.includes("return 'fixture/alpha'") &&
      dom.includes("return 'fixture/beta'"),
    "exact evidence excerpts rendered",
  );
  verify(/E_[0-9a-f]+/.test(dom), "evidence identifiers rendered");

  await button("重試需要確認的項目").click();
  await waitForText(
    "伺服器可能已接受操作，但目前無法確認結果",
    "unknown retry result",
  );
  let observed = await state();
  verify(
    observed.discarded.retry === 1 && observed.discarded.retry_get === 1,
    "retry response and first reconciliation GET discarded",
  );
  verify(
    observed.reanalyze_requests.filter((entry) => entry.operation === "retry")
      .length === 1,
    "unknown retry did not send a second POST",
  );
  const retryControl = button("重試需要確認的項目");
  const reconcileControl = button("重新檢查批次狀態");
  verify(
    (await buttonUnavailable("重試需要確認的項目")) &&
      (await buttonUnavailable("重新分析此專案")) &&
      (await buttonUnavailable("使用目前模型重新分析")) &&
      !(await buttonUnavailable("重新檢查批次狀態")),
    "unknown result disables mutations and leaves reconciliation enabled",
  );
  try {
    await retryControl.click({ force: true, timeout: 500 });
  } catch {
    // A disabled native control may reject the forced pointer action. The
    // server-side count below remains the authoritative negative assertion.
  }
  observed = await state();
  verify(
    observed.reanalyze_requests.filter((entry) => entry.operation === "retry")
      .length === 1,
    "pointer retry attempt while unknown sent no POST",
  );
  verify(
    observed.items.find(
      (item) =>
        item.repository_slug === "fixture/fails-once" &&
        item.source_item_id === null,
    ).state === "generating",
    "retry remains running until explicit release",
  );
  if (reconciliationMode === "running") {
    await reconcileControl.click();
    await waitForText(
      "已處理 2/3；成功 2；進行中 1；失敗 0",
      "manual running reconciliation",
    );
    if (releaseStaleSnapshot) {
      await waitForText("即時進度已連接。", "running stream connected");
      await button("Arm stale batch request").click();
      await button("暫停批次").click();
      await waitFor(
        async () => (await currentBatchStatus()) === "paused",
        "paused snapshot applied",
      );
      await waitFor(async () => {
        const current = await state();
        return current.discarded.stale_get_captured === 1;
      }, "old AdminPage batch GET captured");
      await button("繼續批次").click();
      await waitFor(
        async () => (await currentBatchStatus()) === "running",
        "newer running snapshot applied",
      );
      const beforeOldRequestRelease = await currentBatchStatus();
      await button("Start batch status observation").click();
      await button("Release held batch response").click();
      await waitFor(async () => {
        const current = await state();
        return current.discarded.stale_get === 1;
      }, "old AdminPage batch GET released");
      await new Promise((resolve) => setTimeout(resolve, 250));
      const afterOldRequestRelease = await currentBatchStatus();
      await button("Stop batch status observation").click();
      delayedStatusTransitions = await tab.playwright.evaluate(() => {
        return JSON.parse(
          document.querySelector("[data-browser-status-transitions]")
            ?.textContent ?? "[]",
        );
      });
      verify(
        beforeOldRequestRelease === "running" &&
          afterOldRequestRelease === "running" &&
          delayedStatusTransitions.length === 1 &&
          delayedStatusTransitions[0] === "running",
        "late original batch GET did not replace the newer UI snapshot",
      );
    }
    await button("Release retry provider").click();
  } else {
    await button("Release retry provider").click();
    await waitFor(async () => {
      const current = await state();
      return current.items.some(
        (item) =>
          item.repository_slug === "fixture/fails-once" &&
          item.source_item_id === null &&
          item.state === "failed",
      );
    }, "server-side retry completion");
    await reconcileControl.click();
  }
  await waitForText("已處理 3/3；成功 2；進行中 0；失敗 1", "retry exhausted");
  if (reconciliationMode === "completed") {
    observed = await state();
    verify(
      observed.reanalyze_requests.filter((entry) => entry.operation === "retry")
        .length === 1 &&
        observed.batches.find((batch) => batch.source_batch_id === null)
          ?.state === "completed_with_errors",
      "completed reconciliation applied final snapshot without another POST",
    );
  }
  const timingState = await state();
  const timingSourceBatch = timingState.batches.find(
    (batch) => batch.source_batch_id === null,
  );
  const firstTerminalResponse = await captureBatchSnapshot();
  const failedBefore = firstTerminalResponse.body.items.find(
    (item) =>
      item.slug === "fixture/fails-once" && item.source_item_id === null,
  );
  const failedUiBefore = await tab.playwright.evaluate(
    () =>
      Array.from(document.querySelectorAll("li")).find((item) =>
        item.textContent?.includes("fixture/fails-once"),
      )?.textContent,
  );
  await new Promise((resolve) => setTimeout(resolve, 1100));
  const secondTerminalResponse = await captureBatchSnapshot();
  const failedAfter = secondTerminalResponse.body.items.find(
    (item) => item.item_id === failedBefore.item_id,
  );
  const failedUiAfter = await tab.playwright.evaluate(
    () =>
      Array.from(document.querySelectorAll("li")).find((item) =>
        item.textContent?.includes("fixture/fails-once"),
      )?.textContent,
  );
  const expectedFailedTime = (() => {
    const rounded = Math.max(
      0,
      Math.round(failedAfter.execution_elapsed_seconds),
    );
    const minutes = Math.floor(rounded / 60);
    const seconds = rounded % 60;
    return minutes > 0 ? `${minutes} 分 ${seconds} 秒` : `${seconds} 秒`;
  })();
  verify(
    firstTerminalResponse.status === 200 &&
      secondTerminalResponse.status === 200 &&
      firstTerminalResponse.path === secondTerminalResponse.path &&
      firstTerminalResponse.path.endsWith(`/${timingSourceBatch.batch_id}`) &&
      firstTerminalResponse.body.batch_id ===
        secondTerminalResponse.body.batch_id &&
      firstTerminalResponse.body.state === "completed_with_errors" &&
      secondTerminalResponse.body.state === "completed_with_errors" &&
      failedBefore.execution_elapsed_seconds ===
        failedAfter.execution_elapsed_seconds &&
      typeof failedAfter.execution_elapsed_seconds === "number" &&
      firstTerminalResponse.body.completed_at &&
      firstTerminalResponse.body.completed_at ===
        secondTerminalResponse.body.completed_at &&
      failedUiBefore === failedUiAfter &&
      failedUiAfter.includes("有效執行時間") &&
      failedUiAfter.includes(expectedFailedTime),
    "failed item timing matched two fresh production API snapshots",
  );
  const terminalDom = await snapshot();
  const progressText = await tab.playwright.evaluate(
    () =>
      document.querySelector('[aria-labelledby="batch-progress-heading"]')
        ?.textContent,
  );
  verify(
    progressText.includes("目前無法提供預估時間"),
    "terminal ETA stopped in batch progress",
  );
  verify(
    terminalDom.includes("分析已結束；畫面顯示最終結果") &&
      !terminalDom.includes("即時進度已中斷"),
    "terminal stream ended without disconnect state",
  );

  await button("檢視專案中可確認的資訊並填寫貢獻").click();
  await tab.playwright
    .getByRole("textbox", { name: "你的貢獻說明", exact: true })
    .nth(0)
    .fill("DELAY_BROWSER_CONTRIBUTION");
  await button("產生可編輯建議").nth(0).click();
  await button("English").click();
  await button("Release contribution provider").click();
  await waitFor(
    async () => await button("Generate editable suggestion").nth(0).isEnabled(),
    "stale contribution request settled",
  );
  const staleContribution = await snapshot();
  verify(
    !staleContribution.includes("AI suggestion (not confirmed)"),
    "locale change rejected delayed contribution response",
  );
  await button("繁體中文").click();
  await waitFor(
    () =>
      tab.playwright.evaluate(
        () =>
          document
            .querySelector('button[aria-label="繁體中文"]')
            ?.getAttribute("aria-pressed") === "true",
      ),
    "Traditional Chinese locale settled",
  );
  await new Promise((resolve) => setTimeout(resolve, 250));
  const contributionStatement = tab.playwright
    .getByRole("textbox", { name: "你的貢獻說明", exact: true })
    .nth(0);
  const fillContributionStatement = async (value) => {
    await contributionStatement.fill(value);
    await waitFor(
      () =>
        contributionStatement.evaluate(
          (input, expected) => input.value === expected,
          value,
        ),
      "contribution statement settled",
    );
    // Locale changes remount this controlled editor. Let React finish that
    // commit before the test clicks the newly rendered submit button.
    await new Promise((resolve) => setTimeout(resolve, 250));
  };
  await fillContributionStatement("TRUNCATE_BROWSER_CONTRIBUTION");
  await button("產生可編輯建議").nth(0).click();
  await waitForText(
    "模型回覆達到輸出上限",
    "contribution truncation diagnosis",
  );
  const truncationFocus = await tab.playwright.evaluate(
    () => document.activeElement?.getAttribute("role") === "alert",
  );
  verify(truncationFocus, "contribution error received focus");
  verify(
    (await button("手動輸入貢獻").count()) >= 1,
    "manual contribution path remained available after truncation",
  );
  await button("手動輸入貢獻").nth(0).click();
  await button("Use small contribution context").click();
  await fillContributionStatement("CONTEXT_BROWSER_CONTRIBUTION");
  await button("產生可編輯建議").nth(0).click();
  await waitForText(
    "目前模型的內容空間不足",
    "contribution context admission diagnosis",
  );
  await button("Restore contribution context").click();
  await fillContributionStatement("INVALID_BROWSER_CONTRIBUTION");
  await button("產生可編輯建議").nth(0).click();
  await waitForText(
    "模型沒有回傳可安全使用的完整提案",
    "contribution schema diagnosis",
  );
  await fillContributionStatement("我建立 alpha 驗收流程");
  await button("產生可編輯建議").nth(0).click();
  await waitForText("AI 建議（尚未確認）", "contribution suggestion returned");
  await tab.playwright
    .getByRole("textbox", { name: "角色 (繁體中文)", exact: true })
    .fill("維護者");
  await tab.playwright
    .getByRole("textbox", { name: "角色 (English)", exact: true })
    .fill("Maintainer");
  await tab.playwright
    .getByRole("textbox", { name: "摘要 (繁體中文)", exact: true })
    .fill("建立可重跑的恢復驗收");
  await tab.playwright
    .getByRole("textbox", { name: "摘要 (English)", exact: true })
    .fill("Built repeatable recovery acceptance");
  await button("確認這份貢獻").click();
  await waitForText("此專案的貢獻已由你確認", "contribution confirmed");
  await button("產生可編輯建議").nth(0).click();
  await waitFor(
    async () => (await button("還原上一個已確認版本").count()) === 1,
    "previous confirmed contribution recovery",
  );
  await button("還原上一個已確認版本").click();
  await button("確認這份貢獻").click();
  await waitForText(
    "此專案的貢獻已由你確認",
    "restored contribution reconfirmed",
  );
  await button("編輯已確認內容").click();
  await tab.playwright
    .getByRole("textbox", { name: "摘要 (繁體中文)", exact: true })
    .fill("建立可重跑的恢復驗收（已再次編輯）");
  const editedContribution = await snapshot();
  verify(
    !editedContribution.includes("此專案的貢獻已由你確認"),
    "editing a confirmed proposal requires confirmation again",
  );
  await button("確認這份貢獻").click();
  await waitForText(
    "此專案的貢獻已由你確認",
    "edited contribution reconfirmed",
  );
  await button("返回").click();
  await waitForText("使用目前模型重新分析", "returned to failed analysis");

  const beforeCancel = (await state()).reanalyze_requests.filter(
    (entry) => entry.operation === "reanalyze",
  ).length;
  await button("Cancel next model confirmation").click();
  await button("使用目前模型重新分析").click();
  const afterCancel = (await state()).reanalyze_requests.filter(
    (entry) => entry.operation === "reanalyze",
  ).length;
  verify(
    beforeCancel === afterCancel,
    "cancelled model confirmation sent zero requests",
  );
  await button("Accept model confirmation").click();
  await button("Simulate second-tab model selection").click();
  await button("使用目前模型重新分析").click();
  await waitForText(
    "模型選擇已變更；請重新檢查目前模型並再次確認",
    "stale model confirmation rejected",
  );
  observed = await state();
  verify(
    observed.batches.length === 1,
    "stale confirmation created no successor",
  );
  verify(
    observed.contribution_calls === 5 &&
      observed.contribution_requests.every(
        (entry) =>
          entry.max_output_tokens === 700 &&
          entry.schema_closed === true &&
          JSON.stringify(entry.schema_required) ===
            JSON.stringify(["role", "summary", "claims"]),
      ),
    "contribution failures and recovery used the fixed budget and closed schema",
  );
  await button("使用目前模型重新分析").click();
  await waitForText(
    "已處理 1/1；成功 1；進行中 0；失敗 0",
    "current-model successor",
  );

  const callsBeforeSecondKey = JSON.stringify((await state()).provider_calls);
  await button("Submit equivalent second key").click();
  observed = await state();
  verify(
    observed.second_key_result?.created === false,
    "equivalent second key deduplicated",
  );
  verify(
    JSON.stringify(observed.provider_calls) === callsBeforeSecondKey,
    "equivalent second key caused no provider work",
  );
  const sourceBatch = observed.batches.find(
    (batch) => batch.source_batch_id === null,
  );
  const successorBatch = observed.batches.find(
    (batch) => batch.source_batch_id !== null,
  );
  const sourceItem = observed.items.find(
    (item) =>
      item.repository_slug === "fixture/fails-once" &&
      item.source_item_id === null,
  );
  const successorItem = observed.items.find(
    (item) => item.source_item_id === sourceItem.item_id,
  );
  verify(
    observed.batches.length === 2 &&
      successorBatch.source_batch_id === sourceBatch.batch_id &&
      successorBatch.analysis_round === 2,
    "one direct round-two successor persisted",
  );
  verify(
    sourceItem.successor_batch_id === successorBatch.batch_id &&
      successorItem.batch_id === successorBatch.batch_id,
    "source and successor lineage agree",
  );
  verify(
    sourceItem.resolved_commit_sha === successorItem.resolved_commit_sha,
    "successor preserved source commit",
  );
  verify(
    successorBatch.analysis_model_pair.chat.model_id === "browser-chat-b",
    "runtime used confirmed current model pair",
  );
  verify(
    observed.receipts.length === 2 &&
      observed.receipts.every(
        (receipt) => receipt.batch_id === successorBatch.batch_id,
      ),
    "both idempotency receipts bind one successor",
  );
  const validRequests = observed.reanalyze_requests.filter(
    (entry) =>
      entry.operation === "reanalyze" &&
      entry.expected_selection_generation === observed.selection_generation,
  );
  verify(
    validRequests.length === 2 &&
      validRequests[0].idempotency_key_sha256 ===
        validRequests[1].idempotency_key_sha256,
    "discarded reanalysis retried the same idempotency key",
  );
  verify(
    observed.discarded.reanalyze === 1,
    "successful reanalysis response discarded once",
  );
  verify(
    observed.provider_calls["browser-chat-a|fixture/alpha"] === 1 &&
      observed.provider_calls["browser-chat-a|fixture/beta"] === 1 &&
      observed.provider_calls["browser-chat-a|fixture/fails-once"] === 2 &&
      observed.provider_calls["browser-chat-b|fixture/fails-once"] === 1,
    "provider calls match retry and successor policy",
  );

  dom = await snapshot();
  verify(
    dom.includes("fixture/alpha") &&
      dom.includes("fixture/beta") &&
      dom.includes("fixture/fails-once"),
    "all three results remain visible",
  );
  verify(
    dom.includes("src/main.py:1-2") &&
      dom.includes("src/main.py:4-5") &&
      dom.includes("return 'fixture/fails-once'"),
    "recovered exact evidence remains visible",
  );
  const confirmations = await tab.playwright.evaluate(() =>
    JSON.parse(
      document.querySelector("[data-browser-confirm-messages]")?.textContent ||
        "[]",
    ),
  );
  verify(
    confirmations.some(
      (message) =>
        message.includes(sourceItem.resolved_commit_sha) &&
        message.includes(sourceBatch.analysis_model_pair.chat.profile_id),
    ) &&
      confirmations.some((message) =>
        message.includes(successorBatch.analysis_model_pair.chat.profile_id),
      ),
    "nested model confirmation named original commit and model pairs",
  );

  await button("檢視專案中可確認的資訊並填寫貢獻").click();
  const contributions = await snapshot();
  verify(
    contributions.includes("我建立 alpha 驗收流程") &&
      contributions.includes("建立可重跑的恢復驗收") &&
      contributions.includes("此專案的貢獻已由你確認"),
    "confirmed contribution survived recovery",
  );
  await button("返回").click();
  await button("English").press("Enter");
  await waitForText("Batch analysis", "English batch view");
  const english = await snapshot();
  verify(
    english.includes(
      "Validated production analysis path for fixture/fails-once",
    ) && english.includes("src/main.py:1-2"),
    "English evidence view matches recovered result",
  );
  await button("繁體中文").click();
  await button("檢視專案中可確認的資訊並填寫貢獻").click();
  const remainingContributions = [
    ["fixture/beta", 1, "beta"],
    ["fixture/fails-once", 2, "fails-once"],
  ];
  for (const [_slug, index, label] of remainingContributions) {
    await tab.playwright
      .locator(
        'section[aria-labelledby="guided-contributions-heading"] details',
      )
      .nth(index)
      .locator("summary")
      .click();
    await tab.playwright
      .getByRole("textbox", { name: "你的貢獻說明", exact: true })
      .nth(index)
      .fill(`我協助維護 ${label}`);
    await button("手動輸入貢獻").filter({ visible: true }).click();
    await tab.playwright
      .getByRole("textbox", { name: "角色 (繁體中文)", exact: true })
      .nth(index)
      .fill("協作者");
    await tab.playwright
      .getByRole("textbox", { name: "角色 (English)", exact: true })
      .nth(index)
      .fill("Contributor");
    await tab.playwright
      .getByRole("textbox", { name: "摘要 (繁體中文)", exact: true })
      .nth(index)
      .fill(`協助維護 ${label}`);
    await tab.playwright
      .getByRole("textbox", { name: "摘要 (English)", exact: true })
      .nth(index)
      .fill(`Helped maintain ${label}`);
    await button("確認這份貢獻").filter({ visible: true }).click();
  }
  await button("填寫基本資料").click();
  await tab.playwright
    .getByRole("textbox", { name: "顯示名稱", exact: true })
    .fill("Browser Owner");
  const profileFields = [
    ["#guided-profile-headline-zh-TW", "可靠系統維護者"],
    ["#guided-profile-headline-en", "Reliable systems maintainer"],
    ["#guided-profile-bio-zh-TW", "建立可重跑的驗收流程。"],
    ["#guided-profile-bio-en", "Builds repeatable acceptance flows."],
    ["#guided-profile-greeting-zh-TW", "你好，我是 Browser Owner。"],
    ["#guided-profile-greeting-en", "Hello, I am Browser Owner."],
  ];
  for (const [selector, value] of profileFields) {
    await tab.playwright.locator(selector).fill(value);
  }
  await button("確認基本資料並檢閱草稿").click();
  await button("建立完整 YAML 草稿").click();
  await waitForText(
    "草稿已準備好",
    "confirmed contribution entered YAML draft",
  );
  verify(
    (await snapshot()).includes("草稿已準備好"),
    "confirmed contributions reached the YAML draft boundary",
  );

  const browser = await tab.playwright.evaluate(
    () => document.documentElement.dataset.browserUserAgent,
  );
  const terminalSnapshots = [firstTerminalResponse, secondTerminalResponse].map(
    (response) => {
      const item = response.body.items.find(
        (candidate) => candidate.item_id === failedBefore.item_id,
      );
      return {
        path: response.path,
        status: response.status,
        batch_id: response.body.batch_id,
        state: response.body.state,
        completed_at: response.body.completed_at,
        item_id: item.item_id,
        item_state: item.state,
        execution_elapsed_seconds: item.execution_elapsed_seconds,
      };
    },
  );
  return {
    checks,
    browser,
    mode: reconciliationMode,
    delayedOriginalRequest: releaseStaleSnapshot,
    delayedStatusTransitions,
    terminalSnapshots,
    observations: observed,
  };
}
