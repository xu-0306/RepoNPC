import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { messages } from "../i18n/messages";

import {
  VisitorConversation,
  type Citation,
  type VisitorTurn,
} from "./VisitorConversation";

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

function citationWithClass(id: string, evidence_class: string): Citation {
  return { ...failedTurn.citations![0], evidence_class, id };
}

const friendlyTurn: VisitorTurn = {
  ...failedTurn,
  citations: [
    citationWithClass("ev-owner", "OWNER_ASSERTION"),
    citationWithClass("ev-participation", "PARTICIPATION"),
    citationWithClass("ev-project", "REPOSITORY_FACT"),
  ],
};

describe("VisitorConversation", () => {
  it.each(["zh-TW", "en"] as const)(
    "reuses the accessible retry button and its disabled rules for temporary turns in %s",
    (locale) => {
      for (const [pending, chatAvailable] of [
        [false, true],
        [true, true],
        [false, false],
        [true, false],
      ]) {
        const onRetry = vi.fn();
        const props = {
          chatAvailable,
          locale,
          onRetry,
          pending,
          turns: [
            {
              id: "temporary",
              role: "assistant" as const,
              content: "Temporary answer",
              noMatchKind: "temporary" as const,
              retryQuestion: "Original question?",
            },
          ],
        };
        const markup = renderToStaticMarkup(<VisitorConversation {...props} />);
        expect(markup).toContain(`>${messages[locale].askAgain}</button>`);
        expect(markup).not.toContain(messages[locale].retry);
        expect(markup.match(/<button/g)).toHaveLength(1);
        const conversation = VisitorConversation(props);
        const button = conversation!.props.children[0].props.children.find(
          (child: { type?: string } | null | false) =>
            child && child.type === "button",
        );
        expect(button.props.type).toBe("button");
        expect(button.props.children).toBe(messages[locale].askAgain);
        expect(button.props.disabled).toBe(pending || !chatAvailable);
        if (!button.props.disabled) {
          button.props.onClick();
          expect(onRetry).toHaveBeenCalledExactlyOnceWith("Original question?");
        }
      }
    },
  );

  it.each(["zh-TW", "en"] as const)(
    "deduplicates each turn while preserving older buttons and admission in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <VisitorConversation
          chatAvailable={false}
          canAskSuggestion={(question) => question === "Approved?"}
          locale={locale}
          onRetry={vi.fn()}
          pending={false}
          turns={["older", "latest"].map((id) => ({
            id,
            role: "assistant",
            content: "No match",
            suggestedQuestions: ["Approved?", "Approved?", "Stale?", "Stale?"],
          }))}
        />,
      );
      const lists = markup.match(/<ul class="answer-suggestions">.*?<\/ul>/g);
      expect(lists).toHaveLength(2);
      for (const list of lists!) {
        expect(list.match(/<button/g)).toHaveLength(2);
        expect(list).toContain('<button type="button">Approved?</button>');
        expect(list).toContain(
          '<button disabled="" type="button">Stale?</button>',
        );
      }
    },
  );

  it("renders validated citation metadata and a usable English retry", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="en"
        ownerName="Ada Lovelace"
        onRetry={vi.fn()}
        pending={false}
        turns={[friendlyTurn]}
      />,
    );

    expect(markup).toContain('aria-live="polite"');
    expect(markup).toContain('<details class="citations">');
    expect(markup).toContain("<summary>Sources</summary>");
    expect(markup).toContain("Evidence class");
    expect(markup).toContain("Ada Lovelace");
    expect(markup).toContain("own words");
    expect(markup).toContain("GitHub participation");
    expect(markup).toContain("Project documents and code");
    expect(markup).not.toContain("OWNER_ASSERTION");
    expect(markup).not.toContain("PARTICIPATION");
    expect(markup).not.toContain("REPOSITORY_FACT");
    expect(markup).toContain("owner/repo / src/search.py:10-12 @ 0123456789ab");
    expect(markup).toContain("Retry this question");
    expect(markup).not.toMatch(/<button[^>]*disabled/);
  });

  it("localizes citation labels and disables retry during another request", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="zh-TW"
        ownerName="艾達"
        onRetry={vi.fn()}
        pending
        turns={[failedTurn]}
      />,
    );

    expect(markup).toContain("證據類別");
    expect(markup).toContain("來源位置");
    expect(markup).toMatch(/<button[^>]*disabled/);
  });

  it("offers no-match suggestions and the profile contact link", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="en"
        onRetry={vi.fn()}
        pending={false}
        turns={[
          {
            id: "no-match",
            role: "assistant",
            content: "Try one of these questions.",
            suggestedQuestions: ["Which project uses retrieval?"],
            contactLink: {
              label: "Portfolio contact",
              url: "https://example.com/contact",
            },
          },
        ]}
      />,
    );

    expect(markup).toContain("Which project uses retrieval?");
    expect(markup).toContain('href="https://example.com/contact"');
    expect(markup).toContain("Portfolio contact");
    expect(markup).toMatch(
      /<ul class="answer-suggestions"><li><button type="button">Which project uses retrieval\?<\/button>/,
    );
  });

  it.each(["en", "zh-TW"] as const)(
    "%s allows a current approved suggestion offline while keeping failed live retry disabled",
    (locale) => {
      const markup = renderToStaticMarkup(
        <VisitorConversation
          canAskSuggestion={(question) => question === "Approved FAQ"}
          chatAvailable={false}
          locale={locale}
          onRetry={vi.fn()}
          pending={false}
          turns={[
            {
              ...failedTurn,
              suggestedQuestions: ["Approved FAQ"],
            },
          ]}
        />,
      );

      expect(markup).toMatch(
        /<ul class="answer-suggestions"><li><button type="button">Approved FAQ<\/button>/,
      );
      expect(markup).toMatch(
        /<button disabled="" type="button">(?:Retry this question|重試這個問題)<\/button>/,
      );
    },
  );

  it("keeps stale suggestions disabled offline even with no pending request", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        canAskSuggestion={() => false}
        chatAvailable={false}
        locale="en"
        onRetry={vi.fn()}
        pending={false}
        turns={[
          {
            ...failedTurn,
            suggestedQuestions: ["Stale FAQ"],
          },
        ]}
      />,
    );

    expect(markup).toMatch(
      /<ul class="answer-suggestions"><li><button disabled="" type="button">Stale FAQ<\/button>/,
    );
  });
});
