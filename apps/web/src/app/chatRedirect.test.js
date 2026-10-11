import { once } from "node:events";
import { createServer } from "node:http";
import { expect, it } from "vitest";
import { requestPortfolioChat } from "./visitorChat";

it.each([
  [307, false],
  [308, false],
  [307, true],
  [308, true],
])("does not forward chat on HTTP %i, retry=%s", async (status, retry) => {
  let chatCalls = 0;
  let redirectedCalls = 0;
  const server = createServer((request, response) => {
    request.resume();
    if (request.url === "/api/public/chat/stream") {
      chatCalls += 1;
      if (retry && chatCalls === 1) {
        response.writeHead(413, { "Content-Type": "application/json" });
        response.end(
          JSON.stringify({
            error: {
              code: "PAYLOAD_TOO_LARGE",
              details: {
                max_message_characters: 2000,
                max_history_messages: 0,
                max_history_characters: 0,
              },
            },
          }),
        );
      } else {
        response.writeHead(status, { Location: `/destination-${status}` });
        response.end();
      }
    } else {
      redirectedCalls += 1;
      response.end("unexpected forwarded chat");
    }
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("no port");
    await expect(
      requestPortfolioChat(
        "Synthetic transport question",
        "en",
        retry
          ? [{ question: "Earlier question", answer: "Earlier answer" }]
          : [],
        new AbortController().signal,
        fetch,
        `http://127.0.0.1:${address.port}`,
      ),
    ).rejects.toThrow();
    expect(chatCalls).toBe(retry ? 2 : 1);
    expect(redirectedCalls).toBe(0);
  } finally {
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
