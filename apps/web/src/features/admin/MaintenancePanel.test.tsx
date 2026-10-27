import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  MaintenancePanel,
  type MaintenancePanelProps,
  type MaintenanceRestorePreview,
  type MaintenanceStatus,
} from "./MaintenancePanel";

const STATUS: MaintenanceStatus = {
  active_bundle_id: "current-website-data",
  previous_bundle_id: "retained-website-data",
  pinned_bundle_id: null,
  last_backup_at: "2026-10-03T04:00:00Z",
  local_ready: true,
  gateway_configured: true,
  externally_verified: false,
};
const PREVIEW: MaintenanceRestorePreview = {
  preview_id: "opaque-inspection-token",
  created_at: "2026-10-02T04:00:00Z",
  application_version: "2.8.9",
  schema_version: 47,
  expires_at: "2026-10-03T05:05:00Z",
};

function props(
  overrides: Partial<MaintenancePanelProps> = {},
): MaintenancePanelProps {
  return {
    locale: "en",
    status: STATUS,
    pending: false,
    restorePreview: null,
    onRefresh: vi.fn(),
    onBackup: vi.fn(),
    onInspect: vi.fn(),
    onRestore: vi.fn(),
    onCancelRestore: vi.fn(),
    onPinPrevious: vi.fn(),
    onStopGateway: vi.fn(),
    ...overrides,
  };
}
function render(overrides: Partial<MaintenancePanelProps> = {}) {
  return renderToStaticMarkup(<MaintenancePanel {...props(overrides)} />);
}
function expectAssociatedReferences(markup: string) {
  for (const match of markup.matchAll(
    /aria-(?:labelledby|describedby)="([^"]+)"/g,
  )) {
    for (const id of match[1].split(" ")) {
      expect(markup).toContain(`id="${id}"`);
    }
  }
  for (const input of markup.matchAll(/<input[^>]*>/g)) {
    const id = /id="([^"]+)"/.exec(input[0])?.[1];
    expect(id).toBeDefined();
    expect(markup).toContain(`for="${id}"`);
  }
}
function expectDisabledButton(markup: string, label: string) {
  const button = [...markup.matchAll(/<button[^>]*>[^<]*<\/button>/g)].find(
    (match) => match[0].endsWith(`>${label}</button>`),
  );
  expect(button?.[0]).toContain('disabled=""');
}

afterEach(() => vi.restoreAllMocks());

