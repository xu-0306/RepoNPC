import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { AdminWorkspace, type AdminWorkspaceProps } from "./AdminWorkspace";

function props(
  overrides: Partial<AdminWorkspaceProps> = {},
): AdminWorkspaceProps {
  return {
    locale: "en",
    draft: "schema_version: 1\n",
    validation: { valid: true, errors: [], warnings: [] },
    preview: {
      profile: {
        en: {
          display_name: "Ada",
          headline: "Builder",
          bio: "Evidence-backed work.",
        },
      },
      character: { mode: "builtin", revision: 1, png_base64: "abc" },
      cards: { "light-en": { png_base64: "card" } },
    },
    status: {
      active_bundle_id: "bundle-1",
      previous_bundle_id: null,
      pinned_bundle_id: null,
      last_checked_at: "2026-08-13T00:00:00Z",
      update_error: null,
    },
    snippet: {
      markdown:
        "[![RepoNPC](https://example.test/card.png)](https://example.test)",
    },
    conflict: null,
    busy: false,
    authenticated: true,
    githubOperationsReady: true,
    notice: "",
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

describe("AdminWorkspace", () => {
  it("renders semantic editable, validation, preview, publication, and snippet regions", () => {
    const markup = renderToStaticMarkup(<AdminWorkspace {...props()} />);

    expect(markup).toContain("RepoNPC admin workspace");
    expect(markup).toContain('class="admin-workspace__title"');
    expect(markup).toContain('aria-labelledby="admin-draft-heading"');
    expect(markup).toContain('aria-labelledby="admin-validation-heading"');
    expect(markup).toContain('aria-labelledby="admin-preview-heading"');
    expect(markup).toContain('aria-labelledby="admin-status-heading"');
    expect(markup).toContain('aria-labelledby="admin-snippet-heading"');
    expect(markup).toContain('alt="Unsaved character preview"');
    expect(markup).toContain("Unsaved preview");
    expect(markup).toContain("bundle-1");
    expect(markup).toContain("Copy snippet");
  });

  it("keeps field errors and warnings distinguishable with accessible roles", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          validation: {
            valid: false,
            errors: [
              { path: "profile.bio.en", code: "required", message: "Required" },
            ],
            warnings: [
              {
                path: "card.revision",
                message: "Consider increasing revision",
              },
            ],
          },
        })}
      />,
    );

    expect(markup).toContain('role="alert"');
    expect(markup).toContain('aria-label="Errors"');
    expect(markup).toContain('role="status"');
    expect(markup).toContain('aria-label="Warnings"');
    expect(markup).toContain("profile.bio.en");
    expect(markup).toContain("Consider increasing revision");
  });

  it("disables save on conflict and all editing actions when unauthenticated", () => {
    const conflictMarkup = renderToStaticMarkup(
      <AdminWorkspace {...props({ conflict: { current_blob_sha: "sha" } })} />,
    );
    expect(conflictMarkup).toContain("saving is disabled");
    expect(conflictMarkup).toMatch(
      /<button[^>]*disabled[^>]*>Save configuration<\/button>/,
    );

    const signedOutMarkup = renderToStaticMarkup(
      <AdminWorkspace {...props({ authenticated: false })} />,
    );
    expect(signedOutMarkup).toContain('role="alert"');
    expect(signedOutMarkup).toContain("Sign in to an admin session");
    expect(signedOutMarkup).toMatch(/<textarea[^>]*disabled[^>]*>/);
  });

  it("does not cross-fallback a preview profile into another locale", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ locale: "zh-TW" })} />,
    );

    expect(markup).not.toContain("Ada");
    expect(markup).toContain("未儲存預覽");
  });

  it("keeps save disabled until validation explicitly passes", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ validation: null })} />,
    );

    expect(markup).toMatch(
      /<button[^>]*disabled[^>]*>Save configuration<\/button>/,
    );
  });

  it("keeps local tools usable while GitHub-backed actions are unavailable", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ githubOperationsReady: false })} />,
    );

    expect(markup).toMatch(/<button[^>]*>Validate configuration<\/button>/);
    expect(markup).toMatch(/<button[^>]*>Preview changes<\/button>/);
    expect(markup).toMatch(
      /<button[^>]*disabled[^>]*>Save configuration<\/button>/,
    );
    expect(markup).toMatch(
      /<button[^>]*disabled[^>]*>Request index publication<\/button>/,
    );
  });

  it("keeps degraded-operation notices inside the workspace", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          notice:
            "You are signed in, but GitHub management operations are not configured.",
        })}
      />,
    );

    expect(markup).toContain('class="admin-workspace__notice"');
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("GitHub management operations are not configured");
  });

  it("keeps Traditional Chinese and English presentation text complete", () => {
    const zhMarkup = renderToStaticMarkup(
      <AdminWorkspace {...props({ locale: "zh-TW" })} />,
    );
    expect(zhMarkup).toContain("RepoNPC 管理工作區");
    expect(zhMarkup).toContain("未儲存預覽");
    expect(zhMarkup).toContain("README 複製片段");
  });

  it("defaults to guided content and keeps raw YAML behind advanced mode", () => {
    const guided = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <section id="guided-fixture">Start guided setup</section>,
          advancedMode: false,
          onAdvancedModeChange: vi.fn(),
        })}
      />,
    );
    expect(guided).toContain('id="guided-fixture"');
    expect(guided).toContain('aria-pressed="true"');
    expect(guided).not.toContain('id="admin-config-draft"');

    const advanced = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <section id="guided-fixture">Start guided setup</section>,
          advancedMode: true,
          onAdvancedModeChange: vi.fn(),
        })}
      />,
    );
    expect(advanced).not.toContain('id="guided-fixture"');
    expect(advanced).toContain('id="admin-config-draft"');
    expect(advanced).toContain("Advanced: edit raw YAML");
  });

  it("shows only the guided error surface while guided mode is active", () => {
    const guided = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          notice: "Global workspace failure",
          guidedView: <p role="alert">Guided operation failure</p>,
          advancedMode: false,
          onAdvancedModeChange: vi.fn(),
        })}
      />,
    );

    expect(guided).toContain("Guided operation failure");
    expect(guided).not.toContain("Global workspace failure");
    expect(guided.match(/role="alert"/g)).toHaveLength(1);

    const advanced = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          notice: "Global workspace failure",
          guidedView: <p role="alert">Guided operation failure</p>,
          advancedMode: true,
          onAdvancedModeChange: vi.fn(),
        })}
      />,
    );

    expect(advanced).toContain("Global workspace failure");
    expect(advanced).not.toContain("Guided operation failure");
  });
});
