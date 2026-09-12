export const ADMIN_UI_SCALE_STORAGE_KEY = "reponpc.admin-ui-scale.v1";

export const ADMIN_UI_SCALES = ["standard", "comfortable", "large"] as const;
export type AdminUiScale = (typeof ADMIN_UI_SCALES)[number];

export const DEFAULT_ADMIN_UI_SCALE: AdminUiScale = "comfortable";

export function parseAdminUiScale(value: string | null): AdminUiScale {
  return ADMIN_UI_SCALES.includes(value as AdminUiScale)
    ? (value as AdminUiScale)
    : DEFAULT_ADMIN_UI_SCALE;
}

export function readAdminUiScale(): AdminUiScale {
  if (typeof window === "undefined") return DEFAULT_ADMIN_UI_SCALE;
  try {
    return parseAdminUiScale(
      window.localStorage.getItem(ADMIN_UI_SCALE_STORAGE_KEY),
    );
  } catch {
    return DEFAULT_ADMIN_UI_SCALE;
  }
}

export function applyAdminUiScale(scale: AdminUiScale): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.adminUiScale = scale;
}

export function persistAdminUiScale(scale: AdminUiScale): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ADMIN_UI_SCALE_STORAGE_KEY, scale);
  } catch {
    // The preference is optional; the current in-memory selection still applies.
  }
}
