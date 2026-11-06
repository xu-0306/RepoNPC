import { describe, expect, it } from "vitest";
import {
  tailscaleErrorMessage,
  tailscaleGuide,
  type TailscaleState,
} from "./tailscaleFunnel";
import { visitorGatewayErrorMessage } from "./VisitorGatewayPanel";

const ROWS: [TailscaleState, string, string, string | null][] = [
  ["unavailable_profile", "", "", null],
  [
    "not_installed",
    "這台電腦還沒有安裝 Tailscale。安裝並登入後，回到這裡按「重新檢查」。",
    "Tailscale is not installed on this computer. Install it and sign in, then come back and select Check again.",
    "https://tailscale.com/download",
  ],
  [
    "unsupported_version",
    "你的 Tailscale 版本太舊。請更新到最新版，再按「重新檢查」。",
    "Your Tailscale is too old. Update it to the latest version, then select Check again.",
    "https://tailscale.com/download",
  ],
  [
    "needs_login",
    "Tailscale 還沒有登入。請開啟 Tailscale 並登入，再按「重新檢查」。",
    "Tailscale is not signed in. Open Tailscale and sign in, then select Check again.",
    null,
  ],
  [
    "stopped",
    "Tailscale 目前是關閉的。請在 Tailscale 開啟連線，再按「重新檢查」。",
    "Tailscale is turned off. Turn it on in Tailscale, then select Check again.",
    null,
  ],
  [
    "offline",
    "Tailscale 目前沒有網路連線。請確認這台電腦已連上網路，再按「重新檢查」。",
    "Tailscale cannot reach the network. Check that this computer is online, then select Check again.",
    null,
  ],
  [
    "https_disabled",
    "你的 Tailscale 帳號還沒有開啟 HTTPS 憑證。請依官方說明開啟（只需一次），再按「重新檢查」。",
    "HTTPS certificates are not turned on for your Tailscale account. Turn them on once by following the official guide, then select Check again.",
    "https://tailscale.com/kb/1153/enabling-https",
  ],
  [
    "funnel_not_allowed",
    "這台裝置還沒有被允許使用 Funnel。請依官方說明允許（只需一次），再按「重新檢查」。",
    "Funnel is not allowed for this device yet. Allow it once by following the official guide, then select Check again.",
    "https://tailscale.com/docs/features/tailscale-funnel",
  ],
  [
    "no_free_port",
    "Tailscale 的 Funnel 連接埠都已被其他程式使用，RepoNPC 不會改動它們。請先關閉其中一個，再按「重新檢查」。",
    `Every Funnel port is already used by another program, and RepoNPC does not change them. Turn one off first, then select Check again.`,
    null,
  ],
  [
    "error",
    `RepoNPC 讀不到 Tailscale 的狀態。請確認 Tailscale 正在執行，再按「重新檢查」。`,
    `RepoNPC could not read the Tailscale status. Check that Tailscale is running, then select Check again.`,
    null,
  ],
  [
    "ready",
    "Tailscale 已就緒。按「開啟即時聊天」，訪客就能在你的電腦開機時即時提問。",
    "Tailscale is ready. Select Turn on live chat so visitors can ask live questions while this computer is on.",
    null,
  ],
  [
    "live",
    "即時聊天已開啟，訪客可以即時提問。",
    "Live chat is on. Visitors can ask live questions.",
    null,
  ],
];

describe("Tailscale contract copy", () => {
  it.each(ROWS)(
    "%s has exact bilingual instructions and official links only",
    (state, zh, en, href) => {
      for (const locale of ["zh-TW", "en"] as const) {
        const guide = tailscaleGuide(state, locale);
        expect(guide.text).toBe(locale === "zh-TW" ? zh : en);
        expect(guide.text).not.toMatch(/command|terminal|\.env|\d/i);
        if (href) {
          expect(guide.link).toEqual({
            href,
            label: href.endsWith("download")
              ? locale === "zh-TW"
                ? "下載 Tailscale"
                : "Download Tailscale"
              : locale === "zh-TW"
                ? "Tailscale 官方說明"
                : "Tailscale guide",
          });
        } else expect(guide.link).toBeNull();
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s uses fixed messages for both Tailscale errors",
    (locale) => {
      expect(tailscaleErrorMessage("TAILSCALE_NOT_READY", locale)).toBe(
        locale === "zh-TW"
          ? "現在還不能開啟即時聊天。請依上方說明處理後，按「重新檢查」。"
          : "Live chat cannot be turned on yet. Follow the instruction above, then select Check again.",
      );
      expect(tailscaleErrorMessage("TAILSCALE_FAILED", locale)).toBe(
        locale === "zh-TW"
          ? "Tailscale 沒有完成這個操作。RepoNPC 沒有改動其他連線。請確認 Tailscale 正在執行後再試一次。"
          : `Tailscale did not complete the operation. RepoNPC changed no other connection. Check that Tailscale is running, then try again.`,
      );
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "%s delegates every other code without exposing unknown details",
    (locale) => {
      for (const code of [
        "GATEWAY_CONFLICT",
        "GATEWAY_CONFIGURATION_INVALID",
        "GATEWAY_UNAVAILABLE",
        "AUTHENTICATION_REQUIRED",
        "CSRF_FAILED",
        "VALIDATION_ERROR",
        "SERVICE_NOT_READY",
        "private canary",
        null,
      ]) {
        expect(tailscaleErrorMessage(code, locale)).toBe(
          visitorGatewayErrorMessage(code, locale),
        );
        expect(tailscaleErrorMessage(code, locale)).not.toContain(
          "private canary",
        );
      }
    },
  );
});
