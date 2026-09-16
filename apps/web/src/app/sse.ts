/** Parse RepoNPC's buffered, validated SSE delivery without importing React. */
export interface SseEvent {
  name: string;
  data: Record<string, unknown>;
}

export async function consumeSse(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let exhausted = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      exhausted = done;
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, "\n");
      if (done && buffer.trim()) buffer += "\n\n";
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const name = block.match(/^event: (.+)$/m)?.[1];
        const data = block.match(/^data: (.+)$/m)?.[1];
        if (name && data) {
          const parsed = JSON.parse(data) as unknown;
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            throw new Error("invalid SSE event");
          }
          onEvent({ name, data: parsed as Record<string, unknown> });
        }
      }
      if (done) break;
    }
  } finally {
    if (!exhausted) {
      // Do not leave a network stream running after a rejected event/callback.
      await reader.cancel().catch(() => undefined);
    }
    reader.releaseLock();
  }
}
