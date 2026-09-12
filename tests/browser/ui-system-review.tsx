// Copy beside apps/web/index.html for local Vite review; never part of the production entry.
// All callbacks operate on synthetic in-memory data. No network or stored credentials.
import { useState } from "react";
import { createRoot } from "react-dom/client";
import { AdminWorkspace } from "./src/features/admin/AdminWorkspace";
import { ModelConnectionPanel } from "./src/features/admin/ModelConnectionPanel";
import { ChatProfilePanel } from "./src/features/admin/ChatProfilePanel";
import { EmbeddingProfilePanel } from "./src/features/admin/EmbeddingProfilePanel";
import { ModelSetupWorkspace } from "./src/features/admin/ModelSetupWorkspace";
import { GuidedOnboardingView } from "./src/features/admin/GuidedOnboardingView";
import {
  initialGuidedOnboardingState,
  guidedOnboardingReducer,
} from "./src/features/admin/guidedOnboarding";
import "./src/styles.css";

const noop = () => {};
const fixture = {
  connection_id: "fixture",
  display_name: "Synthetic service",
  provider: "openai_compatible",
  revision: 1,
  source: "managed",
  endpoint_configured: true,
  key_configured: true,
  status: "configured",
};
function Review() {
  const [locale, setLocale] = useState("zh-TW");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState([]);
  const [connections, setConnections] = useState([fixture]);
  const [scenario, setScenario] = useState("models");
  const [state, setState] = useState(() => ({
    ...initialGuidedOnboardingState(),
    step: "repositories",
    repositories: [
      {
        metadata: {
          slug: "example/" + "long-repository-".repeat(8),
          name: "long-repository-".repeat(8),
          description: "A synthetic public repository",
          primary_language: "TypeScript",
          default_branch: "main",
          is_fork: false,
          is_archived: false,
          updated_at: "2026-09-12",
          html_url: "https://github.com/example/demo",
        },
        selected: true,
        ref: null,
        include: [],
        exclude: [],
        confirmedSelectionFingerprint: null,
        analysisStatus: "idle",
        analysis: null,
        ownerStatement: "",
        proposal: null,
        confirmedContribution: null,
      },
    ],
  }));
  const record = (value) => setEvents((old) => [...old, value]);
  const save = (action, draft) => {
    record({
      action,
      endpoint: draft.endpoint_action,
      key: draft.credential_action,
      hasKey: !!draft.api_key,
      hasAddress: !!draft.base_url,
    });
    setPending(true);
    setError("");
  };
  const common = {
    locale,
    connections,
    pending,
    error,
    onRefresh: () => record({ action: "refresh" }),
    onCreate: (draft) => save("create", draft),
    onUpdate: (_, draft) => save("update", draft),
    onDelete: (id) => {
      record({ action: "delete", id });
      setConnections((old) => old.filter((c) => c.connection_id !== id));
    },
    onProbe: () => record({ action: "probe" }),
    onActivate: noop,
  };
  const model = {
    profile_id: "fixture",
    model_id: "synthetic-model",
    active: false,
    status: "probe_failed",
    last_error_code: "PROVIDER_HTTP_402",
    last_error_message:
      "Original failure text: " + "unknown-message-".repeat(10),
    last_probed_at: "2026-09-12T00:00:00Z",
  };
  const models = (
    <section className="guided-onboarding__step">
      <ModelSetupWorkspace
        locale={locale}
        chatConnectionView={<ModelConnectionPanel {...common} purpose="chat" />}
        embeddingConnectionView={
          <ModelConnectionPanel {...common} purpose="embedding" />
        }
        chatView={
          <ChatProfilePanel
            {...common}
            profiles={[
              {
                ...model,
                connection_id: "fixture",
                connection_revision: 1,
                observed_model_id: null,
              },
            ]}
          />
        }
        embeddingView={
          <EmbeddingProfilePanel
            {...common}
            profiles={[
              {
                ...model,
                provider: "openai_compatible",
                connection_reference: "fixture",
                dimension: 2,
                normalized: true,
              },
            ]}
            catalog={[]}
            installedModels={[]}
            onOllamaPull={noop}
            onOllamaDelete={noop}
          />
        }
        selectionView={
          <p>Models must pass an explicit test before selection.</p>
        }
      />
    </section>
  );
  const repositories = (
    <GuidedOnboardingView
      locale={locale}
      state={state}
      busy={false}
      errorCode=""
      providerStatus={null}
      providerStatusPending={false}
      onAction={(action) => {
        record({ action: action.type });
        setState((old) => guidedOnboardingReducer(old, action));
      }}
      onDiscover={noop}
      onResolve={noop}
      onAnalyze={noop}
      onRefreshProviderStatus={noop}
      onSuggestContribution={noop}
      onCreateDraft={noop}
      onCopyDraft={noop}
      onDownloadDraft={noop}
    />
  );
  return (
    <>
      <aside style={{ padding: 12 }}>
        <strong>Isolated synthetic UI review</strong>
        <button onClick={() => setScenario("models")}>Model forms</button>
        <button onClick={() => setScenario("repositories")}>
          Repository choices
        </button>
        <button
          onClick={() => {
            setScenario("repositories");
            setState((old) => ({
              ...old,
              step: "contributions",
              route: "manual",
              selectionConfirmed: true,
              repositories: [
                old.repositories[0],
                {
                  ...old.repositories[0],
                  metadata: {
                    ...old.repositories[0].metadata,
                    slug: "example/second-project",
                    name: "second-project",
                  },
                },
              ],
            }));
          }}
        >
          Contribution editors
        </button>
        <button
          onClick={() => {
            setPending(false);
            setError("Synthetic save failed");
          }}
        >
          Resolve failure
        </button>
        <button
          onClick={() => {
            setPending(false);
            setError("");
          }}
        >
          Resolve success
        </button>
        <button
          onClick={() =>
            (document.documentElement.style.fontSize = document.documentElement
              .style.fontSize
              ? ""
              : "200%")
          }
        >
          Toggle 200% text
        </button>
        <output
          id="review-events"
          style={{ display: "block", overflowWrap: "anywhere" }}
        >
          {JSON.stringify(events)}
        </output>
      </aside>
      <AdminWorkspace
        locale={locale}
        onLocaleChange={setLocale}
        draft="schema_version: 1"
        validation={null}
        preview={null}
        status={null}
        snippet={null}
        conflict={null}
        busy={false}
        authenticated
        githubOperationsReady={false}
        notice=""
        onDraftChange={noop}
        onValidate={noop}
        onPreview={noop}
        onSave={noop}
        onCopy={noop}
        onDispatch={noop}
        onLogout={noop}
        advancedMode={false}
        guidedView={scenario === "models" ? models : repositories}
      />
    </>
  );
}
createRoot(document.getElementById("root")!).render(<Review />);
