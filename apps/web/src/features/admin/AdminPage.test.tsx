import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  AdminAccessPanel,
  AdminPage,
  takeLocalLaunchGrant,
  safeDraftForSessionStorage,
} from "./AdminPage";
import { modelConnectionFailureMessage } from "./modelConnectionFeedback";
import { adminErrorStateReducer, initialAdminErrorState } from "./adminErrors";
import { preflightState } from "./batchPreflight";

describe("batch preflight mapping", () => {
  it("preserves the longest safe retry time and transient GitHub state", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-09T00:00:00Z"));
    try {
      expect(
        preflightState({
          plan_id: "plan-safe-identifier",
          expires_at: "2026-09-09T00:05:00Z",
          selection_hash: "a".repeat(64),
          repositories: [],
          cache_predictions: {},
          core_budget: {
            remaining: 24,
            limit: 60,
            reset_at: "2026-09-09T00:01:00Z",
          },
          secondary_retry_at: "2026-09-09T00:01:30Z",
          provider_ready: true,
          capacity: {
            github_requests: 1,
            archive_staging: 1,
            index_work: 1,
            generation: 1,
            whole_job_items: 1,
          },
          maximum_generation_attempts: 1,
          duration: null,
          blockers: [
            { slug: "github", code: "GITHUB_RATE_LIMITED" },
            { slug: "github", code: "GITHUB_TIMEOUT" },
          ],
          warnings: [],
        }),
      ).toEqual({
        status: "blocked",
        blockers: ["rate_limited", "github_unavailable"],
        retryAfterSeconds: 90,
      });
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("model connection failure guidance", () => {
  it("explains the safety boundary, preserved state, recovery, and diagnostic ID", () => {
    const message = modelConnectionFailureMessage("zh-TW", {
      code: "CREDENTIAL_REPLACE_REQUIRED",
      requestId: "request-safe-123",
    });

    expect(message).toContain("不能把舊金鑰送到新的 origin");
    expect(message).toContain("原設定仍保留");
    expect(message).toContain("重新填入");
    expect(message).toContain("診斷代碼: request-safe-123");
  });

  it("does not display an unsafe diagnostic identifier", () => {
    const message = modelConnectionFailureMessage("en", {
      code: "MODEL_CONNECTION_SAVE_FAILED",
      requestId: "<script>alert(1)</script>",
    });

    expect(message).toContain("existing setting is preserved");
    expect(message).not.toContain("script");
  });

  it("does not claim failure or success when the browser received no result", () => {
    const message = modelConnectionFailureMessage("zh-TW", {
      code: "REQUEST_FAILED",
    });

    expect(message).toContain("無法判定更新是否完成");
    expect(message).toContain("先按「重新整理」核對服務清單");
    expect(message).toContain("金鑰不會保留");
  });
});

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
      passwordAvailable
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

  it("keeps GitHub controls out of the unauthenticated password surface", () => {
    const markup = renderAccessPanel({
      locale: "en",
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain('id="admin-password"');
    expect(markup).not.toContain('class="github-button');
    expect(markup).not.toContain("/api/admin/session/github/start");
  });

  it("shows the host recovery command instead of an unusable production login", () => {
    const markup = renderAccessPanel({
      locale: "en",
      passwordAvailable: false,
      setupStatus: {
        setup_required: false,
        setup_code_available: false,
      },
    });

    expect(markup).toContain('data-mode="recovery"');
    expect(markup).toContain(
      "reponpc admin set-password --data-dir &lt;dir&gt;",
    );
    expect(markup).toContain("Check after setting password");
    expect(markup).not.toContain('id="admin-username"');
    expect(markup).not.toContain('id="admin-password"');
    expect(markup).not.toContain("GitHub sign-in");
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

describe("local-launch bootstrap", () => {
  it("clears a fragment synchronously and accepts exactly one non-empty grant", () => {
    const clear = vi.fn();

    expect(takeLocalLaunchGrant("#local-launch=one-use-grant", clear)).toBe(
      "one-use-grant",
    );
    expect(clear).toHaveBeenCalledOnce();

    const clearInvalid = vi.fn();
    expect(
      takeLocalLaunchGrant(
        "#local-launch=first&local-launch=second",
        clearInvalid,
      ),
    ).toBeNull();
    expect(clearInvalid).toHaveBeenCalledOnce();
  });

  it("renders only the secret-free checking state before bootstrap effects run", () => {
    const markup = renderToStaticMarkup(<AdminPage locale="en" />);

    expect(markup).toContain("Checking the local admin session");
    expect(markup).not.toMatch(/<(form|input|button|a)\b/i);
    expect(markup).not.toMatch(/github|password|setup code|local-launch=/i);
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
