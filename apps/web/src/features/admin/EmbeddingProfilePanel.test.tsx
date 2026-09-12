import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { EmbeddingProfilePanel } from "./EmbeddingProfilePanel";

describe("EmbeddingProfilePanel", () => {
  it("renders safe provider-aware controls without credential or URL fields", () => {
    const markup = renderToStaticMarkup(
      <EmbeddingProfilePanel
        catalog={[
          {
            provider: "ollama",
            model_id: "qwen3-embedding:0.6b",
            recommended: true,
            license: "Apache-2.0",
            language_context_notes: "zh-TW, English, and code",
            resource_hint: "approximately 639 MB",
            operations: ["pull", "list", "probe", "delete"],
          },
        ]}
        connections={[
          {
            connection_id: "embedding-gateway",
            display_name: "Embedding gateway",
            provider: "openai_compatible",
            source: "managed",
            revision: 1,
            endpoint_configured: true,
            key_configured: false,
            status: "configured",
          },
        ]}
        error=""
        installedModels={["qwen3-embedding:0.6b"]}
        locale="en"
        onActivate={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onOllamaDelete={vi.fn()}
        onOllamaPull={vi.fn()}
        onProbe={vi.fn()}
        onRefresh={vi.fn()}
        pending={false}
        profiles={[
          {
            profile_id: "environment",
            provider: "ollama",
            model_id: "qwen3-embedding:0.6b",
            dimension: 1024,
            normalized: true,
            connection_reference: "environment",
            status: "ready",
            active: true,
            last_error_code: null,
            last_probed_at: "2026-08-31T00:00:00Z",
          },
        ]}
      />,
    );

    expect(markup).toContain("Content finder models");
    expect(markup).toContain("qwen3-embedding:0.6b");
    expect(markup).toContain('class="model-brand-icon"');
    expect(markup).toMatch(/<img alt="" src="[^"]+\.svg\?no-inline"\/>/);
    expect(markup).not.toContain("data:image/svg+xml");
    expect(markup).not.toContain("Recommended starter");
    expect(markup).not.toContain("Approved Ollama catalog");
    expect(markup).not.toContain("Installed on the configured Ollama host");
    expect(markup).not.toContain("Apache-2.0");
    expect(markup).not.toContain("live probe remains authoritative");
    expect(markup).toContain("Test model");
    expect(markup).not.toContain("base_url");
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain('type="password"');
    expect(markup).toContain('id="embedding-profile-model"');
  });

  it("separates analysis testing from public activation and model deletion", () => {
    const markup = renderToStaticMarkup(
      <EmbeddingProfilePanel
        catalog={[]}
        connections={[]}
        error=""
        installedModels={[]}
        locale="en"
        managementActions={false}
        onActivate={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onOllamaDelete={vi.fn()}
        onOllamaPull={vi.fn()}
        onProbe={vi.fn()}
        onRefresh={vi.fn()}
        pending={false}
        profiles={[
          {
            profile_id: "embedding-1",
            provider: "ollama",
            model_id: "qwen3-embedding:0.6b",
            dimension: 1024,
            normalized: true,
            connection_reference: "ollama-local",
            status: "ready",
            active: false,
            last_error_code: null,
            last_probed_at: "2026-09-10T00:00:00Z",
          },
        ]}
      />,
    );

    expect(markup).toContain("Test model");
    expect(markup).not.toContain(">Activate<");
    expect(markup).not.toContain("Install through Ollama");
    expect(markup).not.toContain("Delete through Ollama");
  });

  it("renders readable Traditional Chinese copy", () => {
    const markup = renderToStaticMarkup(
      <EmbeddingProfilePanel
        catalog={[]}
        connections={[]}
        error=""
        installedModels={[]}
        locale="zh-TW"
        onActivate={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onOllamaDelete={vi.fn()}
        onOllamaPull={vi.fn()}
        onProbe={vi.fn()}
        onRefresh={vi.fn()}
        pending
        profiles={[]}
      />,
    );

    expect(markup).toContain("資料查找模型");
    expect(markup).toContain("重新整理");
    expect(markup).toContain("正在處理資料查找模型…");
    expect(markup).not.toContain("�");
  });
});
