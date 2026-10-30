// Production AdminPage + FastAPI recovery acceptance. Test-only controls expose
// secret-free server observations; every product action still travels through
// the rendered UI and production API routes.
// ADR-060: docs/DECISIONS.md:610-612; docs/TECHNICAL_SPEC.md:946,954.
export function evidencePresentationFailures({ text, rows, hrefs }, expected) {
  const failures = [];
  // GuidedOnboardingView.tsx:783-790,854-859,934-936: matched facts and labels.
  const location = (fact) =>
    fact.start_line === null
      ? fact.path
      : `${fact.path}:${fact.start_line}${
          fact.end_line && fact.end_line !== fact.start_line
            ? `-${fact.end_line}`
            : ""
        }`;
  for (const { slug, commit, cited, uncited } of expected) {
    if (cited.length < 1) failures.push(`cited facts empty: ${slug}`);
    if (uncited.length < 1) failures.push(`uncited facts empty: ${slug}`);
    if (
      cited.some(
        (fact) =>
          !fact.url.startsWith(`https://github.com/${slug}/blob/${commit}/`),
      )
    ) {
      failures.push(`cited fact URL is not pinned: ${slug}`);
    }
    const links = hrefs.filter((link) => link.source && link.slug === slug);
    const urls = new Set(links.map((link) => link.href));
    const citedUrls = new Set(cited.map((fact) => fact.url));
    if (
      urls.size !== citedUrls.size ||
      [...citedUrls].some((url) => !urls.has(url))
    ) {
      failures.push(`source URL set mismatch: ${slug}`);
    }
    if (
      links.some((link) => {
        const fact = cited.find((fact) => fact.url === link.href);
        return fact && (!link.visible || link.label !== location(fact));
      })
    ) {
      failures.push(`cited source label or visibility mismatch: ${slug}`);
    }
    if (
      uncited.some(
        (fact) =>
          text.includes(fact.url) ||
          hrefs.some((link) => link.href === fact.url) ||
          // GuidedOnboardingView.tsx:934-936,969: labels belong to one repository.
          rows.some(
            (row) => row.slug === slug && row.text.includes(location(fact)),
          ),
      )
    ) {
      failures.push(`uncited fact rendered: ${slug}`);
    }
  }
  if (
    [
      "return 'fixture/alpha'",
      "return 'fixture/beta'",
      "return 'fixture/fails-once'",
      "production runner and validator",
    ].some((excerpt) => text.includes(excerpt))
  ) {
    failures.push("excerpt rendered");
  }
  const labels = [
    text,
    ...hrefs.filter((link) => link.visible).map((link) => link.text),
  ].join(" ");
  if (/E_[0-9a-f]+/i.test(labels))
    failures.push("persistent evidence ID rendered");
  if (/\bS\d+\b/.test(labels)) failures.push("request evidence ID rendered");
  return failures;
}

