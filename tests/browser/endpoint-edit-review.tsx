import { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ModelConnectionPanel,
  type ModelConnectionView,
} from "./src/features/admin/ModelConnectionPanel";
import "./src/styles.css";

// All values are synthetic. No network, credentials or actual model mutations.
function Review() {
  const [mode, setMode] = useState("success");
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  const [reads, setReads] = useState(0);
  const release = useRef<(() => void) | null>(null);
  const [saved, setSaved] = useState("");
  const connections: ModelConnectionView[] = ["one", "two"].map((id) => ({
    connection_id: id,
    display_name: `Service ${id}`,
    provider: "openai_compatible",
    source: "managed",
    revision: 1,
    endpoint_configured: true,
    key_configured: true,
    status: "configured",
  }));
  return (
    <>
      <aside>
        <label>
          Read mode
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option>success</option>
            <option>failure</option>
            <option>delayed</option>
          </select>
        </label>
        <label>
          Language
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as typeof locale)}
          >
            <option value="zh-TW">繁中</option>
            <option value="en">English</option>
          </select>
        </label>
        <button onClick={() => release.current?.()}>Release URL</button>
        <output id="read-count">{reads}</output>
        <output id="saved-intent">{saved}</output>
      </aside>
      <main className="admin-workspace">
        <ModelConnectionPanel
          locale={locale}
          connections={connections}
          pending={false}
          error=""
          onCreate={() => {}}
          onDelete={() => {}}
          onRefresh={() => {}}
          onUpdate={(_id, draft) =>
            setSaved(
              JSON.stringify({
                endpoint: draft.endpoint_action,
                credential: draft.credential_action,
                url: draft.base_url,
              }),
            )
          }
          onReadEndpoint={async (id) => {
            setReads((n) => n + 1);
            if (mode === "failure") throw new Error("Synthetic read failure");
            if (mode === "delayed")
              await new Promise<void>((resolve) => {
                release.current = resolve;
              });
            return {
              connection_id: id,
              revision: 1,
              base_url: `https://${id}.synthetic.example.test/v1`,
            };
          }}
        />
      </main>
    </>
  );
}
createRoot(document.getElementById("root")!).render(<Review />);
