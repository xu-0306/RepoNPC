import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AnalysisSelectionPanel } from "./AnalysisSelectionPanel";
import type { ChatProfileView } from "./ChatProfilePanel";
import type { EmbeddingProfileView } from "./EmbeddingProfilePanel";
import type { ModelConnectionView } from "./ModelConnectionPanel";

const service = (
  id: string,
  name: string,
  revision = 1,
): ModelConnectionView => ({
  connection_id: id,
  display_name: name,
  provider: "openai_compatible",
  source: "managed",
  revision,
  endpoint_configured: true,
  key_configured: true,
  status: "configured",
});
const chat = (id: string, connection: string): ChatProfileView => ({
  profile_id: id,
  connection_id: connection,
  connection_revision: 1,
  model_id: "same-model",
  status: "ready",
  active: false,
  last_error_code: null,
  last_probed_at: "fixture-time",
  observed_model_id: "same-model",
});
const finder: EmbeddingProfileView = {
  profile_id: "finder",
  connection_reference: "service-a",
  connection_revision: 1,
  provider: "openai_compatible",
  model_id: "finder-model",
  dimension: 3,
  normalized: true,
  status: "reindex_required",
  active: false,
  last_error_code: null,
  last_probed_at: "fixture-time",
};
const selected = {
  selection: {
    chat_profile_id: "chat-a",
    embedding_profile_id: "finder",
    generation: 1,
    updated_at: "fixture-time",
  },
  eligible: true,
  reason: "READY",
};

describe("AnalysisSelectionPanel", () => {
  it("distinguishes identical model names by safe service labels", () => {
    const html = renderToStaticMarkup(
      <AnalysisSelectionPanel
        locale="en"
        chatProfiles={[
          chat("chat-a", "service-a"),
          chat("chat-b", "service-b"),
        ]}
        embeddingProfiles={[finder]}
        connections={[
          service("service-a", "Service A"),
          service("service-b", "Service B"),
        ]}
        value={null}
        pending={false}
        error=""
        onSelect={vi.fn()}
      />,
    );
    expect(html).toContain("same-model · Service A");
    expect(html).toContain("same-model · Service B");
    expect(html).toContain("finder-model · Service A");
  });
  it("excludes rotated profiles and explains the required edit and retest", () => {
    const html = renderToStaticMarkup(
      <AnalysisSelectionPanel
        locale="zh-TW"
        chatProfiles={[chat("chat-a", "service-a")]}
        embeddingProfiles={[finder]}
        connections={[service("service-a", "Service A", 2)]}
        value={{
          ...selected,
          eligible: false,
          reason: "CHAT_MODEL_REVISION_STALE",
        }}
        pending={false}
        error=""
        onSelect={vi.fn()}
      />,
    );
    expect(html).not.toContain('option value="chat-a"');
    expect(html).not.toContain('option value="finder"');
    expect(html).toContain("請編輯對應模型並儲存，再測試");
    expect(html).toMatch(/<button disabled=""[^>]*>確認用於分析/);
  });
  it("does not claim readiness for a saved pair missing from current lists", () => {
    const html = renderToStaticMarkup(
      <AnalysisSelectionPanel
        locale="en"
        chatProfiles={[]}
        embeddingProfiles={[]}
        connections={[]}
        value={selected}
        pending={false}
        error=""
        onSelect={vi.fn()}
      />,
    );
    expect(html).not.toContain("Both models are selected and ready");
    expect(html).toMatch(/<button disabled=""[^>]*>Use for analysis/);
  });
});
