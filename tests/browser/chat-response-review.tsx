import { useState } from "react";
import { createRoot } from "react-dom/client";
import { ChatProfilePanel } from "./src/features/admin/ChatProfilePanel";
import "./src/styles.css";

const noop = () => {};
function Review() {
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  return (
    <main style={{ maxWidth: 420, padding: 16, margin: "auto" }}>
      <button onClick={() => setLocale(locale === "zh-TW" ? "en" : "zh-TW")}>
        中文 / English
      </button>
      <ChatProfilePanel
        locale={locale}
        connections={[]}
        pending={false}
        error=""
        onRefresh={noop}
        onCreate={noop}
        onUpdate={noop}
        onProbe={noop}
        onActivate={noop}
        onDelete={noop}
        profiles={[
          {
            profile_id: "synthetic",
            connection_id: "synthetic-service",
            connection_revision: 2,
            model_id: "synthetic/model",
            observed_model_id: null,
            active: false,
            status: "probe_failed",
            last_error_code: "PROVIDER_INVALID_RESPONSE",
            last_error_message:
              "RepoNPC response check: HTTP 200; the response reached the output limit (length).",
            last_probed_at: "2026-09-12T00:00:00Z",
          },
        ]}
      />
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<Review />);
