import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  AdminAccessPanel,
  GitHubConnectionPanel,
  safeDraftForSessionStorage,
} from "./AdminPage";
import { adminErrorStateReducer, initialAdminErrorState } from "./adminErrors";
import {
  GitHubOAuthSetupGuideDialog,
  type GitHubOAuthSetupGuideBody,
} from "./GitHubOAuthSetupGuideDialog";

function renderAccessPanel(
  overrides: Partial<React.ComponentProps<typeof AdminAccessPanel>> = {},
) {
  return renderToStaticMarkup(
    <AdminAccessPanel
      busy={false}
      error=""
      locale="zh-TW"
      onLogin={vi.fn()}
      onPasswordChange={vi.fn()}
      onRefreshSetupStatus={vi.fn()}
      onSetupCodeChange={vi.fn()}
      onSetupOwner={vi.fn()}
      onSetupPasswordChange={vi.fn()}
      onSetupPasswordConfirmationChange={vi.fn()}
      onUsernameChange={vi.fn()}
      password=""
      setupCode=""
      setupPassword=""
      setupPasswordConfirmation=""
      setupStatus={null}
      setupStatusPending={false}
      username=""
      {...overrides}
    />,
  );
}

describe("AdminAccessPanel", () => {
  it("keeps public drafts resumable while rejecting secret-bearing content", () => {
    expect(
      safeDraftForSessionStorage("profile:\n  display_name: Demo\n"),
    ).toContain("display_name");
    expect(
      safeDraftForSessionStorage("provider:\n  api_key: do-not-store\n"),
    ).toBeNull();
  });
  it("shows the complete first-owner form immediately on a fresh runtime", () => {
    const markup = renderAccessPanel({
      setupStatus: {
        setup_required: true,
        setup_code_available: true,
      },
    });

    expect(markup).toContain('data-mode="setup"');
    expect(markup).toContain("這裡沒有預設帳密");
    expect(markup).toContain('id="admin-setup-code"');
    expect(markup).toContain('id="admin-setup-username"');
    expect(markup).toContain('id="admin-setup-password"');
    expect(markup).toContain('maxLength="128"');
    expect(markup).toContain("production 至少 15 個字元");
    expect(markup).toContain("不限制大小寫、數字或符號");
    expect(markup).toContain("建立我的管理員");
    expect(markup).toContain("不會寫入 GitHub");
    expect(markup).not.toContain("使用 GitHub 建立管理員");
    expect(markup).not.toContain('id="admin-username"');
  });

  it("keeps an initialized runtime in sign-in mode without reopening setup", () => {
    const markup = renderAccessPanel({
      locale: "en",
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain('data-mode="login"');
    expect(markup).toContain("no default credentials");
    expect(markup).toContain("never pushed to GitHub");
    expect(markup).toContain('id="admin-username"');
    expect(markup).not.toContain('id="admin-setup-code"');
  });

  it("renders a top-level GitHub OAuth form independently from password sign-in", () => {
    const markup = renderAccessPanel({
      githubAvailable: true,
      locale: "en",
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain('action="/api/admin/session/github/start"');
    expect(markup).toContain("Sign in with GitHub");
    expect(markup).toContain('aria-label="or"');
    expect(markup).toContain('id="admin-password"');
    expect(markup).toContain('class="github-button admin-auth__github-button"');
    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain('focusable="false"');
    expect(markup).not.toContain('aria-hidden="true">GitHub</span>');
  });

  it("keeps an unconfigured GitHub entry point operable for setup guidance", () => {
    const markup = renderAccessPanel({
      locale: "en",
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain("Sign in with GitHub");
    expect(markup).toContain('class="github-button admin-auth__github-button"');
    expect(markup).not.toMatch(
      /class="github-button admin-auth__github-button"[^>]*disabled/,
    );
  });

  it("exposes OAuth redirect progress and exactly one authentication alert", () => {
    const markup = renderAccessPanel({
      error: "GitHub sign-in did not complete. Try again.",
      githubAvailable: true,
      githubPending: true,
      locale: "en",
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain('id="admin-access-heading"');
    expect(markup).toContain('aria-busy="true"');
    expect(markup.match(/role="alert"/g)).toHaveLength(1);
  });

  it("does not flash the login form while setup status is pending", () => {
    const markup = renderAccessPanel({ setupStatusPending: true });

    expect(markup).toContain('data-mode="loading"');
    expect(markup).toContain('role="status"');
    expect(markup).not.toContain('id="admin-username"');
    expect(markup).not.toContain('id="admin-setup-code"');
  });

  it("offers a retry instead of guessing when setup status is unavailable", () => {
    const markup = renderAccessPanel();

    expect(markup).toContain('data-mode="unavailable"');
    expect(markup).toContain("重新檢查");
    expect(markup).not.toContain('id="admin-username"');
  });
});

describe("GitHubConnectionPanel", () => {
  it("uses a labeled password input for PATs without rendering a credential value", () => {
    const markup = renderToStaticMarkup(
      <GitHubConnectionPanel
        connections={[
          {
            id: 7,
            purpose: "identity_public_read",
            github_login: "owner",
            expires_at: null,
            last_validated_at: "2026-08-16T00:00:00Z",
            status: "ready",
          },
        ]}
        error=""
        linkPending={false}
        locale="en"
        oauthAvailable
        onCheck={vi.fn()}
        onDelete={vi.fn()}
        onLink={vi.fn()}
        onPatChange={vi.fn()}
        onSavePat={vi.fn()}
        onUnlink={vi.fn()}
        patToken=""
        pending={false}
      />,
    );

    expect(markup).toContain('id="github-public-read-pat"');
    expect(markup).toContain('type="password"');
    expect(markup).toContain('autoComplete="off"');
    expect(markup).toContain("Reauthenticate GitHub");
    expect(markup).toContain("Unlink GitHub");
    expect(markup).not.toContain("PAT_TOKEN_CANARY");
    expect(markup).toContain('class="github-button"');
  });

  it("explains OAuth unavailability without hiding the connection surface", () => {
    const markup = renderToStaticMarkup(
      <GitHubConnectionPanel
        connections={[]}
        error=""
        linkPending={false}
        locale="en"
        oauthAvailable={false}
        onCheck={vi.fn()}
        onDelete={vi.fn()}
        onLink={vi.fn()}
        onPatChange={vi.fn()}
        onSavePat={vi.fn()}
        onUnlink={vi.fn()}
        patToken="pat-placeholder"
        pending={false}
      />,
    );

    expect(markup).toContain("GitHub connection");
    expect(markup).toContain('role="status"');
    expect(markup).toContain("GitHub OAuth is not configured yet");
    expect(markup).not.toMatch(/id="github-public-read-pat"[^>]*disabled/);
    expect(markup).toContain("Link GitHub");
    expect(markup).not.toMatch(/class="github-button"[^>]*disabled/);
  });
});

describe("GitHubOAuthSetupGuideDialog", () => {
  const guide: GitHubOAuthSetupGuideBody = {
    configured: false,
    callback_url: "http://localhost:8090/api/admin/github/callback",
    documentation_url:
      "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app",
    next_step: "configure_host_secrets_restart_then_recheck",
  };

  it("renders a bilingual-safe, labelled setup guide without credential fields", () => {
    const markup = renderToStaticMarkup(
      <GitHubOAuthSetupGuideDialog
        error=""
        guide={guide}
        locale="en"
        onClose={vi.fn()}
        onRefresh={vi.fn()}
        open
        pending={false}
        returnFocusRef={{ current: null }}
      />,
    );

    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("host-side deployment step");
    expect(markup).toContain(guide.callback_url);
    expect(markup).toContain(guide.documentation_url);
    expect(markup).toContain("Never paste a client secret");
    expect(markup).toContain('target="_blank"');
    expect(markup).not.toContain("CLIENT_SECRET_CANARY");
    expect(markup).not.toContain("OAUTH_TOKEN_CANARY");
  });
});

describe("admin error scopes", () => {
  it("routes guided failures without creating a duplicate global alert", () => {
    const state = adminErrorStateReducer(initialAdminErrorState, {
      type: "SET_GUIDED_ERROR",
      code: "RATE_LIMITED",
    });

    expect(state).toEqual({
      globalMessage: "",
      guidedCode: "RATE_LIMITED",
    });
  });

  it("keeps global and guided errors independently clearable", () => {
    const withGlobalError = adminErrorStateReducer(initialAdminErrorState, {
      type: "SET_GLOBAL_ERROR",
      message: "Admin data could not be loaded.",
    });
    const withBothScopes = adminErrorStateReducer(withGlobalError, {
      type: "SET_GUIDED_ERROR",
      code: "PROVIDER_TIMEOUT",
    });

    expect(
      adminErrorStateReducer(withBothScopes, { type: "CLEAR_GUIDED_ERROR" }),
    ).toEqual({
      globalMessage: "Admin data could not be loaded.",
      guidedCode: "",
    });
    expect(
      adminErrorStateReducer(withBothScopes, { type: "CLEAR_GLOBAL_ERROR" }),
    ).toEqual({
      globalMessage: "",
      guidedCode: "PROVIDER_TIMEOUT",
    });
  });
});
