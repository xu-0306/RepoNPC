import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  BatchAnalysisPanel,
  type BatchAnalysisPanelProps,
  type BatchJobSnapshot,
  type BatchPreflightState,
} from "./BatchAnalysisPanel";

const preflight: BatchPreflightState = {
  status: "ready",
  plan: {
    selectionCount: 3,
    cachedResultCount: 1,
    rateBudget: "available",
    providerReady: true,
    effectiveConcurrency: 2,
    serverConcurrency: 4,
    maximumGenerationAttempts: 1,
    estimatedDuration: {
      minimumSeconds: 90,
      maximumSeconds: 180,
      confidence: "medium",
    },
  },
};

const job: BatchJobSnapshot = {
  id: "batch-42",
  status: "running",
  items: [
    {
      slug: "octocat/demo",
      stage: "embedding",
      state: "active",
      retryable: false,
      error: null,
    },
    {
      slug: "octocat/docs",
      stage: "generating",
      state: "needs_retry_confirmation",
      retryable: true,
      error: {
        scope: "repository",
        code: "PROVIDER_TIMEOUT",
        retryAfterSeconds: 30,
        requestId: "request-id-is-not-rendered",
      },
    },
  ],
};

function props(
  overrides: Partial<BatchAnalysisPanelProps> = {},
): BatchAnalysisPanelProps {
  return {
    locale: "en",
    preflight,
    job,
    progress: {
      totalItems: 3,
      completedItems: 1,
      activeItems: 1,
      failedItems: 1,
      cancelledItems: 0,
      elapsedSeconds: 75,
      estimatedRemaining: {
        minimumSeconds: 60,
        maximumSeconds: 120,
        confidence: "high",
      },
      effectiveConcurrency: 2,
      serverConcurrency: 4,
      announcement: { completedItems: 1, totalItems: 3 },
    },
    stream: {
      connection: "connected",
      reconnectAttempts: 0,
      lastEventId: "event-id-is-not-rendered",
    },
    actions: { pending: null, error: null },
    onPause: vi.fn(),
    onResume: vi.fn(),
    onCancel: vi.fn(),
    onRetry: vi.fn(),
    onRetryPreflight: vi.fn(),
    ...overrides,
  };
}