describe("MaintenancePanel", () => {
  it.each(["en", "zh-TW"] as const)(
    "offers a native ciphertext download link in %s only while supplied",
    (locale) => {
      const markup = render({
        locale,
        backupDownloadUrl:
          "/api/admin/maintenance/backup/20261003T100102-0123456789abcdef",
        notice: "Backup created.",
      });
      expect(markup).toContain(
        '<a href="/api/admin/maintenance/backup/20261003T100102-0123456789abcdef" download="reponpc-backup.reponpc-backup">',
      );
      expect(markup).toContain(
        locale === "en"
          ? "Download the encrypted backup"
          : "下載剛建立的加密備份",
      );
      expectDisabledButton(
        markup,
        locale === "en" ? "Create encrypted backup" : "建立加密備份",
      );
      expect(markup).not.toMatch(
        /Create and download encrypted backup|建立並下載加密備份/,
      );
      expect(markup.indexOf("Backup created.")).toBeLessThan(
        markup.indexOf(
          'href="/api/admin/maintenance/backup/20261003T100102-0123456789abcdef"',
        ),
      );
      expect(
        render({ locale, backupDownloadUrl: null, notice: "Backup created." }),
      ).not.toContain('download="reponpc-backup.reponpc-backup"');
      expect(markup).not.toMatch(/fixture-password|provider_secret/);
    },
  );
  it("offers two collapsed choices with the same-host backup scope before forms", () => {
    const markup = render();
    expect(markup).toContain("<summary>Create a backup</summary>");
    expect(markup).toContain("<summary>Restore from a backup</summary>");
    expect(markup).not.toMatch(/<details[^>]+open/);
    expect(markup).toContain("restores only SQLite settings on the same host");
    expect(markup).toContain("Keep the keys, website data, and images");
    expect(markup).toContain("excludes model weights");
    expect(markup).toContain("not a full migration tool");
    expect(markup.indexOf("restores only SQLite")).toBeLessThan(
      markup.indexOf("<form"),
    );
    expectAssociatedReferences(markup);
  });

  it("starts with empty write-only password controls and requires confirmation", () => {
    const markup = render();
    const passwords = [...markup.matchAll(/<input[^>]+type="password"[^>]*>/g)];
    expect(passwords).toHaveLength(3);
    for (const match of passwords) {
      expect(match[0]).toContain('value=""');
      expect(match[0]).toContain('minLength="12"');
      expect(match[0]).toContain('maxLength="1024"');
      expect(match[0]).toContain('required=""');
      expect(match[0]).not.toContain("readOnly");
    }
    expect(markup).toContain("Both passwords must match");
    expect(markup).toContain("RepoNPC does not store it in the browser");
    expectDisabledButton(markup, "Create encrypted backup");
    expect(markup).not.toMatch(/api_key|base_url|provider_secret|localStorage/);
  });

  it("requires a bounded backup file and inspection before offering a restore", () => {
    const markup = render();
    expect(markup).toContain('accept=".reponpc-backup"');
    expect(markup).toContain("128 MiB plus an 8192-byte header");
    expect(markup).toContain("Inspection does not change your settings");
    expectDisabledButton(markup, "Inspect backup");
    expect(markup).not.toContain("Confirm settings restore");
    expect(markup).not.toContain(PREVIEW.preview_id);
  });

  it("never invokes maintenance callbacks during render or autosaves a preview", () => {
    const initial = props({ restorePreview: PREVIEW });
    renderToStaticMarkup(<MaintenancePanel {...initial} />);
    for (const callback of [
      initial.onRefresh,
      initial.onBackup,
      initial.onInspect,
      initial.onRestore,
      initial.onCancelRestore,
      initial.onPinPrevious,
      initial.onStopGateway,
    ]) {
      expect(callback).not.toHaveBeenCalled();
    }
  });

  it("shows preview metadata and automatic backup but requires fresh explicit consent", () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-03T05:00:00Z"));
    const markup = render({ restorePreview: PREVIEW });
    expect(markup).toMatch(/<details[^>]+open=""/);
    expect(markup).toContain("Inspection result and restore scope");
    expect(markup).toContain(`dateTime="${PREVIEW.created_at}"`);
    expect(markup).toContain(`dateTime="${PREVIEW.expires_at}"`);
    expect(markup).toContain("<dd>2.8.9</dd>");
    expect(markup).toContain("<dd>47</dd>");
    expect(markup).toContain(
      "encrypted with the uploaded backup&#x27;s password",
    );
    expect(markup).toContain("restoring replaces the current SQLite settings");
    expect(markup).not.toContain('checked=""');
    expectDisabledButton(markup, "Confirm settings restore");
    expect(markup).toContain("reopen the admin page and sign in");
    expect(markup).not.toContain(PREVIEW.preview_id);
    expectAssociatedReferences(markup);
  });

  it.each(["2026-10-03T05:00:00Z", "2026-10-03T04:59:59Z", "invalid"])(
    "blocks expired or unverifiable inspection %s and explains reinspection",
    (expires_at) => {
      vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-03T05:00:00Z"));
      const markup = render({ restorePreview: { ...PREVIEW, expires_at } });
      expect(markup).toContain("expired or its expiry cannot be verified");
      expect(markup).toContain("inspect it again");
      const checkboxes = [
        ...markup.matchAll(/<input[^>]+type="checkbox"[^>]*>/g),
      ];
      expect(checkboxes[0][0]).toContain('disabled=""');
      expectDisabledButton(markup, "Confirm settings restore");
      expectAssociatedReferences(markup);
    },
  );

  it("distinguishes local readiness, configuration and external verification", () => {
    const markup = render();
    expect(markup).toContain(
      '<dt>Local service</dt><dd class="px-badge">Ready</dd>',
    );
    expect(markup).toContain(
      '<dt>Visitor service settings</dt><dd class="px-badge">Configured</dd>',
    );
    expect(markup).toContain(
      '<dt>External check</dt><dd class="px-badge">Not confirmed</dd>',
    );
    expect(markup).toContain("current-website-data");
    expect(markup).toContain("retained-website-data");
    expect(markup).toContain(`dateTime="${STATUS.last_backup_at}"`);
    expect(markup).toContain("It does not restore SQLite settings");
    expect(markup).not.toContain('checked=""');
    expectDisabledButton(markup, "Restore retained website data");
  });

  it("keeps unknown status distinct from known unavailable operations", () => {
    const unknown = render({ status: null });
    expect(unknown).toContain("Status not available yet");
    expect(unknown).not.toContain("No backup recorded yet");
    expectDisabledButton(unknown, "Stop visitor service");
    expectAssociatedReferences(unknown);
    const unavailable = render({
      status: {
        ...STATUS,
        previous_bundle_id: null,
        gateway_configured: false,
        last_backup_at: null,
      },
    });
    expect(unavailable).toContain("No backup recorded yet");
    expect(unavailable).toContain("no retained previous website data");
    expect(unavailable).toContain("does not need stopping");
    expectDisabledButton(unavailable, "Restore retained website data");
    expectAssociatedReferences(unavailable);
  });

  it("explains data-preserving updates and links separately to official Funnel steps", () => {
    const markup = render();
    expect(markup).toContain("Run the newer installer");
    expect(markup).toContain("keep the original data directory");
    expect(markup).toContain("does not disable Tailscale Funnel");
    expect(markup).toContain(
      "does not operate Tailscale or request its credentials",
    );
    expect(markup).toContain(
      'href="https://tailscale.com/docs/features/tailscale-funnel"',
    );
    expect(markup).toContain('target="_blank" rel="noopener noreferrer"');
    expect(markup).not.toContain("<iframe");
  });

  it("provides the same scope, controls, confirmation and recovery guidance in Traditional Chinese", () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-03T05:00:00Z"));
    const markup = render({ locale: "zh-TW", restorePreview: PREVIEW });
    for (const text of [
      "只還原同一台主機的 SQLite 設定",
      "密鑰、網站資料與圖片",
      "不含模型權重",
      "建立備份",
      "從備份還原",
      "再次輸入備份密碼",
      "檢查備份",
      "我了解還原會取代目前的 SQLite 設定",
      "剛上傳備份的密碼加密備份目前設定",
      "gateway 會保持關閉",
      "重新開啟管理頁並登入",
      "回復保留網站資料",
      "停止訪客 gateway",
      "執行較新版安裝程式",
      "不會要求其憑證",
    ])
      expect(markup).toContain(text);
    expect(markup).not.toContain('checked=""');
    expectAssociatedReferences(markup);
  });

  it("announces safe parent-provided feedback and disables operations while pending", () => {
    const markup = render({
      pending: true,
      error: "The backup could not be inspected. Check the file and password.",
      notice: "Your encrypted backup is ready to download.",
      restorePreview: PREVIEW,
    });
    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain(
      '<p role="alert">The backup could not be inspected',
    );
    expect(markup).toContain(
      '<p role="status" aria-live="polite">Your encrypted backup',
    );
    for (const label of [
      "Refresh status",
      "Create encrypted backup",
      "Inspect backup",
      "Cancel restore",
      "Confirm settings restore",
      "Restore retained website data",
      "Stop visitor service",
    ])
      expectDisabledButton(markup, label);
    expect(markup).not.toMatch(
      /MAINTENANCE_RESTORE_FAILED|provider_secret|localStorage/,
    );
    expectAssociatedReferences(markup);
  });
});
