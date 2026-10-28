import type { Locale } from "../../i18n/messages";

type Message = readonly [string, string];

const EXPORT_FAILED: Message = [
  "目前無法產生網站檔案。請重新整理後再試；若仍失敗，到「維護」查看服務狀態。",
  "The site files cannot be built right now. Refresh and try again. If it keeps failing, check the service status in Maintenance.",
];

const MESSAGES: Record<string, Message> = {
  SHARING_VERIFICATION_FAILED: [
    "Pages 網站上的內容與目前本機的網站不同，或讀不到入口頁與 export-manifest.json。請下載最新網站，把所有檔案上傳到 Pages，等 Pages 更新後再按「核對 Pages 網站」。",
    "The content on the Pages site differs from the current local site, or the entry page and export-manifest.json cannot be read. Download the latest site, upload every file to Pages, wait for Pages to update, then select Check Pages site.",
  ],
  SHARING_VERIFICATION_UNAVAILABLE: [
    "連不上 Pages 網站，或核對逾時。請確認網址正確且網站已發布，稍後再按「核對 Pages 網站」。",
    "The Pages site could not be reached, or the check timed out. Check that the URL is correct and the site is published, then select Check Pages site again later.",
  ],
  SHARING_CONFIGURATION_INVALID: [
    "Pages 網址無效，或上一步的訪客入口設定還不完整。請確認網域與上一步的 Pages 網域相同、網址包含網站路徑，儲存後再核對。",
    "The Pages URL is not valid, or the visitor-entry setup in the previous step is incomplete. Check that the domain matches the Pages domain in the previous step and that the URL includes the site path. Save it, then check again.",
  ],
  SHARING_CONFLICT: [
    "核對期間網站內容有變動。請重新整理後，再按「核對 Pages 網站」。",
    "The site changed during the check. Refresh, then select Check Pages site again.",
  ],
  SHARING_EXPORT_UNAVAILABLE: EXPORT_FAILED,
  SHARING_EXPORT_INVALID: EXPORT_FAILED,
};

const FALLBACK: Message = [
  "操作未完成。請重新整理後再試；若仍失敗，到「維護」查看服務狀態。",
  "Could not complete the action. Refresh and try again. If it keeps failing, check the service status in Maintenance.",
];

export function pagesShareErrorMessage(locale: Locale, error: unknown): string {
  const code = error instanceof Error ? error.message : "REQUEST_FAILED";
  const message = Object.hasOwn(MESSAGES, code) ? MESSAGES[code] : FALLBACK;
  return message[locale === "zh-TW" ? 0 : 1];
}
