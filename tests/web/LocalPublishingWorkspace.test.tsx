import { renderToStaticMarkup } from "../../apps/web/node_modules/react-dom/server";
import { createElement } from "../../apps/web/node_modules/react";
import { describe, expect, it, vi } from "vitest";

import {
  LocalPublishingWorkspace,
  type LocalDraftBody,
} from "../../apps/web/src/features/admin/LocalPublishingWorkspace";
import { previewInputsMatch } from "../../apps/web/src/features/admin/sharing";

type Request = <T>(path: string, options?: RequestInit) => Promise<T>;

function props(
  overrides: Partial<{
    locale: "zh-TW" | "en";
    content: string;
    spriteBase64: string | null;
    revision: string | null;
    initialAccount: string;
    selection: {
      selection: {
        chat_profile_id: string | null;
        embedding_profile_id: string | null;
        generation: number;
        updated_at: string;
      };
      eligible: boolean;
      reason: string;
    } | null;
    request: Request;
    onStored: (body: LocalDraftBody) => void;
    onCreateDraft: () => void;
  }> = {},
) {
  return {
    locale: "en" as const,
    content: "schema_version: 1\n",
    spriteBase64: null,
    revision: "a".repeat(64),
    initialAccount: "octo-lab",
    selection: {
      selection: {
        chat_profile_id: "chat-profile",
        embedding_profile_id: "embedding-profile",
        generation: 3,
        updated_at: "2026-09-23T00:00:00Z",
      },
      eligible: true,
      reason: "",
    },
    request: vi.fn(
      async (_path: string, _options?: RequestInit): Promise<unknown> => ({}),
    ) as unknown as Request,
    onStored: vi.fn(),
    onCreateDraft: vi.fn(),
    ...overrides,
  };
}

function renderWorkspace(overrides: Parameters<typeof props>[0] = {}): string {
  return renderToStaticMarkup(
    createElement(LocalPublishingWorkspace, props(overrides)),
  );
}

describe("LocalPublishingWorkspace", () => {
  it("keeps local preparation available while sharing waits for a public URL", () => {
    const markup = renderWorkspace();

    expect(markup).toContain(
      "Preview your portfolio and card, save the draft, then prepare or update the NPC.",
    );
    expect(markup).toContain(
      "You can finish the local trial and card image before getting a public URL.",
    );
    expect(markup).toMatch(/<button[^>]*>Prepare and apply NPC<\/button>/);
    expect(markup).toContain("No public visitor link is ready yet.");
    expect(markup).toContain(
      "The local publication status is unknown right now; check again shortly.",
    );
    expect(markup).not.toContain("Local NPC has not been prepared.");
  });

  it("normalizes a profile URL before rendering account links", () => {
    const markup = renderWorkspace({
      initialAccount: "https://github.com/octo-lab/",
    });

    expect(markup).toContain('value="octo-lab"');
    expect(markup).toContain("https://github.com/octo-lab/octo-lab");
    expect(markup).not.toContain("https://github.com/https://github.com");
  });

  it("accepts sprite changes as preview input changes", () => {
    expect(previewInputsMatch("draft", "sprite-a", "draft", "sprite-a")).toBe(
      true,
    );
    expect(previewInputsMatch("draft", "sprite-a", "draft", "sprite-b")).toBe(
      false,
    );
    expect(previewInputsMatch("draft", null, "changed", null)).toBe(false);
  });
});
