import { chromium } from "file:///C:/Users/xu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs";

const baseURL = "http://127.0.0.1:8765";
const artifactDir = "D:/RepoNPC/.agent-foreman/phase3-grounded-visitor/artifacts";
fs.mkdirSync(artifactDir, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
const consoleErrors = [];
const failedResponses = [];
page.on("console", (message) => {
  if (message.type() === "error") {
    consoleErrors.push({ text: message.text(), location: message.location() });
  }
});
page.on("pageerror", (error) => consoleErrors.push(error.message));
page.on("response", (response) => {
  if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() });
});

const report = { checks: {}, consoleErrors, failedResponses };
try {
  await page.goto(baseURL, { waitUntil: "networkidle" });
  report.checks.desktop = {
    title: await page.title(),
    lang: await page.locator("html").getAttribute("lang"),
    h1: await page.locator("h1").innerText(),
    projects: await page.locator(".project-grid > li").count(),
    status: await page.locator("[role=status]").allTextContents(),
    textareaLabel: await page.locator("label[for=portfolio-question]").innerText(),
  };
  const suggested = page.locator(".suggestion-list button").first();
  await suggested.click();
  const textarea = page.locator("textarea");
  const suggestedValue = await textarea.inputValue();
  await textarea.fill(suggestedValue + " ");
  await page.locator("button[type=submit]").click();
  await page.waitForSelector('.citations a[target="_blank"]', { timeout: 5000 });
  const citation = page.locator('.citations a[target="_blank"]').last();
  report.checks.chat = {
    answerVisible: await page.getByText(/evidence|證據/i).count(),
    citationHref: await citation.getAttribute("href"),
    citationRel: await citation.getAttribute("rel"),
    characterState: await page.locator("[data-character-state]").getAttribute("data-character-state"),
  };
  const conversationBefore = await page.locator(".turn").count();
  await page.getByRole("button", { name: "English" }).click();
  await page.waitForFunction(() => document.documentElement.lang === "en");
  report.checks.locale = {
    lang: await page.locator("html").getAttribute("lang"),
    conversationBefore,
    conversationAfter: await page.locator(".turn").count(),
    h1: await page.locator("h1").innerText(),
  };
  await page.setViewportSize({ width: 390, height: 844 });
  report.checks.mobile = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload({ waitUntil: "networkidle" });
  report.checks.reducedMotion = {
    value: await page.locator("[data-reduced-motion]").getAttribute("data-reduced-motion"),
  };
  report.checks.accessibility = await page.evaluate(() => ({
    unnamedButtons: [...document.querySelectorAll("button")].filter(
      (element) => !(element.textContent || element.getAttribute("aria-label") || "").trim(),
    ).length,
    unnamedLinks: [...document.querySelectorAll("a")].filter(
      (element) => !(element.textContent || element.getAttribute("aria-label") || "").trim(),
    ).length,
    headings: [...document.querySelectorAll("h1,h2,h3")].map((element) => element.textContent?.trim()),
    liveRegions: document.querySelectorAll('[aria-live], [role="status"]').length,
  }));
  await page.screenshot({ path: `${artifactDir}/browser-mobile.png`, fullPage: true });
} finally {
  fs.writeFileSync(`${artifactDir}/browser-probe.json`, JSON.stringify(report, null, 2));
  await browser.close();
}

if (
  report.consoleErrors.length ||
  report.failedResponses.length ||
  report.checks.desktop.projects < 1 ||
  !report.checks.desktop.textareaLabel ||
  report.checks.chat.citationRel !== "noopener noreferrer" ||
  report.checks.locale.conversationAfter !== report.checks.locale.conversationBefore ||
  report.checks.mobile.scrollWidth > report.checks.mobile.clientWidth ||
  report.checks.reducedMotion.value !== "true" ||
  report.checks.accessibility.unnamedButtons ||
  report.checks.accessibility.unnamedLinks
) {
  console.error(JSON.stringify(report, null, 2));
  process.exit(1);
}
console.log(JSON.stringify(report, null, 2));