describe("BatchAnalysisPanel", () => {
  it("renders typed preflight, aggregate progress, stream status, and repository stages", () => {
    const markup = renderToStaticMarkup(<BatchAnalysisPanel {...props()} />);

    expect(markup).toContain("Batch analysis");
    expect(markup).toContain('data-preflight-status="ready"');
    expect(markup).toContain(
      "Preflight is complete. The batch can be created.",
    );
    expect(markup).toContain("Anonymous GitHub REST budget");
    expect(markup).not.toContain("GitHub connection");
    expect(markup).not.toContain("Reconnect required");
    expect(markup).toContain("3");
    expect(markup).toContain("1m 30s–3m 0s");
    expect(markup).toContain('data-batch-status="running"');
    expect(markup).toContain("Live progress is connected.");
    expect(markup).toContain("Batch progress: 1 of 3 complete.");
    expect(markup).toContain("octocat/demo");
    expect(markup).toContain("Embedding");
    expect(markup).toContain("Needs explicit retry confirmation");
    expect(markup).toContain("This repository needs attention.");
  });

  it("keeps pause and cancel independently available while a pause request is pending", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({ actions: { pending: "pause", error: null } })}
      />,
    );
    expect(markup).toMatch(/<button[^>]*disabled[^>]*>Pause batch<\/button>/);
    expect(markup).toMatch(/<button[^>]*>Cancel batch<\/button>/);
    expect(markup).toMatch(
      /<button[^>]*>Retry items that need confirmation<\/button>/,
    );
  });

  it("renders durable rate-limit waiting state without treating it as a failure", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          job: {
            ...job,
            items: [
              {
                ...job.items[0],
                stage: "queued",
                state: "waiting_rate_limit",
              },
            ],
          },
        })}
      />,
    );

    expect(markup).toContain("Waiting for GitHub capacity");
    expect(markup).not.toContain("Needs attention");
  });

  it("uses one actionable alert for an operation failure and never renders unsafe error fields", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          preflight: {
            status: "failed",
            error: {
              scope: "preflight",
              code: "UNSAFE_SERVER_DETAIL",
              requestId: "request-id-is-not-rendered",
            },
          },
          job: null,
          progress: null,
        })}
      />,
    );

    expect(markup.match(/role="alert"/g)).toHaveLength(1);
    expect(markup).toContain("Preflight did not complete.");
    expect(markup).toContain(
      '<button type="button">Run preflight again</button>',
    );
    expect(markup).not.toContain("UNSAFE_SERVER_DETAIL");
    expect(markup).not.toContain("request-id-is-not-rendered");
    expect(markup).not.toContain("event-id-is-not-rendered");
  });

  it("turns GitHub rate-limit errors into a safe retry message", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          preflight: {
            status: "failed",
            error: {
              scope: "preflight",
              code: "GITHUB_RATE_LIMITED",
              retryAfterSeconds: 30,
            },
          },
          job: null,
          progress: null,
        })}
      />,
    );

    expect(markup).toContain("GitHub is limiting new work.");
    expect(markup).toContain("Try again in about 30s.");
    expect(markup).toMatch(/<button[^>]*disabled[^>]*>Run preflight again/);
    expect(markup).not.toContain("GITHUB_RATE_LIMITED");
  });

  it("shows a durable safe repository error code and validation reason", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          job: {
            id: "batch-failed",
            status: "failed",
            items: [
              {
                slug: "octocat/demo",
                stage: "validating",
                state: "failed",
                retryable: true,
                error: {
                  scope: "repository",
                  code: "PROVIDER_ERROR",
                  reason: "PROVIDER_OUTPUT_SCHEMA_INVALID",
                  requestId: "request-id-is-not-rendered",
                },
              },
            ],
          },
        })}
      />,
    );

    expect(markup).toContain("Error code");
    expect(markup).toContain("PROVIDER_ERROR");
    expect(markup).toContain("Failure reason");
    expect(markup).toContain("PROVIDER_OUTPUT_SCHEMA_INVALID");
    expect(markup).toContain("did not match the analysis JSON schema");
    expect(markup).not.toContain("request-id-is-not-rendered");
  });

  it("does not render an unrecognized repository error or reason", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          job: {
            id: "batch-unsafe-error",
            status: "failed",
            items: [
              {
                slug: "octocat/demo",
                stage: "validating",
                state: "failed",
                retryable: false,
                error: {
                  scope: "repository",
                  code: "UNSAFE_SERVER_DETAIL",
                  reason: "PRIVATE_PROVIDER_BODY",
                },
              },
            ],
          },
        })}
      />,
    );

    expect(markup).toContain("ANALYSIS_FAILED");
    expect(markup).not.toContain("UNSAFE_SERVER_DETAIL");
    expect(markup).not.toContain("PRIVATE_PROVIDER_BODY");
  });

  it("keeps Traditional Chinese controls and status text materially equivalent", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel {...props({ locale: "zh-TW" })} />,
    );

    expect(markup).toContain("批次分析");
    expect(markup).toContain("分析前檢查已完成，可以建立批次。");
    expect(markup).toContain("即時進度已連接。");
    expect(markup).toContain("暫停批次");
    expect(markup).toContain("取消批次");
    expect(markup).toContain("重試需要確認的項目");
  });

  it("shows anonymous rate-limit blockers before a batch exists", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          preflight: {
            status: "blocked",
            blockers: ["rate_limited"],
            retryAfterSeconds: 90,
          },
          job: null,
          progress: null,
        })}
      />,
    );

    expect(markup).toContain("GitHub is limiting new work.");
    expect(markup).toContain("Try again in about 1m 30s.");
    expect(markup).toMatch(/<button[^>]*disabled[^>]*>Run preflight again/);
    expect(markup).toContain("No analysis batch has been created.");
  });

  it("keeps transient GitHub failures distinct from selection changes", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          preflight: {
            status: "blocked",
            blockers: ["github_unavailable"],
          },
          job: null,
          progress: null,
        })}
      />,
    );

    expect(markup).toContain("GitHub is temporarily unavailable.");
    expect(markup).not.toContain("repository selection changed");
    expect(markup).toContain(
      '<button type="button">Run preflight again</button>',
    );
  });

  it("allows preflight retry after the previous batch is terminal", () => {
    const markup = renderToStaticMarkup(
      <BatchAnalysisPanel
        {...props({
          preflight: {
            status: "failed",
            error: { scope: "preflight", code: "GITHUB_ERROR" },
          },
          job: { ...job, status: "completed" },
          progress: null,
        })}
      />,
    );

    expect(markup).toContain(
      '<button type="button">Run preflight again</button>',
    );
  });
});
