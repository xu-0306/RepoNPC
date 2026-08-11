/** Original RepoNPC P2 fixture source; it is not production retrieval code. */

export type SearchRequest = {
  readonly question: string;
  readonly locale: "zh-TW" | "en";
};

export function compileSearchRequest(question: string, locale: "zh-TW" | "en"): SearchRequest {
  return { question, locale };
}
