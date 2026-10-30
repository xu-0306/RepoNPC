import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AnalysisSelectionPanel } from "./AnalysisSelectionPanel";
import { ChatProfilePanel, type ChatProfileView } from "./ChatProfilePanel";
import {
  EmbeddingProfilePanel,
  type EmbeddingProfileView,
} from "./EmbeddingProfilePanel";
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
  chat: {
    profile_id: "chat-a",
    model_id: "same-model",
    status: "ready",
    connection_revision: 1,
    tested: true,
  },
  embedding: {
    profile_id: "finder",
    model_id: "finder-model",
    status: "ready",
    connection_revision: 1,
    tested: true,
  },
};

describe("AnalysisSelectionPanel", () => {
  it.each(["zh-TW", "en"] as const)(
    "names the rendered analysis button in both model hints in %s",
    (locale) => {
      const selection = renderToStaticMarkup(
        <AnalysisSelectionPanel
          locale={locale}
          chatProfiles={[]}
          embeddingProfiles={[]}
          value={null}
          pending={false}
          error=""
          onSelect={vi.fn()}
        />,
      );
      const buttonLabel = selection.match(
        /<button\b[^>]*>([^<]+)<\/button>/,
      )?.[1];
      expect(buttonLabel).toBeDefined();
      const props = {
        locale,
        connections: [],
        profiles: [],
        pending: false,
        error: "",
        managementActions: false,
        onActivate: vi.fn(),
        onCreate: vi.fn(),
        onDelete: vi.fn(),
        onProbe: vi.fn(),
        onRefresh: vi.fn(),
        onUpdate: vi.fn(),
      };
      for (const panel of [
        <ChatProfilePanel {...props} />,
        <EmbeddingProfilePanel
          {...props}
          catalog={[]}
          installedModels={[]}
          onOllamaDelete={vi.fn()}
          onOllamaPull={vi.fn()}
        />,
      ]) {
        const hint = renderToStaticMarkup(panel).match(/<p>([^<]+)<\/p>/)?.[1];
        expect(hint).toBeDefined();
        expect(hint).toContain(buttonLabel);
      }
    },
  );

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

it.each(["zh-TW", "en"] as const)(
  "discloses the full explanation and shows only current feedback in %s",
  (locale) => {
    for (const error of ["", "<unsafe-error>"]) {
      const html = renderToStaticMarkup(
        <AnalysisSelectionPanel
          locale={locale}
          chatProfiles={[]}
          embeddingProfiles={[]}
          value={null}
          pending={false}
          error={error}
          onSelect={vi.fn()}
        />,
      );
      const info = html.match(
        /<details class="model-selection__info px-info">(.*?)<\/details>/s,
      )?.[1];
      expect(info).toBeDefined();
      expect(info).toContain('<summary><span aria-hidden="true">ⓘ</span> ');
      expect(info).toContain(locale === "en" ? "About analysis" : "分析說明");
      expect(info).toContain(
        locale === "en"
          ? "Analysis uses two tested models. This does not change the public website model or index."
          : "分析會使用兩個已測試的模型；不會變更網站目前使用的公開模型或索引。",
      );
      expect(html).toMatch(
        /<label for="analysis-chat-profile"><span>[^<]+<\/span><select[^>]+id="analysis-chat-profile"/,
      );
      expect(html).toMatch(
        /<label for="analysis-embedding-profile"><span>[^<]+<\/span><select[^>]+id="analysis-embedding-profile"/,
      );
      expect(html.match(/role="(?:status|alert)"/g)).toHaveLength(1);
      if (error) {
        expect(html).toContain('<p role="alert">&lt;unsafe-error&gt;</p>');
        expect(html).not.toContain('role="status"');
      } else {
        expect(html).toContain('<p role="status">');
        expect(html).toContain(
          locale === "en"
            ? "Add and test both types of model, then select and confirm them."
            : "請先新增並測試兩種模型，再分別選擇並確認。",
        );
      }
    }
  },
);
