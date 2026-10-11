import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MaintenancePanelProps } from "./MaintenancePanel";
import { MaintenanceSetup } from "./MaintenanceSetup";

// The project has no DOM unit-test runtime. Exercise only the request callbacks
// with hook state; native form interactions remain in the browser acceptance.
const hooks = vi.hoisted(() => ({
  cursor: 0,
  slots: [] as {
    value: unknown;
    deps?: readonly unknown[];
    cleanup?: () => void;
  }[],
  effects: [] as (() => void)[],
}));
vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  const slot = (initial: unknown) => {
    const index = hooks.cursor++;
    return hooks.slots[index] ?? (hooks.slots[index] = { value: initial });
  };
  const changed = (
    previous: readonly unknown[] | undefined,
    next: readonly unknown[],
  ) =>
    !previous ||
    previous.length !== next.length ||
    previous.some((value, index) => value !== next[index]);
  return {
    ...react,
    useState: (initial: unknown) => {
      const state = slot(initial);
      return [
        state.value,
        (value: unknown) => {
          state.value = value;
        },
      ];
    },
    useRef: (initial: unknown) => slot({ current: initial }).value,
    useCallback: (callback: unknown, deps: readonly unknown[]) => {
      const state = slot(callback);
      if (changed(state.deps, deps)) {
        state.value = callback;
        state.deps = deps;
      }
      return state.value;
    },
    useEffect: (
      effect: () => (() => void) | undefined,
      deps: readonly unknown[],
    ) => {
      const state = slot(undefined);
      if (changed(state.deps, deps)) {
        state.deps = deps;
        hooks.effects.push(() => {
          state.cleanup?.();
          state.cleanup = effect();
        });
      }
    },
  };
});

