// Run with playwright-cli run-code --filename tests/browser/check-admin-ux.js.
// Requires the disposable A5 host, logged in at the manual Profile step.
async (page) => {
  const checks = [];
  const verify = (condition, message) => {
    if (!condition) throw new Error(message);
    checks.push(message);
  };
  const button = (name) => page.getByRole("button", { name, exact: true });
  const marker = "UX locale regression draft";
  await page
    .getByRole("textbox", { name: "顯示名稱", exact: true })
    .fill(marker);
  let draftReads = 0;
  const observe = (request) => {
    if (
      request.url().endsWith("/api/admin/portfolio") &&
      request.method() === "GET"
    )
      draftReads++;
  };
  page.on("request", observe);
  try {
    await button("English").click();
    await page
      .getByRole("textbox", { name: "Display name", exact: true })
      .waitFor();
    await page.waitForLoadState("networkidle");
    verify(
      (await page
        .getByRole("textbox", { name: "Display name", exact: true })
        .inputValue()) === marker,
      "English retains the unconfirmed profile",
    );
    await button("繁體中文").click();
    await page
      .getByRole("textbox", { name: "顯示名稱", exact: true })
      .waitFor();
    await page.waitForLoadState("networkidle");
    verify(
      (await page
        .getByRole("textbox", { name: "顯示名稱", exact: true })
        .inputValue()) === marker,
      "Chinese retains the unconfirmed profile",
    );
    verify(
      draftReads === 0,
      "Changing language does not reload the saved draft",
    );
  } finally {
    page.off("request", observe);
  }

  const focusAt = async (id) => {
    await page.waitForFunction(
      (target) => document.activeElement?.id === target,
      id,
    );
    const top = await page
      .locator(`#${id}`)
      .evaluate((node) => node.getBoundingClientRect().top);
    verify(
      top >= 0 && top < page.viewportSize().height,
      `${id} is focused and visible`,
    );
  };
  const keyboardActivate = async (locator) => {
    await locator.focus();
    await page.keyboard.press("Enter");
  };
  const measurements = [];
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 375, height: 844 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    for (const locale of ["zh-TW", "en"]) {
      const zh = locale === "zh-TW";
      await button(zh ? "繁體中文" : "English").click();
      await button(zh ? "預覽與分享" : "Preview & share").click();
      await focusAt("local-publication-heading");
      const prepare = button(
        zh ? "檢查專案並更新 NPC" : "Check projects and update NPC",
      );
      verify(
        await prepare.isDisabled(),
        "Preparation still requires tested models",
      );
      const reason = await prepare.getAttribute("aria-describedby");
      verify(
        reason && (await page.locator(`#${reason}`).innerText()).length > 0,
        "Disabled preparation has an accessible reason",
      );
      const share = await page
        .locator(".local-publication")
        .evaluate((node) => ({
          headings: [...node.querySelectorAll("h2")]
            .slice(0, 4)
            .map((heading) => heading.id),
          optionalClosed: [
            ...node.querySelectorAll(".publication-optional"),
          ].every((item) => !item.open),
        }));
      verify(
        share.headings.join(",") ===
          "local-publication-heading,visitor-gateway-heading,pages-share-panel-heading,github-share-guide-heading",
        "Sharing follows prepare, connect, upload/verify, card order",
      );
      verify(
        share.optionalClosed,
        "Appearance and FAQ are collapsed optional steps",
      );
      await keyboardActivate(button(zh ? "前往設定模型" : "Set up models"));
      await focusAt("guided-onboarding-heading");
      const modelLayout = await page.evaluate(() => {
        const add = document.querySelector(
          ".model-panel--connection .model-editor > summary",
        );
        const rect = add.getBoundingClientRect();
        const progress = document.querySelector(
          '.onboarding-stepper [role="progressbar"]',
        );
        return {
          addTop: rect.top,
          addBottom: rect.bottom,
          overflow: document.documentElement.scrollWidth > innerWidth,
          statusClosed: !document.querySelector(".admin-status-overview").open,
          progress: {
            value: Number(progress.getAttribute("aria-valuenow")),
            max: Number(progress.getAttribute("aria-valuemax")),
          },
        };
      });
      verify(
        modelLayout.addTop >= 0 && modelLayout.addBottom <= size.height,
        `${locale} ${size.width}: Add service is in the first viewport`,
      );
      verify(
        !modelLayout.overflow && modelLayout.statusClosed,
        `${locale} ${size.width}: no horizontal overflow, status collapsed`,
      );
      verify(
        modelLayout.progress.value === 0 && modelLayout.progress.max === 6,
        "First AI step consistently has zero completed steps",
      );
      await page.screenshot({
        path: `output/playwright/ux-fix-20261011/models-${locale}-${size.width}.png`,
      });
      if (size.width === 1440) {
        const confirm = await button(
          zh ? "確認用於分析" : "Use for analysis",
        ).boundingBox();
        verify(
          confirm &&
            confirm.y >= 0 &&
            confirm.y + confirm.height <= size.height,
          `${locale}: model confirmation stays in the first viewport`,
        );
      }
      const editor = page
        .locator(".model-panel--connection .model-editor")
        .first();
      await keyboardActivate(editor.locator("summary"));
      await editor.locator("form").waitFor({ state: "visible" });
      await keyboardActivate(
        editor.getByRole("button", {
          name: zh ? "取消" : "Cancel",
          exact: true,
        }),
      );
      verify(
        await editor.evaluate(
          (node) =>
            !node.open &&
            document.activeElement === node.querySelector("summary"),
        ),
        "Service editor opens by keyboard and cancel returns focus",
      );
      const returnName =
        size.width >= 1024
          ? zh
            ? "返回準備 NPC"
            : "Return to prepare NPC"
          : zh
            ? "返回"
            : "Back";
      await keyboardActivate(button(returnName));
      await focusAt("local-publication-heading");
      const prepareBox = await prepare.boundingBox();
      verify(
        prepareBox.y >= 0 && prepareBox.y + prepareBox.height <= size.height,
        `${locale} ${size.width}: Return brings preparation into view`,
      );
      await page.screenshot({
        path: `output/playwright/ux-fix-20261011/publish-${locale}-${size.width}.png`,
      });
      await button(zh ? "引導設定" : "Guided setup").click();
      verify(
        (await page
          .getByRole("textbox", {
            name: zh ? "顯示名稱" : "Display name",
            exact: true,
          })
          .inputValue()) === marker,
        `${locale} ${size.width}: model detour preserves the unconfirmed profile`,
      );
      const progress = page.getByRole("progressbar");
      verify(
        (await progress.getAttribute("aria-valuenow")) === "2" &&
          (await progress.getAttribute("aria-valuemax")) === "4",
        "Returning restores manual progress and completed contributions",
      );
      measurements.push({
        locale,
        ...size,
        ...modelLayout,
        prepareTop: prepareBox.y,
      });
    }
  }
  for (let step = 0; step < 3; step++) await button("Back").click();
  const firstEntry = [];
  for (const locale of ["zh-TW", "en"]) {
    const zh = locale === "zh-TW";
    await button(zh ? "繁體中文" : "English").click();
    await button(zh ? "設定 AI 並開始" : "Set up AI and begin").click();
    await focusAt("guided-onboarding-heading");
    const add = await page
      .locator(".model-panel--connection .model-editor > summary")
      .first()
      .boundingBox();
    verify(
      add.y >= 0 && add.y + add.height <= 844,
      `${locale}: first AI entry shows Add service`,
    );
    firstEntry.push({ locale, addTop: add.y, addBottom: add.y + add.height });
    await page.screenshot({
      path: `output/playwright/ux-fix-20261011/first-models-${locale}-390.png`,
    });
    await button(zh ? "返回" : "Back").click();
  }
  await button("Set up AI and begin").click();
  await page.reload();
  await page.waitForLoadState("networkidle");
  await focusAt("guided-onboarding-heading");
  const resumedAdd = await page
    .locator(".model-panel--connection .model-editor > summary")
    .first()
    .boundingBox();
  verify(
    resumedAdd.y >= 0 && resumedAdd.y + resumedAdd.height <= 844,
    "Reloading model setup keeps Add service in view",
  );
  return { checks, measurements, firstEntry, draftReads };
};
