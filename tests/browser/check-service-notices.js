// Run against a fresh admin-events-review fixture. No live network is used.
import { setTimeout as delay } from "node:timers/promises";

export async function checkServiceNotices(tab) {
  const results = [];
  const verify = (value, label) => {
    if (!value) throw new Error(label);
    results.push(label);
  };
  const button = (name) =>
    tab.playwright.getByRole("button", { name, exact: true });
  const mode = tab.playwright.getByRole("combobox", {
    name: "Save result",
    exact: true,
  });
  const toast = tab.playwright.locator(".admin-success-toast");
  await button("進階：編輯原始 YAML").click();
  await button("編輯 Synthetic Ollama").click();
  await mode.selectOption("failure");
  await button("更新服務").click();
  const failed = await tab.playwright.evaluate(() => ({
    open: !!document.querySelector(".model-editor[open]"),
    error: document.querySelector(".model-connection-form [role=alert]")
      ?.textContent,
    success: !!document.querySelector(".admin-success-toast"),
  }));
  verify(
    failed.open && !!failed.error && !failed.success,
    "failed save keeps form and inline error without success",
  );
  await mode.selectOption("success");
  await button("更新服務").click();
  verify((await toast.count()) === 1, "confirmed save announces success");
  verify(
    (await tab.playwright.locator(".model-editor[open]").count()) === 0,
    "successful save closes the submitted editor",
  );
  await delay(1000);
  await button("編輯 Synthetic Ollama").click();
  await button("更新服務").click();
  await delay(4200);
  verify(
    (await toast.count()) === 1,
    "repeat save survives the previous notice deadline",
  );
  await delay(1100);
  verify((await toast.count()) === 0, "notice disappears after five seconds");
  await button("English").click();
  await mode.selectOption("refresh-failure");
  await button("Edit Synthetic Ollama").click();
  await button("Update service").click();
  const saved = await tab.playwright.evaluate(() => ({
    statuses: [...document.querySelectorAll("[role=status]")].map(
      (node) => node.textContent,
    ),
    errors: document.querySelectorAll("[role=alert]").length,
    overflow: document.documentElement.scrollWidth > innerWidth,
  }));
  verify(
    saved.statuses.some((text) => text.includes("Service updated")),
    "English save success is visible",
  );
  verify(
    saved.statuses.some((text) =>
      text.includes("service list could not refresh"),
    ) && saved.errors === 0,
    "refresh failure does not misreport a successful write",
  );
  verify(!saved.overflow, "notice does not overflow the narrow viewport");
  return results;
}
