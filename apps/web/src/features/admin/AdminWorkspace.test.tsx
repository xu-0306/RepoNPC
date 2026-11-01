import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { AdminWorkspace, type AdminWorkspaceProps } from "./AdminWorkspace";
import { OnboardingStepper } from "./OnboardingStepper";
import { GUIDED_PROGRESS_COPY } from "./GuidedOnboardingView";
import { initialGuidedOnboardingState } from "./guidedOnboarding";

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
    },
    snippet: {
      markdown:
        "[![RepoNPC](https://example.test/card.png)](https://example.test)",
    },
    busy: false,
    authenticated: true,
    notice: "",
    onDraftChange: vi.fn(),
    onValidate: vi.fn(),
    onPreview: vi.fn(),
    onCopy: vi.fn(),
    onLogout: vi.fn(),
    ...overrides,
  };
}

describe("AdminWorkspace", () => {
  it.each([
    ["zh-TW", "RepoNPC 管理工作區"],
    ["en", "RepoNPC admin workspace"],
  ] as const)(
    "keeps the brand paragraph unnamed and the navigation named in %s",
    (locale, title) => {
      const markup = renderToStaticMarkup(
        <AdminWorkspace
          {...props({ locale, guidedView: <h1>Page purpose</h1> })}
        />,
      );
      expect(markup).toContain('<p class="admin-workspace__title">RepoNPC</p>');
      expect(markup).not.toMatch(/<p\b[^>]*aria-label=/);
      expect(markup).toContain(
        `<nav aria-label="${title}" class="admin-workspace__modes">`,
      );
      expect(markup.match(/<main\b/g)).toHaveLength(1);
      expect(markup.match(/<header\b/g)).toHaveLength(1);
      const landmarks = [...markup.matchAll(/<(main|nav|header)\b[^>]*>/g)];
      const names = landmarks.map((landmark) => {
        const name = landmark[0].match(/aria-label="([^"]*)"/);
        if (!name) return landmark[1];
        expect(name[1].trim()).not.toBe("");
        return `${landmark[1]}:${name[1]}`;
      });
      expect(new Set(names).size).toBe(names.length);
    },
  );

  it("uses only the active canonical character on the static scene strip", () => {
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
    expect(markup).toContain('data-reduced-motion="true"');
    expect(markup).toContain('data-character-state="idle"');
    const empty = renderToStaticMarkup(<AdminWorkspace {...props()} />);
    expect(empty).toContain('class="admin-workspace__scene px-scene"');
    expect(empty).not.toContain('class="px-scene__npc"');
    expect(empty).not.toContain("character-renderer");
  });
  it("renders semantic editable, validation, preview, publication, and snippet regions", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({ guidedView: <div />, workspaceMode: "advanced" })}
      />,
    );

    expect(markup).toContain(
      '<nav aria-label="RepoNPC admin workspace" class="admin-workspace__modes">',
    );
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

  it("disables editing actions when unauthenticated", () => {
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

  it("keeps local validation and preview tools usable", () => {
    const markup = renderToStaticMarkup(<AdminWorkspace {...props()} />);

    expect(markup).toMatch(/<button[^>]*>Check configuration<\/button>/);
    expect(markup).toMatch(/<button[^>]*>Preview changes<\/button>/);
  });

  it("keeps degraded-operation notices inside the workspace", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          notice:
            "You are signed in, but local portfolio management is not ready.",
        })}
      />,
    );

    expect(markup).toContain('class="admin-workspace__notice"');
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("local portfolio management is not ready");
  });

  it("keeps Traditional Chinese and English presentation text complete", () => {
    const zhMarkup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          locale: "zh-TW",
          guidedView: <div />,
          workspaceMode: "advanced",
        })}
      />,
    );
    expect(zhMarkup).toContain(
      '<nav aria-label="RepoNPC 管理工作區" class="admin-workspace__modes">',
    );
    expect(zhMarkup).toContain("未儲存預覽");
    expect(zhMarkup).toContain("README 複製片段");
  });

  it("renders the localized workspace shell and language controls", () => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ onLocaleChange: vi.fn() })} />,
    );

    expect(markup).toContain("Pixel Workshop");
    expect(markup).not.toContain("Follow the steps");
    expect(markup).not.toContain("admin-workspace__speech");
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

