import { describe, expect, it, vi } from "vitest";

import {
  batchMutationResultUnknown,
  reconcileUnknownBatchMutation,
} from "./batchMutationRecovery";

describe("unknown batch mutation recovery", () => {
  it("blocks old-snapshot mutations until the unknown result is reconciled", () => {
    expect(
      batchMutationResultUnknown({
        error: { code: "ANALYSIS_RESULT_UNKNOWN" },
      }),
    ).toBe(true);
    expect(batchMutationResultUnknown({ error: null })).toBe(false);
  });

  it.each(["running", "completed"])(
    "reads the exact batch once when the accepted mutation is now %s",
    async () => {
      const refresh = vi.fn().mockResolvedValue(true);

      const result = await reconcileUnknownBatchMutation({
        batchId: "batch-source",
        generation: 4,
        currentGeneration: () => 4,
        refresh,
      });

      expect(result).toBe("reconciled");
      expect(refresh).toHaveBeenCalledOnce();
      expect(refresh).toHaveBeenCalledWith("batch-source", 4);
    },
  );

  it("keeps an actionable unknown result when the exact-batch read also fails", async () => {
    const refresh = vi.fn().mockRejectedValue(new TypeError("network lost"));

    const result = await reconcileUnknownBatchMutation({
      batchId: "batch-source",
      generation: 4,
      currentGeneration: () => 4,
      refresh,
    });

    expect(result).toBe("unknown");
    expect(refresh).toHaveBeenCalledOnce();
  });

  it("does not apply an old reconciliation after the UI generation changes", async () => {
    const refresh = vi.fn().mockResolvedValue(false);

    const result = await reconcileUnknownBatchMutation({
      batchId: "batch-source",
      generation: 4,
      currentGeneration: () => 5,
      refresh,
    });

    expect(result).toBe("stale");
  });
});
