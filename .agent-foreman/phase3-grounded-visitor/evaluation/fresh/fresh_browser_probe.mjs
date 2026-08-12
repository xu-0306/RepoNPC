import { chromium } from "file:///C:/Users/xu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";
import fs from "node:fs";

const baseURL = "http://127.0.0.1:8876";
const artifactDir = "D:/RepoNPC/.agent-foreman/phase3-grounded-visitor/artifacts";
const jsonPath = `${artifactDir}/fresh-browser-probe.json`;
const screenshotPath = `${artifactDir}/fresh-browser-mobile.png`;
const consoleErrors = [];
const failedResponses = [];
const report = {
  schema_version: 1,
  command: "rtk proxy node .agent-foreman/phase3-grounded-visitor/evaluation/fresh/fresh_browser_probe.mjs",
  browser: {},
  probes: [],
  passed: false,
};

function add(id, setup, fault, trigger, oracle, antiOracle, observed, passed) {
  report.probes.push({
    id,
    setup,
    fault_injection: fault,
    production_trigger: trigger,
    oracle,
    anti_oracle: antiOracle,
    observed,
    passed,
  });
}

fs.mkdirSync(artifactDir, { recursive: true });
let browser;
try {
  browser = await chromium.launch({ headless: true, channel: "msedge" });
  report.browser = {
    requestedChannel: "msedge",
    version: browser.version(),
  };
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() });
  });

  await page.goto(baseURL, { waitUntil: "networkidle" });
  const middlewareHeaders = await page.evaluate(async () => {
    const response = await fetch("/api/public/status", {
      headers: { "X-Request-ID": "33333333-3333-4333-8333-333333333333" },
    });
    return {
      status: response.status,
      requestId: response.headers.get("x-request-id"),
      cacheControl: response.headers.get("cache-control"),
      contentSecurityPolicy: response.headers.get("content-security-policy"),
      contentTypeOptions: response.headers.get("x-content-type-options"),
    };
  });
  add(
    "edge_pure_asgi_headers",
    "Production FastAPI pure-ASGI boundary reached from same-origin Microsoft Edge",
    "Explicit valid request ID on public status fetch",
    "Browser fetch /api/public/status through production middleware",
    "200 plus correlated X-Request-ID, no-store, restrictive CSP, and nosniff",
    "Missing/corrupted headers or request-ID correlation",
    middlewareHeaders,
    middlewareHeaders.status === 200 &&
      middlewareHeaders.requestId === "33333333-3333-4333-8333-333333333333" &&
      middlewareHeaders.cacheControl === "no-store" &&
      middlewareHeaders.contentSecurityPolicy?.includes("default-src 'none'") &&
      middlewareHeaders.contentTypeOptions === "nosniff",
  );
  const desktop = await page.evaluate(() => ({
    htmlLang: document.documentElement.lang,
    mainLang: document.querySelector("main")?.getAttribute("lang"),
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    projects: document.querySelectorAll(".project-grid > li").length,
    unnamedButtons: [...document.querySelectorAll("button")].filter(
      (node) => !(node.textContent || node.getAttribute("aria-label") || "").trim(),
    ).length,
    unnamedLinks: [...document.querySelectorAll("a")].filter(
      (node) => !(node.textContent || node.getAttribute("aria-label") || "").trim(),
    ).length,
  }));
  add(
    "edge_desktop_semantics_layout",
    "Production Vite build served same-origin by production FastAPI on Edge desktop 1440x900",
    "Normal ready profile",
    "Navigate / and wait for network idle",
    "zh-TW html/main lang, project visible, named controls, no horizontal overflow or console/network errors",
    "Wrong lang, missing profile, unnamed control, overflow, console error, or failed response",
    { ...desktop, consoleErrors: [...consoleErrors], failedResponses: [...failedResponses] },
    desktop.htmlLang === "zh-TW" && desktop.mainLang === "zh-TW" && desktop.projects === 1 &&
      desktop.unnamedButtons === 0 && desktop.unnamedLinks === 0 &&
      desktop.scrollWidth <= desktop.clientWidth && !consoleErrors.length && !failedResponses.length,
  );

  const suggestion = page.locator(".suggestion-list button").first();
  await suggestion.click();
  const textarea = page.locator("textarea");
  const initial = await textarea.inputValue();
  await textarea.fill(`${initial} fresh-edit`);
  await page.locator("button[type=submit]").click();
  await page.waitForSelector('.citations a[target="_blank"]', { timeout: 5000 });
  const citation = page.locator('.citations a[target="_blank"]').last();
  const chat = {
    turns: await page.locator(".turn").count(),
    href: await citation.getAttribute("href"),
    rel: await citation.getAttribute("rel"),
    target: await citation.getAttribute("target"),
    characterState: await page.locator("[data-character-state]").getAttribute("data-character-state"),
  };
  add(
    "edge_chat_citation_character",
    "Ready Edge visitor with edited suggested question",
    "Submit through production fetch/SSE parser",
    "Suggestion button -> textarea edit -> form submit -> SSE -> citation DOM",
    "Two turns, immutable GitHub SHA href, noopener noreferrer, target blank, character success",
    "Lost turn, mutable/unsafe link, or character not success",
    chat,
    chat.turns === 2 && chat.href === "https://github.com/owner/repo/blob/" + "b".repeat(40) + "/src/search.py#L10-L12" &&
      chat.rel === "noopener noreferrer" && chat.target === "_blank" && chat.characterState === "success",
  );

  const before = await page.locator(".turn > p:first-child").allTextContents();
  const citationBefore = await citation.getAttribute("href");
  await page.getByRole("button", { name: "English" }).click();
  await page.waitForFunction(() => document.documentElement.lang === "en");
  await page.waitForSelector("text=Verifiable engineering portfolio");
  const locale = {
    htmlLang: await page.locator("html").getAttribute("lang"),
    mainLang: await page.locator("main").getAttribute("lang"),
    before,
    after: await page.locator(".turn > p:first-child").allTextContents(),
    citationBefore,
    citationAfter: await page.locator('.citations a[target="_blank"]').last().getAttribute("href"),
    headline: await page.getByText("Verifiable engineering portfolio").count(),
  };
  add(
    "edge_locale_history",
    "Completed zh-TW conversation on Edge",
    "Switch locale to English",
    "English locale button and profile refetch",
    "html/main become en, English profile visible, conversation byte-for-byte preserved",
    "Conversation cleared/translated or stale document language/profile",
    locale,
    locale.htmlLang === "en" && locale.mainLang === "en" && locale.headline === 1 &&
      JSON.stringify(locale.before) === JSON.stringify(locale.after) &&
      locale.citationBefore === locale.citationAfter,
  );

  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.getBoundingClientRect().width,
  }));
  await page.screenshot({ path: screenshotPath, fullPage: true });
  add(
    "edge_mobile_overflow",
    "Same production visitor on Edge 390x844",
    "Narrow mobile viewport after populated conversation",
    "Resize live Edge page and inspect document geometry",
    "scrollWidth <= clientWidth with populated profile/chat/citation",
    "Any horizontal overflow",
    mobile,
    mobile.scrollWidth <= mobile.clientWidth,
  );

  const reducedContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const reducedPage = await reducedContext.newPage();
  const reducedErrors = [];
  reducedPage.on("console", (message) => {
    if (message.type() === "error") reducedErrors.push(message.text());
  });
  await reducedPage.goto(baseURL, { waitUntil: "networkidle" });
  const reduced = {
    flag: await reducedPage.locator("[data-reduced-motion]").getAttribute("data-reduced-motion"),
    frameStart: await reducedPage.locator(".character-renderer__sheet").evaluate(
      (node) => getComputedStyle(node).getPropertyValue("--character-frame-start-x").trim(),
    ),
    errors: reducedErrors,
  };
  add(
    "edge_reduced_motion",
    "Fresh Edge context with prefers-reduced-motion: reduce",
    "Reduced-motion media preference before navigation",
    "Production matchMedia -> CharacterRenderer",
    "Renderer marks reduced motion and pins first frame without console errors",
    "Animation-enabled flag, nonzero start frame, or console error",
    reduced,
    reduced.flag === "true" && reduced.frameStart === "0px" && !reduced.errors.length,
  );
  await reducedContext.close();
  await context.close();
} catch (error) {
  report.runner_error = { name: error?.name, message: String(error?.message || error) };
} finally {
  if (browser) await browser.close();
  report.consoleErrors = consoleErrors;
  report.failedResponses = failedResponses;
  report.passed = !report.runner_error && report.probes.length === 6 && report.probes.every((probe) => probe.passed);
  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2));
}

console.log(JSON.stringify(report, null, 2));
process.exit(report.passed ? 0 : 1);
