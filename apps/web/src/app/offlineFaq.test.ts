import { describe, expect, it } from "vitest";

import { matchOfflineFaq } from "./offlineFaq";
import type { PublicFaq } from "./publicTypes";

function faq(entries: PublicFaq["entries"]): PublicFaq {
  return {
    bundle_id: "bundle-fixture",
    locale: "en",
    entries,
  };
}

function entry(question: string, variants: string[] = []) {
  return {
    question,
    variants,
    answer_markdown: `Approved: ${question}`,
    citations: [],
  };
}

describe("matchOfflineFaq", () => {
  it("returns an existing approved answer for an exact primary question", () => {
    const item = entry("Which portfolio projects stand out?");
    expect(matchOfflineFaq(item.question, faq([item]))).toEqual({
      kind: "answer",
      entry: item,
    });
  });

  it("matches owner-approved variants and normalized punctuation", () => {
    const item = entry("What did you build?", ["Tell me about your projects"]);
    expect(
      matchOfflineFaq("ＴＥＬＬ　ｍｅ about your projects!", faq([item])),
    ).toEqual({
      kind: "answer",
      entry: item,
    });
  });

  it("matches CJK questions after NFKC and punctuation normalization", () => {
    const item = entry("你最有代表性的專案是什麼？");
    expect(matchOfflineFaq("你最有代表性的專案是什麼", faq([item]))).toEqual({
      kind: "answer",
      entry: item,
    });
  });

  it("never answers a spelling typo under the exact policy", () => {
    const item = entry("What technologies are used?");
    expect(matchOfflineFaq("What technologies are use?", faq([item]))).toEqual({
      kind: "suggestions",
      questions: [item.question],
    });
  });

  it("answers only after NFKC, case, whitespace and trailing punctuation normalization", () => {
    const item = entry("What technologies are used?", ["這個專案用什麼技術？"]);
    for (const question of [
      "  WHAT   technologies are used ",
      "what technologies are used!!",
      "What technologies are used。",
      "ＷＨＡＴ technologies are used，",
      "這個專案用什麼技術",
      "這個專案用什麼技術？！",
    ]) {
      expect(matchOfflineFaq(question, faq([item])).kind).toBe("answer");
    }
    for (const question of [
      "What technologies are used? Really",
      "technologies are used?",
      "What technologies are used?x",
      "這個專案用什麼技術嗎",
    ]) {
      expect(matchOfflineFaq(question, faq([item])).kind).toBe("suggestions");
    }
  });

  it.each([
    [
      "What is the temperature at -1 degrees?",
      "What is the temperature at 1 degrees?",
    ],
    ["Does this plan allow 5% growth?", "Does this plan allow 5 growth?"],
    ["這個上限是5%嗎？", "這個上限是5嗎？"],
    [
      "Does this service use 5ms timeouts?",
      "Does this service use 5s timeouts?",
    ],
    [
      "Does this project use EngineC for builds?",
      "Does this project use EngineR for builds?",
    ],
    ["Does this project use C++?", "Does this project use C#?"],
    [
      "Does this project use C for data analysis?",
      "Does this project use R for data analysis?",
    ],
    ["這個專案使用C進行資料分析嗎？", "這個專案使用R進行資料分析嗎？"],
    [
      "Does this endpoint accept values <5?",
      "Does this endpoint accept values >5?",
    ],
    [
      "Does this endpoint accept values <=5?",
      "Does this endpoint accept values <5?",
    ],
    [
      "Does this endpoint accept values >=5?",
      "Does this endpoint accept values >5?",
    ],
    ["Does this endpoint accept user_id?", "Does this endpoint accept userid?"],
    [
      "Does this project read src/config.py?",
      "Does this project read srcconfig.py?",
    ],
    [
      "Does this project read srcconfig.py?",
      "Does this project read src/config.py?",
    ],
    [
      "Does this project read src/config.py?",
      "Does this project read src.config.py?",
    ],
    ["Does user.name override username?", "Does username override user.name?"],
    ["Does username override user.name?", "Does user.name override username?"],
    ["Does this compare x<y?", "Does this compare y<x?"],
    ["Does this compare y<x?", "Does this compare x<y?"],
    [
      "Does this filter require x<5 and y>5?",
      "Does this filter require x>5 and y<5?",
    ],
    [
      "Does this filter require x>5 and y<5?",
      "Does this filter require x<5 and y>5?",
    ],
    ["Does user_id override userid?", "Does userid override user_id?"],
    ["Does userid override user_id?", "Does user_id override userid?"],
  ])("does not answer when a factual token changes", (question, changed) => {
    expect(matchOfflineFaq(changed, faq([entry(question)])).kind).toBe(
      "suggestions",
    );
  });

  it("keeps equivalent unit formatting and an exact approved variant answerable", () => {
    const item = entry("Does this service use 5ms timeouts?", [
      "Does this service use 5 ms timeouts?",
    ]);
    expect(
      matchOfflineFaq("Does this service use 5 ms timeouts", faq([item])),
    ).toEqual({ kind: "answer", entry: item });
  });

  it("does not treat spaced Chinese percent formatting as exact", () => {
    const item = entry("這個上限是 5 ％ 嗎？");
    expect(matchOfflineFaq("這個上限是5%嗎？", faq([item])).kind).toBe(
      "suggestions",
    );
    expect(matchOfflineFaq("這個上限是 5 % 嗎", faq([item])).kind).toBe(
      "answer",
    );
  });

  it("allows an owner-approved identifier variant exactly", () => {
    const item = entry("Does this endpoint accept user_id?", [
      "Does this endpoint accept userid?",
    ]);
    expect(
      matchOfflineFaq("Does this endpoint accept userid?", faq([item])),
    ).toEqual({ kind: "answer", entry: item });
  });

  it("keeps case-normalized technical identifiers answerable", () => {
    const item = entry("Does this project use EngineC?");
    expect(
      matchOfflineFaq("does this project use enginec?", faq([item])),
    ).toEqual({ kind: "answer", entry: item });
  });

  it("returns suggestions when two approved rows match equally", () => {
    const first = entry("What did you build?", ["Tell me about the work"]);
    const second = entry("Which work did you build?", [
      "Tell me about the work",
    ]);
    expect(
      matchOfflineFaq("Tell me about the work", faq([first, second])),
    ).toEqual({
      kind: "suggestions",
      questions: [first.question, second.question],
    });
  });

  it("returns nearest suggestions below the confidence threshold", () => {
    const items = [
      entry("Which portfolio projects stand out?"),
      entry("What tools do you use?"),
      entry("How do you approach testing?"),
      entry("What is your favorite color?"),
    ];
    const result = matchOfflineFaq("banana", faq(items));
    expect(result.kind).toBe("suggestions");
    if (result.kind === "suggestions") {
      expect(result.questions).toHaveLength(3);
      expect(result.questions).toEqual(
        items.slice(0, 3).map((item) => item.question),
      );
    }
  });

  it("does not invent a suggestion or answer when the approved set is empty", () => {
    expect(matchOfflineFaq("anything", faq([]))).toEqual({
      kind: "suggestions",
      questions: [],
    });
  });
});
