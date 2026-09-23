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

export function publicVisitorUrl(value: string): string | null {
  if (value.includes("#") || /[<>\r\n]/.test(value)) return null;
  try {
    const url = new URL(value.trim());
    const host = url.hostname.toLowerCase().replace(/\.$/, "");
    if (
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      url.hash ||
      !host.includes(".") ||
      host.endsWith(".localhost") ||
      host.endsWith(".local") ||
      host.endsWith(".internal") ||
      host.includes(":")
    )
      return null;
    if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
      const [a, b] = host.split(".").map(Number);
      if (
        a === 0 ||
        a === 10 ||
        a === 127 ||
        a >= 224 ||
        (a === 169 && b === 254) ||
        (a === 172 && b >= 16 && b <= 31) ||
        (a === 192 && b === 168) ||
        (a === 100 && b >= 64 && b <= 127)
      )
        return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

export function safeShareFields(
  account: string,
  publicUrl: string,
): { account?: string; publicUrl?: string } {
  const normalizedAccount = githubAccount(account);
  const normalizedUrl = publicVisitorUrl(publicUrl);
  return {
    ...(normalizedAccount ? { account: normalizedAccount } : {}),
    ...(normalizedUrl ? { publicUrl: normalizedUrl } : {}),
  };
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

export function cardMarkdown(url: string, locale: "zh-TW" | "en"): string {
  const target = publicVisitorUrl(url);
  if (!target) return "";
  return `[![${locale === "zh-TW" ? "與我的 RepoNPC 對話" : "Chat with my RepoNPC"}](./${CARD_FILENAME})](<${target}>)`;
}
