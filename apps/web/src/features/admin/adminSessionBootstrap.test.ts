import { describe, expect, it, vi } from "vitest";

import { restoreExistingAdminSession } from "./adminSessionBootstrap";

const methods = {
  mode: "local_launch" as const,
  password: { available: false },
  setup_required: false,
};

const session = {
  csrf_token: "memory-only-csrf",
  expires_at: "2026-09-13T12:30:00Z",
  absolute_expires_at: "2026-09-14T00:00:00Z",
};

describe("existing admin session bootstrap", () => {
  it("restores a valid cookie-backed session before showing recovery", async () => {
    const loadMethods = vi.fn().mockResolvedValue(methods);
    const resumeSession = vi.fn().mockResolvedValue(session);

    await expect(
      restoreExistingAdminSession(loadMethods, resumeSession),
    ).resolves.toEqual({ methods, session });
    expect(loadMethods).toHaveBeenCalledOnce();
    expect(resumeSession).toHaveBeenCalledOnce();
    expect(loadMethods.mock.invocationCallOrder[0]).toBeLessThan(
      resumeSession.mock.invocationCallOrder[0],
    );
  });

  it("keeps the deployment access method when no valid session remains", async () => {
    const resumeSession = vi.fn().mockRejectedValue(new Error("expired"));

    await expect(
      restoreExistingAdminSession(
        vi.fn().mockResolvedValue(methods),
        resumeSession,
      ),
    ).resolves.toEqual({ methods, session: null });
  });

  it("does not attempt resume when method discovery itself is unavailable", async () => {
    const resumeSession = vi.fn();

    await expect(
      restoreExistingAdminSession(
        vi.fn().mockRejectedValue(new Error("offline")),
        resumeSession,
      ),
    ).rejects.toThrow("offline");
    expect(resumeSession).not.toHaveBeenCalled();
  });
});
