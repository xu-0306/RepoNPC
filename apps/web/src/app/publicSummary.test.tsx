import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { VisitorConversation } from "./VisitorConversation";
import {
  chatPublicSummary,
  collectValidatedReply,
  buildChatHistory,
} from "./visitorChat";

const stream = (text: string) =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
const frame = (name: string, data: object) =>
  `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

describe("provider public summaries", () => {
  it.each(["zh-TW", "en"] as const)(
    "renders unverified plain text inside disclosure in %s",
    (locale) => {
      const markup = renderToStaticMarkup(
        <VisitorConversation
          chatAvailable
          locale={locale}
          onRetry={() => undefined}
          pending={false}
          turns={[
            {
              id: "a",
              role: "assistant",
              content: "Checked answer",
              process: {
                startedAt: 0,
                elapsedMs: 2200,
                status: "complete",
                stages: ["thinking"],
                summaries: ["<script>run()</script>\nUnverified process."],
              },
            },
          ]}
        />,
      );
      expect(markup).toContain("&lt;script&gt;");
      expect(markup).not.toContain("<script>");
      expect(markup).toContain(
        locale === "en" ? "Model public summary" : "模型公開摘要",
      );
      expect(markup.indexOf("Unverified process.")).toBeLessThan(
        markup.indexOf("</details>"),
      );
      expect(markup.indexOf("</details>")).toBeLessThan(
        markup.indexOf("Checked answer"),
      );
    },
  );

  it("admits only the final answer to model history", async () => {
    const answer = await collectValidatedReply(
      stream(
        frame("reasoning_summary", {
          text: "Unverified explanation",
          elapsed_ms: 1,
        }) +
          frame("metadata", {}) +
          frame("token", { delta: "Checked reply" }) +
          frame("complete", {}),
      ),
    );
    expect(buildChatHistory([{ question: "Question", answer }])).toEqual([
      { role: "user", content: "Question" },
      { role: "assistant", content: "Checked reply" },
    ]);
  });

  it.each([
    { text: "x", elapsed_ms: 1, prompt: "private" },
    { text: "x".repeat(4097), elapsed_ms: 1 },
    { text: "", elapsed_ms: 1 },
    { text: "x", elapsed_ms: -1 },
  ])("rejects malformed summary projection", (data) => {
    expect(() =>
      chatPublicSummary({ name: "reasoning_summary", data }),
    ).toThrow();
  });

  it("rejects late, excessive and incomplete summaries", async () => {
    const summary = frame("reasoning_summary", {
      text: "Unverified explanation",
      elapsed_ms: 1,
    });
    await expect(
      collectValidatedReply(stream(frame("metadata", {}) + summary)),
    ).rejects.toThrow();
    await expect(
      collectValidatedReply(stream(summary.repeat(9))),
    ).rejects.toThrow();
    await expect(collectValidatedReply(stream(summary))).rejects.toThrow();
    await expect(
      collectValidatedReply(stream(summary + frame("error", {}))),
    ).rejects.toThrow();
  });
});