export async function checkAnalysisRecovery(tab, options = {}) {
  const reconciliationMode = options.reconciliationMode ?? "running";
  const releaseStaleSnapshot = options.releaseStaleSnapshot === true;
  const checks = [];
  let delayedStatusTransitions = [];
  const verify = (condition, name) => {
    if (!condition) {
      const error = new Error(name);
      error.checks = [...checks];
      throw error;
    }
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
  const diagnostics = tab.playwright.locator("details.p4-w1-diagnostics");
  // The batch panel remounts (for example after 返回) with diagnostics closed again.
  const openDiagnostics = async () => {
    if (
      (await diagnostics.count()) === 1 &&
      !(await diagnostics.evaluate((node) => node.open))
    ) {
      await diagnostics.locator(":scope > summary").click();
    }
  };
  await openDiagnostics();
  const evidencePresentation = async () => {
    const highlights = tab.playwright.locator(
      '.guided-analysis__toggle[aria-expanded="false"]',
    );
    while ((await highlights.count()) > 0) {
      await highlights.nth(0).click();
    }
    return tab.playwright.evaluate(() => {
      const content = document.body.cloneNode(true);
      // Test observations contain API evidence IDs; inspect only product text.
      content
        .querySelector('[aria-label="Browser acceptance controls"]')
        ?.remove();
      return {
        text: content.textContent.replace(/\s+/g, " ").trim(),
        rows: Array.from(
          content.querySelectorAll("[data-analysis-result]"),
          (row) => ({
            slug: row.dataset.analysisResult,
            text: row.textContent.replace(/\s+/g, " ").trim(),
          }),
        ),
        hrefs: Array.from(document.querySelectorAll("a[href]"), (link) => {
          // GuidedOnboardingView.tsx:854-859: exclude decoration/announcements.
          const label = link.cloneNode(true);
          label
            .querySelectorAll('[aria-hidden="true"], .visually-hidden')
            .forEach((node) => node.remove());
          return {
            slug: link.closest("[data-analysis-result]")?.dataset
              .analysisResult,
            source: Boolean(link.closest(".guided-analysis__body")),
            href: link.getAttribute("href"),
            text: link.textContent,
            label: label.textContent.trim(),
            visible: link.getClientRects().length > 0,
          };
        }),
      };
    });
  };
  // docs/TECHNICAL_SPEC.md:945-947; GuidedOnboardingView.tsx:934-936.
  const sourceExpectations = (items, payloads) => {
    const analyses = [];
    const inspect = (value) => {
      if (!value || typeof value !== "object") return;
      if (Array.isArray(value.facts)) analyses.push(value);
      Object.values(value).forEach(inspect);
    };
    payloads.forEach(inspect);
    return items.map((item) => {
      const analysis = analyses.find(
        (value) => value.repository.slug === item.repository_slug,
      );
      const citedIds = new Set(
        analysis?.inferences.flatMap(
          (inference) => inference.supporting_evidence_ids,
        ) ?? [],
      );
      const facts = analysis?.facts ?? [];
      return {
        slug: item.repository_slug,
        commit: item.resolved_commit_sha,
        cited: facts.filter((fact) => citedIds.has(fact.evidence_id)),
        uncited: facts.filter((fact) => !citedIds.has(fact.evidence_id)),
      };
    });
  };
  const initialPayload = await captureBatchSnapshot();
  const initialSources = sourceExpectations(
    (await state()).items.filter(
      (item) => item.repository_slug !== "fixture/fails-once",
    ),
    [initialPayload.body],
  );
  const initialEvidence = evidencePresentationFailures(
    await evidencePresentation(),
    initialSources,
  );
  let dom = await snapshot();
  // docs/TECHNICAL_SPEC.md:946,954; GuidedOnboardingView.tsx:854-855,934-936.
  verify(
    initialSources.length === 2 &&
      !initialEvidence.some(
        (failure) =>
          ![
            "excerpt rendered",
            "persistent evidence ID rendered",
            "request evidence ID rendered",
          ].includes(failure),
      ),
    "cited source permalinks match frozen commits and uncited sources stay absent",
  );
  // docs/DECISIONS.md:610; docs/TECHNICAL_SPEC.md:954.
  verify(
    !initialEvidence.includes("excerpt rendered"),
    "source excerpts stay absent from all product DOM text",
  );
  // docs/TECHNICAL_SPEC.md:954.
  verify(
    !initialEvidence.includes("persistent evidence ID rendered") &&
      !initialEvidence.includes("request evidence ID rendered"),
    "technical evidence IDs stay absent from product text and source labels",
  );
  // docs/DECISIONS.md:610; docs/TECHNICAL_SPEC.md:946.
  verify(
    initialPayload.status === 200 &&
      !/"excerpt"\s*:/.test(JSON.stringify(initialPayload.body)),
    "production analysis payload omits excerpt keys per ADR-060",
  );

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

  // GuidedOnboardingView.tsx:318; docs/TECHNICAL_SPEC.md:954.
  await button("描述我的貢獻").click();
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
    "達到上限，因此未採用不完整提案",
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
  // GuidedOnboardingView.tsx:1485-1507: restore lives in the closed "其他操作" details.
  const alphaEditor = tab.playwright.locator(
    'article[data-slug="fixture/alpha"]',
  );
  const restorePrevious = alphaEditor.getByRole("button", {
    name: "還原上一個已確認版本",
    exact: true,
  });
  await waitFor(async () => {
    const actions = alphaEditor.locator("details.p4-w2__info");
    if (
      (await actions.count()) === 1 &&
      !(await actions.evaluate((node) => node.open))
    ) {
      await actions.locator(":scope > summary").click();
    }
    return (await restorePrevious.count()) === 1;
  }, "previous confirmed contribution recovery");
  await restorePrevious.click();
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
  await waitFor(async () => {
    await openDiagnostics();
    return (await button("使用目前模型重新分析").count()) === 1;
  }, "returned to failed analysis");

  // AdminPage asks through the react-aria ConfirmDialog (ConfirmDialog.tsx),
  // so the dialog text is the confirmation message and its buttons the answer.
  const confirmations = [];
  const answerModelConfirmation = async (answer) => {
    const dialog = tab.playwright.getByRole("alertdialog");
    await waitFor(
      async () => (await dialog.count()) === 1,
      "model confirmation",
    );
    confirmations.push(
      await dialog
        .locator(".admin-confirm-dialog__description")
        .evaluate((node) => node.textContent),
    );
    await dialog.getByRole("button", { name: answer, exact: true }).click();
    await waitFor(
      async () => (await dialog.count()) === 0,
      "model confirmation closed",
    );
  };
  const beforeCancel = (await state()).reanalyze_requests.filter(
    (entry) => entry.operation === "reanalyze",
  ).length;
  await button("使用目前模型重新分析").click();
  await answerModelConfirmation("取消");
  const afterCancel = (await state()).reanalyze_requests.filter(
    (entry) => entry.operation === "reanalyze",
  ).length;
  verify(
    beforeCancel === afterCancel,
    "cancelled model confirmation sent zero requests",
  );
  await button("Simulate second-tab model selection").click();
  await button("使用目前模型重新分析").click();
  await answerModelConfirmation("重新分析");
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
          entry.max_output_tokens === 16384 &&
          entry.schema_closed === true &&
          JSON.stringify(entry.schema_required) ===
            JSON.stringify(["role", "summary", "claims"]),
      ),
    "contribution failures and recovery carried the full 16,384 allowance (the fixture declares a 32,768 context and 16,384 max output), and the closed schema",
  );
  await button("使用目前模型重新分析").click();
  await answerModelConfirmation("重新分析");
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
  const recoveredPayloads = await tab.playwright.evaluate(
    async (batchIds) =>
      Promise.all(
        batchIds.map(async (id) => {
          const response = await fetch(
            `/api/admin/onboarding/analysis-batches/${encodeURIComponent(id)}`,
          );
          return { status: response.status, body: await response.json() };
        }),
      ),
    observed.batches.map((batch) => batch.batch_id),
  );
  const recoveredSources = sourceExpectations(
    observed.items.filter((item) => item.source_item_id === null),
    recoveredPayloads.map((payload) => payload.body),
  );
  // docs/TECHNICAL_SPEC.md:946,954; GuidedOnboardingView.tsx:854-855,934-936.
  verify(
    recoveredSources.length === 3 &&
      recoveredPayloads.every(
        (payload) =>
          payload.status === 200 &&
          !/"excerpt"\s*:/.test(JSON.stringify(payload.body)),
      ) &&
      evidencePresentationFailures(
        await evidencePresentation(),
        recoveredSources,
      ).length === 0,
    "recovered cited permalinks remain pinned without uncited sources, excerpts or IDs",
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

  await button("描述我的貢獻").click();
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
  const englishEvidence = evidencePresentationFailures(
    await evidencePresentation(),
    recoveredSources,
  );
  const english = await snapshot();
  // docs/TECHNICAL_SPEC.md:954; GuidedOnboardingView.tsx:854-855,934-936.
  verify(
    english.includes(
      "Validated production analysis path for fixture/fails-once",
    ) && englishEvidence.length === 0,
    "English recovered view keeps cited permalinks pinned without uncited sources, excerpts or IDs",
  );
  await button("繁體中文").click();
  await button("描述我的貢獻").click();
  const remainingContributions = [
    ["fixture/beta", "beta"],
    ["fixture/fails-once", "fails-once"],
  ];
  // GuidedOnboardingView.tsx:1201-1218,2163-2164,2207-2233: closed editors and help details invalidate global indexes.
  for (const [slug, label] of remainingContributions) {
    const editor = tab.playwright.locator(`article[data-slug="${slug}"]`);
    await tab.playwright
      .locator(`details:has(> article[data-slug="${slug}"]) > summary`)
      .click();
    await editor
      .getByRole("textbox", { name: "你的貢獻說明", exact: true })
      .fill(`我協助維護 ${label}`);
    await editor
      .getByRole("button", { name: "手動輸入貢獻", exact: true })
      .filter({ visible: true })
      .click();
    await editor
      .getByRole("textbox", { name: "角色 (繁體中文)", exact: true })
      .fill("協作者");
    await editor
      .getByRole("textbox", { name: "角色 (English)", exact: true })
      .fill("Contributor");
    await editor
      .getByRole("textbox", { name: "摘要 (繁體中文)", exact: true })
      .fill(`協助維護 ${label}`);
    await editor
      .getByRole("textbox", { name: "摘要 (English)", exact: true })
      .fill(`Helped maintain ${label}`);
    await editor
      .getByRole("button", { name: "確認這份貢獻", exact: true })
      .filter({ visible: true })
      .click();
  }
  await button("填寫基本資料").click();
  // GuidedOnboardingView.tsx:2333-2358: the empty field's label includes required text.
  await tab.playwright
    .locator("#guided-profile-display-name")
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
  // GuidedOnboardingView.tsx:396,2664-2667: current label still creates the draft.
  await button("完成內容").click();
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
    sourceExpectations: {
      initial: initialSources,
      recovered: recoveredSources,
    },
    observations: observed,
  };
}
