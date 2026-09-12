import { describe, expect, it } from "vitest";
import { ModelSetupRequests, replaceSetting } from "./modelSetupRequests";

describe("model setting response ordering", () => {
  it("keeps the returned probe result when a preceding read arrives late and a later refresh fails", async () => {
    const requests = new ModelSetupRequests();
    const stale = {
      profile_id: "model",
      status: "probe",
      last_error_code: null as string | null,
    };
    let rendered = [stale];
    let deliver!: (value: typeof rendered) => void;
    const read = requests.read(
      () =>
        new Promise<typeof rendered>((resolve) => {
          deliver = resolve;
        }),
      (value) => {
        rendered = value;
      },
    );
    const result = {
      profile_id: "model",
      status: "probe_failed",
      last_error_code: "PROVIDER_HTTP_402",
    };
    await requests.mutate(
      async () => result,
      (saved) => {
        rendered = replaceSetting(rendered, saved, "profile_id");
      },
    );
    deliver([stale]);
    await read;
    await expect(
      requests.read(
        async () => {
          throw new Error("offline");
        },
        (value) => {
          rendered = value as typeof rendered;
        },
      ),
    ).rejects.toThrow("offline");
    expect(rendered).toEqual([result]);
  });

  it("retains successful deletion when an old list response arrives", async () => {
    const requests = new ModelSetupRequests();
    let rendered = ["deleted-model"];
    let deliver!: (value: string[]) => void;
    const read = requests.read(
      () =>
        new Promise<string[]>((resolve) => {
          deliver = resolve;
        }),
      (value) => {
        rendered = value;
      },
    );
    await requests.mutate(
      async () => undefined,
      () => {
        rendered = [];
      },
    );
    deliver(["deleted-model"]);
    await read;
    expect(rendered).toEqual([]);
  });

  it("does not apply a failed mutation or retry it automatically", async () => {
    const requests = new ModelSetupRequests();
    let calls = 0;
    let applied = false;
    await expect(
      requests.mutate(
        async () => {
          calls++;
          throw new Error("offline");
        },
        () => {
          applied = true;
        },
      ),
    ).rejects.toThrow("offline");
    expect(calls).toBe(1);
    expect(applied).toBe(false);
  });
});
