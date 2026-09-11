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
    expect(markup).not.toContain("https://");
    expect(markup).not.toContain("api_key");
    expect(markup).not.toContain("MODEL_API_KEY");
  });
});
