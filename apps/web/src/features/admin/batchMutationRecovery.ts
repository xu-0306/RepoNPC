export type BatchMutationReconciliation = "reconciled" | "unknown" | "stale";

export function batchMutationResultUnknown(actions: {
  error: { code: string } | null;
}): boolean {
  return actions.error?.code === "ANALYSIS_RESULT_UNKNOWN";
}

export async function reconcileUnknownBatchMutation(options: {
  batchId: string;
  generation: number;
  currentGeneration: () => number;
  refresh: (batchId: string, generation: number) => Promise<boolean>;
}): Promise<BatchMutationReconciliation> {
  try {
    const applied = await options.refresh(options.batchId, options.generation);
    if (options.generation !== options.currentGeneration()) return "stale";
    return applied ? "reconciled" : "stale";
  } catch {
    return options.generation === options.currentGeneration()
      ? "unknown"
      : "stale";
  }
}
