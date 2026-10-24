import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MaintenancePanel } from "./MaintenancePanel";

describe("P6 pixel UI markup", () => {
  it("renders separate maintenance groups with badge-only service states", () => {
    const html = renderToStaticMarkup(
      <MaintenancePanel
        locale="en"
        status={{
          active_bundle_id: "active",
          previous_bundle_id: "previous",
          pinned_bundle_id: "pinned",
          last_backup_at: "2026-10-24T00:00:00Z",
          local_ready: true,
          gateway_configured: true,
          externally_verified: true,
        }}
        pending={false}
        restorePreview={null}
        onRefresh={() => {}}
        onBackup={() => {}}
        onInspect={() => {}}
        onRestore={() => {}}
        onCancelRestore={() => {}}
        onPinPrevious={() => {}}
        onStopGateway={() => {}}
      />,
    );
    expect(html).toContain('class="admin-maintenance__group"');
    expect(html).toContain('class="admin-maintenance__status"');
    expect(html).toContain('class="admin-maintenance__data"');
    expect(html.match(/admin-maintenance__status dd/g)).toBeNull();
    expect(html).toMatch(/admin-maintenance__status[\s\S]*class="px-badge"/);
    expect(html).not.toMatch(/admin-maintenance__data[\s\S]*class="px-badge"/);
  });
});
