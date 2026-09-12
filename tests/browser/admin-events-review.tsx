import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AdminPage } from "./src/features/admin/AdminPage";
import "./src/styles.css";

// Isolated browser fixture. No request is forwarded to a real API.
const time = "2026-09-12T05:00:00Z";
let connection = {
  connection_id: "fixture-ollama",
  display_name: "Synthetic Ollama",
  provider: "ollama",
  revision: 1,
  key_configured: false,
  source: "managed",
  created_at: time,
  updated_at: time,
};
let delayInstalled = false;
let saveMode = "success";
let failListRefresh = false;
let releaseInstalled: (() => void) | undefined;
const requests: string[] = [];
window.fetch = async (input, init) => {
  const path = String(input);
  const method = init?.method ?? "GET";
  requests.push(`${method} ${path}`);
  const output = document.getElementById("fixture-requests");
  if (output) output.textContent = requests.join("\n");
  const reply = (value: unknown, status = 200) =>
    new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  if (path === "/api/admin/session/local-launch")
    return reply({ csrf_token: "SYNTHETIC_FIXTURE_CSRF" });
  if (path === "/api/admin/analysis-selection")
    return reply({
      selection: {
        chat_profile_id: null,
        embedding_profile_id: null,
        generation: 0,
        updated_at: time,
      },
      eligible: false,
      reason: "ANALYSIS_MODELS_NOT_SELECTED",
    });
  if (path === "/api/admin/config")
    return reply({ content: "schema_version: 1\n", blob_sha: "synthetic-sha" });
  if (path === "/api/admin/config/validate")
    return reply({ valid: true, errors: [], parsed: {} });
  if (path === "/api/admin/config/preview")
    return reply({
      profile: {
        display_name: "Synthetic preview A",
        headline: "Unpublished",
        bio: "Fixture only",
      },
    });
  if (path === "/api/admin/index/status")
    return reply({ active_bundle_id: null });
  if (path.startsWith("/api/admin/readme-snippet"))
    return reply({ markdown: "", asset_url: "", target_url: "" });
  if (path === "/api/admin/embedding-models/catalog")
    return reply({ models: [] });
  if (path.startsWith("/api/admin/embedding-models/installed")) {
    const revision = connection.revision;
    if (delayInstalled)
      await new Promise<void>((resolve) => {
        releaseInstalled = resolve;
      });
    return reply({ models: [`synthetic-model-revision-${revision}`] });
  }
  if (
    path === "/api/admin/model-connections" &&
    method === "GET" &&
    failListRefresh
  )
    return reply({ error: { code: "FIXTURE_REFRESH_FAILED" } }, 503);
  if (path === "/api/admin/model-connections")
    return reply({ connections: [connection] });
  if (path === "/api/admin/model-connections/fixture-ollama") {
    if (saveMode === "failure")
      return reply({ error: { code: "CREDENTIAL_REPLACE_REQUIRED" } }, 400);
    const body = JSON.parse(String(init?.body ?? "{}"));
    connection = {
      ...connection,
      display_name: body.display_name,
      provider: body.provider,
      revision: connection.revision + 1,
    };
    if (saveMode === "refresh-failure") failListRefresh = true;
    return reply(connection);
  }
  if (
    path === "/api/admin/chat-profiles" ||
    path === "/api/admin/embedding-profiles"
  )
    return reply({ profiles: [] });
  return reply({ error: { code: "FIXTURE_UNHANDLED" } }, 404);
};

function Review() {
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  return (
    <>
      <aside>
        <strong>Isolated admin event review</strong>
        <label>
          Save result
          <select
            onChange={(event) => {
              saveMode = event.target.value;
              failListRefresh = false;
            }}
          >
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="refresh-failure">Saved but refresh fails</option>
          </select>
        </label>
        <button
          onClick={() => {
            connection = { ...connection, revision: connection.revision + 1 };
          }}
        >
          Simulate external service revision
        </button>
        <label>
          <input
            type="checkbox"
            onChange={(event) => {
              delayInstalled = event.target.checked;
            }}
          />
          Delay installed response
        </label>
        <button
          onClick={() => {
            releaseInstalled?.();
            releaseInstalled = undefined;
          }}
        >
          Release installed response
        </button>
        <details>
          <summary>Fixture requests</summary>
          <pre id="fixture-requests" />
        </details>
      </aside>
      <AdminPage locale={locale} onLocaleChange={setLocale} />
    </>
  );
}
createRoot(document.getElementById("root")!).render(<Review />);
