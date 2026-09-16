import {
  buildChatHistory,
  CHAT_HISTORY_LIMITS,
  collectValidatedReply,
  retainSuccessfulExchanges,
  type ChatHistoryMessage,
  type SuccessfulExchange,
} from "./visitorChat";
import { consumeSse } from "./sse";

type RegisterTest = (name: string, body: () => void | Promise<void>) => unknown;

function equal(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`,
    );
  }
}

function check(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

async function rejects(
  promise: Promise<unknown>,
  reason: string,
): Promise<void> {
  try {
    await promise;
  } catch (error) {
    check(error instanceof Error && error.message.includes(reason), reason);
    return;
  }
  throw new Error(`Expected rejection containing: ${reason}`);
}

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

function event(name: string, data: Record<string, unknown>): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
}

function validHistory(history: readonly ChatHistoryMessage[]): void {
  check(history.length <= 10, "message count exceeds backend contract");
  check(history.length % 2 === 0, "history contains an incomplete pair");
  let total = 0;
  history.forEach((message, position) => {
    equal(message.role, position % 2 === 0 ? "user" : "assistant");
    const length = Array.from(message.content).length;
    check(length >= 1 && length <= 4000, "message exceeds backend contract");
    total += length;
  });
  check(total <= 12000, "history exceeds total backend character budget");
}

/** Shared real cases: registered with Vitest in-project and node:test offline. */
export function registerVisitorChatTests(test: RegisterTest): void {
  test("history limits match the inspected public API contract", () => {
    equal(CHAT_HISTORY_LIMITS, {
      messages: 10,
      messageCharacters: 4000,
      totalCharacters: 12000,
    });
  });

  test("empty successful history produces no messages", () => {
    equal(buildChatHistory([]), []);
  });

  test("six completed exchanges retain the five newest complete pairs", () => {
    const exchanges = Array.from({ length: 6 }, (_, index) => ({
      question: `question ${index}`,
      answer: `answer ${index}`,
    }));
    const history = buildChatHistory(exchanges);
    validHistory(history);
    equal(history.length, 10);
    equal(history[0], { role: "user", content: "question 1" });
    equal(history[9], { role: "assistant", content: "answer 5" });
  });

  test("12000 characters fit exactly without splitting a pair", () => {
    const history = buildChatHistory([
      { question: "a".repeat(2000), answer: "b".repeat(2000) },
      { question: "c".repeat(4000), answer: "d".repeat(4000) },
    ]);
    equal(history.length, 4);
    validHistory(history);
  });

  test("a 12001-character history drops an entire oldest pair", () => {
    const exchanges = [
      { question: "a".repeat(2001), answer: "b".repeat(2000) },
      { question: "c".repeat(4000), answer: "d".repeat(4000) },
    ];
    equal(retainSuccessfulExchanges(exchanges), [exchanges[1]]);
    validHistory(buildChatHistory(exchanges));
  });

  test("an oversized latest answer starts fresh context without altering display data", () => {
    const exchanges = [
      { question: "old question", answer: "old answer" },
      { question: "long answer please", answer: "答".repeat(4001) },
    ];
    const before = JSON.stringify(exchanges);
    equal(buildChatHistory(exchanges), []);
    equal(JSON.stringify(exchanges), before);
    equal(exchanges[1].answer.length, 4001);
  });

  test("a newer valid pair after an oversized one is retained without stale context", () => {
    const latest = { question: "new", answer: "new answer" };
    equal(
      retainSuccessfulExchanges([
        { question: "old", answer: "old answer" },
        { question: "oversized", answer: "x".repeat(4001) },
        latest,
      ]),
      [latest],
    );
  });

  test("oversized questions and empty replies never form model-history pairs", () => {
    equal(buildChatHistory([{ question: "q".repeat(4001), answer: "a" }]), []);
    equal(buildChatHistory([{ question: "q", answer: " " }]), []);
    equal(buildChatHistory([{ question: " ", answer: "a" }]), []);
  });

  test("Unicode characters use Python code-point limits rather than UTF-16 units", () => {
    const history = buildChatHistory([
      { question: "😀".repeat(4000), answer: "繁體中文" },
    ]);
    equal(history.length, 2);
    validHistory(history);
  });

  test("retained pairs are copies, not references that can mutate the transcript", () => {
    const original = [{ question: "q", answer: "a" }];
    const retained = retainSuccessfulExchanges(original);
    retained[0].answer = "changed";
    equal(original[0].answer, "a");
  });

  test("SSE collection requires complete before recording a successful exchange", async () => {
    const seen: string[] = [];
    const answer = await collectValidatedReply(
      streamOf(
        event("metadata", { evidence_count: 1 }),
        event("token", { delta: "完整" }),
        event("token", { delta: "答案" }),
        event("citations", { items: [] }),
        event("complete", { finish_reason: "stop" }),
      ),
      (value) => seen.push(value.name),
    );
    equal(answer, "完整答案");
    equal(seen, ["metadata", "token", "token", "citations", "complete"]);
  });

  test("an interrupted reply rejects instead of entering history", async () => {
    await rejects(
      collectValidatedReply(streamOf(event("token", { delta: "partial" }))),
      "incomplete",
    );
  });

  test("a failed reply followed by retry records only the successful pair", async () => {
    let history: SuccessfulExchange[] = [];
    async function submit(stream: ReadableStream<Uint8Array>) {
      const answer = await collectValidatedReply(stream);
      history = retainSuccessfulExchanges([
        ...history,
        { question: "retry question", answer },
      ]);
    }
    await rejects(
      submit(streamOf(event("error", { code: "MODEL_UNAVAILABLE" }))),
      "failed",
    );
    equal(buildChatHistory(history), []);
    await submit(
      streamOf(
        event("token", { delta: "successful answer" }),
        event("complete", { finish_reason: "stop" }),
      ),
    );
    equal(buildChatHistory(history), [
      { role: "user", content: "retry question" },
      { role: "assistant", content: "successful answer" },
    ]);
  });

  test("transport cancellation rejects without admitting the partial response", async () => {
    const encoder = new TextEncoder();
    let reads = 0;
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (reads++ === 0) {
          controller.enqueue(
            encoder.encode(event("token", { delta: "partial" })),
          );
        } else {
          controller.error(new DOMException("request aborted", "AbortError"));
        }
      },
    });
    await rejects(collectValidatedReply(stream), "aborted");
    equal(stream.locked, false);
  });

  test("empty or metadata-only completion does not create a successful exchange", async () => {
    await rejects(
      collectValidatedReply(
        streamOf(event("complete", { finish_reason: "stop" })),
      ),
      "incomplete",
    );
  });

  test("an error after partial text rejects the entire exchange", async () => {
    await rejects(
      collectValidatedReply(
        streamOf(
          event("token", { delta: "partial" }),
          event("error", { code: "INTERNAL_ERROR" }),
        ),
      ),
      "failed",
    );
  });

  test("events after complete are rejected rather than altering a completed answer", async () => {
    await rejects(
      collectValidatedReply(
        streamOf(
          event("token", { delta: "answer" }),
          event("complete", {}),
          event("token", { delta: "unexpected" }),
        ),
      ),
      "after completion",
    );
  });

  test("non-string token payloads are rejected", async () => {
    await rejects(
      collectValidatedReply(
        streamOf(event("token", { delta: { text: "bad" } })),
      ),
      "invalid chat token",
    );
  });

  test("malformed JSON releases the reader and cancels unfinished transport", async () => {
    let cancelled = false;
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("event: token\ndata: not-json\n\n"));
      },
      cancel() {
        cancelled = true;
      },
    });
    try {
      await consumeSse(stream, () => undefined);
      throw new Error("should reject invalid JSON");
    } catch (error) {
      check(error instanceof SyntaxError, "expected the JSON parser error");
    }
    equal(cancelled, true);
    equal(stream.locked, false);
  });

  test("normal completion releases the reader without cancelling exhausted transport", async () => {
    const stream = streamOf(
      event("token", { delta: "answer" }),
      event("complete", {}),
    );
    await collectValidatedReply(stream);
    equal(stream.locked, false);
  });

  test("CRLF and UTF-8 characters survive byte-by-byte chunk boundaries", async () => {
    const text = (
      event("token", { delta: "你好😀" }) + event("complete", {})
    ).replace(/\n/g, "\r\n");
    const bytes = new TextEncoder().encode(text);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      },
    });
    equal(await collectValidatedReply(stream), "你好😀");
  });

  test("identical successful questions are not deduplicated as though they failed", () => {
    const exchanges = [
      { question: "same", answer: "first answer" },
      { question: "same", answer: "second answer" },
    ];
    equal(buildChatHistory(exchanges).length, 4);
  });

  test("deterministic mixed-size histories always satisfy every backend size constraint", () => {
    let seed = 17;
    const next = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed;
    };
    for (let trial = 0; trial < 200; trial += 1) {
      const exchanges = Array.from({ length: next() % 16 }, () => ({
        question: "問".repeat(1 + (next() % 4500)),
        answer: "😀".repeat(1 + (next() % 4500)),
      }));
      validHistory(buildChatHistory(exchanges));
    }
  });
}
