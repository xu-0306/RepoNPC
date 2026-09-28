// Synthetic private snapshots exercise the real panel without Funnel or provider calls.
import { useCallback, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  VisitorGatewayPanel,
  type VisitorGatewayStatus,
} from "./src/features/admin/VisitorGatewayPanel";
import "./src/styles.css";

const initial: VisitorGatewayStatus = {
  revision: 1,
  gateway_origin: "https://fixture.ts.net",
  pages_origin: "https://fixture.github.io",
  enabled: false,
  listener_ready: false,
  error_code: null,
  local_ready: true,
  entry_configured: false,
  external_verified: false,
  verified_at: null,
  verification_method: null,
  active_bundle_id: "fixture-bundle-one",
  client_identity_mode: "aggregate",
};

function Review() {
  const [locale, setLocale] = useState<"zh-TW" | "en">("zh-TW");
  const status = useRef({ ...initial });
  const hold = useRef(false);
  const release = useRef<(() => void) | null>(null);
  const conflict = useRef(false);
  const [logs, setLogs] = useState<string[]>([]);
  const request = useCallback(
    async <T,>(path: string, options?: RequestInit): Promise<T> => {
      if (!options?.method || options.method === "GET")
        return { ...status.current } as T;
      const body = JSON.parse(String(options.body));
      setLogs((rows) => [
        ...rows,
        `${options.method} ${path} ${JSON.stringify(body)}`,
      ]);
      if (hold.current) {
        hold.current = false;
        await new Promise<void>((resolve) => {
          release.current = resolve;
        });
      }
      if (conflict.current) {
        conflict.current = false;
        status.current.revision += 1;
        throw new Error("GATEWAY_CONFLICT");
      }
      if (body.revision !== status.current.revision)
        throw new Error("GATEWAY_CONFLICT");
      if (options.method === "PUT") {
        status.current.gateway_origin = body.gateway_origin;
        status.current.pages_origin = body.pages_origin;
        status.current.external_verified = false;
      } else if (path.endsWith("/start")) {
        status.current.enabled =
          status.current.listener_ready =
          status.current.entry_configured =
            true;
        status.current.external_verified = false;
      } else if (path.endsWith("/stop")) {
        status.current.enabled =
          status.current.listener_ready =
          status.current.entry_configured =
            false;
        status.current.external_verified = false;
      } else if (path.endsWith("/verify")) {
        if (
          !body.external_checks_confirmed ||
          body.bundle_id !== status.current.active_bundle_id
        )
          throw new Error("GATEWAY_VERIFICATION_STALE");
        status.current.external_verified = true;
        status.current.verified_at = "2026-09-29T01:00:00Z";
        status.current.verification_method = "owner_reported";
      }
      status.current.revision += 1;
      return { ...status.current } as T;
    },
    [],
  );

  return (
    <main className="admin-workspace">
      <h1>A1 independent gateway review</h1>
      <nav
        aria-label="Synthetic review controls"
        className="admin-workspace__actions"
      >
        <button
          onClick={() => {
            setLocale("zh-TW");
            document.documentElement.lang = "zh-Hant";
          }}
        >
          Chinese fixture
        </button>
        <button
          onClick={() => {
            setLocale("en");
            document.documentElement.lang = "en";
          }}
        >
          English fixture
        </button>
        <button
          onClick={() => {
            status.current = { ...initial };
            setLogs([]);
          }}
        >
          Reset fixture
        </button>
        <button
          onClick={() => {
            status.current.local_ready = false;
            status.current.external_verified = false;
          }}
        >
          Observe local failure
        </button>
        <button
          onClick={() => {
            status.current.local_ready = true;
          }}
        >
          Restore local readiness
        </button>
        <button
          onClick={() => {
            status.current.active_bundle_id = "fixture-bundle-two";
            status.current.external_verified = false;
          }}
        >
          Activate next bundle
        </button>
        <button
          onClick={() => {
            conflict.current = true;
          }}
        >
          Conflict next mutation
        </button>
        <button
          onClick={() => {
            hold.current = true;
          }}
        >
          Hold next mutation
        </button>
        <button
          onClick={() => {
            release.current?.();
            release.current = null;
          }}
        >
          Release mutation
        </button>
      </nav>
      <VisitorGatewayPanel locale={locale} request={request} />
      <h2>Observed synthetic requests</h2>
      <pre
        aria-label="Observed synthetic requests"
        style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
      >
        {logs.join("\n")}
      </pre>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<Review />);
