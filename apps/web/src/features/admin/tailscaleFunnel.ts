import { chromeLocale } from "../../i18n/languages";
import type { AdminLocale } from "./AdminWorkspace";
import {
  visitorGatewayErrorMessage,
  type VisitorGatewayStatus,
} from "./VisitorGatewayPanel";

export type TailscaleState =
  | "unavailable_profile"
  | "not_installed"
  | "unsupported_version"
  | "needs_login"
  | "stopped"
  | "offline"
  | "https_disabled"
  | "funnel_not_allowed"
  | "no_free_port"
  | "error"
  | "ready"
  | "live";

export interface TailscaleStatus {
  state: TailscaleState;
  funnel_url: string | null;
  port: number | null;
  version: string | null;
}

export interface TailscaleActionResult {
  tailscale: TailscaleStatus;
  gateway: VisitorGatewayStatus;
}

const INSTRUCTIONS: Record<TailscaleState, { "zh-TW": string; en: string }> = {
  unavailable_profile: { "zh-TW": "", en: "" },
  not_installed: {
    "zh-TW":
      "這台電腦還沒有安裝 Tailscale。安裝並登入後，回到這裡按「重新檢查」。",
    en: "Tailscale is not installed on this computer. Install it and sign in, then come back and select Check again.",
  },
  unsupported_version: {
    "zh-TW": "你的 Tailscale 版本太舊。請更新到最新版，再按「重新檢查」。",
    en: "Your Tailscale is too old. Update it to the latest version, then select Check again.",
  },
  needs_login: {
    "zh-TW":
      "Tailscale 還沒有登入。請開啟 Tailscale 並登入，再按「重新檢查」。",
    en: "Tailscale is not signed in. Open Tailscale and sign in, then select Check again.",
  },
  stopped: {
    "zh-TW":
      "Tailscale 目前是關閉的。請在 Tailscale 開啟連線，再按「重新檢查」。",
    en: "Tailscale is turned off. Turn it on in Tailscale, then select Check again.",
  },
  offline: {
    "zh-TW":
      "Tailscale 目前沒有網路連線。請確認這台電腦已連上網路，再按「重新檢查」。",
    en: "Tailscale cannot reach the network. Check that this computer is online, then select Check again.",
  },
  https_disabled: {
    "zh-TW":
      "你的 Tailscale 帳號還沒有開啟 HTTPS 憑證。請依官方說明開啟（只需一次），再按「重新檢查」。",
    en: "HTTPS certificates are not turned on for your Tailscale account. Turn them on once by following the official guide, then select Check again.",
  },
  funnel_not_allowed: {
    "zh-TW":
      "這台裝置還沒有被允許使用 Funnel。請依官方說明允許（只需一次），再按「重新檢查」。",
    en: "Funnel is not allowed for this device yet. Allow it once by following the official guide, then select Check again.",
  },
  no_free_port: {
    "zh-TW":
      "Tailscale 的 Funnel 連接埠都已被其他程式使用，RepoNPC 不會改動它們。請先關閉其中一個，再按「重新檢查」。",
    en: `Every Funnel port is already used by another program, and RepoNPC does not change them. Turn one off first, then select Check again.`,
  },
  error: {
    "zh-TW": `RepoNPC 讀不到 Tailscale 的狀態。請確認 Tailscale 正在執行，再按「重新檢查」。`,
    en: `RepoNPC could not read the Tailscale status. Check that Tailscale is running, then select Check again.`,
  },
  ready: {
    "zh-TW":
      "Tailscale 已就緒。按「開啟即時聊天」，訪客就能在你的電腦開機時即時提問。",
    en: "Tailscale is ready. Select Turn on live chat so visitors can ask live questions while this computer is on.",
  },
  live: {
    "zh-TW": "即時聊天已開啟，訪客可以即時提問。",
    en: "Live chat is on. Visitors can ask live questions.",
  },
};

export function tailscaleGuide(state: TailscaleState, locale: AdminLocale) {
  const language = chromeLocale(locale);
  let link: { href: string; label: string } | null = null;
  if (state === "not_installed" || state === "unsupported_version") {
    link = {
      href: "https://tailscale.com/download",
      label: language === "zh-TW" ? "下載 Tailscale" : "Download Tailscale",
    };
  } else if (state === "https_disabled" || state === "funnel_not_allowed") {
    link = {
      href:
        state === "https_disabled"
          ? "https://tailscale.com/kb/1153/enabling-https"
          : "https://tailscale.com/docs/features/tailscale-funnel",
      label: language === "zh-TW" ? "Tailscale 官方說明" : "Tailscale guide",
    };
  }
  return { text: INSTRUCTIONS[state][language], link };
}

export function tailscaleErrorMessage(
  code: unknown,
  locale: AdminLocale,
): string {
  const zh = chromeLocale(locale) === "zh-TW";
  switch (code) {
    case "TAILSCALE_NOT_READY":
      return zh
        ? "現在還不能開啟即時聊天。請依上方說明處理後，按「重新檢查」。"
        : "Live chat cannot be turned on yet. Follow the instruction above, then select Check again.";
    case "TAILSCALE_FAILED":
      return zh
        ? "Tailscale 沒有完成這個操作。RepoNPC 沒有改動其他連線。請確認 Tailscale 正在執行後再試一次。"
        : `Tailscale did not complete the operation. RepoNPC changed no other connection. Check that Tailscale is running, then try again.`;
    default:
      return visitorGatewayErrorMessage(code, locale);
  }
}
