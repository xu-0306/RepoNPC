const FUNNEL_HTTPS_PORTS = new Set(["443", "8443", "10000"]);

export type FunnelHttpsPort = "443" | "8443" | "10000";

/** Funnel port taken from the visitor origin; null when it cannot be one. */
export function funnelHttpsPort(origin: string): string | null {
  let url: URL;
  try {
    url = new URL(origin.trim());
  } catch {
    return null;
  }
  if (url.protocol !== "https:") return null;
  const port = url.port || "443";
  return FUNNEL_HTTPS_PORTS.has(port) ? port : null;
}

/**
 * Return the origin with its Funnel port replaced. 443 is written without a
 * port, matching the backend's normalized origins. Anything that is not a
 * parseable https URL is returned unchanged.
 */
export function withFunnelPort(origin: string, port: FunnelHttpsPort): string {
  let url: URL;
  try {
    url = new URL(origin.trim());
  } catch {
    return origin;
  }
  if (url.protocol !== "https:") return origin;
  url.port = port === "443" ? "" : port;
  return url.origin;
}

/** Local visitor service port: an integer from 1024 to 65535, else null. */
export function parseVisitorPort(text: string): number | null {
  const value = text.trim();
  if (!/^\d{1,5}$/.test(value)) return null;
  const port = Number(value);
  return port >= 1024 && port <= 65535 ? port : null;
}