const STATUS = {
  active_bundle_id: "current",
  previous_bundle_id: "retained",
  pinned_bundle_id: null,
  last_backup_at: null,
  local_ready: true,
  gateway_configured: true,
  externally_verified: false,
};
const PREVIEW = {
  preview_id: "opaque/id",
  created_at: "2026-10-03T01:00:00Z",
  application_version: "0.1.0",
  schema_version: 37,
  expires_at: "2099-10-03T01:10:00Z",
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
type Request = (path: string, init?: RequestInit) => Promise<Response>;

function view(sendRequest: Request, locale: "en" | "zh-TW" = "en") {
  const render = () => {
    hooks.cursor = 0;
    const element = MaintenanceSetup({
      locale,
      sendRequest,
    }) as ReactElement<MaintenancePanelProps>;
    const effects = hooks.effects.splice(0);
    effects.forEach((effect) => effect());
    return element.props;
  };
  render();
  return {
    render,
    unmount: () => hooks.slots.forEach((slot) => slot.cleanup?.()),
  };
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
function requestFor(action: Request = async () => json(STATUS)) {
  return vi.fn<Request>(async (path, init) =>
    path.endsWith("/status") ? json(STATUS) : action(path, init),
  );
}

const BACKUP_LOCATION =
  "/api/admin/maintenance/backup/20261003T100102-0123456789abcdef";
function encrypted(location: string | null = BACKUP_LOCATION) {
  return new Response("ciphertext-fixture", {
    headers: {
      "Content-Type": "application/octet-stream",
      ...(location === null ? {} : { "Content-Location": location }),
    },
  });
}

beforeEach(() => {
  hooks.cursor = 0;
  hooks.slots = [];
  hooks.effects = [];
});
afterEach(() => {
  hooks.slots.forEach((slot) => slot.cleanup?.());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("MaintenanceSetup request boundary", () => {
  it("loads only status on mount and preserves separate readiness facts", async () => {
    const request = requestFor();
    const app = view(request);
    await settle();
    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toBe("/api/admin/maintenance/status");
    expect(request.mock.calls[0][1]?.method).toBeUndefined();
    expect(request.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
    expect(app.render().status).toEqual(STATUS);
    expect(app.render().restorePreview).toBeNull();
  });

  it("exposes only the authenticated native download path and refreshes the backup time without reading binary or downloading", async () => {
    let statusReads = 0;
    const updated = { ...STATUS, last_backup_at: "2026-10-03T10:01:02Z" };
    const response = encrypted();
    const blob = vi.spyOn(response, "blob");
    const request = vi.fn<Request>(async (path) =>
      path.endsWith("/status")
        ? json(statusReads++ === 0 ? STATUS : updated)
        : response,
    );
    const app = view(request);
    await settle();
    app.render().onBackup("typed-only-fixture-password");
    await settle();
    expect(request.mock.calls[1][0]).toBe("/api/admin/maintenance/backup");
    expect(request.mock.calls[1][1]?.method).toBe("POST");
    expect(JSON.parse(request.mock.calls[1][1]?.body as string)).toEqual({
      password: "typed-only-fixture-password",
    });
    expect(blob).not.toHaveBeenCalled();
    expect(response.bodyUsed).toBe(false);
    expect(app.render().backupDownloadUrl).toBe(BACKUP_LOCATION);
    expect(app.render().notice).toContain("retained on this host");
    expect(app.render().status?.last_backup_at).toBe(updated.last_backup_at);
    expect(request.mock.calls.map(([path]) => path)).toEqual([
      "/api/admin/maintenance/status",
      "/api/admin/maintenance/backup",
      "/api/admin/maintenance/status",
    ]);
    expect(JSON.stringify(app.render())).not.toContain(
      "typed-only-fixture-password",
    );
    app.render().onRefresh();
    await settle();
    expect(app.render().backupDownloadUrl).toBe(BACKUP_LOCATION);
    expect(request.mock.calls.some(([path]) => path === BACKUP_LOCATION)).toBe(
      false,
    );
  });

  it.each(["en", "zh-TW"] as const)(
    "keeps the completed backup successful when status refresh fails in %s",
    async (locale) => {
      let statusReads = 0;
      const request = vi.fn<Request>(async (path) => {
        if (path.endsWith("/status")) {
          if (statusReads++ === 0) return json(STATUS);
          throw new Error("private-status-error https://private.invalid");
        }
        return encrypted();
      });
      const app = view(request, locale);
      await settle();
      app.render().onBackup("typed-only-fixture-password");
      await settle();
      expect(app.render().backupDownloadUrl).toBe(BACKUP_LOCATION);
      expect(app.render().error).toBe("");
      expect(app.render().pending).toBe(false);
      expect(app.render().status).toEqual(STATUS);
      expect(app.render().notice).toContain(
        locale === "en" ? "backup was created" : "備份已建立",
      );
      expect(app.render().notice).toContain(
        locale === "en"
          ? "Select ‘Download the encrypted backup’ to save the file"
          : "請按「下載剛建立的加密備份」保存檔案",
      );
      expect(app.render().notice).toContain(
        locale === "en" ? "Refresh status later" : "更新狀態",
      );
      expect(app.render().notice).not.toMatch(
        /private-status-error|private\.invalid/,
      );
      expect(request).toHaveBeenCalledTimes(3);
      expect(
        request.mock.calls.some(([path]) => path === BACKUP_LOCATION),
      ).toBe(false);
    },
  );

  it.each([
    null,
    "https://private.invalid" + BACKUP_LOCATION,
    "//private.invalid" + BACKUP_LOCATION,
    "javascript:private-secret",
    "blob:encrypted-fixture",
    BACKUP_LOCATION + "?password=private-secret",
    BACKUP_LOCATION + "#private-secret",
    BACKUP_LOCATION + "/extra",
    "/api/admin/maintenance/backup/../status",
    "/api/admin/maintenance/backup/%2e%2e/status",
    BACKUP_LOCATION.replace("/backup/", "/restore/"),
    BACKUP_LOCATION.slice(1),
    BACKUP_LOCATION.replace("abcdef", "ABCDEF"),
    BACKUP_LOCATION.slice(0, -1),
    BACKUP_LOCATION + "0",
    BACKUP_LOCATION.replace("20261003T100102", "20261003-100102"),
    BACKUP_LOCATION.replace("/backup/", "/backup\\"),
  ])(
    "rejects unsafe or missing Content-Location %s without a download or binary read",
    async (location) => {
      const response = encrypted(location);
      const blob = vi.spyOn(response, "blob");
      const request = requestFor(async () => response);
      const app = view(request);
      await settle();
      app.render().onBackup("fixture-password");
      await settle();
      expect(app.render().backupDownloadUrl).toBeNull();
      expect(app.render().pending).toBe(false);
      expect(app.render().error).toContain(
        "maintenance operation could not finish",
      );
      expect(app.render().notice).toBe("");
      expect(JSON.stringify(app.render())).not.toMatch(
        /private-secret|private\.invalid|fixture-password/,
      );
      expect(blob).not.toHaveBeenCalled();
      expect(response.bodyUsed).toBe(false);
      expect(request).toHaveBeenCalledTimes(2);
    },
  );

  it("does not accept a download path from a non-binary backup response", async () => {
    const request = requestFor(
      async () =>
        new Response("private-body", {
          headers: {
            "Content-Type": "text/html",
            "Content-Location": BACKUP_LOCATION,
          },
        }),
    );
    const app = view(request);
    await settle();
    app.render().onBackup("fixture-password");
    await settle();
    expect(app.render().backupDownloadUrl).toBeNull();
    expect(app.render().error).not.toContain("private-body");
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("ignores a late backup response after unmount without downloading or refreshing", async () => {
    let complete: ((response: Response) => void) | undefined;
    const request = requestFor(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    );
    const app = view(request);
    await settle();
    app.render().onBackup("fixture-password");
    app.unmount();
    expect(request.mock.calls[1][1]?.signal?.aborted).toBe(true);
    complete?.(encrypted());
    await settle();
    expect(app.render().backupDownloadUrl).toBeNull();
    expect(app.render().notice).toBe("");
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("ignores a late backup-status refresh after unmount", async () => {
    let statusReads = 0;
    let complete: ((response: Response) => void) | undefined;
    const request = vi.fn<Request>(async (path) => {
      if (path.endsWith("/status")) {
        if (statusReads++ === 0) return json(STATUS);
        return new Promise((resolve) => {
          complete = resolve;
        });
      }
      return encrypted();
    });
    const app = view(request);
    await settle();
    app.render().onBackup("fixture-password");
    await settle();
    app.unmount();
    expect(request.mock.calls[2][1]?.signal?.aborted).toBe(true);
    complete?.(json({ ...STATUS, last_backup_at: "2099-01-01T00:00:00Z" }));
    await settle();
    expect(app.render().status).toEqual(STATUS);
    expect(request).toHaveBeenCalledTimes(3);
  });

  it("replaces a prepared link only through a new explicit backup and clears it on failed creation", async () => {
    const next = BACKUP_LOCATION.replace(
      "0123456789abcdef",
      "fedcba9876543210",
    );
    let backups = 0;
    const request = requestFor(async () => {
      if (backups++ === 0) return encrypted();
      if (backups === 2) return encrypted(next);
      throw Object.assign(new Error("private-provider-key"), {
        code: "BACKUP_STORAGE_UNAVAILABLE",
      });
    });
    const app = view(request);
    await settle();
    app.render().onBackup("first-fixture-password");
    await settle();
    expect(app.render().backupDownloadUrl).toBe(BACKUP_LOCATION);
    app.render().onBackup("second-fixture-password");
    expect(app.render().backupDownloadUrl).toBeNull();
    await settle();
    expect(app.render().backupDownloadUrl).toBe(next);
    app.render().onBackup("third-fixture-password");
    await settle();
    expect(app.render().backupDownloadUrl).toBeNull();
    expect(app.render().error).toContain("cannot safely save the backup");
    expect(app.render().error).not.toContain("private-provider-key");
    expect(
      request.mock.calls.filter(([path]) => path.endsWith("/backup")),
    ).toHaveLength(3);
    expect(
      request.mock.calls.some(
        ([path]) => path === BACKUP_LOCATION || path === next,
      ),
    ).toBe(false);
  });

  it("inspects multipart backup/password without restoring and cancels the encoded preview", async () => {
    const request = requestFor(async (path) =>
      path.endsWith("/inspect")
        ? json(PREVIEW)
        : new Response(null, { status: 204 }),
    );
    const app = view(request);
    await settle();
    const file = new File(["fixture-ciphertext"], "fixture.reponpc-backup");
    app.render().onInspect(file, "typed-only-fixture-password");
    await settle();
    const call = request.mock.calls[1];
    expect(call[0]).toBe("/api/admin/maintenance/restore/inspect");
    expect(call[1]?.body).toBeInstanceOf(FormData);
    const body = call[1]?.body as FormData;
    expect([...body.keys()]).toEqual(["backup", "password"]);
    expect(body.get("backup")).toBe(file);
    expect(body.get("password")).toBe("typed-only-fixture-password");
    expect(call[1]?.headers).toBeUndefined();
    expect(app.render().restorePreview).toEqual(PREVIEW);
    expect(request.mock.calls.some(([path]) => path.endsWith("/restore"))).toBe(
      false,
    );
    expect(JSON.stringify(app.render())).not.toContain(
      "typed-only-fixture-password",
    );
    app.render().onCancelRestore();
    await settle();
    expect(request.mock.calls[2][0]).toBe(
      "/api/admin/maintenance/restore/opaque%2Fid",
    );
    expect(request.mock.calls[2][1]?.method).toBe("DELETE");
    expect(app.render().restorePreview).toBeNull();
  });

  it("requires the inspected identity and accepts restore once without polling or automatic login", async () => {
    const request = requestFor(async (path) =>
      path.endsWith("/inspect")
        ? json(PREVIEW)
        : json({ status: "restoring" }, 202),
    );
    const app = view(request);
    await settle();
    app
      .render()
      .onInspect(
        new File(["fixture"], "fixture.reponpc-backup"),
        "fixture-password",
      );
    await settle();
    app.render().onRestore("different-preview");
    expect(request).toHaveBeenCalledTimes(2);
    app.render().onRestore(PREVIEW.preview_id);
    await settle();
    expect(request.mock.calls[2][0]).toBe("/api/admin/maintenance/restore");
    expect(JSON.parse(request.mock.calls[2][1]?.body as string)).toEqual({
      preview_id: PREVIEW.preview_id,
      confirmed: true,
    });
    expect(app.render().restorePreview).toBeNull();
    expect(app.render().pending).toBe(true);
    expect(app.render().notice).toContain("reopen the admin page and sign in");
    app.render().onRefresh();
    app.render().onRestore(PREVIEW.preview_id);
    app.render().onStopGateway();
    await settle();
    expect(request).toHaveBeenCalledTimes(3);
  });

  it("blocks an uncertain restore write, hides raw private errors and does not retry", async () => {
    const request = requestFor(async (path) => {
      if (path.endsWith("/inspect")) return json(PREVIEW);
      throw Object.assign(
        new Error("private-provider-key https://private.invalid"),
        { code: "REQUEST_FAILED" },
      );
    });
    const app = view(request);
    await settle();
    app
      .render()
      .onInspect(
        new File(["fixture"], "fixture.reponpc-backup"),
        "fixture-password",
      );
    await settle();
    app.render().onRestore(PREVIEW.preview_id);
    await settle();
    expect(app.render().error).toContain("acceptance could not be confirmed");
    expect(app.render().error).not.toMatch(
      /private-provider-key|private\.invalid|REQUEST_FAILED/,
    );
    expect(app.render().restorePreview).toBeNull();
    app.render().onRefresh();
    app.render().onRestore(PREVIEW.preview_id);
    await settle();
    expect(request).toHaveBeenCalledTimes(3);
  });

  it.each(["en", "zh-TW"] as const)(
    "maps known failures to safe %s explanations",
    async (locale) => {
      const request = requestFor(async () => {
        throw Object.assign(new Error("private-secret"), {
          code: "BACKUP_DECRYPT_FAILED",
        });
      });
      const app = view(request, locale);
      await settle();
      app
        .render()
        .onInspect(
          new File(["fixture"], "fixture.reponpc-backup"),
          "fixture-password",
        );
      await settle();
      expect(app.render().error).toContain(
        locale === "en" ? "could not be decrypted" : "無法解開備份",
      );
      expect(app.render().error).not.toMatch(
        /private-secret|BACKUP_DECRYPT_FAILED/,
      );
    },
  );

  describe.each(["en", "zh-TW"] as const)(
    "%s restore safety explanations",
    (locale) => {
      it.each([
        ["RESTORE_OWNER_MISMATCH", "different owner", "不同的擁有者"],
        ["RESTORE_SECRET_UNAVAILABLE", "encryption keys", "加密密鑰"],
        ["RESTORE_BUNDLE_UNAVAILABLE", "website data", "網站資料"],
        [
          "RESTORE_APPEARANCE_UNAVAILABLE",
          "character or background",
          "角色或背景",
        ],
        ["RESTORE_PORTFOLIO_UNAVAILABLE", "portfolio", "作品集"],
        ["RESTORE_EMBEDDING_INCOMPATIBLE", "incompatible", "不相容"],
        ["RESTORE_MODEL_UNAVAILABLE", "local model files", "本機模型檔案"],
        ["RESTORE_RESOURCE_INVALID", "safely verified", "安全驗證"],
        ["RESTORE_WORK_PENDING", "still running", "正在執行"],
        ["BACKUP_VALIDATION_TIMEOUT", "took too long", "超出時間"],
        ["MAINTENANCE_STOP_FAILED", "safely stopped", "安全停止"],
        ["RESTORE_FAILED", "did not finish", "還原未完成"],
      ])(
        "explains %s without leaking exception data",
        async (code, english, chinese) => {
          const request = requestFor(async () => {
            throw Object.assign(
              new Error("private-provider-key https://private.invalid"),
              { code },
            );
          });
          const app = view(request, locale);
          await settle();
          app
            .render()
            .onInspect(
              new File(["fixture"], "fixture.reponpc-backup"),
              "fixture-password",
            );
          await settle();
          expect(app.render().error).toContain(
            locale === "en" ? english : chinese,
          );
          expect(app.render().error).not.toContain(code);
          expect(JSON.stringify(app.render())).not.toMatch(
            /private-provider-key|private\.invalid|fixture-password/,
          );
          expect(app.render().pending).toBe(false);
          expect(app.render().restorePreview).toBeNull();
          expect(request).toHaveBeenCalledTimes(2);
        },
      );
    },
  );

  it.each(["en", "zh-TW"] as const)(
    "keeps a rejected restore available for review without retrying in %s",
    async (locale) => {
      const request = requestFor(async (path) => {
        if (path.endsWith("/inspect")) return json(PREVIEW);
        throw Object.assign(new Error("private-secret"), {
          code: "RESTORE_SECRET_UNAVAILABLE",
        });
      });
      const app = view(request, locale);
      await settle();
      app
        .render()
        .onInspect(
          new File(["fixture"], "fixture.reponpc-backup"),
          "fixture-password",
        );
      await settle();
      app.render().onRestore(PREVIEW.preview_id);
      await settle();
      expect(app.render().pending).toBe(false);
      expect(app.render().error).toContain(
        locale === "en" ? "encryption keys" : "加密密鑰",
      );
      expect(app.render().restorePreview).toEqual(PREVIEW);
      expect(app.render().status).toEqual(STATUS);
      expect(request).toHaveBeenCalledTimes(3);
      app.render().onRefresh();
      await settle();
      expect(request).toHaveBeenCalledTimes(4);
      expect(
        request.mock.calls.filter(([path]) => path.endsWith("/restore")),
      ).toHaveLength(1);
    },
  );

  it("posts explicit pin confirmation only for retained data and stops only the local gateway", async () => {
    const request = requestFor(async () =>
      json({ ...STATUS, pinned_bundle_id: "retained" }),
    );
    const app = view(request);
    await settle();
    app.render().onPinPrevious("unknown");
    expect(request).toHaveBeenCalledTimes(1);
    app.render().onPinPrevious("retained");
    await settle();
    expect(request.mock.calls[1][0]).toBe("/api/admin/maintenance/pin");
    expect(JSON.parse(request.mock.calls[1][1]?.body as string)).toEqual({
      bundle_id: "retained",
      confirmed: true,
    });
    expect(app.render().status?.pinned_bundle_id).toBe("retained");
    app.render().onStopGateway();
    await settle();
    expect(request.mock.calls[2][0]).toBe(
      "/api/admin/maintenance/gateway/stop",
    );
    expect(request.mock.calls[2][1]?.body).toBe("{}");
    expect(app.render().notice).toContain("separately follow Tailscale");
  });

  it("allows one operation at a time and ignores late completion after abort/unmount", async () => {
    let complete: ((response: Response) => void) | undefined;
    const request = vi.fn<Request>(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    );
    const app = view(request);
    app.render().onBackup("fixture-password");
    expect(request).toHaveBeenCalledTimes(1);
    const signal = request.mock.calls[0][1]?.signal;
    app.unmount();
    expect(signal?.aborted).toBe(true);
    complete?.(json(STATUS));
    await settle();
    expect(app.render().status).toBeNull();
    expect(app.render().notice).toBe("");
    expect(request).toHaveBeenCalledTimes(1);
  });
});
