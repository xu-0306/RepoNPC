import { describe, expect, it, vi } from "vitest";
import { requestPortfolioChat } from "./visitorChat";

const exchanges = Array.from({ length: 5 }, (_, i) => ({
  question: `Question ${i}`,
  answer: `Answer ${i}`,
}));
const rejected = (overrides = {}) =>
  Response.json(
    {
      error: {
        code: "PAYLOAD_TOO_LARGE",
        details: {
          max_message_characters: 2000,
          max_history_messages: 6,
          max_history_characters: 6000,
          ...overrides,
        },
      },
    },
    { status: 413 },
  );

describe("configured chat history admission", () => {
  it("retries with recent whole exchanges after admission rejects oversized history", async () => {
    const success = new Response("validated stream");
    const send = vi
      .fn()
      .mockResolvedValueOnce(rejected())
      .mockResolvedValueOnce(success);
    const response = await requestPortfolioChat(
      "Next",
      "en",
      exchanges,
      new AbortController().signal,
      send,
    );
    expect(response).toBe(success);
    expect(send).toHaveBeenCalledTimes(2);
    const first = JSON.parse(send.mock.calls[0][1].body);
    const retry = JSON.parse(send.mock.calls[1][1].body);
    expect(first.history).toHaveLength(10);
    expect(retry.history).toHaveLength(6);
    expect(retry.history[0].content).toBe("Question 2");
    expect(retry.message).toBe("Next");
    expect(exchanges).toHaveLength(5);
  });

  it("respects character bounds without truncating messages", async () => {
    const send = vi
      .fn()
      .mockResolvedValueOnce(rejected({ max_history_characters: 20 }))
      .mockResolvedValueOnce(new Response("ok"));
    await requestPortfolioChat(
      "Next",
      "en",
      exchanges,
      new AbortController().signal,
      send,
    );
    expect(JSON.parse(send.mock.calls[1][1].body).history).toEqual([
      { role: "user", content: "Question 4" },
      { role: "assistant", content: "Answer 4" },
    ]);
  });

  it("never loops or retries an oversized current question, malformed limits, or other failures", async () => {
    for (const response of [
      rejected({ max_message_characters: 1 }),
      rejected({ max_history_messages: -1 }),
      new Response("bad", { status: 413 }),
      new Response("offline", { status: 503 }),
    ]) {
      const send = vi.fn().mockResolvedValue(response);
      expect(
        await requestPortfolioChat(
          "Next",
          "en",
          exchanges,
          new AbortController().signal,
          send,
        ),
      ).toBe(response);
      expect(send).toHaveBeenCalledTimes(1);
    }
    const send = vi.fn().mockImplementation(async () => rejected());
    const result = await requestPortfolioChat(
      "Next",
      "en",
      exchanges,
      new AbortController().signal,
      send,
    );
    expect(result.status).toBe(413);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("does not retry after cancellation", async () => {
    const controller = new AbortController();
    const response = rejected();
    const send = vi.fn().mockImplementation(async () => {
      controller.abort();
      return response;
    });
    await requestPortfolioChat(
      "Next",
      "en",
      exchanges,
      controller.signal,
      send,
    );
    expect(send).toHaveBeenCalledTimes(1);
  });
});
