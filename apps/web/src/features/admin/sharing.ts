import { chromeLocale, type LanguageTag } from "../../i18n/languages";
export const CARD_FILENAME = "reponpc-card.gif";

export function githubAccount(value: string): string | null {
  let account = value.trim();
  if (account.startsWith("https://")) {
    try {
      const url = new URL(account);
      const authority = account.slice("https://".length).split(/[/?#]/, 1)[0];
      if (
        url.hostname.toLowerCase() !== "github.com" ||
        authority.toLowerCase() !== "github.com" ||
        url.search ||
        url.hash ||
        url.username ||
        url.password ||
        url.port
      )
        return null;
      const parts = url.pathname.split("/").filter(Boolean);
      if (parts.length !== 1) return null;
      account = parts[0];
    } catch {
      return null;
    }
  }
  return /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/.test(account)
    ? account
    : null;
}

export function safeShareFields(account: string): { account?: string } {
  const normalizedAccount = githubAccount(account);
  return normalizedAccount ? { account: normalizedAccount } : {};
}

export function previewInputsMatch(
  currentContent: string,
  currentSprite: string | null,
  requestedContent: string,
  requestedSprite: string | null,
): boolean {
  return (
    currentContent === requestedContent && currentSprite === requestedSprite
  );
}

export function verifiedPagesMarkdown(
  value: string,
  locale: LanguageTag,
): string {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    const pathParts = url.pathname.split("/").filter(Boolean);
    if (
      url.protocol !== "https:" ||
      value !== `${url.origin}${url.pathname}` ||
      !/^[a-z0-9-]+\.github\.io$/.test(host) ||
      url.port ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      !url.pathname.startsWith("/") ||
      !url.pathname.endsWith("/") ||
      pathParts.some(
        (part) =>
          !/^[A-Za-z0-9._-]{1,128}$/.test(part) ||
          part === "." ||
          part === "..",
      )
    ) {
      return "";
    }
    return `[![${chromeLocale(locale) === "zh-TW" ? "與我的 RepoNPC 對話" : "Chat with my RepoNPC"}](./${CARD_FILENAME})](<${url.href}>)`;
  } catch {
    return "";
  }
}

/**
 * The origin of a saved Pages URL (`https://account.github.io`), or null when
 * the value is empty or not an HTTPS URL. Live chat settings take their Pages
 * address from here, so the owner enters a Pages URL once (ADR-081).
 */
export function pagesUrlOrigin(
  value: string | null | undefined,
): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.origin : null;
  } catch {
    return null;
  }
}

export function githubPagesRepository(
  account: string,
  pagesUrl: string,
): string | null {
  const login = githubAccount(account);
  if (!login || !verifiedPagesMarkdown(pagesUrl, "en")) return null;
  const url = new URL(pagesUrl);
  if (url.hostname.toLowerCase() !== `${login.toLowerCase()}.github.io`)
    return null;
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length > 1) return null;
  const repository = parts[0] ?? `${login}.github.io`;
  return `https://github.com/${login}/${repository}`;
}
