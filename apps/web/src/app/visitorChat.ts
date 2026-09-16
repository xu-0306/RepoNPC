import { consumeSse, type SseEvent } from "./sse";

/** Keep in sync with PublicChatRequest/PublicChatHistory in api/public.py. */
export const CHAT_HISTORY_LIMITS = {
  messages: 10,
  messageCharacters: 4000,
  totalCharacters: 12000,
} as const;

/** Only a reply whose validated SSE delivery completed can form an exchange. */
export interface SuccessfulExchange {
  question: string;
  answer: string;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

function characterCount(text: string): number {
  // Python/Pydantic count Unicode code points, not JavaScript UTF-16 units.
  return Array.from(text).length;
}

/**
 * Retain a recent, contiguous suffix of whole successful exchanges.
 * Never truncate an individual message or summarize it implicitly. An oversized
 * latest reply therefore starts a fresh model context, not a stale older one.
 * This does not alter the separate, complete transcript shown to the visitor.
 */
export function retainSuccessfulExchanges(
  exchanges: readonly SuccessfulExchange[],
): SuccessfulExchange[] {
  const retained: SuccessfulExchange[] = [];
  let characters = 0;
  for (let index = exchanges.length - 1; index >= 0; index -= 1) {
    if ((retained.length + 1) * 2 > CHAT_HISTORY_LIMITS.messages) break;
    const exchange = exchanges[index];
    const questionLength = characterCount(exchange.question);
    const answerLength = characterCount(exchange.answer);
    if (
      !exchange.question.trim() ||
      !exchange.answer.trim() ||
      questionLength > CHAT_HISTORY_LIMITS.messageCharacters ||
      answerLength > CHAT_HISTORY_LIMITS.messageCharacters ||
      characters + questionLength + answerLength >
        CHAT_HISTORY_LIMITS.totalCharacters
    ) {
      break;
    }
    retained.unshift({ ...exchange });
    characters += questionLength + answerLength;
  }
  return retained;
}

export function buildChatHistory(
  exchanges: readonly SuccessfulExchange[],
): ChatHistoryMessage[] {
  return retainSuccessfulExchanges(exchanges).flatMap((exchange) => [
    { role: "user" as const, content: exchange.question },
    { role: "assistant" as const, content: exchange.answer },
  ]);
}

/**
 * Buffer an answer for model-history admission while emitting display events.
 * Public output is already validated by the backend; these checks detect an
 * incomplete/failed transport, not a second model or citation-validation step.
 */
export async function collectValidatedReply(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void = () => undefined,
): Promise<string> {
  let answer = "";
  let completed = false;
  await consumeSse(stream, (event) => {
    if (event.name === "error") throw new Error("chat delivery failed");
    if (completed) throw new Error("chat event after completion");
    if (event.name === "token") {
      if (typeof event.data.delta !== "string") {
        throw new Error("invalid chat token");
      }
      answer += event.data.delta;
    } else if (event.name === "complete") {
      completed = true;
    }
    onEvent(event);
  });
  if (!completed || !answer.trim()) throw new Error("chat stream incomplete");
  return answer;
}
