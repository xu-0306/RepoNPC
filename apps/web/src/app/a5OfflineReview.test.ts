import { afterEach, describe, expect, it, vi } from "vitest";

import { matchOfflineFaq } from "./offlineFaq";
import type { PublicFaq } from "./publicTypes";
import { fetchPublicFaq, fetchPublicStatus } from "./visitorData";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function approved(question: string, locale: PublicFaq["locale"]): PublicFaq {
  return {
    bundle_id: "a5-review-fixture",
    locale,
    entries: [
      {
        question,
        variants: [],
        answer_markdown: "Reviewed answer",
        citations: [],
      },
    ],
  };
}

describe("A5 independent offline confidence review", () => {
  it.each([
    [
      "en",
      "Does this project use Python?",
      "Does this project not use Python?",
    ],
    ["zh-TW", "此專案使用 Python 嗎？", "此專案不使用 Python 嗎？"],
    ["en", "Does this project use Java?", "Does this project use Rust?"],
    ["en", "Can this project use Python?", "Can't this project use Python?"],
    ["en", "Does this project use C++?", "Does this project use C#?"],
    [
      "en",
      "Does this project use version 1.0?",
      "Does this project use version 10?",
    ],
    [
      "en",
      "Can this project handle 10 requests?",
      "Can this project handle 100 requests?",
    ],
  ] as const)(
    "suggests rather than answering a changed fact (%s)",
    (locale, question, changed) => {
      expect(matchOfflineFaq(changed, approved(question, locale)).kind).toBe(
        "suggestions",
      );
    },
  );

  it.each([
    ["en", "Does this endpoint accept -1?", "Does this endpoint accept 1?"],
    ["zh-TW", "此端點接受 -1 嗎？", "此端點接受 1 嗎？"],
    ["en", "Does the limit allow 5%?", "Does the limit allow 5?"],
    ["zh-TW", "這個上限是 5% 嗎？", "這個上限是 5 嗎？"],
    ["zh-TW", "這個上限是5%嗎？", "這個上限是5嗎？"],
    ["en", "Does this request take 5ms?", "Does this request take 5s?"],
    ["zh-TW", "這個請求需要 5 毫秒嗎？", "這個請求需要 5 秒嗎？"],
    [
      "en",
      "Does the request adapter use EngineC in this path?",
      "Does the request adapter use EngineR in this path?",
    ],
    [
      "en",
      "Does this project use C for data analysis?",
      "Does this project use R for data analysis?",
    ],
    ["zh-TW", "這個專案使用C進行資料分析嗎？", "這個專案使用R進行資料分析嗎？"],
    [
      "zh-TW",
      "這個專案使用 C 進行資料分析嗎？",
      "這個專案使用 R 進行資料分析嗎？",
    ],
    [
      "en",
      "Does this endpoint accept values <5?",
      "Does this endpoint accept values >5?",
    ],
    [
      "en",
      "Does this endpoint accept values <=5?",
      "Does this endpoint accept values >=5?",
    ],
    [
      "en",
      "Does this endpoint accept values <=5?",
      "Does this endpoint accept values <5?",
    ],
    [
      "en",
      "Does this endpoint accept values >=5?",
      "Does this endpoint accept values >5?",
    ],
    [
      "en",
      "Does this endpoint accept values >=5 and <=10?",
      "Does this endpoint accept values <=5 and >=10?",
    ],
    ["zh-TW", "此端點接受>=5且<=10嗎？", "此端點接受<=5且>=10嗎？"],
    [
      "en",
      "Does this filter require x<5 and y>5?",
      "Does this filter require x>5 and y<5?",
    ],
    [
      "en",
      "Does this filter require x>5 and y<5?",
      "Does this filter require x<5 and y>5?",
    ],
    ["en", "Does user_id override userid?", "Does userid override user_id?"],
    ["en", "Does userid override user_id?", "Does user_id override userid?"],
    [
      "en",
      "Does this project read src/config.py?",
      "Does this project read srcconfig.py?",
    ],
    [
      "en",
      "Does this project read srcconfig.py?",
      "Does this project read src/config.py?",
    ],
    [
      "en",
      "Does this project read src/config.py?",
      "Does this project read src.config.py?",
    ],
    [
      "en",
      "Does user.name override username?",
      "Does username override user.name?",
    ],
    [
      "en",
      "Does username override user.name?",
      "Does user.name override username?",
    ],
    ["en", "Does this filter require x<y?", "Does this filter require y<x?"],
    ["en", "Is this field named user_id?", "Is this field named userid?"],
  ] as const)(
    "does not answer a single approved row after numeric or identifier drift (%s)",
    (locale, question, changed) => {
      expect(matchOfflineFaq(changed, approved(question, locale)).kind).toBe(
        "suggestions",
      );
    },
  );

  it("answers the original and an explicitly approved variant, never a typo", () => {
    const fixture = approved("What technologies are used?", "en");
    fixture.entries[0].variants = ["Which technologies are in use?"];
    for (const question of [
      "What technologies are used?",
      "Which technologies are in use?",
    ]) {
      expect(matchOfflineFaq(question, fixture).kind).toBe("answer");
    }
    expect(matchOfflineFaq("What technologies are use?", fixture).kind).toBe(
      "suggestions",
    );
  });

  it("answers approved structural variants but not respaced comparisons", () => {
    const fixture = approved("Does this filter require x<5 and y>5?", "en");
    fixture.entries[0].variants = ["Does this filter require x>5 and y<5?"];
    expect(
      matchOfflineFaq("Does this filter require x>5 and y<5?", fixture).kind,
    ).toBe("answer");
    expect(
      matchOfflineFaq("Does this filter require x < 5 and y > 5?", fixture)
        .kind,
    ).toBe("suggestions");
  });
});

describe("Main's independent bounded public reads", () => {
  it.each(["status", "faq"] as const)(
    "settles %s without response headers",
    async (kind) => {
      vi.useFakeTimers();
      let signal: AbortSignal | undefined;
      const send: typeof fetch = (_input, options) =>
        new Promise((_resolve, reject) => {
          signal = options?.signal ?? undefined;
          signal?.addEventListener("abort", () => reject(signal?.reason), {
            once: true,
          });
        });
      const read =
        kind === "status"
          ? fetchPublicStatus(new AbortController().signal, send)
          : fetchPublicFaq("en", new AbortController().signal, send);
      const observed = read.then(
        () => "settled",
        () => "settled",
      );
      await vi.advanceTimersByTimeAsync(60_000);
      expect(await observed).toBe("settled");
      expect(signal?.aborted).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    },
  );

  it.each(["deadline", "parent"] as const)(
    "cancels a never-ending FAQ body on %s",
    async (reason) => {
      vi.useFakeTimers();
      const cancel = vi.fn();
      const parent = new AbortController();
      const body = new ReadableStream<Uint8Array>({
        cancel,
      });
      const send: typeof fetch = async () => new Response(body);
      const read = fetchPublicFaq("en", parent.signal, send);
      const observed = read.then(
        () => "settled",
        () => "settled",
      );
      await vi.waitFor(() => expect(body.locked).toBe(true));
      if (reason === "parent") parent.abort();
      else await vi.advanceTimersByTimeAsync(60_000);
      expect(await observed).toBe("settled");
      expect(cancel).toHaveBeenCalledOnce();
      expect(body.locked).toBe(false);
      expect(vi.getTimerCount()).toBe(0);
    },
  );
});
