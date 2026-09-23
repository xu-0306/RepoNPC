// Production React + public FastAPI acceptance for R09 and the implemented
// visitor chat/NPC-state subset of R14.
export async function checkVisitorChat(tab, options = {}) {
  const baseUrl = options.baseUrl;
  const reducedMotion = options.reducedMotion === true;
  if (!baseUrl) throw new Error("baseUrl is required");
  const checks = [];
  const transitions = [];
  const verify = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  const waitFor = async (predicate, name, timeoutMs = 30000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const value = await predicate();
      if (value) return value;
      await new Promise((resolve) => setTimeout(resolve, 75));
    }
    throw new Error(name + " timed out");
  };
  const snapshot = () => tab.playwright.domSnapshot();
  const button = (name) =>
    tab.playwright.getByRole("button", { name, exact: true });
  const questionBox = (locale = "zh-TW") =>
    tab.playwright.getByRole("textbox", {
      name: locale === "zh-TW" ? "你的問題" : "Your question",
      exact: true,
    });
  const character = () =>
    tab.playwright.evaluate(() => {
      const node = document.querySelector("[data-character-state]");
      const sheet = document.querySelector(".character-renderer__sheet");
      return {
        state: node?.getAttribute("data-character-state"),
        label: node?.getAttribute("aria-label"),
        movement: node?.getAttribute("data-character-movement"),
        reduced: node?.getAttribute("data-reduced-motion"),
        duration: sheet?.style.getPropertyValue(
          "--character-animation-duration",
        ),
        animation: sheet ? getComputedStyle(sheet).animationName : null,
      };
    });
  const observeTransitions = async () => {
    await button("Reset character transitions").click();
  };
  const collectTransitions = async (scenario) => {
    const values = await tab.playwright.evaluate(() =>
      JSON.parse(
        document.querySelector("[data-character-transitions]")?.textContent ??
          "[]",
      ),
    );
    transitions.push({ scenario, states: values });
    return values;
  };
  const state = async () => {
    const controls = tab.playwright.locator(
      '[aria-label="Visitor acceptance controls"]',
    );
    const before = await controls.getAttribute("data-state-version");
    await button("Refresh visitor state").click();
    return waitFor(async () => {
      const current = await controls.getAttribute("data-state-version");
      if (current === before) return null;
      return tab.playwright.evaluate(() =>
        JSON.parse(
          document.querySelector("[data-visitor-state]")?.textContent ?? "{}",
        ),
      );
    }, "visitor observations");
  };
  const navigate = async (name) => {
    const query = new URLSearchParams({ run: name });
    if (reducedMotion) query.set("reduced", "1");
    await tab.goto(`${baseUrl}?${query}`);
    await waitFor(
      async () => (await button("送出問題").count()) === 1,
      "visitor application",
    );
    await waitFor(
      async () => (await snapshot()).includes("繁體中文問候"),
      "localized production profile",
    );
    await waitFor(
      async () => (await snapshot()).includes("索引與模型已就緒"),
      "ready public status",
    );
  };
  const submit = async (value, locale = "zh-TW") => {
    const box = questionBox(locale);
    await box.fill(value);
    await button(locale === "zh-TW" ? "送出問題" : "Ask question").click();
  };
  const waitForAnswer = (value) =>
    waitFor(async () => (await snapshot()).includes(value), `answer ${value}`);

  await navigate(reducedMotion ? "reduced" : "normal");
  let rendered = await character();
  verify(
    rendered.duration === "960ms",
    "profile frame duration reaches renderer",
  );
  if (reducedMotion) {
    verify(rendered.reduced === "true", "reduced motion sampled before mount");
    verify(
      rendered.animation === "none",
      "reduced motion disables sprite animation",
    );
    verify(
      Boolean(rendered.label),
      "reduced motion preserves semantic state label",
    );
    await button("English").click();
    await waitFor(
      async () => (await snapshot()).includes("English greeting"),
      "English profile",
    );
    rendered = await character();
    verify(
      rendered.label === "Character is idle",
      "English character state is localized",
    );
    const layout = await tab.playwright.evaluate(() => ({
      width: innerWidth,
      overflow: document.documentElement.scrollWidth > innerWidth,
      main: document.querySelectorAll("main").length,
    }));
    verify(
      !layout.overflow && layout.main === 1,
      "reduced-motion page has no basic content loss",
    );
    return {
      mode: "reduced-motion",
      checks,
      transitions,
      browser: await tab.playwright.evaluate(
        () => document.documentElement.dataset.browserUserAgent,
      ),
      viewport: layout.width,
      observations: await state(),
    };
  }

  await observeTransitions();
  await questionBox().fill("browser-normal");
  verify((await character()).state === "listen", "typing sets listen state");
  await button("送出問題").click();
  verify((await character()).state === "think", "submission sets think state");
  await button("Release blocked chat").click();
  await waitFor(
    async () => (await character()).state === "success",
    "complete sets success state",
  );
  let dom = await snapshot();
  verify(
    dom.includes("Fixture evidence") &&
      dom.includes("REPOSITORY_FACT") &&
      dom.includes("src/main.py:10-12") &&
      dom.includes("bbbbbbbbbbbb"),
    "validated citation renders class, path and commit",
  );
  await waitFor(
    async () => (await character()).state === "idle",
    "success returns to idle",
    4000,
  );
  let sequence = await collectTransitions("normal-success");
  verify(
    sequence.join("|").includes("listen|think|talk|success|idle"),
    "normal character states are ordered",
  );

  await button("English").click();
  await waitFor(
    async () => (await snapshot()).includes("English greeting"),
    "English profile switch",
  );
  verify(
    (await snapshot()).includes("Validated answer for browser-normal"),
    "locale switch preserves transcript",
  );
  await submit("locale-en", "en");
  await waitForAnswer("Validated answer for locale-en");
  let observed = await state();
  const localeCall = observed.calls.find(
    (entry) => entry.message_id === "question:locale-en",
  );
  verify(localeCall.locale === "en", "selected locale reaches public chat API");
  verify(
    localeCall.history.map((item) => item.content_id).join("|") ===
      "question:browser-normal|answer:browser-normal",
    "successful prior exchange enters model history",
  );
  verify(
    (await character()).label === "Answer complete",
    "character aria label follows locale",
  );

  await navigate("history");
  for (let index = 1; index <= 7; index += 1) {
    await submit(`round-${index}`);
    await waitForAnswer(`Validated answer for round-${index}`);
  }
  observed = await state();
  const roundSix = observed.calls.find(
    (entry) => entry.message_id === "question:round-6",
  );
  const roundSeven = observed.calls.find(
    (entry) => entry.message_id === "question:round-7",
  );
  verify(
    roundSix.history.length === 10,
    "history admits at most five complete exchanges",
  );
  verify(
    roundSix.history.map((item) => item.content_id).join("|") ===
      Array.from(
        { length: 5 },
        (_, index) => `question:round-${index + 1}|answer:round-${index + 1}`,
      ).join("|"),
    "history is an alternating contiguous suffix",
  );
  verify(
    roundSeven.history[0].content_id === "question:round-2" &&
      roundSeven.history.at(-1).content_id === "answer:round-6",
    "history drops only the oldest whole exchange",
  );
  dom = await snapshot();
  verify(
    dom.includes("round-1") && dom.includes("round-7"),
    "complete transcript remains visible",
  );

  await navigate("long");
  await submit("browser-long");
  await waitFor(
    () =>
      tab.playwright.evaluate(() =>
        Array.from(document.querySelectorAll(".turn--assistant > p")).some(
          (node) => Array.from(node.textContent ?? "").length === 4001,
        ),
      ),
    "full long answer",
  );
  await submit("after-long");
  await waitForAnswer("Validated answer for after-long");
  observed = await state();
  const afterLong = observed.calls.find(
    (entry) => entry.message_id === "question:after-long",
  );
  verify(
    afterLong.history.length === 0,
    "oversized newest answer starts fresh model context",
  );

  await navigate("failure");
  await submit("browser-failure");
  await waitFor(
    async () => (await button("重試這個問題").count()) === 1,
    "failure retry control",
  );
  await waitFor(
    () =>
      tab.playwright.evaluate(
        () => document.activeElement?.id === "portfolio-question",
      ),
    "failure returns focus to question input",
  );
  verify(true, "failure returns focus to question input");
  await button("重試這個問題").click();
  await waitForAnswer("Validated answer for browser-failure");
  await submit("after-failure");
  await waitForAnswer("Validated answer for after-failure");
  observed = await state();
  const failureCalls = observed.calls.filter(
    (entry) => entry.message_id === "question:browser-failure",
  );
  const afterFailure = observed.calls.find(
    (entry) => entry.message_id === "question:after-failure",
  );
  verify(
    failureCalls.length === 2 &&
      failureCalls.every((entry) => entry.history.length === 0),
    "failed attempt never enters retry history",
  );
  verify(
    afterFailure.history.length === 2,
    "successful retry enters history exactly once",
  );
  verify(
    (await snapshot()).includes("目前無法完成回答"),
    "failed visible turn remains in transcript",
  );

  await navigate("incomplete");
  await submit("browser-incomplete");
  await waitFor(
    async () => (await button("重試這個問題").count()) === 1,
    "incomplete transport retry",
  );
  verify(
    (await snapshot()).includes("Validated answer for browser-incomplete"),
    "partial incomplete content remains visible",
  );
  await submit("after-incomplete");
  await waitForAnswer("Validated answer for after-incomplete");
  observed = await state();
  const afterIncomplete = observed.calls.find(
    (entry) => entry.message_id === "question:after-incomplete",
  );
  verify(
    afterIncomplete.history.length === 0,
    "incomplete delivery never enters history",
  );

  await navigate("double");
  await questionBox().fill("browser-double");
  const rapidSubmit = button("送出問題");
  await Promise.allSettled([
    rapidSubmit.click({ force: true }),
    rapidSubmit.click({ force: true }),
  ]);
  await waitFor(async () => {
    const value = await state();
    return (
      value.calls.filter(
        (entry) => entry.message_id === "question:browser-double",
      ).length === 1
    );
  }, "single rapid submission");
  await button("Release blocked chat").click();
  await waitForAnswer("Validated answer for browser-double");
  verify(true, "synchronous request lock rejects rapid duplicate submission");

  await navigate("unmount");
  await submit("browser-unmount");
  await waitFor(async () => {
    const value = await state();
    return value.calls.some(
      (entry) => entry.message_id === "question:browser-unmount",
    );
  }, "blocked unmount request started");
  await tab.goto(`${baseUrl}?run=after-unmount`);
  await waitFor(
    async () => (await button("送出問題").count()) === 1,
    "page remounted",
  );
  await waitFor(
    async () => (await state()).disconnect_observed === true,
    "client disconnect observed",
  );
  verify(true, "unmount aborts the production chat request");

  await observeTransitions();
  await submit("browser-failure-delayed");
  await button("Set status unavailable").click();
  await button("Release blocked chat").click();
  await waitFor(
    async () => (await character()).state === "offline",
    "status-confirmed offline state",
  );
  verify(
    (await snapshot()).includes("聊天目前無法使用"),
    "degraded status remains readable",
  );
  await button("Set status ready").click();
  await button("重新檢查聊天狀態").click();
  await waitFor(
    async () => (await character()).state === "idle",
    "status recovery returns idle",
  );
  sequence = await collectTransitions("degraded-recovery");
  verify(
    sequence.includes("offline") && sequence.at(-1) === "idle",
    "status recovery sequence recorded",
  );

  const layout = await tab.playwright.evaluate(() => ({
    width: innerWidth,
    overflow: document.documentElement.scrollWidth > innerWidth,
    main: document.querySelectorAll("main").length,
  }));
  verify(
    !layout.overflow && layout.main === 1,
    "visitor page has no basic content loss",
  );
  return {
    mode: "normal",
    checks,
    transitions,
    browser: await tab.playwright.evaluate(
      () => document.documentElement.dataset.browserUserAgent,
    ),
    viewport: layout.width,
    observations: await state(),
  };
}
