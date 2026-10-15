import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { AdminWorkspace, type AdminWorkspaceProps } from "./AdminWorkspace";

// Node omits overlay portals. Expose authored popover content for the existing
// markup assertions; browser focus and dismissal still need browser checks.
vi.mock("react-aria-components", async (importOriginal) => {
  const rac = await importOriginal<typeof import("react-aria-components")>();
  return {
    ...rac,
    Popover: ({ children }: { children: ReactNode }) => <>{children}</>,
  };
});

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
  it("uses the active canonical character for its guide and falls back before publication", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          activeCharacter: {
            mode: "custom",
            revision: 42,
            asset_url: "/api/public/character.png?rev=42",
            frame_duration_ms: 160,
            movement: "none",
          },
        })}
      />,
    );
    expect(markup).toContain("/api/public/character.png?rev=42");
    expect(markup).not.toContain('class="admin-workspace__npc"');
    expect(renderToStaticMarkup(<AdminWorkspace {...props()} />)).toContain(
      'class="admin-workspace__npc"',
    );
  });
  it("renders semantic editable, validation, preview, publication, and snippet regions", () => {
    const markup = renderToStaticMarkup(<AdminWorkspace {...props()} />);

    expect(markup).toContain("RepoNPC admin workspace");
    expect(markup).toContain('class="admin-workspace__title"');
    expect(markup).toContain('aria-labelledby="admin-draft-heading"');
    expect(markup).toContain('aria-labelledby="admin-validation-heading"');
    expect(markup).toContain('aria-labelledby="admin-preview-heading"');
    expect(markup).toContain('aria-labelledby="admin-status-heading"');
    expect(markup).toContain('aria-labelledby="admin-snippet-heading"');
    expect(markup).toContain('aria-label="Unsaved character preview"');
    expect(markup).toContain(
      'aria-label="Unsaved RepoNPC card preview: light-en"',
    );
    expect(markup).not.toContain("data:image/png;base64");
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
      /<button[^>]*disabled[^>]*>Save to GitHub<\/button>/,
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
      /<button[^>]*disabled[^>]*>Save to GitHub<\/button>/,
    );
  });

  it("keeps local tools usable while GitHub-backed actions are unavailable", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ githubOperationsReady: false })} />,
    );

    expect(markup).toMatch(/<button[^>]*>Validate configuration<\/button>/);
    expect(markup).toMatch(/<button[^>]*>Preview changes<\/button>/);
    expect(markup).toMatch(
      /<button[^>]*disabled[^>]*>Save to GitHub<\/button>/,
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

  it("renders the localized workspace shell and language controls", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ onLocaleChange: vi.fn() })} />,
    );

    expect(markup).toContain("Set up AI models and sources");
    expect(markup).toContain("Follow the steps");
    expect(markup).toContain('aria-label="Interface language"');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain("Setup guide");
    expect(markup).toContain('aria-label="Display settings"');
    expect(markup).toMatch(
      /<button(?=[^>]*aria-label="Display settings")(?=[^>]*aria-expanded="false")[^>]*>/,
    );
    expect(markup).toContain('role="dialog"');
    expect(markup).not.toContain('<details class="admin-display-settings"');
    expect(markup).toContain('id="admin-interface-scale"');
    expect(markup).toContain("Standard (100%)");
    expect(markup).toContain("Large (125%)");
    expect(markup).toContain("Comfortable (default, 112.5%)");
    expect(markup).toContain("Administrator");
  });

  it("gives ordinary character setup its own workspace and keeps raw YAML advanced", () => {
    const guided = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <section id="guided-fixture">Start guided setup</section>,
          characterAssetView: (
            <section id="character-fixture">Upload character art</section>
          ),
          workspaceMode: "guided",
          onWorkspaceModeChange: vi.fn(),
        })}
      />,
    );
    expect(guided).toContain('id="guided-fixture"');
    expect(guided).toContain("Character &amp; animation");
    expect(guided).not.toContain('id="character-fixture"');
    expect(guided).not.toContain('id="admin-config-draft"');

    const character = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <section id="guided-fixture">Start guided setup</section>,
          characterAssetView: (
            <section id="character-fixture">Upload character art</section>
          ),
          workspaceMode: "character",
          onWorkspaceModeChange: vi.fn(),
        })}
      />,
    );
    expect(character).toContain('id="character-fixture"');
    expect(character).not.toContain('id="guided-fixture"');
    expect(character).not.toContain('id="admin-config-draft"');

    const advanced = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <section id="guided-fixture">Start guided setup</section>,
          characterAssetView: (
            <section id="character-fixture">Upload character art</section>
          ),
          workspaceMode: "advanced",
          onWorkspaceModeChange: vi.fn(),
        })}
      />,
    );
    expect(advanced).not.toContain('id="guided-fixture"');
    expect(advanced).not.toContain('id="character-fixture"');
    expect(advanced).toContain('id="admin-config-draft"');
    expect(advanced).toContain("Advanced: edit raw YAML");
  });

  it("shows only the guided error surface while guided mode is active", () => {
    const guided = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          notice: "Global workspace failure",
          guidedView: <p role="alert">Guided operation failure</p>,
          workspaceMode: "guided",
          onWorkspaceModeChange: vi.fn(),
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
          workspaceMode: "advanced",
          onWorkspaceModeChange: vi.fn(),
        })}
      />,
    );

    expect(advanced).toContain("Global workspace failure");
    expect(advanced).not.toContain("Guided operation failure");
  });
});

it.each(["guided", "advanced", "character", "publish", "maintenance"] as const)(
  "links help to the rendered %s heading",
  (workspaceMode) => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          workspaceMode,
          guidedView: <h2 id="guided-onboarding-heading">Guide</h2>,
          characterAssetView: (
            <h2 id="admin-character-converter-heading">Character</h2>
          ),
          publicationView: <h2 id="local-publication-heading">Publication</h2>,
          maintenanceView: <h2 id="admin-maintenance-heading">Maintenance</h2>,
        })}
      />,
    );
    const target = markup.match(
      /class="admin-workspace__help" href="#([^"]+)"/,
    )?.[1];
    expect(target).toBeTruthy();
    expect(markup).toContain('id="' + target + '"');
  },
);
