const FUNNEL_HTTPS_PORTS = new Set(["443", "8443", "10000"]);

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
