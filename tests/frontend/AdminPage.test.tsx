import { describe, expect, it } from "vitest";

import {
  adminDataErrorMessage,
  loginErrorMessage,
  setupErrorMessage,
} from "../../apps/web/src/features/admin/AdminPage";

describe("admin first-owner presentation messages", () => {
  it.each([
    ["zh-TW", "管理員服務尚未就緒。請在部署主機設定 REPONPC_IP_HASH_KEY_FILE，重新啟動服務後再試。"],
    ["en", "Admin sign-in is not ready. Configure REPONPC_IP_HASH_KEY_FILE on the deployment host, restart the service, and try again."],
  ] as const)("keeps SERVICE_NOT_READY login guidance minimal in %s", (locale, expected) => {
    const message = loginErrorMessage(locale, new Error("SERVICE_NOT_READY"));

    expect(message).toBe(expected);
    expect(message).toContain("REPONPC_IP_HASH_KEY_FILE");
    expect(message).not.toContain("REPONPC_ADMIN_PASSWORD_HASH");
    expect(message).not.toContain("REPONPC_GITHUB_TOKEN_FILE");
    expect(message).not.toContain("test-secret-value");
  });

  it.each([
    ["zh-TW", "設定碼無效或已過期。請在部署主機重新產生設定碼後再試。"],
    ["en", "The setup code is invalid or expired. Generate a new code on the deployment host and try again."],
  ] as const)("never echoes a denied setup code in %s", (locale, expected) => {
    const message = setupErrorMessage(locale, new Error("SETUP_DENIED"));

    expect(message).toBe(expected);
    expect(message).not.toContain("example-setup-code");
  });

  it.each([
    ["zh-TW", "已登入，但 GitHub 管理操作尚未設定。"],
    ["en", "You are signed in, but GitHub management operations are not configured."],
  ] as const)("distinguishes authenticated GitHub setup in %s", (locale, expected) => {
    expect(adminDataErrorMessage(locale, new Error("SERVICE_NOT_READY"))).toBe(
      expected,
    );
  });

  it("keeps unrelated sign-in and setup failures generic", () => {
    expect(loginErrorMessage("en", new Error("AUTHENTICATION_FAILED"))).toBe(
      "Sign-in failed.",
    );
    expect(setupErrorMessage("en", new Error("REQUEST_FAILED"))).toBe(
      "Administrator setup failed. Try again.",
    );
  });
});
