import { describe, expect, it } from "vitest";

import { consumeSse, syncDocumentLanguage } from "./App";
import { messages } from "../i18n/messages";

describe("visitor locale contract", () => {
  it("keeps Traditional Chinese and English message keys equivalent", () => {
    expect(Object.keys(messages["zh-TW"]).sort()).toEqual(
      Object.keys(messages.en).sort(),
    );
  });

  it("contains visitor chat and accessibility guidance in both locales", () => {
    for (const locale of ["zh-TW", "en"] as const) {
      expect(messages[locale].chatTitle).not.toEqual("");
      expect(messages[locale].inputLabel).not.toEqual("");
      expect(messages[locale].characterOffline).not.toEqual("");
      expect(messages[locale].characterWalk).not.toEqual("");
      expect(messages[locale].avatarLink).not.toEqual("");
      expect(messages[locale].suggestionItems).toHaveLength(2);
    }
  });

  it("updates the document language when the visitor changes locale", () => {
    const element = { lang: "zh-TW" };
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: { documentElement: element },
    });
    syncDocumentLanguage("en");
    expect(element.lang).toBe("en");
  });

  it("delivers already validated SSE events progressively across chunk boundaries", async () => {
    const encoder = new TextEncoder();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(value) {
        controller = value;
      },
    });
    const delivered: string[] = [];
    const consuming = consumeSse(stream, (event) => delivered.push(event.name));

    controller.enqueue(encoder.encode('event: token\r\ndata: {"delta":"Hel'));
    controller.enqueue(encoder.encode('lo"}\r\n\r\n'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(delivered).toEqual(["token"]);

    controller.enqueue(
      encoder.encode(
        'event: citations\ndata: {"items":[]}\n\nevent: complete\ndata: {"finish_reason":"stop"}\n\n',
      ),
    );
    controller.close();
    await consuming;

    expect(delivered).toEqual(["token", "citations", "complete"]);
  });
});
