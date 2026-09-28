// Mount beside apps/web/index.html for a synthetic, real-App browser regression.
// Controlled public responses deliberately ignore abort so request identity is checked.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./src/app/App";
import "./src/styles.css";

let approved = true;
let bundle = "visitor-one";
let delay = false;
let release: (() => void) | null = null;
let calls = 0;
let chatCalls = 0;
const observe = () => {
  const output = document.querySelector('[aria-label="Public request counts"]');
  if (output) output.textContent = JSON.stringify({ faq: calls, chat: chatCalls, held: !!release });
};
window.fetch = async (input) => {
  const url = new URL(String(input), location.href);
  const locale = url.searchParams.get("locale") ?? "zh-TW";
  let value;
  if (url.pathname === "/api/public/status") value = { chat_available: false };
  else if (url.pathname === "/api/public/profile") value = {
    index: { version: bundle },
    profile: { display_name: "Synthetic owner", headline: "Fixture portfolio", bio: "Safe fixture", greeting: "Hello", location: null, avatar_url: null, links: [] },
    repositories: [], suggested_questions: [],
    character: { mode: "builtin", asset_url: "/character.png", revision: 1, frame_duration_ms: 160, movement: "none" },
  };
  else if (url.pathname === "/api/public/faq") {
    calls++;
    value = { bundle_id: bundle, locale, entries: approved ? [{
      question: locale === "en" ? "Approved question" : "已核准的問題",
      answer_markdown: locale === "en" ? "APPROVED_EN_ANSWER" : "APPROVED_ZH_ANSWER",
      citations: [{ id: "S1", evidence_class: "REPOSITORY_FACT", repository: "owner/demo", commit_sha: "a".repeat(40), path: "README.md", start_line: 1, end_line: 1, title: "Synthetic evidence", excerpt: "Fixture evidence", url: "https://github.com/owner/demo/blob/" + "a".repeat(40) + "/README.md#L1" }],
    }] : [] };
    if (delay) {
      delay = false;
      await new Promise<void>(resolve => { release = resolve; observe(); });
      release = null;
    }
  } else {
    chatCalls++; observe();
    throw new Error("Unexpected synthetic request");
  }
  observe();
  return new Response(JSON.stringify(value), { headers: { "Content-Type": "application/json" } });
};
function Review() {
  const [, update] = useState(0);
  const control = (operation: () => void) => { operation(); update(value => value + 1); observe(); };
  return <>
    <aside aria-label="Synthetic visitor controls">
      <button onClick={() => control(() => { delay = true; })}>Delay next FAQ fixture</button>
      <button onClick={() => control(() => { release?.(); })}>Release FAQ fixture</button>
      <button onClick={() => control(() => { approved = !approved; })}>Toggle approval fixture</button>
      <button onClick={() => control(() => { bundle = "visitor-two"; })}>Switch visitor bundle fixture</button>
      <output aria-label="Public request counts">{"{\"faq\":0,\"chat\":0,\"held\":false}"}</output>
    </aside>
    <App />
  </>;
}
createRoot(document.getElementById("root")!).render(<Review />);
