import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { VisitorConversation, type VisitorTurn } from "./VisitorConversation";

const failedTurn: VisitorTurn = {
  id: "assistant-1",
  role: "assistant",
  content: "Partial answer",
  failed: true,
  retryQuestion: "Which project uses retrieval?",
  citations: [
    {
      id: "ev-1",
      evidence_class: "REPOSITORY_FACT",
      repository: "owner/repo",
      commit_sha: "0123456789abcdef",
      path: "src/search.py",
      start_line: 10,
      end_line: 12,
      title: "Search implementation",
      excerpt: "Hybrid retrieval is configured here.",
      url: "https://github.com/owner/repo/blob/0123456789abcdef/src/search.py#L10-L12",
    },
  ],
};

describe("VisitorConversation", () => {
  it("renders validated citation metadata and a usable English retry", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="en"
        onRetry={vi.fn()}
        pending={false}
        turns={[failedTurn]}
      />,
    );

    expect(markup).toContain('aria-live="polite"');
    expect(markup).toContain("Evidence class");
    expect(markup).toContain("REPOSITORY_FACT");
    expect(markup).toContain("owner/repo / src/search.py:10-12 @ 0123456789ab");
    expect(markup).toContain("Retry this question");
    expect(markup).not.toMatch(/<button[^>]*disabled/);
  });

  it("localizes citation labels and disables retry during another request", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="zh-TW"
        onRetry={vi.fn()}
        pending
        turns={[failedTurn]}
      />,
    );

    expect(markup).toContain("證據類別");
    expect(markup).toContain("來源位置");
    expect(markup).toMatch(/<button[^>]*disabled/);
  });
});
