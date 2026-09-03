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

    expect(markup).toContain("Embedding model center");
    expect(markup).toContain("qwen3-embedding:0.6b");
    expect(markup).toContain("Recommended starter");
    expect(markup).toContain("Approved Ollama catalog");
    expect(markup).toContain("Installed on the configured Ollama host");
    expect(markup).toContain("Apache-2.0");
    expect(markup).toContain("live probe remains authoritative");
    expect(markup).toContain("Probe");
    expect(markup).not.toContain("base_url");
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain('type="password"');
    expect(markup).toContain('<select id="embedding-profile-model"');
  });

  it("renders readable Traditional Chinese copy", () => {
    const markup = renderToStaticMarkup(
      <EmbeddingProfilePanel
        catalog={[]}
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

    expect(markup).toContain("Embedding 模型中心");
    expect(markup).toContain("重新整理");
    expect(markup).toContain("正在處理 embedding profile…");
    expect(markup).not.toContain("�");
  });
});
