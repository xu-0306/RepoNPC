import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";

import { AdminAccessPanel } from "./AdminPage";
import { AdminWorkspace } from "./AdminWorkspace";
import { MaintenancePanel } from "./MaintenancePanel";

const css = readFileSync(new URL("../../p4-w4.css", import.meta.url), "utf8");
const noop = () => {};

it.each(["zh-TW", "en"])(
  "keeps pixel sign-in controls and alerts accessible in %s",
  (locale) => {
    const markup = renderToStaticMarkup(
      <AdminAccessPanel
        locale={locale}
        busy={false}
        error="Fixture error"
        passwordAvailable
        setupStatus={{ setup_required: false, setup_code_available: false }}
        setupStatusPending={false}
        username=""
        password=""
        setupCode=""
        setupPassword=""
        setupPasswordConfirmation=""
        onUsernameChange={noop}
        onPasswordChange={noop}
        onSetupCodeChange={noop}
        onSetupPasswordChange={noop}
        onSetupPasswordConfirmationChange={noop}
        onLogin={noop}
        onSetupOwner={noop}
        onRefreshSetupStatus={noop}
      />,
    );
    expect(markup).toContain(
      'class="admin-auth-card px-panel px-panel--raised"',
    );
    expect(markup).toContain(
      'class="admin-auth__scene px-scene" aria-hidden="true"',
    );
    expect(markup).toContain('aria-labelledby="admin-access-heading"');
    expect(markup).toContain('role="alert">Fixture error');
    for (const id of ["admin-username", "admin-password"]) {
      expect(markup).toContain(`for="${id}"`);
      expect(markup).toMatch(
        new RegExp(`<input[^>]*class="px-field"[^>]*id="${id}"`),
      );
    }
    expect(markup).toContain(
      'class="px-button px-button--primary" type="submit"',
    );
    expect(markup).toContain(
      locale === "en" ? "never pushed to GitHub" : "不會推送到 GitHub",
    );
    expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
  },
);

it.each(["zh-TW", "en"])(
  "retains YAML validation, unsaved status and snippet in %s",
  (locale) => {
    const markup = renderToStaticMarkup(
      <AdminWorkspace
        locale={locale}
        draft="schema_version: 1"
        validation={{
          valid: false,
          errors: [{ path: "profile.bio", message: "Required" }],
        }}
        preview={{
          profile: {
            display_name: "Fixture",
            headline: "Heading",
            bio: "Body",
          },
        }}
        status={{ active_bundle_id: "fixture-version" }}
        snippet="Fixture Markdown"
        busy={false}
        authenticated
        notice=""
        onDraftChange={noop}
        onValidate={noop}
        onPreview={noop}
        onCopy={noop}
        onLogout={noop}
        embeddingProfileView={<p>Fixture model information</p>}
      />,
    );
    for (const id of ["draft", "validation", "preview", "status", "snippet"])
      expect(markup).toContain(`aria-labelledby="admin-${id}-heading"`);
    expect(markup).toContain(
      'class="admin-workspace__yaml px-panel px-panel--raised"',
    );
    expect(markup).toContain(
      'class="admin-workspace__preview-banner px-badge" role="status"',
    );
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("profile.bio");
    expect(markup).toContain("Required");
    expect(markup).toContain("fixture-version");
    expect(markup).toContain("Fixture Markdown");
    expect(markup).toContain(
      '<details class="admin-workspace__yaml-model-info px-info">',
    );
    expect(markup).toContain(
      locale === "en" ? "Models and device information" : "模型與裝置資訊",
    );
    expect(markup.indexOf("Fixture model information")).toBeGreaterThan(
      markup.indexOf('id="admin-validation-heading"'),
    );
    expect(markup).toContain('class="px-button px-button--primary"');
    expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
  },
);

it.each(["zh-TW", "en"])(
  "keeps maintenance consent, scope and busy feedback in %s",
  (locale) => {
    const onRestore = vi.fn();
    const markup = renderToStaticMarkup(
      <MaintenancePanel
        locale={locale}
        status={{
          active_bundle_id: "current",
          previous_bundle_id: "previous",
          pinned_bundle_id: null,
          last_backup_at: null,
          local_ready: true,
          gateway_configured: true,
          externally_verified: false,
        }}
        pending
        notice="Fixture pending"
        restorePreview={{
          preview_id: "fixture-preview",
          created_at: "2026-10-01T00:00:00Z",
          application_version: "1.0",
          schema_version: 1,
          expires_at: "2099-10-24T00:00:00Z",
        }}
        onRefresh={noop}
        onBackup={noop}
        onInspect={noop}
        onRestore={onRestore}
        onCancelRestore={noop}
        onPinPrevious={noop}
        onStopGateway={noop}
      />,
    );
    expect(markup).toContain(
      'class="admin-maintenance px-panel px-panel--raised"',
    );
    expect(markup).toContain('aria-labelledby="admin-maintenance-heading"');
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain('class="px-badge"');
    expect(markup).toContain('class="px-button px-button--danger"');
    expect(markup).toContain(
      locale === "en"
        ? "replaces the current SQLite settings"
        : "取代目前的 SQLite 設定",
    );
    expect(markup).toContain(locale === "en" ? "same host" : "同一台主機");
    expect(markup).toContain(
      'role="status" aria-live="polite">Fixture pending',
    );
    expect(markup).not.toContain('checked=""');
    expect(markup).not.toMatch(/style="[^"]*(?:color|background)/);
    expect(onRestore).not.toHaveBeenCalled();
  },
);

it("uses token colours, square corners, readable text and visible focus", () => {
  expect(css).not.toMatch(
    /#[\da-f]{3,8}\b|\b(?:rgb|hsl)a?\s*\(|!important|https?:/i,
  );
  expect(css).not.toMatch(/font-size:\s*(?:[0-9]|1[0-2])px/);
  expect(css).toContain("outline: 3px solid var(--px-focus)");
  expect(css).toContain("white-space: pre-line");
  expect(css).toMatch(
    /\.admin-confirm-dialog__description\s*\{[^}]*white-space: pre-line/s,
  );
  // Only the modal backdrop scrolls, keeping long confirmations reachable.
  const pageRules = css.replace(
    /\.admin-confirm-overlay\.admin-confirm-overlay\s*\{[^}]*\}/,
    "",
  );
  expect(pageRules).not.toMatch(/overflow(?:-y)?:\s*(?:auto|scroll)/);
});
