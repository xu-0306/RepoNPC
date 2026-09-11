import type {
  BatchDurationEstimate,
  BatchPreflightBlocker,
  BatchPreflightState,
} from "./BatchAnalysisPanel";

interface BatchRepositoryPlanBody {
  slug: string;
  commit_sha: string;
  default_branch: string;
  is_archived: boolean;
}

interface BatchCachePredictionBody {
  derived_index_hit: boolean;
  validated_analysis_hit: boolean;
}

interface BatchRateBudgetBody {
  remaining?: number;
  limit?: number;
  reset_at?: string | null;
}

interface BatchCapacityBody {
  github_requests: number;
  archive_staging: number;
  index_work: number;
  generation: number;
  whole_job_items: number;
}

interface BatchDurationBody {
  minimum_seconds: number;
  maximum_seconds: number;
  confidence: "low" | "medium" | "high";
}

interface BatchBlockerBody {
  slug: string;
  code: string;
}

export interface BatchPreflightBody {
  plan_id: string;
  expires_at: string;
  selection_hash: string;
  repositories: BatchRepositoryPlanBody[];
  cache_predictions: Record<string, BatchCachePredictionBody>;
  core_budget: BatchRateBudgetBody;
  secondary_retry_at?: string | null;
  provider_ready: boolean;
  capacity: BatchCapacityBody;
  maximum_generation_attempts: number;
  duration: BatchDurationBody | null;
  blockers: BatchBlockerBody[];
  warnings: string[];
}

export function batchDuration(
  duration: BatchDurationBody | null,
): BatchDurationEstimate | null {
  if (!duration) return null;
  return {
    minimumSeconds: Math.max(0, duration.minimum_seconds),
    maximumSeconds: Math.max(0, duration.maximum_seconds),
    confidence: duration.confidence,
  };
}

function preflightBlocker(code: string): BatchPreflightBlocker {
  if (code === "MODEL_UNAVAILABLE") return "provider_unavailable";
  if (code === "GITHUB_RATE_LIMITED" || code === "RATE_LIMITED") {
    return "rate_limited";
  }
  if (code === "NO_REPOSITORIES") return "no_repositories";
  if (code === "GITHUB_ERROR" || code === "GITHUB_TIMEOUT") {
    return "github_unavailable";
  }
  return "selection_changed";
}

function budgetStatus(
  plan: BatchPreflightBody,
): "available" | "limited" | "exhausted" {
  if (
    plan.core_budget.remaining !== undefined &&
    plan.core_budget.remaining <= 0
  ) {
    return "exhausted";
  }
  return plan.secondary_retry_at ? "limited" : "available";
}

function retryAfterSeconds(
  retryAt: string | null | undefined,
): number | undefined {
  if (!retryAt) return undefined;
  const value = Date.parse(retryAt);
  if (Number.isNaN(value)) return undefined;
  return Math.max(0, Math.ceil((value - Date.now()) / 1000));
}

export function preflightState(plan: BatchPreflightBody): BatchPreflightState {
  const blockers = plan.blockers.map((blocker) =>
    preflightBlocker(blocker.code),
  );
  if (blockers.length > 0) {
    const retryAfterSecondsValues = [
      retryAfterSeconds(plan.core_budget.reset_at),
      retryAfterSeconds(plan.secondary_retry_at),
    ].filter((value): value is number => value !== undefined);
    return {
      status: "blocked",
      blockers,
      retryAfterSeconds:
        retryAfterSecondsValues.length > 0
          ? Math.max(...retryAfterSecondsValues)
          : undefined,
    };
  }

  const cachedResultCount = Object.values(plan.cache_predictions).filter(
    (prediction) => prediction.validated_analysis_hit,
  ).length;
  return {
    status: "ready",
    plan: {
      selectionCount: plan.repositories.length,
      cachedResultCount,
      rateBudget: budgetStatus(plan),
      providerReady: plan.provider_ready,
      effectiveConcurrency: Math.min(
        plan.capacity.generation,
        plan.capacity.whole_job_items,
      ),
      serverConcurrency: plan.capacity.whole_job_items,
      maximumGenerationAttempts: plan.maximum_generation_attempts,
      estimatedDuration: batchDuration(plan.duration),
    },
  };
}
