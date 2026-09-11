import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ChatProfilePanel } from "./ChatProfilePanel";

describe("ChatProfilePanel", () => {
  it("keeps model setup provider-neutral and makes testing explicit", () => {
    const markup = renderToStaticMarkup(
      <ChatProfilePanel
        connections={[
          {
            connection_id: "chat-gateway",
            display_name: "Private chat gateway",
            provider: "openai_compatible",
            source: "managed",
            revision: 2,
            endpoint_configured: true,
            key_configured: true,
            status: "configured",
          },
        ]}
        error=""
        locale="en"
        onActivate={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onProbe={vi.fn()}
        onRefresh={vi.fn()}
        onUpdate={vi.fn()}
        pending={false}
        profiles={[
          {
            profile_id: "chat-profile",
            connection_id: "chat-gateway",
            connection_revision: 2,
            model_id: "chat-model",
            status: "ready",
            active: false,
            observed_model_id: "chat-model",
            last_error_code: null,
            last_probed_at: "2026-09-10T00:00:00Z",
          },
        ]}
      />,
    );

    expect(markup).toContain("Chat models");
    expect(markup).toContain("Private chat gateway");
    expect(markup).toContain("Test connection");
    expect(markup).toContain("Use for Chat");
    expect(markup).not.toContain("base_url");
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain('type="password"');
  });

  it("offers service setup before model selection when no connection exists", () => {
    const markup = renderToStaticMarkup(
      <ChatProfilePanel
        connections={[]}
        error=""
        locale="en"
        onActivate={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onProbe={vi.fn()}
        onRefresh={vi.fn()}
        onUpdate={vi.fn()}
        pending={false}
        profiles={[]}
      />,
    );

    expect(markup).toContain("Configure a model service first.");
    expect(markup).not.toContain('id="chat-profile-model"');
  });
});
