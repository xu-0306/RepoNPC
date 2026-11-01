import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { VisitorConversation } from "./VisitorConversation";
import {
  chatProgress,
  collectValidatedReply,
  type ChatProcess,
} from "./visitorChat";

const stream = (text: string) =>
  new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });

describe("real processing display", () => {
  it("announces current activity when a model returns to a previous phase", () => {
    const markup = renderToStaticMarkup(
      <VisitorConversation
        chatAvailable
        locale="en"
        onRetry={() => undefined}
        pending
        turns={[
          {
            id: "a",
            role: "assistant",
            content: "",
            process: {
              startedAt: 0,
              status: "pending",
              stages: ["thinking", "generating"],
              currentStage: "thinking",
            },
          },
        ]}
      />,
    );
    expect(markup).toContain('aria-live="polite">The model is thinking</p>');
  });

  it.each(["zh-TW", "en"] as const)(
    "renders a keyboard disclosure and frozen duration in %s",
    (locale) => {
      const process: ChatProcess = {
        startedAt: 0,
        elapsedMs: 197000,
        status: "complete",
        stages: ["searching", "thinking", "validating"],
      };
      const markup = renderToStaticMarkup(
        <VisitorConversation
          chatAvailable
          locale={locale}
          onRetry={() => undefined}
          pending={false}
          turns={[{ id: "a", role: "assistant", content: "Answer", process }]}
        />,
      );
      expect(markup).toContain('<details class="chat-process__details">');
      expect(markup).toContain("<summary");
      expect(markup).toContain(
        locale === "en" ? "Processed for 3 min 17 sec" : "處理了 3 分鐘 17 秒",
      );
      expect(markup).toContain(
        locale === "en" ? "The model is thinking" : "模型正在思考",
      );
      expect(markup).toContain('aria-live="off"');
    },
  );

  it("accepts actual phases without putting them in answer history", async () => {
    const answer = await collectValidatedReply(
      stream(
        'event: progress\ndata: {"stage":"thinking","elapsed_ms":1500}\n\nevent: token\ndata: {"delta":"Validated answer"}\n\nevent: complete\ndata: {}\n\n',
      ),
    );
    expect(answer).toBe("Validated answer");
  });

  it.each([300001, 600000])(
    "delivers a complete answer with progress and summary at %i ms",
    async (elapsed) => {
      const answer = await collectValidatedReply(
        stream(
          `event: progress\ndata: {"stage":"thinking","elapsed_ms":${elapsed}}\n\nevent: reasoning_summary\ndata: {"text":"Public summary","elapsed_ms":${elapsed}}\n\nevent: token\ndata: {"delta":"Validated answer"}\n\nevent: complete\ndata: {}\n\n`,
        ),
      );
      expect(answer).toBe("Validated answer");
    },
  );

  it.each([
    { stage: "fake_tool", elapsed_ms: 0 },
    { stage: "thinking", elapsed_ms: -1 },
    { stage: "thinking", elapsed_ms: 1, thinking: "SECRET" },
    { stage: "thinking", elapsed_ms: 600001 },
  ])("rejects invalid phases, timings or raw thinking %#", (data) => {
    expect(() => chatProgress({ name: "progress", data })).toThrow();
  });

  it("rejects progress after final delivery starts", async () => {
    await expect(
      collectValidatedReply(
        stream(
          'event: token\ndata: {"delta":"x"}\n\nevent: progress\ndata: {"stage":"thinking","elapsed_ms":0}\n\nevent: complete\ndata: {}\n\n',
        ),
      ),
    ).rejects.toThrow();
  });
});
