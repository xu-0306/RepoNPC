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

interface HistoryLimits {
  messages: number;
  messageCharacters: number;
  totalCharacters: number;
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
  limits: HistoryLimits = CHAT_HISTORY_LIMITS,
): SuccessfulExchange[] {
  const retained: SuccessfulExchange[] = [];
  let characters = 0;
  for (let index = exchanges.length - 1; index >= 0; index -= 1) {
    if ((retained.length + 1) * 2 > limits.messages) break;
    const exchange = exchanges[index];
    const questionLength = characterCount(exchange.question);
    const answerLength = characterCount(exchange.answer);
    if (
      !exchange.question.trim() ||
      !exchange.answer.trim() ||
      questionLength > limits.messageCharacters ||
      answerLength > limits.messageCharacters ||
      characters + questionLength + answerLength > limits.totalCharacters
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
  limits: HistoryLimits = CHAT_HISTORY_LIMITS,
): ChatHistoryMessage[] {
  return retainSuccessfulExchanges(exchanges, limits).flatMap((exchange) => [
    { role: "user" as const, content: exchange.question },
    { role: "assistant" as const, content: exchange.answer },
  ]);
}

/** Retry once only when admission reports smaller history limits. No model
 * request has run for this 413 response; the visible transcript stays intact. */
export async function requestPortfolioChat(
  message: string,
  locale: string,
  exchanges: readonly SuccessfulExchange[],
  signal: AbortSignal,
  send: typeof fetch = fetch,
): Promise<Response> {
  const history = buildChatHistory(exchanges);
  const post = (selected: ChatHistoryMessage[]) =>
    send("/api/public/chat/stream", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, locale, history: selected }),
    });
  const response = await post(history);
  if (response.status !== 413 || history.length === 0 || signal.aborted)
    return response;
  let error;
  try {
    error = (await response.clone().json()).error;
  } catch {
    return response;
  }
  const details = error?.details;
  if (
    error?.code !== "PAYLOAD_TOO_LARGE" ||
    !details ||
    ![
      details.max_message_characters,
      details.max_history_messages,
      details.max_history_characters,
    ].every((value) => Number.isSafeInteger(value) && value >= 0) ||
    characterCount(message) > details.max_message_characters
  )
    return response;
  const bounded = buildChatHistory(exchanges, {
    ...CHAT_HISTORY_LIMITS,
    messages: Math.min(
      details.max_history_messages,
      CHAT_HISTORY_LIMITS.messages,
    ),
    totalCharacters: Math.min(
      details.max_history_characters,
      CHAT_HISTORY_LIMITS.totalCharacters,
    ),
  });
  if (bounded.length >= history.length || signal.aborted) return response;
  return post(bounded);
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