it.each(["guided", "character", "publish", "advanced", "maintenance"] as const)(
  "keeps shell landmark order and the quest rail in %s mode",
  (workspaceMode) => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          workspaceMode,
          busy: true,
          onLocaleChange: vi.fn(),
          guidedView: <h2 id="guided-onboarding-heading">Guide</h2>,
          characterAssetView: (
            <h2 id="admin-character-converter-heading">Character</h2>
          ),
          publicationView: <h2 id="local-publication-heading">Publish</h2>,
          maintenanceView: <h2 id="admin-maintenance-heading">Maintenance</h2>,
          questRail: (
            <OnboardingStepper
              copy={GUIDED_PROGRESS_COPY.en}
              locale="en"
              state={{ ...initialGuidedOnboardingState(), step: "analysis" }}
            />
          ),
        })}
      />,
    );
    const header = markup.indexOf("<header");
    const modes = markup.indexOf('class="admin-workspace__modes"');
    const rail = markup.indexOf('class="onboarding-stepper');
    const content = markup.indexOf('<main class="admin-workspace__content"');
    expect(header).toBeLessThan(modes);
    expect(modes).toBeLessThan(rail);
    expect(rail).toBeLessThan(content);
    const tabs = markup
      .slice(modes, rail)
      .match(
        /<button[^>]+class="px-tab(?: admin-workspace__advanced-tab)?"[^>]*>/g,
      )!;
    expect(tabs).toHaveLength(5);
    expect(
      tabs.filter((tab) => tab.includes("admin-workspace__advanced-tab")),
    ).toHaveLength(1);
    expect(tabs.every((tab) => tab.includes('disabled=""'))).toBe(true);
    expect(
      tabs.filter((tab) => tab.includes('aria-pressed="true"')),
    ).toHaveLength(1);
    expect(markup).toContain('aria-label="Interface language"');
    expect(markup).toContain('aria-label="Display settings"');
    expect(markup).toContain("Administrator");
    expect(markup).toContain("Log out");
  },
);

it("keeps optional modes conditional and uses full width when the rail has no applicable step", () => {
  for (const step of ["intro", "draft"] as const) {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        {...props({
          guidedView: <h2 id="guided-onboarding-heading">Guide</h2>,
          questRail: (
            <OnboardingStepper
              copy={GUIDED_PROGRESS_COPY.en}
              locale="en"
              state={{ ...initialGuidedOnboardingState(), step }}
            />
          ),
        })}
      />,
    );
    expect(markup).not.toContain('class="onboarding-stepper');
    expect(markup).not.toContain("Preview &amp; share");
    expect(markup).not.toContain(">Maintenance<");
    expect(
      markup.match(/class="px-tab(?: admin-workspace__advanced-tab)?"/g),
    ).toHaveLength(3);
    expect(
      markup.match(/class="px-tab admin-workspace__advanced-tab"/g),
    ).toHaveLength(1);
  }
});

it.each([
  ["zh-TW", "顯示設定", "使用說明", "管理員", "登出"],
  ["en", "Display settings", "Setup guide", "Administrator", "Log out"],
] as const)(
  "keeps full accessible utility names when the %s phone header shows icons",
  (locale, display, help, owner, logout) => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace {...props({ locale, onLocaleChange: vi.fn() })} />,
    );
    const header = markup.slice(
      markup.indexOf("<header"),
      markup.indexOf("</header>"),
    );
    expect(
      header.match(/class="admin-workspace__utility-label"/g),
    ).toHaveLength(3);
    expect(header).toMatch(
      new RegExp(`<button[^>]*aria-label="${display}"[^>]*>`),
    );
    expect(header).toContain(
      `<span class="admin-workspace__utility-label">${display}</span>`,
    );
    expect(header).toMatch(
      new RegExp(
        `<a class="admin-workspace__help"[^>]*><span aria-hidden="true">\\?</span><span class="admin-workspace__utility-label">${help}</span></a>`,
      ),
    );
    expect(header).toContain(
      `<span aria-hidden="true">R</span><span class="admin-workspace__utility-label">${owner}</span>`,
    );
    expect(header).toContain(`aria-label="${owner}"`);
    expect(header).toMatch(
      new RegExp(
        `<button class="admin-workspace__logout[^>]*>${logout}</button>`,
      ),
    );
    expect(header).toContain('aria-label="繁體中文"');
    expect(header).toContain('aria-label="English"');
    expect(header).not.toMatch(
      /class="admin-workspace__utility-label"[^>]*aria-hidden/,
    );
  },
);
