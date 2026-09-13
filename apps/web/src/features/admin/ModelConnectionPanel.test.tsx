import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ModelConnectionPanel } from "./ModelConnectionPanel";

describe("ModelConnectionPanel", () => {
  it("shows safe metadata and an explicit credential-removal path", () => {
    const markup = renderToStaticMarkup(
      <ModelConnectionPanel
        connections={[
          {
            connection_id: "gateway",
            display_name: "Gateway",
            provider: "openai_compatible",
            source: "managed",
            revision: 3,
            endpoint_configured: true,
            key_configured: true,
            status: "configured",
          },
        ]}
        error=""
        locale="en"
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onRefresh={vi.fn()}
        onUpdate={vi.fn()}
        pending={false}
      />,
    );

    expect(markup).toContain("Gateway");
    expect(markup).toContain("Edit");
    expect(markup).toContain('class="model-brand-icon"');
    expect(markup).toContain("OpenAI-compatible");
    expect(markup).not.toContain("unpkg.com");
    expect(markup).not.toContain("https://");
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain("MODEL_API_KEY");
    expect(markup).toContain('class="model-connection-form"');
    expect(markup).toContain('class="model-connection-form__actions"');
  });

  it("provides connection deletion in guided setup", () => {
    const markup = renderToStaticMarkup(
      <ModelConnectionPanel
        connections={[
          {
            connection_id: "gateway",
            display_name: "Gateway",
            provider: "openai_compatible",
            source: "managed",
            revision: 3,
            endpoint_configured: true,
            key_configured: true,
            status: "configured",
          },
        ]}
        error=""
        locale="en"
        managementActions={false}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onRefresh={vi.fn()}
        onUpdate={vi.fn()}
        pending={false}
      />,
    );

    expect(markup).toContain("Edit");
    expect(markup).toContain(">Delete setting<");
    expect(markup).toContain('aria-label="Delete setting: Gateway"');
  });

  it("lets the owner replace or delete the host-provided service for this role", () => {
    const hostConnection = (
      purpose: "chat" | "embedding",
    ): Parameters<typeof ModelConnectionPanel>[0]["connections"][number] => ({
      connection_id: `environment-${purpose}`,
      display_name: `Environment ${purpose}`,
      provider: "ollama",
      source: "host-managed",
      revision: 1,
      endpoint_configured: true,
      key_configured: false,
      status: "configured",
    });
    const markup = renderToStaticMarkup(
      <ModelConnectionPanel
        connections={[hostConnection("chat"), hostConnection("embedding")]}
        error=""
        locale="zh-TW"
        managementActions={false}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onRefresh={vi.fn()}
        onUpdate={vi.fn()}
        pending={false}
        purpose="chat"
      />,
    );

    expect(markup).toContain("環境預設連線（回答）");
    expect(markup).toContain("不是 RepoNPC 內建的 AI 服務");
    expect(markup).toContain("你可以在這裡覆寫或刪除");
    expect(markup).toContain(">編輯<");
    expect(markup).toContain(">刪除設定<");
    expect(markup).toContain('aria-label="刪除設定: 環境預設連線（回答）"');
    expect(markup).not.toContain("Environment embedding");
    expect(markup).not.toContain("環境預設連線（資料查找）");
  });
});
