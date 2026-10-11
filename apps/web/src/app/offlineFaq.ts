import type { PublicFaq } from "./publicTypes";

export type OfflineFaqResult =
  | { kind: "answer"; entry: PublicFaq["entries"][number] }
  | { kind: "suggestions"; questions: string[] };

/** Matcher version 2: answer only when the normalized input equals exactly one
 * approved question or approved variant. Everything else shows the nearest questions;
 * typos, reordering and paraphrases are deliberately never answered offline. */
export function matchOfflineFaq(
  question: string,
  faq: PublicFaq,
): OfflineFaqResult {
  const input = normalize(question);
  const exact = input
    ? faq.entries.filter((entry) =>
        [entry.question, ...entry.variants].some(
          (text) => normalize(text) === input,
        ),
      )
    : [];
  // Two approved rows claiming the same text are ambiguous, never answered.
  if (exact.length === 1) return { kind: "answer", entry: exact[0] };
  const grams = ngrams(input);
  const nearest = faq.entries
    .map((entry, ordinal) => ({
      question: entry.question,
      ordinal,
      score: Math.max(
        ...[entry.question, ...entry.variants].map((text) =>
          dice(grams, ngrams(normalize(text))),
        ),
      ),
    }))
    .sort(
      (left, right) => right.score - left.score || left.ordinal - right.ordinal,
    );
  return {
    kind: "suggestions",
    questions: [...new Set(nearest.slice(0, 3).map((item) => item.question))],
  };
}

/** NFKC, lowercase, collapsed whitespace, trailing sentence punctuation removed. */
export function normalize(value: string): string {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/gu, " ")
    .trim()
    .replace(/[?!。.,\s]+$/u, "");
}

function ngrams(value: string): Set<string> {
  const characters = Array.from(value.replace(/ /g, ""));
  const size = characters.length < 3 ? 1 : 2;
  const result = new Set<string>();
  for (let index = 0; index <= characters.length - size; index += 1) {
    result.add(characters.slice(index, index + size).join(""));
  }
  return result;
}

function dice(left: Set<string>, right: Set<string>): number {
  if (!left.size || !right.size) return 0;
  let overlap = 0;
  for (const item of left) if (right.has(item)) overlap += 1;
  return (2 * overlap) / (left.size + right.size);
}
