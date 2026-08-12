import { createElement } from "../../../../apps/web/node_modules/react/index.js";
import { renderToStaticMarkup } from "../../../../apps/web/node_modules/react-dom/server.js";
import { describe, expect, it, vi } from "vitest";

import { AdminWorkspace, type AdminWorkspaceProps } from "../../../../apps/web/src/features/admin/AdminWorkspace";

function props(overrides: Partial<AdminWorkspaceProps> = {}): AdminWorkspaceProps {
  return {
    locale: "zh-TW",
    draft: "schema_version: 1\nsecret-canary: unsaved",
    validation: null,
    preview: {
      profile: { en: { display_name: "EN-only", headline: "No fallback", bio: "No fallback" } },
      character: { mode: "builtin", revision: 3, png_base64: "abc" },
      cards: {},
    },
    status: null,
    snippet: null,
    conflict: null,
    busy: false,
    authenticated: true,
    onDraftChange: vi.fn(),
    onValidate: vi.fn(),
    onPreview: vi.fn(),
    onSave: vi.fn(),
    onCopy: vi.fn(),
    onDispatch: vi.fn(),
    onLogout: vi.fn(),
    ...overrides,
  };
}

describe("fresh Phase 4 AdminWorkspace probe", () => {
  it("keeps locale preview exact and denies save until valid or after conflict/logout", () => {
    const untranslated = renderToStaticMarkup(createElement(AdminWorkspace, props()));
    expect(untranslated).not.toContain("EN-only");
    expect(untranslated).toMatch(/<button[^>]*disabled[^>]*>[^<]*<\/button>/);

    const conflict = renderToStaticMarkup(
      createElement(
        AdminWorkspace,
        props({
          validation: { valid: true, errors: [], warnings: [] },
          conflict: { current_blob_sha: "fresh-conflict" },
        }),
      ),
    );
    expect(conflict).toContain('id="admin-conflict"');
    expect(conflict).toContain('role="alert"');
    expect(conflict).toMatch(/<button[^>]*disabled[^>]*>[^<]*<\/button>/);

    const loggedOut = renderToStaticMarkup(
      createElement(AdminWorkspace, props({ authenticated: false })),
    );
    expect(loggedOut).toContain('role="alert"');
    expect(loggedOut).toMatch(/<textarea[^>]*disabled[^>]*>/);
  });
});
